"""Drift reporter — self-healing data quality surface.

Produces a drift.json after each v2 refresh containing:
- unmatched provider models (provider_model_id → could not be resolved)
- entities that are new / removed since the previous refresh
- entities sourced only from LiteLLM (no provider offering)
- price drift > 5% between primary provider and LiteLLM reference
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from models.v2 import (
    DriftCountsV2,
    DriftReportV2,
    EntityCoreV2,
    OfferingV2,
    PriceDriftItem,
    UnmatchedProviderModel,
)
from .litellm_registry import LiteLLMRegistry

logger = logging.getLogger(__name__)

DRIFT_PATH = Path(__file__).parent.parent / "data" / "v2" / "drift.json"
PRICE_DRIFT_THRESHOLD_PCT = 5.0


class DriftReporter:
    def __init__(self) -> None:
        self.unmatched: List[UnmatchedProviderModel] = []

    def record_unmatched(self, provider: str, model_id: str, tried: Iterable[str]) -> None:
        self.unmatched.append(
            UnmatchedProviderModel(
                provider=provider,
                model_id=model_id,
                tried_aliases=list(tried),
            )
        )

    def build_report(
        self,
        *,
        entities: List[EntityCoreV2],
        offerings_by_entity: Dict[str, List[OfferingV2]],
        previous_slugs: set[str],
        registry: LiteLLMRegistry,
    ) -> DriftReportV2:
        current_slugs = {e.slug for e in entities}
        new_entities = sorted(current_slugs - previous_slugs)
        removed_entities = sorted(previous_slugs - current_slugs)

        total_offerings = sum(len(offerings_by_entity.get(s, [])) for s in current_slugs)

        orphan_entities = [
            e.slug
            for e in entities
            if all(
                o.source == "litellm_fallback"
                for o in offerings_by_entity.get(e.slug, [])
            )
        ]

        price_drift_items = self._price_drift(entities, offerings_by_entity, registry)

        counts = DriftCountsV2(
            entities_total=len(entities),
            entities_new=len(new_entities),
            entities_removed=len(removed_entities),
            offerings_total=total_offerings,
            unmatched_provider_models=len(self.unmatched),
            orphan_entities=len(orphan_entities),
            price_drift_items=len(price_drift_items),
        )

        return DriftReportV2(
            generated_at=datetime.utcnow(),
            counts=counts,
            unmatched_provider_models=self.unmatched,
            price_drift=price_drift_items,
            new_entities=new_entities,
            removed_entities=removed_entities,
            orphan_entities=orphan_entities,
            note=None,
        )

    def _price_drift(
        self,
        entities: List[EntityCoreV2],
        offerings_by_entity: Dict[str, List[OfferingV2]],
        registry: LiteLLMRegistry,
    ) -> List[PriceDriftItem]:
        drifts: List[PriceDriftItem] = []
        for entity in entities:
            litellm_entry = registry.get(entity.canonical_id)
            if not litellm_entry:
                continue
            for offering in offerings_by_entity.get(entity.slug, []):
                if offering.source == "litellm_fallback":
                    continue
                for field, ref in (
                    ("input", litellm_entry.input_price),
                    ("output", litellm_entry.output_price),
                ):
                    candidate: Optional[float] = getattr(offering.pricing, field)
                    if ref is None or candidate is None:
                        continue
                    if ref == 0:
                        continue
                    delta_pct = ((candidate - ref) / ref) * 100.0
                    if abs(delta_pct) >= PRICE_DRIFT_THRESHOLD_PCT:
                        drifts.append(
                            PriceDriftItem(
                                entity=entity.slug,
                                provider=offering.provider,
                                field=field,
                                provider_value=candidate,
                                litellm_value=ref,
                                delta_pct=round(delta_pct, 2),
                            )
                        )
        return drifts

    @staticmethod
    def load_previous_slugs() -> set[str]:
        if not DRIFT_PATH.exists():
            return set()
        try:
            data = json.loads(DRIFT_PATH.read_text(encoding="utf-8"))
            snapshot = data.get("_snapshot_slugs") or []
            return set(snapshot)
        except (OSError, json.JSONDecodeError):
            return set()

    @staticmethod
    def save_report(report: DriftReportV2, current_slugs: set[str]) -> None:
        DRIFT_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = report.model_dump(mode="json")
        payload["_snapshot_slugs"] = sorted(current_slugs)
        DRIFT_PATH.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
