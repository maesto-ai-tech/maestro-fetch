import pytest
from maestro_fetch.adapters.base import BaseAdapter
from maestro_fetch.core.config import FetchConfig
from maestro_fetch.core.result import FetchResult


class ConcreteAdapter(BaseAdapter):
    def supports(self, url: str) -> bool:
        return url.startswith("fake://")

    async def fetch(self, url: str, config: FetchConfig) -> FetchResult:
        return FetchResult(url=url, source_type="test", content="ok")


def test_supports():
    adapter = ConcreteAdapter()
    assert adapter.supports("fake://anything") is True
    assert adapter.supports("https://example.com") is False


@pytest.mark.asyncio
async def test_fetch():
    adapter = ConcreteAdapter()
    config = FetchConfig()
    result = await adapter.fetch("fake://x", config)
    assert result.content == "ok"
    assert result.source_type == "test"


def test_abstract_cannot_instantiate():
    with pytest.raises(TypeError):
        BaseAdapter()
