"""Tests for mail message building (pure; no SMTP)."""

from __future__ import annotations

from agents import mail


def test_build_message_plain():
    msg = mail.build_message("me@x.com", "you@x.com", "Hi", "body")
    assert msg["From"] == "me@x.com"
    assert msg["Subject"] == "Hi"
    assert msg.get_content_type() == "text/plain"


def test_build_message_attaches_existing_png(tmp_path):
    png = tmp_path / "strip_2026-08-28.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    msg = mail.build_message("me@x.com", "you@x.com", "Hi", "body", attachments=[str(png)])
    attachments = [p for p in msg.iter_attachments()]
    assert len(attachments) == 1
    a = attachments[0]
    assert a.get_content_type() == "image/png"
    assert a.get_filename() == "strip_2026-08-28.png"


def test_build_message_skips_missing_attachments(tmp_path):
    msg = mail.build_message(
        "me@x.com", "you@x.com", "Hi", "body",
        attachments=[str(tmp_path / "nope.png")],
    )
    assert list(msg.iter_attachments()) == []
