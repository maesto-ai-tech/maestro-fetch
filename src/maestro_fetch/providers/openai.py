from __future__ import annotations
import json
from maestro_fetch.providers.base import LLMProvider
from maestro_fetch.providers.registry import register
from maestro_fetch.core.errors import ProviderError

DEFAULT_MODEL = "gpt-4o"


@register("openai")
class OpenAIProvider(LLMProvider):
    """Extracts structured data using GPT-4o."""

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    async def extract(self, content: str, schema: dict) -> dict:
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise ImportError("pip install maestro-fetch[openai]") from e

        client = AsyncOpenAI()
        prompt = (
            f"Extract fields per schema: {json.dumps(schema)}\n"
            f"Return ONLY valid JSON.\n\nText:\n{content[:8000]}"
        )
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            raise ProviderError(f"OpenAI extraction failed: {e}") from e
