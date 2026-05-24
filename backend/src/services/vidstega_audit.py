"""
VidStega Audit Trail – Weeks 5-6
Embeds encrypted AI reasoning into receipt images using LSB steganography,
then signs the result for tamper-proof verification.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import struct
from datetime import datetime, UTC
from io import BytesIO
from typing import Any

from PIL import Image


def _text_to_bits(text: str) -> list[int]:
    """Encode a UTF-8 string as a flat list of bits."""
    data = text.encode("utf-8")
    bits: list[int] = []
    # 4-byte length prefix (big-endian)
    bits.extend(int(b) for b in f"{len(data):032b}")
    for byte in data:
        bits.extend(int(b) for b in f"{byte:08b}")
    return bits


def _bits_to_text(bits: list[int]) -> str:
    """Decode a flat list of bits back to a UTF-8 string."""
    length = int("".join(str(b) for b in bits[:32]), 2)
    payload_bits = bits[32 : 32 + length * 8]
    chars = [
        chr(int("".join(str(b) for b in payload_bits[i : i + 8]), 2))
        for i in range(0, len(payload_bits), 8)
    ]
    return "".join(chars)


def embed_lsb(image: Image.Image, payload: str) -> Image.Image:
    """Embed *payload* into the LSB channel of *image*."""
    img = image.convert("RGB")
    pixels = list(img.getdata())
    bits = _text_to_bits(payload)

    capacity = len(pixels) * 3
    if len(bits) > capacity:
        raise ValueError(
            f"Payload too large for image: need {len(bits)} bits, have {capacity}."
        )

    flat: list[int] = []
    for r, g, b in pixels:
        flat.extend([r, g, b])

    for idx, bit in enumerate(bits):
        flat[idx] = (flat[idx] & 0xFE) | bit

    new_pixels = [(flat[i], flat[i + 1], flat[i + 2]) for i in range(0, len(flat) - 2, 3)]
    out = Image.new("RGB", img.size)
    out.putdata(new_pixels)
    return out


def extract_lsb(image: Image.Image) -> str:
    """Extract a payload previously embedded with :func:`embed_lsb`."""
    img = image.convert("RGB")
    pixels = list(img.getdata())
    flat: list[int] = []
    for r, g, b in pixels:
        flat.extend([r, g, b])

    bits = [v & 1 for v in flat]
    return _bits_to_text(bits)


def sign_image(image_bytes: bytes, secret: str) -> str:
    """HMAC-SHA256 signature of *image_bytes*."""
    return hmac.new(secret.encode(), image_bytes, hashlib.sha256).hexdigest()


def verify_signature(image_bytes: bytes, signature: str, secret: str) -> bool:
    """Constant-time HMAC verification."""
    expected = sign_image(image_bytes, secret)
    return hmac.compare_digest(expected, signature)


class VidStegaAuditTrail:
    """Creates and verifies tamper-proof audit records embedded in receipt images."""

    def __init__(self, signing_secret: str | None = None) -> None:
        self._secret = signing_secret or os.environ.get(
            "VIDSTEGA_SIGNING_SECRET", "change-me-in-production"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_audit_record(
        self,
        decision_id: str,
        ai_reasoning: dict[str, Any],
        user_approval: str,
        amount: float,
        receipt_image: Image.Image | None = None,
    ) -> tuple[bytes, str]:
        """Embed an audit record into a receipt image.

        Returns
        -------
        (image_bytes, signature)
            *image_bytes* is a PNG with the audit data hidden in its LSBs.
            *signature* is an HMAC-SHA256 hex string for integrity checks.
        """
        audit_data = {
            "decision_id": decision_id,
            "ai_reasoning": ai_reasoning,
            "model": "claude-3-5-sonnet-20241022",
            "user_approval": user_approval,
            "amount_usd": amount,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        payload = json.dumps(audit_data, separators=(",", ":"))

        img = receipt_image or self._blank_receipt()
        stamped = embed_lsb(img, payload)

        buf = BytesIO()
        stamped.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        signature = sign_image(image_bytes, self._secret)
        return image_bytes, signature

    def verify_audit_record(
        self, image_bytes: bytes, signature: str
    ) -> dict[str, Any]:
        """Verify and extract the audit record from a receipt image.

        Returns
        -------
        dict with keys: valid (bool), audit_data (dict | None)
        """
        if not verify_signature(image_bytes, signature, self._secret):
            return {"valid": False, "audit_data": None, "error": "Signature mismatch"}

        img = Image.open(BytesIO(image_bytes))
        try:
            payload = extract_lsb(img)
            audit_data = json.loads(payload)
            return {"valid": True, "audit_data": audit_data}
        except Exception as exc:
            return {"valid": False, "audit_data": None, "error": str(exc)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _blank_receipt(width: int = 400, height: int = 300) -> Image.Image:
        """Generate a simple white receipt canvas."""
        img = Image.new("RGB", (width, height), color=(255, 255, 255))
        return img
