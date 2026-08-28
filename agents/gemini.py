"""
Image generation via Google's Gemini 2.5 Flash Image ("Nano Banana").

Chosen because it is the strongest, cheapest way to keep RECURRING characters
consistent: you hand it a character's canon reference image and it redraws that
same character in a new scene (~$0.04/image). One API key, plain HTTP — so it
runs headless from the nightly GitHub Action.

Enabled by ``GEMINI_API_KEY`` (get one free at Google AI Studio). With no key
this degrades gracefully: ``configured()`` is False and ``generate_image()``
returns ``None``, so the cartoon step falls back to a text storyboard instead of
raising.

Deliberately dependency-free (stdlib ``urllib`` + ``base64``), matching the
other readers in this package.

REST contract (Gemini API):
  POST https://generativelanguage.googleapis.com/v1beta/models/
       gemini-2.5-flash-image:generateContent
  header:  x-goog-api-key: <key>
  body:    {"contents":[{"parts":[{"text":...},
                                   {"inlineData":{"mimeType","data"}}...]}],
            "generationConfig":{"responseModalities":["IMAGE"]}}
  image:   candidates[0].content.parts[].inlineData.data  (base64, camelCase)
"""

from __future__ import annotations

import base64
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_MODEL = "gemini-2.5-flash-image"
_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL}:generateContent"
)
# One image (data: URIs aside) can be up to a few MB; the API caps a request at
# 20MB including all inline reference images.
_MAX_REQUEST_BYTES = 20 * 1024 * 1024


def api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip()


def configured() -> bool:
    """True when an image-generation key is available (real images vs text-only)."""
    return bool(api_key())


def _part_for_reference(png_bytes: bytes) -> dict:
    return {
        "inlineData": {
            "mimeType": "image/png",
            "data": base64.b64encode(png_bytes).decode("ascii"),
        }
    }


def build_request(prompt: str, references: list[bytes] | None = None) -> dict:
    """Assemble the generateContent request body. Pure; no network."""
    parts: list[dict] = [{"text": prompt}]
    for ref in references or []:
        if ref:
            parts.append(_part_for_reference(ref))
    return {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }


def first_image_bytes(payload: dict) -> bytes | None:
    """Extract the first generated image's decoded PNG bytes from a response.

    Pure; tolerates a malformed/parts-less payload by returning None.
    """
    if not isinstance(payload, dict):
        return None
    for cand in payload.get("candidates", []) or []:
        content = cand.get("content") if isinstance(cand, dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        for part in parts or []:
            inline = part.get("inlineData") if isinstance(part, dict) else None
            data = inline.get("data") if isinstance(inline, dict) else None
            if data:
                try:
                    return base64.b64decode(data)
                except (ValueError, TypeError):
                    return None
    return None


def generate_image(
    prompt: str,
    references: list[bytes] | None = None,
    *,
    key: str | None = None,
    timeout: float = 90.0,
) -> bytes | None:
    """Generate one image, optionally conditioned on reference PNGs.

    Returns the PNG bytes, or ``None`` (never raises) when no key is set, the
    request would exceed the size cap, or the call/parse fails — so callers can
    degrade to a text storyboard without special-casing.
    """
    k = key if key is not None else api_key()
    if not k:
        return None
    body = json.dumps(build_request(prompt, references)).encode("utf-8")
    if len(body) > _MAX_REQUEST_BYTES:
        return None
    req = Request(
        _ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": k,
        },
    )
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - trusted Google endpoint
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except HTTPError as exc:
        # Surface the reason into the run log (never raises) — the most common
        # one is a quota/billing wall on the image model: HTTP 429 or a 400 with
        # "limit: 0", which means billing must be enabled on the key's project.
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
        except Exception:  # noqa: BLE001
            detail = ""
        print(f"[gemini] image request failed: HTTP {exc.code} {detail}")
        return None
    except (URLError, ValueError, TimeoutError, OSError) as exc:
        print(f"[gemini] image request failed: {type(exc).__name__}: {exc}")
        return None
    return first_image_bytes(payload)
