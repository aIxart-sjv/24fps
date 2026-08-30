"""
QR code image generation for physical custody handoff tokens (Phase 21,
Part A).

Pure, DB-free: encodes exactly one opaque string (the raw handoff token
from `app.security.tokens.generate_token`) as a PNG, base64-encoded for
JSON transport. Never encodes anything else -- no evidence metadata, no
password, no session token, no PII (task Phase 21 scope: "QR code
content: only the opaque token/reference... Never encode: passwords,
general session tokens, secret keys, unnecessary evidence metadata or
PII"). Uses the maintained `qrcode` library rather than a hand-rolled
encoder.
"""

from __future__ import annotations

import base64
from io import BytesIO

import qrcode

__all__ = ["generate_qr_png_base64"]


def generate_qr_png_base64(payload: str) -> str:
    """Render `payload` as a QR code PNG, returned as a base64 string.

    Args:
        payload: The exact opaque string to encode -- callers must pass
            only a raw handoff token, never a composite structure
            containing anything sensitive beyond it.

    Returns:
        Base64-encoded PNG image bytes (no data-URI prefix).
    """
    image = qrcode.make(payload)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")
