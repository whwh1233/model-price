"""Tests for the small pure helpers inside offering_merger.

These don't need network or a registry — they exercise the name
cleanup, cluster keying, and author prefix mapping that drive
synthetic entity creation.
"""

from datetime import datetime

from models import ModelPricing, Pricing
from services.offering_merger import (
    _maker_from_model_id,
    _round_price,
    _unmatched_cluster_key,
)


def _make_model(model_id: str, model_name: str = "") -> ModelPricing:
    return ModelPricing(
        id=f"openrouter:{model_id}",
        provider="openrouter",
        model_id=model_id,
        model_name=model_name or model_id,
        pricing=Pricing(input=1.0, output=2.0),
        capabilities=["text"],
        input_modalities=["text"],
        output_modalities=["text"],
        last_updated=datetime.utcnow(),
    )


class TestRoundPrice:
    def test_rounds_to_four_decimals(self):
        assert _round_price(0.19999999999999998) == 0.2

    def test_passes_through_clean_values(self):
        assert _round_price(3.0) == 3.0
        assert _round_price(0.0) == 0.0

    def test_handles_none(self):
        assert _round_price(None) is None

    def test_handles_invalid(self):
        assert _round_price("not a number") is None  # type: ignore[arg-type]


class TestUnmatchedClusterKey:
    def test_prefers_model_id_over_name(self):
        """model_id is more stable across providers and carries version
        information in the raw form we want to cluster by."""
        model = _make_model("moonshotai/kimi-k2.5", "MoonshotAI: Kimi K2.5")
        assert _unmatched_cluster_key(model) == "kimi-k2-5"

    def test_different_versions_stay_separate(self):
        """K2.5 and K2 Thinking must land in different clusters even
        though the model_name prefix is identical."""
        k25 = _make_model("moonshotai/kimi-k2.5", "MoonshotAI: Kimi K2.5")
        k2_thinking = _make_model("moonshotai/kimi-k2-thinking", "MoonshotAI: Kimi K2 Thinking")
        assert _unmatched_cluster_key(k25) != _unmatched_cluster_key(k2_thinking)

    def test_falls_back_to_name_when_id_is_too_short(self):
        model = _make_model("chat", "MoonshotAI: Kimi Chat")
        # "chat" is too short → name wins
        key = _unmatched_cluster_key(model)
        assert "kimi" in key or "moonshot" in key


class TestMakerFromModelId:
    def test_known_authors(self):
        assert _maker_from_model_id("anthropic/claude-3.5-sonnet") == "Anthropic"
        assert _maker_from_model_id("allenai/olmo-3-32b") == "AllenAI"
        assert _maker_from_model_id("meta-llama/llama-4-maverick") == "Meta"
        assert _maker_from_model_id("moonshotai/kimi-k2.5") == "Moonshot AI"

    def test_unknown_falls_back_to_titled_prefix(self):
        # No entry in AUTHOR_PREFIX_TO_MAKER → title-case the prefix
        assert _maker_from_model_id("somelab/weird-model") == "Somelab"

    def test_returns_none_for_nameless(self):
        assert _maker_from_model_id("") is None
        assert _maker_from_model_id(None) is None

    def test_returns_none_when_no_separator(self):
        assert _maker_from_model_id("justamodel") is None
