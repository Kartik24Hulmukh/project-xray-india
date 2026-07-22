"""Pure trusted-gateway contract for Cognito/ALB identity adaptation.

The AWS-specific ALB signature verifier remains an injected boundary.  This
module handles the locally testable security contract: inbound header
stripping, stable issuer+subject identity, exact role binding, and fresh
versioned downstream assertions.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from typing import Mapping

ALLOWED_ROLES = frozenset({"admin", "reviewer", "scanner"})
ASSERTION_VERSION = 1
MAX_LIFETIME_SECONDS = 30


def strip_client_auth_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Remove all client-supplied application assertion headers."""
    return {
        str(name): str(value)
        for name, value in headers.items()
        if not str(name).lower().startswith("x-auth-")
    }


def stable_principal(issuer: str, subject: str) -> str:
    if not issuer or not subject:
        raise ValueError("verified issuer and subject are required")
    digest = hashlib.sha256((issuer + "\x00" + subject).encode("utf-8")).hexdigest()
    return "oidc:" + digest


def canonical_assertion(payload: Mapping[str, object]) -> bytes:
    return json.dumps(
        dict(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def assertion_signature(payload: Mapping[str, object], secret: str) -> str:
    if len(secret) < 32:
        raise ValueError("gateway signing secret is too short")
    message = b"project-xray-gateway-assertion-v1\n" + canonical_assertion(payload)
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def resolve_role_binding(
    bindings: Mapping[str, object], issuer: str, subject: str
) -> str:
    """Resolve exactly one server-controlled role for issuer+subject."""
    principal = stable_principal(issuer, subject)
    value = bindings.get(principal)
    if not isinstance(value, str) or value not in ALLOWED_ROLES:
        raise PermissionError("verified identity is not bound to exactly one role")
    return value


def mint_gateway_assertion(
    *,
    issuer: str,
    subject: str,
    role: str,
    secret: str,
    key_id: str,
    audience: str = "project-xray-app",
    issued_at: int | None = None,
    nonce: str | None = None,
    lifetime_seconds: int = MAX_LIFETIME_SECONDS,
) -> dict[str, str]:
    if role not in ALLOWED_ROLES:
        raise ValueError("invalid gateway role")
    if not key_id or len(key_id) > 100:
        raise ValueError("invalid gateway key ID")
    if not audience or len(audience) > 200:
        raise ValueError("invalid gateway audience")
    if not 1 <= int(lifetime_seconds) <= MAX_LIFETIME_SECONDS:
        raise ValueError("gateway assertion lifetime is invalid")
    issued_at = int(time.time()) if issued_at is None else int(issued_at)
    nonce = nonce or secrets.token_urlsafe(24)
    if not 16 <= len(nonce) <= 128:
        raise ValueError("gateway nonce is invalid")
    principal = stable_principal(issuer, subject)
    payload = {
        "audience": audience,
        "expires_at": issued_at + int(lifetime_seconds),
        "issued_at": issued_at,
        "issuer": issuer,
        "key_id": key_id,
        "mfa": True,
        "nonce": nonce,
        "principal": principal,
        "role": role,
        "subject": subject,
        "version": ASSERTION_VERSION,
    }
    signature = assertion_signature(payload, secret)
    return {
        "X-Auth-Version": str(payload["version"]),
        "X-Auth-Issuer": str(payload["issuer"]),
        "X-Auth-Subject": str(payload["subject"]),
        "X-Auth-Principal": str(payload["principal"]),
        "X-Auth-Role": str(payload["role"]),
        "X-Auth-MFA": "true",
        "X-Auth-Issued-At": str(payload["issued_at"]),
        "X-Auth-Expires-At": str(payload["expires_at"]),
        "X-Auth-Audience": str(payload["audience"]),
        "X-Auth-Nonce": str(payload["nonce"]),
        "X-Auth-Key-Id": str(payload["key_id"]),
        "X-Auth-Signature": signature,
    }
