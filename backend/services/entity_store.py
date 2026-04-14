"""Thread-safe in-memory store for v2 entities and offerings.

Wraps the on-disk snapshot with convenient lookups used by api_v2.py:
- list / filter / sort entities
- fetch by slug with offerings + alternatives
- fuzzy search
- compare lookup
- stats + drift

The store is loaded once at startup and mutated only by
`refresh_from_pipeline`, which swaps the internal state atomically.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from models.v2 import (
    AlternativeV2,
    CompareResultV2,
    DriftReportV2,
    EntityCoreV2,
    EntityDetailV2,
    EntityListItemV2,
    EntityStoreSnapshot,
    OfferingV2,
    SearchResultV2,
    StatsV2,
)

from .alternatives import compute_alternatives
from .drift_reporter import DRIFT_PATH
from .offering_merger import load_snapshot, run_refresh_pipeline

logger = logging.getLogger(__name__)

FIXTURE_PATH = Path(__file__).parent.parent / "data" / "v2" / "fixtures" / "sample.json"
MAX_COMPARE_IDS = 4


class EntityStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entities: List[EntityCoreV2] = []
        self._by_slug: Dict[str, EntityCoreV2] = {}
        self._offerings_by_entity: Dict[str, List[OfferingV2]] = {}
        self._last_refresh: Optional[datetime] = None
        self._is_fixture: bool = True

    # ─── Lifecycle ────────────────────────────────────────────

    def load_from_disk_or_fixture(self) -> None:
        """Load in priority order: entities.json → fixture fallback."""
        with self._lock:
            loaded = load_snapshot()
            if loaded is not None:
                snapshot, offerings_by_entity = loaded
                if snapshot.entities:
                    self._apply_snapshot(
                        snapshot,
                        offerings_by_entity,
                        is_fixture=False,
                    )
                    logger.info(
                        "EntityStore: loaded %s entities from disk",
                        len(self._entities),
                    )
                    return

            self._load_fixture()

    def _load_fixture(self) -> None:
        if not FIXTURE_PATH.exists():
            logger.warning("EntityStore: no fixture at %s", FIXTURE_PATH)
            self._entities = []
            self._by_slug = {}
            self._offerings_by_entity = {}
            self._is_fixture = True
            self._last_refresh = None
            return

        with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        entities: List[EntityCoreV2] = []
        offerings_by_entity: Dict[str, List[OfferingV2]] = {}
        for raw in payload.get("entities", []):
            core_payload = {k: v for k, v in raw.items() if k not in ("offerings", "alternatives")}
            entity = EntityCoreV2.model_validate(core_payload)
            entities.append(entity)
            offerings_by_entity[entity.slug] = [
                OfferingV2.model_validate(o) for o in raw.get("offerings", [])
            ]

        self._entities = entities
        self._by_slug = {e.slug: e for e in entities}
        self._offerings_by_entity = offerings_by_entity
        self._is_fixture = True
        self._last_refresh = datetime.utcnow()
        logger.info(
            "EntityStore: loaded %s entities from fixture (phase 0 stub data)",
            len(entities),
        )

    def _apply_snapshot(
        self,
        snapshot: EntityStoreSnapshot,
        offerings_by_entity: Dict[str, List[OfferingV2]],
        *,
        is_fixture: bool,
    ) -> None:
        self._entities = list(snapshot.entities)
        self._by_slug = {e.slug: e for e in self._entities}
        # Ensure every entity has an entry (even empty) for downstream code.
        self._offerings_by_entity = {
            e.slug: list(offerings_by_entity.get(e.slug, []))
            for e in self._entities
        }
        self._is_fixture = is_fixture
        self._last_refresh = snapshot.generated_at

    async def refresh_from_pipeline(self, force_network: bool = True) -> DriftReportV2:
        snapshot, report, offerings_by_entity = await run_refresh_pipeline(
            force_network=force_network
        )
        with self._lock:
            self._apply_snapshot(snapshot, offerings_by_entity, is_fixture=False)
        return report

    # ─── Reads ────────────────────────────────────────────────

    @property
    def is_fixture(self) -> bool:
        return self._is_fixture

    def all_entities(self) -> List[EntityCoreV2]:
        with self._lock:
            return list(self._entities)

    def get(self, slug: str) -> Optional[EntityCoreV2]:
        with self._lock:
            return self._by_slug.get(slug)

    def offerings_for(self, slug: str) -> List[OfferingV2]:
        with self._lock:
            return list(self._offerings_by_entity.get(slug, []))

    def stats(self) -> StatsV2:
        with self._lock:
            makers = {e.maker for e in self._entities}
            families = {e.family for e in self._entities}
            return StatsV2(
                total_entities=len(self._entities),
                total_offerings=sum(len(v) for v in self._offerings_by_entity.values()),
                makers=len(makers),
                families=len(families),
                last_refresh=self._last_refresh,
                fixture=self._is_fixture,
            )

    def list_filtered(
        self,
        *,
        q: Optional[str] = None,
        family: Optional[str] = None,
        maker: Optional[str] = None,
        capability: Optional[str] = None,
        min_context: Optional[int] = None,
        max_input_price: Optional[float] = None,
        sort: str = "name",
        order: str = "asc",
    ) -> List[EntityListItemV2]:
        with self._lock:
            entities = list(self._entities)

        if q:
            ql = q.lower()
            entities = [
                e
                for e in entities
                if ql in (e.name or "").lower()
                or ql in (e.canonical_id or "").lower()
                or ql in (e.family or "").lower()
            ]
        if family:
            entities = [e for e in entities if e.family == family]
        if maker:
            entities = [e for e in entities if e.maker == maker]
        if capability:
            entities = [e for e in entities if capability in (e.capabilities or [])]
        if min_context is not None:
            entities = [e for e in entities if (e.context_length or 0) >= min_context]

        items: List[EntityListItemV2] = []
        for entity in entities:
            primary = self._primary_offering(entity)
            if max_input_price is not None and primary is not None and primary.pricing.input is not None:
                if primary.pricing.input > max_input_price:
                    continue
            items.append(self._to_list_item(entity, primary))

        return self._sort_items(items, sort=sort, order=order)

    def detail(self, slug: str) -> Optional[EntityDetailV2]:
        with self._lock:
            entity = self._by_slug.get(slug)
            if entity is None:
                return None
            offerings = list(self._offerings_by_entity.get(slug, []))
            alternatives = compute_alternatives(
                entity,
                self._entities,
                self._offerings_by_entity,
                limit=3,
            )
            return EntityDetailV2(entity=entity, offerings=offerings, alternatives=alternatives)

    def search(self, q: str, limit: int = 10) -> List[SearchResultV2]:
        ql = q.lower().strip()
        if not ql:
            return []
        with self._lock:
            scored: list[tuple[int, SearchResultV2]] = []
            for entity in self._entities:
                name_lower = (entity.name or "").lower()
                canonical_lower = (entity.canonical_id or "").lower()
                if name_lower == ql or canonical_lower == ql:
                    rank = 0
                elif name_lower.startswith(ql) or canonical_lower.startswith(ql):
                    rank = 1
                elif ql in name_lower or ql in canonical_lower:
                    rank = 2
                elif ql in (entity.family or "").lower():
                    rank = 3
                else:
                    continue
                primary = self._primary_offering(entity)
                scored.append(
                    (
                        rank,
                        SearchResultV2(
                            canonical_id=entity.canonical_id,
                            slug=entity.slug,
                            name=entity.name,
                            family=entity.family,
                            maker=entity.maker,
                            primary_input_price=(primary.pricing.input if primary else None),
                            primary_output_price=(primary.pricing.output if primary else None),
                        ),
                    )
                )
            scored.sort(key=lambda pair: (pair[0], pair[1].name.lower()))
            return [item for _, item in scored[:limit]]

    def compare(self, ids: List[str]) -> CompareResultV2:
        cleaned = [s.strip() for s in ids if s.strip()]
        with self._lock:
            entities: List[EntityDetailV2] = []
            missing: List[str] = []
            cap_sets: List[set[str]] = []
            for slug in cleaned:
                detail = self.detail(slug)
                if detail is None:
                    missing.append(slug)
                    continue
                entities.append(detail)
                cap_sets.append(set(detail.entity.capabilities or []))
            common = sorted(set.intersection(*cap_sets)) if cap_sets else []
        return CompareResultV2(
            entities=entities,
            common_capabilities=common,
            requested_ids=cleaned,
            missing_ids=missing,
        )

    @staticmethod
    def drift_report() -> Optional[DriftReportV2]:
        if not DRIFT_PATH.exists():
            return None
        try:
            raw = json.loads(DRIFT_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        raw.pop("_snapshot_slugs", None)
        try:
            return DriftReportV2.model_validate(raw)
        except Exception as exc:
            logger.warning("drift.json unparseable: %s", exc)
            return None

    # ─── Internals ────────────────────────────────────────────

    def _primary_offering(self, entity: EntityCoreV2) -> Optional[OfferingV2]:
        offerings = self._offerings_by_entity.get(entity.slug, [])
        if not offerings:
            return None
        for off in offerings:
            if off.provider == entity.primary_offering_provider:
                return off
        return offerings[0]

    def _to_list_item(
        self, entity: EntityCoreV2, primary: Optional[OfferingV2]
    ) -> EntityListItemV2:
        return EntityListItemV2(
            **entity.model_dump(),
            primary_offering=primary,
        )

    def _sort_items(
        self, items: List[EntityListItemV2], *, sort: str, order: str
    ) -> List[EntityListItemV2]:
        reverse = order == "desc"

        def price_key(item: EntityListItemV2, field: str) -> float:
            if item.primary_offering is None:
                return float("inf")
            value = getattr(item.primary_offering.pricing, field)
            return float(value) if value is not None else float("inf")

        if sort == "input":
            return sorted(items, key=lambda i: price_key(i, "input"), reverse=reverse)
        if sort == "output":
            return sorted(items, key=lambda i: price_key(i, "output"), reverse=reverse)
        if sort == "context":
            return sorted(
                items,
                key=lambda i: i.context_length or 0,
                reverse=reverse,
            )
        return sorted(items, key=lambda i: (i.name or "").lower(), reverse=reverse)


# Module-level singleton
_store = EntityStore()


def get_store() -> EntityStore:
    return _store
