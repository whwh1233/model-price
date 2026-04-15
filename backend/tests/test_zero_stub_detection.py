"""Tests for LiteLLM zero-price stub detection.

LiteLLM publishes rows with `input_cost_per_token: 0` for two classes
of models: genuinely new releases that don't have USD pricing yet
(kimi-k2-thinking-251104), and non-USD-priced Chinese labs
(volcengine Doubao, deepseek-v3-2-251201 on volcengine). Neither is
truly free. The detector must null them out before they reach
alternatives or drift reporting.
"""

from services.litellm_registry import _is_zero_stub_row


class TestZeroStubDetection:
    def test_doubao_embedding_placeholder_is_stub(self):
        raw = {
            "mode": "embedding",
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
            "litellm_provider": "volcengine",
        }
        assert _is_zero_stub_row(raw) is True

    def test_new_release_chat_placeholder_is_stub(self):
        """kimi-k2-thinking-251104 shape: brand-new model, USD unknown."""
        raw = {
            "mode": "chat",
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
            "litellm_provider": "volcengine",
        }
        assert _is_zero_stub_row(raw) is True

    def test_embedding_with_real_price_not_stub(self):
        """Cohere embed-v4: input has a real price, output is 0 because
        embedding models don't bill per output token. This must stay."""
        raw = {
            "mode": "embedding",
            "input_cost_per_token": 1.2e-07,
            "output_cost_per_token": 0.0,
        }
        assert _is_zero_stub_row(raw) is False

    def test_rerank_all_zero_not_stub(self):
        """Rerank endpoints legitimately have no per-token cost (they're
        priced per request). We still skip them downstream, but not here."""
        raw = {
            "mode": "rerank",
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
        }
        assert _is_zero_stub_row(raw) is False

    def test_real_chat_model_not_stub(self):
        raw = {
            "mode": "chat",
            "input_cost_per_token": 3e-6,
            "output_cost_per_token": 1.5e-5,
        }
        assert _is_zero_stub_row(raw) is False

    def test_missing_both_prices_not_stub(self):
        """None is different from 0: None means "no field", not "zero"."""
        raw = {"mode": "chat"}
        assert _is_zero_stub_row(raw) is False

    def test_zero_input_with_cache_price_not_stub(self):
        """If the row carries any other pricing signal (cache read, batch,
        image input), it's not a placeholder."""
        raw = {
            "mode": "chat",
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
            "cache_read_input_token_cost": 2e-7,
        }
        assert _is_zero_stub_row(raw) is False

    def test_image_gen_all_zero_is_stub(self):
        """Image gen models priced per-image sometimes land in LiteLLM
        with $0 per-token entries. Without input_cost_per_image signal
        they're placeholders."""
        raw = {
            "mode": "image_generation",
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
        }
        assert _is_zero_stub_row(raw) is True

    def test_image_gen_with_per_image_cost_not_stub(self):
        raw = {
            "mode": "image_generation",
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
            "input_cost_per_image": 0.04,
        }
        assert _is_zero_stub_row(raw) is False
