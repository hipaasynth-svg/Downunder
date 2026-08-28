"""Tests for the Gemini image client's pure helpers (no network)."""

from __future__ import annotations

import base64

from agents import gemini


def test_configured_reads_env(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert gemini.configured() is False
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    assert gemini.configured() is True


def test_build_request_shape_text_only():
    body = gemini.build_request("draw a cat")
    assert body["contents"][0]["parts"][0] == {"text": "draw a cat"}
    assert body["generationConfig"]["responseModalities"] == ["IMAGE"]


def test_build_request_attaches_references_as_inlinedata():
    body = gemini.build_request("draw her here", references=[b"\x89PNGfake"])
    parts = body["contents"][0]["parts"]
    assert parts[0] == {"text": "draw her here"}
    ref = parts[1]["inlineData"]
    assert ref["mimeType"] == "image/png"
    assert base64.b64decode(ref["data"]) == b"\x89PNGfake"


def test_build_request_skips_empty_references():
    body = gemini.build_request("x", references=[b"", None])  # type: ignore[list-item]
    assert len(body["contents"][0]["parts"]) == 1  # only the text part


def test_first_image_bytes_decodes_inlinedata():
    raw = b"\x89PNG-image-bytes"
    payload = {
        "candidates": [
            {"content": {"parts": [
                {"text": "here you go"},
                {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(raw).decode()}},
            ]}}
        ]
    }
    assert gemini.first_image_bytes(payload) == raw


def test_first_image_bytes_none_when_no_image():
    assert gemini.first_image_bytes({"candidates": [{"content": {"parts": [{"text": "no image"}]}}]}) is None
    assert gemini.first_image_bytes({}) is None
    assert gemini.first_image_bytes("nope") is None


def test_generate_image_returns_none_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert gemini.generate_image("draw a cat") is None
