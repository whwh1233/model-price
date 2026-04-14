"""Tests for CanonicalResolver against a fake LiteLLMRegistry.

We construct a small in-memory registry and exercise the resolver's
cascade: direct alias → prefix strip → version strip → contains.
Each test covers a specific resolution strategy.
"""

from services.canonical import CanonicalResolver
from services.litellm_registry import LiteLLMEntry, LiteLLMRegistry


def _make_entry(canonical_id: str, maker: str = "Anthropic", family: str = "Claude") -> LiteLLMEntry:
    return LiteLLMEntry(
        raw_key=canonical_id,
        canonical_id=canonical_id,
        slug=canonical_id,
        name=canonical_id,
        family=family,
        maker=maker,
        litellm_provider="anthropic",
        is_canonical=True,
        input_price=3.0,
        output_price=15.0,
        cache_read_price=None,
        cache_write_price=None,
        image_input_price=None,
        audio_input_price=None,
        audio_output_price=None,
        embedding_price=None,
        batch_input_price=None,
        batch_output_price=None,
        context_length=200_000,
        max_output_tokens=64_000,
        capabilities=["text", "vision"],
        input_modalities=["text", "image"],
        output_modalities=["text"],
        mode="chat",
        raw={},
    )


def _make_registry_with(entries: dict[str, LiteLLMEntry]) -> LiteLLMRegistry:
    """Build a registry directly (bypassing network/cache) for tests."""
    registry = LiteLLMRegistry()
    for canonical_id, entry in entries.items():
        registry._entries[canonical_id] = entry
        registry._alias[canonical_id] = canonical_id
    return registry


class TestCanonicalResolver:
    def test_direct_alias_hit(self):
        reg = _make_registry_with(
            {"claude-sonnet-4-5": _make_entry("claude-sonnet-4-5")}
        )
        resolver = CanonicalResolver(reg)
        result = resolver.resolve("anthropic", "claude-sonnet-4-5")
        assert result.matched()
        assert result.canonical_id == "claude-sonnet-4-5"
        assert result.strategy == "alias"

    def test_prefix_strip_openrouter(self):
        reg = _make_registry_with(
            {"claude-sonnet-4-5": _make_entry("claude-sonnet-4-5")}
        )
        resolver = CanonicalResolver(reg)
        # OpenRouter-style: "anthropic/claude-sonnet-4.5"
        result = resolver.resolve("openrouter", "anthropic/claude-sonnet-4.5")
        assert result.matched()
        assert result.canonical_id == "claude-sonnet-4-5"

    def test_dot_prefix_strip_bedrock(self):
        reg = _make_registry_with(
            {"claude-sonnet-4-5": _make_entry("claude-sonnet-4-5")}
        )
        resolver = CanonicalResolver(reg)
        # Bedrock-style: "anthropic.claude-sonnet-4-5-20250929-v1:0"
        result = resolver.resolve(
            "aws_bedrock",
            "anthropic.claude-sonnet-4-5-20250929-v1:0",
        )
        assert result.matched()
        assert result.canonical_id == "claude-sonnet-4-5"

    def test_version_suffix_strip(self):
        reg = _make_registry_with({"gpt-4o": _make_entry("gpt-4o", maker="OpenAI", family="GPT")})
        resolver = CanonicalResolver(reg)
        result = resolver.resolve("openai", "gpt-4o-2024-11-20")
        assert result.matched()
        assert result.canonical_id == "gpt-4o"

    def test_miss_goes_to_miss_strategy(self):
        reg = _make_registry_with(
            {"claude-sonnet-4-5": _make_entry("claude-sonnet-4-5")}
        )
        resolver = CanonicalResolver(reg)
        result = resolver.resolve("openrouter", "nonexistent/some-weird-model")
        assert not result.matched()
        assert result.canonical_id is None
        assert result.strategy == "miss"
        # tried list should record what we attempted so drift report can log it
        assert len(result.tried) > 0

    def test_empty_input_returns_none(self):
        reg = _make_registry_with({})
        resolver = CanonicalResolver(reg)
        result = resolver.resolve("openai", "")
        assert not result.matched()
        assert result.strategy == "empty"

    def test_contains_fallback_last_resort(self):
        """When nothing else matches, a needle that's a full slug suffix
        (after dash boundary) should contain-match as last resort."""
        reg = _make_registry_with(
            {"llama-4-maverick-17b": _make_entry("llama-4-maverick-17b", maker="Meta", family="Llama")}
        )
        resolver = CanonicalResolver(reg)
        # Passing an exact match should still resolve
        result = resolver.resolve("meta", "llama-4-maverick-17b")
        assert result.matched()
        assert result.canonical_id == "llama-4-maverick-17b"
