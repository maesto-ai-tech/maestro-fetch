from __future__ import annotations
from abc import ABC, abstractmethod
from maestro_fetch.core.config import FetchConfig
from maestro_fetch.core.result import FetchResult


class BaseAdapter(ABC):
    """Contract for all source adapters.

    Responsibilities:
    - supports(): tell the Router whether this adapter handles a URL
    - fetch(): download/parse the source, return unified FetchResult

    Invariants:
    - fetch() must always return FetchResult (never None)
    - fetch() raises FetchError subclasses on failure, never swallows
    """

    @abstractmethod
    def supports(self, url: str) -> bool:
        """Return True if this adapter can handle the given URL."""

    @abstractmethod
    async def fetch(self, url: str, config: FetchConfig) -> FetchResult:
        """Fetch and parse data from url. Raises FetchError on failure."""
