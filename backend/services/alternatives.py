"""Same-tier cheaper alternatives for an entity.

Scores every other entity by:
  score = capability_overlap × (1 + max(0, -delta_input_pct/100))

The top-3 strictly cheaper hits are returned. If fewer than 3 are
strictly cheaper, the tail is filled with closest-capability matches
that may be at-price or more expensive so the UI always has something
to show for well-priced entries.
"""

from __future__ import annotations

from typing import Iterable, List

from models.v2 import AlternativeV2, EntityCoreV2, OfferingV2


def _primary_price(
    entity: EntityCoreV2,
    offerings_by_entity: dict[str, List[OfferingV2]],
) -> tuple[float | None, float | None]:
    offerings = offerings_by_entity.get(entity.slug, [])
    primary = next(
        (o for o in offerings if o.provider == entity.primary_offering_provider),
        offerings[0] if offerings else None,
    )
    if not primary:
        return None, None
    return primary.pricing.input, primary.pricing.output


def _overlap(reference: set[str], candidate: set[str]) -> float:
    if not reference and not candidate:
        return 1.0
    union = reference | candidate
    if not union:
        return 0.0
    return len(reference & candidate) / len(union)


def _delta_pct(reference: float | None, candidate: float | None) -> float | None:
    if reference is None or candidate is None:
        return None
    if reference == 0:
        return 0.0 if candidate == 0 else float("inf")
    return round(((candidate - reference) / reference) * 100.0, 1)


def compute_alternatives(
    target: EntityCoreV2,
    all_entities: Iterable[EntityCoreV2],
    offerings_by_entity: dict[str, List[OfferingV2]],
    limit: int = 3,
) -> List[AlternativeV2]:
    ref_input, ref_output = _primary_price(target, offerings_by_entity)
    if ref_input is None:
        return []

    target_caps = set(target.capabilities or [])
    target_mode = target.mode or "chat"

    scored: list[tuple[float, float, AlternativeV2]] = []
    for entity in all_entities:
        if entity.slug == target.slug:
            continue
        if (entity.mode or "chat") != target_mode:
            continue
        overlap = _overlap(target_caps, set(entity.capabilities or []))
        if overlap < 0.5:
            continue
        cand_input, cand_output = _primary_price(entity, offerings_by_entity)
        if cand_input is None:
            continue
        delta_in = _delta_pct(ref_input, cand_input)
        delta_out = _delta_pct(ref_output, cand_output)
        if delta_in is None:
            continue
        # Composite score: prefers cheaper + higher overlap
        savings = max(0.0, -delta_in / 100.0)
        score = overlap * (1.0 + savings)
        scored.append(
            (
                score,
                delta_in,  # secondary sort key (more negative = cheaper)
                AlternativeV2(
                    canonical_id=entity.canonical_id,
                    name=entity.name,
                    delta_input_pct=delta_in,
                    delta_output_pct=delta_out if delta_out is not None else 0.0,
                    capability_overlap=round(overlap, 3),
                ),
            )
        )

    if not scored:
        return []

    # Prefer strictly cheaper, otherwise fall back to highest overlap
    cheaper = [s for s in scored if s[2].delta_input_pct < 0]
    cheaper.sort(key=lambda s: (-s[0], s[1]))
    picks = cheaper[:limit]

    if len(picks) < limit:
        backup = [s for s in scored if s[2].delta_input_pct >= 0]
        backup.sort(key=lambda s: (-s[0], s[1]))
        picks.extend(backup[: limit - len(picks)])

    return [alt for _, _, alt in picks]
