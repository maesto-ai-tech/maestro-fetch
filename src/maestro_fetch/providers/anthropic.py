from __future__ import annotations
import json
from maestro_fetch.providers.base import LLMProvider
from maestro_fetch.providers.registry import register
from maestro_fetch.core.errors import ProviderError

DEFAULT_MODEL = "claude-sonnet-4-6"


@register("anthropic")
class AnthropicProvider(LLMProvider):
    """Extracts structured data using Claude."""

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    async def extract(self, content: str, schema: dict) -> dict:
        try:
            import anthropic
        except ImportError as e:
            raise ImportError("pip install maestro-fetch[anthropic]") from e

        client = anthropic.AsyncAnthropic()
        prompt = (
            f"Extract the following fields from the text below.\n"
            f"Schema: {json.dumps(schema)}\n"
            f"Return ONLY valid JSON.\n\n"
            f"Text:\n{content[:8000]}"
        )
        try:
            message = await client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text
            return json.loads(raw)
        except Exception as e:
            raise ProviderError(f"Anthropic extraction failed: {e}") from e
