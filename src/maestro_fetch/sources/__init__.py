"""External source adapter loader.

Re-exports the public API from sources.loader so callers can write::

    from maestro_fetch.sources import load_sources, run_adapter
"""
from __future__ import annotations

from maestro_fetch.sources.loader import (
    SourceAdapter,
    SourceContext,
    SourceMeta,
    load_sources,
    parse_meta,
    run_adapter,
)

__all__ = [
    "SourceAdapter",
    "SourceContext",
    "SourceMeta",
    "load_sources",
    "parse_meta",
    "run_adapter",
]
