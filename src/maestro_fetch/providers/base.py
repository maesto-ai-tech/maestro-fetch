from __future__ import annotations
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Interface for LLM-based extraction providers.

    Invariant: extract() always returns a dict (may be empty on failure).
    """

    @abstractmethod
    async def extract(self, content: str, schema: dict) -> dict:
        """Extract structured data from content according to schema."""
