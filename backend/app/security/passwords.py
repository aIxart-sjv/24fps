"""
Password hashing (Phase 21, "Physical Chain of Custody + QR Handoff").

No password hashing existed anywhere in this codebase before Phase 21
(confirmed by inspection: no `User` model, no auth module, no password
handling of any kind). `bcrypt` is added as this project's one, minimal,
purpose-built dependency for this -- not `app.hashing.sha256`/`md5`
(Phase 3), which are deliberately fast, unsalted digests correct for
*evidence integrity* (proving a file's bytes are unchanged) and
deliberately wrong for *password* storage (fast + unsalted is exactly
what makes a hash brute-forceable/rainbow-table-able). Reusing them here
would be the "reuse a hash for the wrong purpose" mistake, not the "reuse
existing infrastructure" this project otherwise consistently practices.

`bcrypt` handles its own per-password random salt and work factor
internally -- nothing here needs its own salt management.
"""

from __future__ import annotations

import bcrypt

__all__ = ["hash_password", "verify_password"]


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password for storage.

    Args:
        plain_password: The plaintext password. Never logged, never
            stored anywhere except as the return value of this function.

    Returns:
        A bcrypt hash string (includes the algorithm identifier, cost
        factor, and salt -- everything `verify_password` needs, safe to
        store directly in a database column).
    """
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash.

    Args:
        plain_password: The plaintext password supplied at login.
        password_hash: The stored hash from `hash_password`.

    Returns:
        `True` if the password matches. `False` for a mismatch or for
        any malformed/corrupt stored hash -- never raises for bad stored
        data, since that would turn a data problem into an outage rather
        than a clean "authentication failed".
    """
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False
