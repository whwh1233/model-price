"""Tests for compute_alternatives ranking.

The ranking function is a pure, testable math pipeline: capability
overlap × price savings. These tests cover the key behaviours the UI
depends on (strictly-cheaper picks first, overlap floor, tie-breaking).
"""

from datetime import datetime

from models.v2 import EntityCoreV2, OfferingV2, PricingV2
from services.alternatives import compute_alternatives


def _make_entity(
    slug: str,
    capabilities: list[str],
    input_price: float,
    output_price: float,
    mode: str = "chat",
) -> tuple[EntityCoreV2, OfferingV2]:
    entity = EntityCoreV2(
        canonical_id=slug,
        slug=slug,
        name=slug,
        family="Test",
        maker="Test",
        context_length=100_000,
        max_output_tokens=8_000,
        capabilities=capabilities,
        input_modalities=["text"],
        output_modalities=["text"],
        mode=mode,
        is_open_source=False,
        primary_offering_provider="test",
        sources=["test"],
        last_refreshed=datetime.utcnow(),
    )
    offering = OfferingV2(
        provider="test",
        provider_model_id=slug,
        pricing=PricingV2(input=input_price, output=output_price),
        batch_pricing=None,
        availability="ga",
        region=None,
        notes=None,
        last_updated=datetime.utcnow(),
        source="provider_api",
    )
    return entity, offering


class TestComputeAlternatives:
    def test_returns_strictly_cheaper_first(self):
        target, target_off = _make_entity(
            "premium", ["text", "vision", "tool_use", "reasoning"], 10.0, 30.0
        )
        cheaper, cheaper_off = _make_entity(
            "budget", ["text", "vision", "tool_use", "reasoning"], 1.0, 3.0
        )
        expensive, expensive_off = _make_entity(
            "pricey", ["text", "vision", "tool_use", "reasoning"], 20.0, 60.0
        )
        offerings = {
            "premium": [target_off],
            "budget": [cheaper_off],
            "pricey": [expensive_off],
        }
        result = compute_alternatives(
            target, [target, cheaper, expensive], offerings, limit=3
        )
        # Budget (cheaper) must be first
        assert result[0].canonical_id == "budget"
        # Budget should report -90% input delta
        assert result[0].delta_input_pct == -90.0

    def test_requires_minimum_capability_overlap(self):
        target, target_off = _make_entity(
            "target", ["text", "vision", "tool_use", "reasoning"], 10.0, 30.0
        )
        # Only 1 capability shared out of 4 target caps → overlap too low
        barely_related, barely_off = _make_entity(
            "barely", ["text"], 1.0, 3.0
        )
        offerings = {"target": [target_off], "barely": [barely_off]}
        result = compute_alternatives(target, [target, barely_related], offerings)
        assert len(result) == 0

    def test_skips_different_modes(self):
        target, target_off = _make_entity("target", ["text"], 10.0, 30.0, mode="chat")
        wrong_mode, wrong_off = _make_entity(
            "wrong", ["text"], 1.0, 3.0, mode="embedding"
        )
        offerings = {"target": [target_off], "wrong": [wrong_off]}
        result = compute_alternatives(target, [target, wrong_mode], offerings)
        assert len(result) == 0

    def test_excludes_self(self):
        target, target_off = _make_entity("same", ["text", "vision"], 10.0, 30.0)
        offerings = {"same": [target_off]}
        result = compute_alternatives(target, [target], offerings)
        assert len(result) == 0

    def test_returns_empty_when_target_has_no_price(self):
        target = EntityCoreV2(
            canonical_id="nameless",
            slug="nameless",
            name="nameless",
            family="Test",
            maker="Test",
            context_length=None,
            max_output_tokens=None,
            capabilities=["text"],
            input_modalities=["text"],
            output_modalities=["text"],
            mode="chat",
            is_open_source=None,
            primary_offering_provider="test",
            sources=[],
            last_refreshed=datetime.utcnow(),
        )
        result = compute_alternatives(target, [target], {})
        assert result == []

    def test_fills_with_similar_priced_when_no_cheaper_exists(self):
        target, target_off = _make_entity("cheapest", ["text", "vision"], 1.0, 3.0)
        pricier, pricier_off = _make_entity("pricier", ["text", "vision"], 2.0, 6.0)
        offerings = {"cheapest": [target_off], "pricier": [pricier_off]}
        result = compute_alternatives(target, [target, pricier], offerings, limit=3)
        # No strictly cheaper alternative → fall back to closest-capability
        assert len(result) == 1
        assert result[0].canonical_id == "pricier"
        assert result[0].delta_input_pct > 0  # it's more expensive

    def test_free_target_does_not_emit_infinite_delta(self):
        """Regression: a target priced at $0 must not produce inf deltas.

        When `_delta_pct(0, non_zero)` returned `inf`, the resulting
        AlternativeV2 serialized to an invalid JSON float and crashed
        `GET /api/v2/entities/{slug}` with a 500. Reproduced on
        kimi-k2-thinking-251104 (litellm-fallback only, input=0,
        output=0). See services/alternatives.py::_delta_pct.
        """
        import json
        import math

        free_target, free_off = _make_entity(
            "free-target", ["text", "reasoning"], 0.0, 0.0
        )
        paid, paid_off = _make_entity(
            "paid-rival", ["text", "reasoning"], 2.0, 6.0
        )
        offerings = {"free-target": [free_off], "paid-rival": [paid_off]}
        result = compute_alternatives(free_target, [free_target, paid], offerings)

        # Paid rivals must be filtered out (delta_in undefined, not inf).
        for alt in result:
            assert math.isfinite(alt.delta_input_pct), alt
            assert math.isfinite(alt.delta_output_pct), alt
            # Must round-trip through strict JSON (no inf/nan).
            json.dumps(alt.model_dump())

    def test_zero_priced_alternative_shows_as_cheapest(self):
        """A free alternative to a non-free target ranks as -100%."""
        paid_target, paid_off = _make_entity("paid", ["text"], 5.0, 15.0)
        free_alt, free_alt_off = _make_entity("free", ["text"], 0.0, 0.0)
        offerings = {"paid": [paid_off], "free": [free_alt_off]}
        result = compute_alternatives(paid_target, [paid_target, free_alt], offerings)
        assert len(result) == 1
        assert result[0].canonical_id == "free"
        assert result[0].delta_input_pct == -100.0


class TestModeAwareOverlapThreshold:
    """Embedding mode needs a higher overlap floor because
    `{embedding}` vs `{embedding, vision}` already hits 0.5."""

    def test_embedding_50_percent_overlap_rejected(self):
        target, target_off = _make_entity(
            "multi", ["embedding", "vision"], 0.12, 0.0, mode="embedding"
        )
        # Only `embedding` in common → overlap = 0.5 — below the 0.8 floor.
        plain, plain_off = _make_entity(
            "plain", ["embedding"], 0.02, 0.0, mode="embedding"
        )
        offerings = {"multi": [target_off], "plain": [plain_off]}
        result = compute_alternatives(target, [target, plain], offerings)
        assert result == []

    def test_embedding_full_overlap_accepted(self):
        target, target_off = _make_entity(
            "a", ["embedding", "vision"], 0.12, 0.0, mode="embedding"
        )
        rival, rival_off = _make_entity(
            "b", ["embedding", "vision"], 0.02, 0.0, mode="embedding"
        )
        offerings = {"a": [target_off], "b": [rival_off]}
        result = compute_alternatives(target, [target, rival], offerings)
        assert len(result) == 1
        assert result[0].canonical_id == "b"

    def test_embedding_output_delta_suppressed(self):
        """Output token axis doesn't exist for embeddings. Report 0.0
        rather than the meaningless `(0 - 0) / 0 → 0%` computation."""
        target, target_off = _make_entity(
            "a", ["embedding", "vision"], 0.12, 0.0, mode="embedding"
        )
        rival, rival_off = _make_entity(
            "b", ["embedding", "vision"], 0.02, 5.0, mode="embedding"
        )
        offerings = {"a": [target_off], "b": [rival_off]}
        result = compute_alternatives(target, [target, rival], offerings)
        assert len(result) == 1
        # Output delta suppressed even though candidate has a non-zero output price.
        assert result[0].delta_output_pct == 0.0

    def test_chat_mode_still_uses_default_threshold(self):
        """Chat is the only high-arity vocabulary; the 0.5 floor stays."""
        target, target_off = _make_entity(
            "chat-target", ["text", "vision", "tool_use", "reasoning"], 5.0, 15.0
        )
        # 2/4 caps shared → overlap 0.5, exactly on the floor.
        cheap, cheap_off = _make_entity(
            "chat-cheap", ["text", "vision"], 1.0, 3.0
        )
        offerings = {"chat-target": [target_off], "chat-cheap": [cheap_off]}
        result = compute_alternatives(target, [target, cheap], offerings)
        assert len(result) == 1
        assert result[0].canonical_id == "chat-cheap"
