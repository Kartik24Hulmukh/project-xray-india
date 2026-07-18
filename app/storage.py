"""Managed S3-compatible evidence storage verification.

AWS deployments use the botocore default credential chain (including ECS task
roles) whenever explicit STORAGE_ACCESS_KEY/STORAGE_SECRET_KEY values are not
configured.  Static credentials and custom endpoints remain available for
local MinIO/S3-compatible tests.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass


class StorageConfigurationError(RuntimeError):
    """Raised before network I/O when storage configuration is unsafe."""


@dataclass(frozen=True)
class StorageSettings:
    bucket: str
    region: str = "ap-south-1"
    endpoint: str = ""
    access_key: str = ""
    secret_key: str = ""
    session_token: str = ""

    @property
    def credential_mode(self) -> str:
        if bool(self.access_key) != bool(self.secret_key):
            raise StorageConfigurationError(
                "STORAGE_ACCESS_KEY and STORAGE_SECRET_KEY must be set together"
            )
        return "static" if self.access_key else "default_chain"


def settings_from_env(
    *,
    bucket: str | None = None,
    region: str | None = None,
    endpoint: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
    session_token: str | None = None,
) -> StorageSettings:
    settings = StorageSettings(
        bucket=bucket if bucket is not None else os.getenv("STORAGE_BUCKET", ""),
        region=region if region is not None else os.getenv("STORAGE_REGION", "ap-south-1"),
        endpoint=endpoint if endpoint is not None else os.getenv("STORAGE_ENDPOINT", ""),
        access_key=access_key if access_key is not None else os.getenv("STORAGE_ACCESS_KEY", ""),
        secret_key=secret_key if secret_key is not None else os.getenv("STORAGE_SECRET_KEY", ""),
        session_token=(
            session_token
            if session_token is not None
            else os.getenv("STORAGE_SESSION_TOKEN", "")
        ),
    )
    if not settings.bucket:
        raise StorageConfigurationError("STORAGE_BUCKET is required")
    if settings.endpoint and not settings.endpoint.startswith(("https://", "http://")):
        raise StorageConfigurationError("STORAGE_ENDPOINT must be an HTTP(S) URL")
    if (
        os.getenv("APP_ENV") == "production"
        and settings.endpoint.startswith("http://")
        and os.getenv("PRODUCTION_REHEARSAL") != "1"
    ):
        raise StorageConfigurationError("production custom storage endpoint must use HTTPS")
    settings.credential_mode  # validate the explicit pair
    return settings


def managed_uri_components(uri: str, bucket: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "s3" or parsed.netloc != bucket or not parsed.path.lstrip("/"):
        raise ValueError("invalid managed storage URI")
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
    unknown = set(query) - {"versionId"}
    if unknown:
        raise ValueError("unsupported managed storage URI query")
    versions = query.get("versionId", [])
    if len(versions) > 1:
        raise ValueError("managed storage URI has multiple version IDs")
    version_id = versions[0].strip() if versions else ""
    if version_id and len(version_id) > 1024:
        raise ValueError("managed storage version ID is too long")
    return parsed.path.lstrip("/"), version_id


def parse_uri(uri: str, bucket: str) -> str:
    """Backward-compatible key parser."""
    return managed_uri_components(uri, bucket)[0]


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


def sigv4_headers(
    method: str,
    url: str,
    access_key: str,
    secret_key: str,
    region: str = "ap-south-1",
    service: str = "s3",
    now: datetime.datetime | None = None,
    session_token: str = "",
) -> dict[str, str]:
    """Sign custom-endpoint requests used by the static credential path."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    parsed = urllib.parse.urlparse(url)
    canonical_uri = urllib.parse.quote(parsed.path or "/", safe="/-_.~")
    canonical_query = "&".join(
        f"{urllib.parse.quote(key, safe='-_.~')}={urllib.parse.quote(value, safe='-_.~')}"
        for key, value in sorted(
            urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        )
    )
    payload_hash = hashlib.sha256(b"").hexdigest()
    signed_headers = ["host", "x-amz-content-sha256", "x-amz-date"]
    canonical_header_items = [
        ("host", parsed.netloc),
        ("x-amz-content-sha256", payload_hash),
        ("x-amz-date", amzdate),
    ]
    if session_token:
        signed_headers.append("x-amz-security-token")
        canonical_header_items.append(("x-amz-security-token", session_token))
    canonical_header_items.sort()
    canonical_headers = "".join(f"{key}:{value}\n" for key, value in canonical_header_items)
    signed = ";".join(sorted(signed_headers))
    canonical_request = "\n".join(
        (
            method,
            canonical_uri,
            canonical_query,
            canonical_headers,
            signed,
            payload_hash,
        )
    )
    scope = f"{datestamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        (
            "AWS4-HMAC-SHA256",
            amzdate,
            scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        )
    )
    date_key = hmac.new(
        ("AWS4" + secret_key).encode(), datestamp.encode(), hashlib.sha256
    ).digest()
    region_key = hmac.new(date_key, region.encode(), hashlib.sha256).digest()
    service_key = hmac.new(region_key, service.encode(), hashlib.sha256).digest()
    signing_key = hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
        f"SignedHeaders={signed}, Signature={signature}"
    )
    headers = {
        "Host": parsed.netloc,
        "x-amz-date": amzdate,
        "x-amz-content-sha256": payload_hash,
        "Authorization": authorization,
    }
    if session_token:
        headers["x-amz-security-token"] = session_token
    return headers


def _default_s3_client(settings: StorageSettings):
    try:
        from botocore.config import Config
        from botocore.session import Session
    except ImportError as exc:  # pragma: no cover - exercised through stable error path
        raise StorageConfigurationError(
            "botocore is required for AWS default credential chain storage"
        ) from exc

    kwargs = {
        "service_name": "s3",
        "region_name": settings.region,
        "config": Config(
            signature_version="s3v4",
            connect_timeout=3,
            read_timeout=5,
            retries={"mode": "standard", "max_attempts": 3},
            s3={"addressing_style": "path" if settings.endpoint else "auto"},
        ),
    }
    if settings.endpoint:
        kwargs["endpoint_url"] = settings.endpoint.rstrip("/")
    # Deliberately omit credential arguments so the SDK can resolve and refresh
    # ECS task-role/container credentials and the rest of the default chain.
    return Session().create_client(**kwargs)


def _head_with_default_chain(
    settings: StorageSettings,
    key: str,
    version_id: str,
    client=None,
) -> tuple[int, str, str]:
    client = client or _default_s3_client(settings)
    request = {"Bucket": settings.bucket, "Key": key}
    if version_id:
        request["VersionId"] = version_id
    response = client.head_object(**request)
    metadata = response.get("Metadata") or {}
    return (
        int(response.get("ContentLength", -1)),
        str(metadata.get("sha256", "")).lower(),
        str(response.get("VersionId", version_id or "")),
    )


def _head_with_static_credentials(
    settings: StorageSettings,
    key: str,
    version_id: str,
    timeout: int,
) -> tuple[int, str, str]:
    endpoint = (settings.endpoint or "https://s3.amazonaws.com").rstrip("/")
    url = (
        f"{endpoint}/{urllib.parse.quote(settings.bucket, safe='')}/"
        f"{urllib.parse.quote(key, safe='/-_.~')}"
    )
    if version_id:
        url += "?versionId=" + urllib.parse.quote(version_id, safe="-_.~")
    headers = sigv4_headers(
        "HEAD",
        url,
        settings.access_key,
        settings.secret_key,
        settings.region,
        session_token=settings.session_token,
    )
    request = urllib.request.Request(url, headers=headers, method="HEAD")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return (
            int(response.headers.get("Content-Length", "-1")),
            response.headers.get("x-amz-meta-sha256", "").lower(),
            response.headers.get("x-amz-version-id", version_id or ""),
        )


def verify_managed_object(
    uri: str,
    expected_sha256: str,
    expected_size: int,
    endpoint: str | None = None,
    bucket: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
    region: str | None = None,
    timeout: int = 5,
    *,
    session_token: str | None = None,
    client=None,
    require_version: bool = False,
) -> dict[str, object]:
    settings = settings_from_env(
        endpoint=endpoint,
        bucket=bucket,
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        session_token=session_token,
    )
    key, expected_version_id = managed_uri_components(uri, settings.bucket)
    if require_version and not expected_version_id:
        raise StorageConfigurationError("version-bound managed storage URI required")

    if settings.credential_mode == "static":
        size, sha256, observed_version_id = _head_with_static_credentials(
            settings, key, expected_version_id, timeout
        )
    else:
        size, sha256, observed_version_id = _head_with_default_chain(
            settings, key, expected_version_id, client=client
        )

    if size != int(expected_size) or sha256 != expected_sha256.lower():
        raise RuntimeError("managed object metadata does not match evidence record")
    if expected_version_id and observed_version_id != expected_version_id:
        raise RuntimeError("managed object version does not match evidence record")
    return {
        "uri": uri,
        "size_bytes": size,
        "sha256": sha256,
        "version_id": observed_version_id,
        "credential_mode": settings.credential_mode,
    }
