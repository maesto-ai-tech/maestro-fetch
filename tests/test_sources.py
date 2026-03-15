"""Tests for source adapter loader (sources/loader.py).

Covers: @meta parsing, directory scanning, adapter execution.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from maestro_fetch.sources.loader import (
    SourceContext,
    load_sources,
    parse_meta,
    run_adapter,
)


# -- @meta parsing ---------------------------------------------------------

_VALID_SOURCE = '''\
"""Example adapter.

@meta
name: test-adapter
description: A test adapter
category: testing
output: json
"""


async def run(ctx, **kwargs):
    return {"content": "hello from test adapter", "extra": kwargs}
'''

_NO_META_SOURCE = '''\
"""This module has no @meta block."""


def helper():
    return 42
'''


def test_parse_meta_valid(tmp_path: Path) -> None:
    """parse_meta extracts name, description, category, output from @meta."""
    py_file = tmp_path / "adapter.py"
    py_file.write_text(_VALID_SOURCE, encoding="utf-8")

    meta = parse_meta(py_file)
    assert meta is not None
    assert meta.name == "test-adapter"
    assert meta.description == "A test adapter"
    assert meta.category == "testing"
    assert meta.output == "json"


def test_parse_meta_no_meta(tmp_path: Path) -> None:
    """parse_meta returns None when no @meta block is present."""
    py_file = tmp_path / "plain.py"
    py_file.write_text(_NO_META_SOURCE, encoding="utf-8")

    assert parse_meta(py_file) is None


# -- load_sources ----------------------------------------------------------


def test_load_sources_empty_dir(tmp_path: Path) -> None:
    """An empty directory yields an empty adapter list."""
    assert load_sources(tmp_path) == []


def test_load_sources_with_adapters(tmp_path: Path) -> None:
    """Discovers .py files with @meta blocks; ignores files starting with _."""
    (tmp_path / "good.py").write_text(_VALID_SOURCE, encoding="utf-8")
    (tmp_path / "_private.py").write_text(_VALID_SOURCE, encoding="utf-8")
    (tmp_path / "no_meta.py").write_text(_NO_META_SOURCE, encoding="utf-8")

    adapters = load_sources(tmp_path)
    assert len(adapters) == 1
    assert adapters[0].meta.name == "test-adapter"


def test_load_sources_nonexistent_dir(tmp_path: Path) -> None:
    """A path that does not exist returns an empty list."""
    assert load_sources(tmp_path / "nope") == []


# -- run_adapter -----------------------------------------------------------


@pytest.mark.asyncio
async def test_run_adapter(tmp_path: Path) -> None:
    """Execute a simple adapter and verify its return dict."""
    (tmp_path / "hello.py").write_text(_VALID_SOURCE, encoding="utf-8")
    adapters = load_sources(tmp_path)
    assert len(adapters) == 1

    ctx = SourceContext()
    result = await run_adapter(adapters[0], ctx, greeting="world")
    assert result["content"] == "hello from test adapter"
    assert result["extra"]["greeting"] == "world"
