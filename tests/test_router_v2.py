"""Tests for the URL router (core/router.py) — Phase 2 additions.

Covers: PDF, YouTube, Dropbox, Baidu Pan, web fallback.
Does NOT modify the existing tests/unit/test_router.py.
"""
from __future__ import annotations

from maestro_fetch.core.router import detect_type


def test_detect_pdf() -> None:
    """*.pdf URLs are classified as 'doc'."""
    assert detect_type("https://example.com/report.pdf") == "doc"
    assert detect_type("https://cdn.example.com/white-paper.pdf?token=abc") == "doc"


def test_detect_youtube() -> None:
    """youtube.com watch URLs are classified as 'media'."""
    assert detect_type("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "media"
    assert detect_type("https://youtu.be/dQw4w9WgXcQ") == "media"


def test_detect_dropbox() -> None:
    """dropbox.com URLs are classified as 'cloud'."""
    assert detect_type("https://www.dropbox.com/s/abc123/file.csv?dl=0") == "cloud"


def test_detect_baidu_pan() -> None:
    """pan.baidu.com URLs are classified as 'baidu_pan'."""
    assert detect_type("https://pan.baidu.com/s/1abc123?pwd=xxxx") == "baidu_pan"


def test_detect_web_fallback() -> None:
    """Unrecognised URLs default to 'web'."""
    assert detect_type("https://news.ycombinator.com/") == "web"
    assert detect_type("https://example.com/page") == "web"
