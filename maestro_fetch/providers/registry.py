from __future__ import annotations
from maestro_fetch.providers.base import LLMProvider

_REGISTRY: dict[str, type[LLMProvider]] = {}


def register(name: str):
    """Class decorator that registers an LLMProvider under the given name."""
    def decorator(cls):
        _REGISTRY[name] = cls
        return cls
    return decorator


def get_provider(name: str) -> LLMProvider:
    """Return an instance of the named provider, or raise ValueError."""
    if name not in _REGISTRY:
        raise ValueError(f"Unknown provider '{name}'. Available: {list(_REGISTRY)}")
    return _REGISTRY[name]()
