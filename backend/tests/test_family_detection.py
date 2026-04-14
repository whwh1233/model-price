"""Tests for FAMILY_PATTERNS matching order.

Substring-based family detection is order-sensitive: a more specific
pattern must appear before a more general one whose needles would
also match. This module captures every "ordering bug" we've hit so
they don't regress silently.
"""

import pytest

from services.litellm_registry import detect_family_maker


class TestFamilyOrdering:
    @pytest.mark.parametrize(
        "canonical_id,expected_family,expected_maker",
        [
            # Codex must win over GPT (both match "gpt-" needle space).
            ("gpt-5-codex", "Codex", "OpenAI"),
            ("gpt-5-1-codex", "Codex", "OpenAI"),
            ("gpt-5-1-codex-max", "Codex", "OpenAI"),
            ("gpt-5-1-codex-mini", "Codex", "OpenAI"),
            ("codex-mini", "Codex", "OpenAI"),
            # Cogito must win over Llama (Cogito names contain "llama").
            ("cogito-v1-70b", "Cogito", "Deep Cogito"),
            # Regular GPT still lands on GPT.
            ("gpt-4o", "GPT", "OpenAI"),
            ("gpt-4o-mini", "GPT", "OpenAI"),
            ("gpt-5", "GPT", "OpenAI"),
            ("chatgpt-4o", "GPT", "OpenAI"),
            # O-Series hits OpenAI O-Series, not GPT.
            ("o1-mini", "OpenAI O-Series", "OpenAI"),
            ("o3-pro", "OpenAI O-Series", "OpenAI"),
            ("o4-mini", "OpenAI O-Series", "OpenAI"),
            # Claude family
            ("claude-sonnet-4-5", "Claude", "Anthropic"),
            ("claude-haiku-4-5", "Claude", "Anthropic"),
            # Gemini family
            ("gemini-2-5-pro", "Gemini", "Google"),
            ("gemini-3-flash", "Gemini", "Google"),
            # Moonshot Kimi — was missing until Phase 1 fix.
            ("kimi-k2-5", "Kimi", "Moonshot AI"),
            ("kimi-k2-thinking", "Kimi", "Moonshot AI"),
            ("moonshot-v1-8k", "Moonshot", "Moonshot AI"),
            # Chinese / third-party labs.
            ("glm-4-5", "GLM", "Z.AI"),
            ("minimax-m2", "MiniMax", "MiniMax"),
            ("qwen3-max", "Qwen", "Alibaba"),
            ("deepseek-chat", "DeepSeek", "DeepSeek"),
            ("grok-4", "Grok", "xAI"),
            # Legacy OpenAI completion models were previously Unknown.
            ("babbage-002", "GPT", "OpenAI"),
            ("davinci-002", "GPT", "OpenAI"),
        ],
    )
    def test_canonical_id_maps_to_family(self, canonical_id, expected_family, expected_maker):
        family, maker = detect_family_maker(canonical_id, canonical_id)
        assert family == expected_family, f"{canonical_id} → expected {expected_family}, got {family}"
        assert maker == expected_maker, f"{canonical_id} → expected {expected_maker}, got {maker}"

    def test_unknown_model_returns_other(self):
        family, maker = detect_family_maker("some-obscure-fine-tune", "Some Obscure Fine Tune")
        assert family == "Other"
        assert maker == "Unknown"
