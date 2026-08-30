"""
Minimal authentication/security primitives (Phase 21).

Pure, DB-free, HTTP-free: password hashing (`app.security.passwords`),
opaque-token generation/hashing (`app.security.tokens`), and QR image
rendering of an opaque token (`app.security.qr`). `app.core.
auth_manager`/`app.core.custody_manager` are the DB-aware layers built on
top of these, mirroring every prior phase's pure-primitive/DB-manager
split.
"""

from __future__ import annotations

from app.security.passwords import hash_password, verify_password
from app.security.qr import generate_qr_png_base64
from app.security.tokens import generate_token, hash_token

__all__ = [
    "generate_qr_png_base64",
    "generate_token",
    "hash_password",
    "hash_token",
    "verify_password",
]
