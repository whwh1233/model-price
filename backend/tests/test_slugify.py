"""Tests for slug normalization and version suffix stripping.

These functions are the backbone of canonical resolution — a change to
their behaviour cascades to entity identity, so they get thorough
coverage including regression cases captured during Phase 1.
"""

from services.litellm_registry import slugify, strip_version_suffix


class TestSlugify:
    def test_lowercases(self):
        assert slugify("Claude-Sonnet-4-5") == "claude-sonnet-4-5"

    def test_drops_leading_provider_prefix(self):
        assert slugify("bedrock/anthropic.claude-sonnet-4-5") == "anthropic-claude-sonnet-4-5"
        assert slugify("openrouter/google/gemini-2.5-pro") == "google-gemini-2-5-pro"

    def test_flattens_slashes(self):
        assert slugify("meta-llama/llama-4-maverick") == "llama-4-maverick"

    def test_flattens_dots(self):
        assert slugify("claude-sonnet-4.5") == "claude-sonnet-4-5"
        assert slugify("gpt-3.5-turbo") == "gpt-3-5-turbo"

    def test_collapses_special_chars(self):
        assert slugify("claude-sonnet-4-5:beta") == "claude-sonnet-4-5-beta"
        assert slugify("claude sonnet 4-5") == "claude-sonnet-4-5"

    def test_strips_leading_trailing_dashes(self):
        assert slugify("--claude--") == "claude"

    def test_empty_and_whitespace(self):
        assert slugify("") == ""
        assert slugify("   ") == ""

    def test_preserves_multi_slash_prefix_style(self):
        # "openrouter/anthropic/claude-3.5-sonnet" → drops only first segment
        assert slugify("openrouter/anthropic/claude-3.5-sonnet") == "anthropic-claude-3-5-sonnet"


class TestStripVersionSuffix:
    def test_bedrock_v1_colon_0(self):
        assert strip_version_suffix("claude-sonnet-4-5-v1-0") == "claude-sonnet-4-5"
        assert strip_version_suffix("claude-sonnet-4-5-v2-0") == "claude-sonnet-4-5"

    def test_eight_digit_date(self):
        assert strip_version_suffix("claude-sonnet-4-5-20250929") == "claude-sonnet-4-5"
        assert strip_version_suffix("gpt-4o-20241120") == "gpt-4o"

    def test_yyyy_mm_dd(self):
        assert strip_version_suffix("gpt-4o-2024-11-20") == "gpt-4o"

    def test_preview_latest_exp_carry_identity(self):
        """Regression: -preview / -latest / -exp / -experimental / -instruct
        used to be stripped as "packaging variants" but they carry real
        product identity. Stripping them collapsed gpt-3.5-turbo-instruct
        → gpt-3-5-turbo and gemini-2.5-pro-preview → gemini-2.5-pro,
        producing entities with mixed pricing from genuinely distinct
        products. They must survive normalization unchanged."""
        assert strip_version_suffix("gemini-3-pro-preview") == "gemini-3-pro-preview"
        assert strip_version_suffix("claude-sonnet-4-5-latest") == "claude-sonnet-4-5-latest"
        assert strip_version_suffix("claude-3-5-sonnet-experimental") == "claude-3-5-sonnet-experimental"
        assert strip_version_suffix("deepseek-v3-2-exp") == "deepseek-v3-2-exp"
        assert strip_version_suffix("gpt-3-5-turbo-instruct") == "gpt-3-5-turbo-instruct"

    def test_quantization_tags_stripped(self):
        """Pure storage/hardware variants ARE the same logical model
        and still strip — fp8/fp16/bf16/int4/int8/rlhf and the MoE
        expert-count tags."""
        assert strip_version_suffix("llama-3-70b-fp8") == "llama-3-70b"
        assert strip_version_suffix("llama-3-70b-bf16") == "llama-3-70b"
        assert strip_version_suffix("llama-3-70b-int4") == "llama-3-70b"
        # MoE expert counts
        assert strip_version_suffix("llama-4-maverick-17b-128e") == "llama-4-maverick-17b"

    def test_chained_quantization_and_version_collapse(self):
        """Storage variant + Bedrock version suffix should both strip."""
        assert (
            strip_version_suffix("llama-4-maverick-17b-128e-v1-0")
            == "llama-4-maverick-17b"
        )

    def test_instruct_no_longer_stripped_in_chain(self):
        """The -instruct tag carries identity (gpt-3.5-turbo-instruct
        is a separate product), so a chain like 128e-instruct-v1-0 only
        strips the -v1-0, leaving -instruct intact for downstream
        canonical lookup."""
        assert (
            strip_version_suffix("llama-4-maverick-17b-128e-instruct-v1-0")
            == "llama-4-maverick-17b-128e-instruct"
        )

    def test_preserves_bare_version_in_name(self):
        # "deepseek-v3" is a product name; the -v3 must NOT be treated as a
        # Bedrock version suffix. This is the regression we fixed in Phase 1.
        assert strip_version_suffix("deepseek-v3") == "deepseek-v3"
        assert strip_version_suffix("moonshot-v1-8k") == "moonshot-v1-8k"
        assert strip_version_suffix("deepseek-v3-2") == "deepseek-v3-2"

    def test_preserves_chat_and_base(self):
        # -chat / -base are legitimate product names and must not be stripped.
        assert strip_version_suffix("deepseek-chat") == "deepseek-chat"
        assert strip_version_suffix("qwen-base") == "qwen-base"

    def test_idempotent(self):
        already_clean = "claude-sonnet-4-5"
        assert strip_version_suffix(already_clean) == already_clean
