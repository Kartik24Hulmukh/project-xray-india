"""Authentication helpers for Project X-Ray India.

OIDC proxy assertion policy (fail-closed):
- MFA must be true
- Signature must validate over the exact header values
- Timestamp must be within max_age seconds
- Subject must match a conservative format/length bound
- Exactly one recognized application role is required after normalization
- Zero recognized roles: deny
- More than one distinct recognized role: deny as ambiguous
- Duplicate of the same normalized role collapses to one
- Unknown roles never grant access
- Replay protection blocks reuse of the same signed assertion
- Gateways SHOULD send a unique X-Auth-Nonce per request so multi-call
  sessions are not treated as replays when timestamps share a second
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone

RECOGNIZED_ROLES = frozenset({'admin', 'reviewer', 'scanner'})
_SUBJECT_RE = re.compile(r'^[A-Za-z0-9._:@+/-]{1,200}$')
_NONCE_RE = re.compile(r'^[A-Za-z0-9._:-]{1,128}$')

# Process-local replay cache: signature -> expiry epoch
_replay_lock = threading.Lock()
_replay_seen = OrderedDict()
_REPLAY_MAX = 4096


def token_hash(token, pepper):
    return hmac.new(pepper.encode(), token.encode(), hashlib.sha256).hexdigest()


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def proxy_signature(subject, roles, mfa, timestamp, secret, nonce=''):
    """HMAC over subject|roles|mfa|timestamp[|nonce]."""
    parts = [subject, roles, mfa, timestamp]
    if nonce:
        parts.append(nonce)
    message = '|'.join(parts)
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def normalize_roles(roles_header):
    """Normalize a comma-separated roles header into ordered unique roles.

    Returns (recognized_unique_roles, had_unknown).
    Whitespace is stripped; case is lowercased for matching.
    """
    if roles_header is None:
        return [], False
    raw_parts = [p.strip().lower() for p in str(roles_header).split(',')]
    raw_parts = [p for p in raw_parts if p]
    recognized = []
    seen = set()
    had_unknown = False
    for part in raw_parts:
        if part in RECOGNIZED_ROLES:
            if part not in seen:
                recognized.append(part)
                seen.add(part)
        else:
            had_unknown = True
    return recognized, had_unknown


def resolve_single_role(roles_header):
    """Fail-closed role resolution.

    Accepts exactly one distinct recognized role. Duplicates of the same
    role are collapsed. Unknown-only or multi-role assertions are denied.
    Presence of unknown roles alongside a recognized role is denied.
    """
    recognized, had_unknown = normalize_roles(roles_header)
    if had_unknown:
        return None
    if len(recognized) != 1:
        return None
    return recognized[0]


def _remember_assertion(signature, expires_at):
    """Record assertion signature to block replay within max_age window."""
    now = time.time()
    with _replay_lock:
        while _replay_seen:
            k, exp = next(iter(_replay_seen.items()))
            if exp >= now:
                break
            _replay_seen.popitem(last=False)
        if signature in _replay_seen:
            return False
        _replay_seen[signature] = expires_at
        while len(_replay_seen) > _REPLAY_MAX:
            _replay_seen.popitem(last=False)
    return True


def verify_proxy(headers, secret, max_age=None, allow_replay=False):
    """Verify OIDC proxy headers.

    Returns (role, subject) on success, else None.
    """
    if not secret:
        return None
    if max_age is None:
        max_age = int(os.getenv('OIDC_MAX_AGE_SECONDS', '90'))

    subject = headers.get('X-Auth-Subject', '').strip()
    roles = headers.get('X-Auth-Roles', '').strip()
    mfa = headers.get('X-Auth-MFA', '').strip().lower()
    stamp = headers.get('X-Auth-Timestamp', '').strip()
    signature = headers.get('X-Auth-Signature', '').strip()
    nonce = headers.get('X-Auth-Nonce', '').strip()

    if not all((subject, roles, stamp, signature)) or mfa != 'true':
        return None
    if not _SUBJECT_RE.match(subject):
        return None
    if nonce and not _NONCE_RE.match(nonce):
        return None
    if len(signature) > 128 or not re.fullmatch(r'[0-9a-fA-F]+', signature):
        return None

    try:
        ts = int(stamp)
    except ValueError:
        return None
    now = time.time()
    if abs(now - ts) > max_age:
        return None

    expected = proxy_signature(subject, roles, mfa, stamp, secret, nonce=nonce)
    if not hmac.compare_digest(signature, expected):
        return None

    role = resolve_single_role(roles)
    if role is None:
        return None

    if not allow_replay:
        # Replay protection: same signed assertion cannot be reused.
        if not _remember_assertion(signature.lower(), ts + max_age + 1):
            return None

    return (role, subject)


def clear_replay_cache():
    """Test helper to reset replay state."""
    with _replay_lock:
        _replay_seen.clear()
