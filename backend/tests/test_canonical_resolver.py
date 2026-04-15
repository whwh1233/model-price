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

    def test_exact_match_only_no_prefix_boundary(self):
        """Exact slug match resolves; prefix-boundary heuristics must NOT.

        Regression for the bug that collapsed kimi-k2 → kimi-k2-5,
        qwen3-coder → qwen3-coder-plus, veo-3 → veo-3-1-fast-generate-001,
        and bare 'claude' → claude-opus-4-1. The old _contains_match
        accepted slug.startswith(needle + '-') which non-deterministically
        merged distinct models into whichever k2/coder/veo variant Python's
        set iteration happened to surface first.
        """
        reg = _make_registry_with({
            "kimi-k2-5": _make_entry("kimi-k2-5", maker="Moonshot AI", family="Kimi"),
            "kimi-k2-thinking": _make_entry("kimi-k2-thinking", maker="Moonshot AI", family="Kimi"),
            "qwen3-coder-plus": _make_entry("qwen3-coder-plus", maker="Alibaba", family="Qwen"),
            "claude-opus-4-1": _make_entry("claude-opus-4-1"),
            "veo-3-1-lite-generate": _make_entry("veo-3-1-lite-generate", maker="Google", family="Veo"),
        })
        resolver = CanonicalResolver(reg)

        # These must miss — none of them is in the canonical set, and
        # each one is a structurally distinct model from the prefix-
        # matching candidates above.
        for raw in [
            "moonshotai/kimi-k2",       # not kimi-k2-5
            "qwen/qwen3-coder",         # not qwen3-coder-plus
            "claude",                   # not claude-opus-4-1
            "veo-3",                    # not veo-3-1-lite-generate
            "veo-3.1",
        ]:
            result = resolver.resolve("openrouter", raw)
            assert not result.matched(), (
                f"{raw!r} must NOT match a prefix sibling; got {result.canonical_id}"
            )

        # Exact matches still work
        result = resolver.resolve("openrouter", "moonshotai/kimi-k2.5")
        assert result.canonical_id == "kimi-k2-5"

    def test_variant_tags_no_longer_strip_identity_carrying_suffixes(self):
        """Regression for the LiteLLM-inherited alias bug.

        Tags like -instruct, -preview, -exp, -experimental, -latest
        were once in _VARIANT_TAGS and got stripped during version
        normalization. That collapsed gpt-3.5-turbo-instruct →
        gpt-3-5-turbo (different products, different prices),
        gemini-2.5-pro-preview → gemini-2-5-pro, and
        deepseek-v3.2-exp → deepseek-v3-2.

        These suffixes carry product identity and must survive.
        """
        reg = _make_registry_with({
            "gpt-3-5-turbo": _make_entry("gpt-3-5-turbo", maker="OpenAI", family="GPT"),
            "gpt-3-5-turbo-instruct": _make_entry(
                "gpt-3-5-turbo-instruct", maker="OpenAI", family="GPT"
            ),
            "gemini-2-5-pro": _make_entry("gemini-2-5-pro", maker="Google", family="Gemini"),
            "gemini-2-5-pro-preview": _make_entry(
                "gemini-2-5-pro-preview", maker="Google", family="Gemini"
            ),
            "deepseek-v3-2": _make_entry("deepseek-v3-2", maker="DeepSeek", family="DeepSeek"),
        })
        resolver = CanonicalResolver(reg)

        # -instruct must reach its OWN canonical, not the parent
        r = resolver.resolve("openrouter", "openai/gpt-3.5-turbo-instruct")
        assert r.canonical_id == "gpt-3-5-turbo-instruct"

        # Parent still resolves correctly
        r = resolver.resolve("openrouter", "openai/gpt-3.5-turbo")
        assert r.canonical_id == "gpt-3-5-turbo"

        # -preview must reach its own canonical
        r = resolver.resolve("openrouter", "google/gemini-2.5-pro-preview")
        assert r.canonical_id == "gemini-2-5-pro-preview"

        # -exp must NOT silently collapse into the parent when no
        # canonical exists for the exp variant. With no entry for
        # deepseek-v3-2-exp, the resolver returns miss so the merger
        # promotes it as a synthetic entity instead of merging into
        # deepseek-v3-2 with mixed pricing.
        r = resolver.resolve("openrouter", "deepseek/deepseek-v3.2-exp")
        assert r.canonical_id is None

    def test_quantization_tags_still_strip(self):
        """Hardware/quantization variants are genuinely the same logical
        model with different storage formats — these MUST still strip."""
        reg = _make_registry_with({
            "llama-3-8b": _make_entry("llama-3-8b", maker="Meta", family="Llama"),
        })
        resolver = CanonicalResolver(reg)
        for raw in ["meta-llama/llama-3-8b-fp8", "meta-llama/llama-3-8b-int4",
                    "meta-llama/llama-3-8b-bf16"]:
            r = resolver.resolve("openrouter", raw)
            assert r.canonical_id == "llama-3-8b", f"{raw} should strip to llama-3-8b"
