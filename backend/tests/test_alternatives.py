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
