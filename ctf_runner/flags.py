"""Flag generation and validation.

Flags are never stored in plaintext inside ``event.json`` — only their
SHA-256 hash — so a leaked config/scoreboard file cannot reveal flags.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import string

TOKEN_ALPHABET = string.ascii_lowercase + string.digits
DEFAULT_PREFIX = "flag"
TOKEN_LENGTH = 16


def generate_flag(prefix: str = DEFAULT_PREFIX, length: int = TOKEN_LENGTH) -> str:
    """Generate a random flag like ``flag{a3f9c0...}``."""
    token = "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(length))
    return f"{prefix}{{{token}}}"


def hash_flag(flag: str) -> str:
    """Return the SHA-256 hex digest of a (stripped) flag."""
    return hashlib.sha256(flag.strip().encode("utf-8")).hexdigest()


def verify_flag(flag: str, expected_hash: str) -> bool:
    """Constant-time comparison of a submitted flag against a stored hash."""
    return hmac.compare_digest(hash_flag(flag), expected_hash)
