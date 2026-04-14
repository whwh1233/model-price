"""v2 API router — Phase 0 stub serving fixture data.

Contract: docs/plans/v2-api-contract.md
Design:   docs/plans/2026-04-14-v2-redesign-design.md §4–§5

Phase 1 will replace the fixture loader with the real
LiteLLM registry + offering merger pipeline. The endpoint
shapes and query parameters MUST remain identical to what
this stub exposes — that's the whole point of freezing the
contract at Phase 0.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2", tags=["v2"])

FIXTURE_PATH = Path(__file__).parent / "data" / "v2" / "fixtures" / "sample.json"

MAX_COMPARE_IDS = 4


def _load_fixture() -> dict[str, Any]:
    """Load fixture JSON on every request.

    Phase 0 accepts the per-request read cost for simplicity and
    hot-reload friendliness; Phase 1 replaces this with a real
    registry that's loaded once at startup.
    """
    try:
        return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.error("v2 fixture not found at %s", FIXTURE_PATH)
        raise HTTPException(
            status_code=500,
            detail={"code": "internal_error", "message": "v2 fixture missing"},
        )


def _entities() -> list[dict[str, Any]]:
    return _load_fixture().get("entities", [])


def _strip_to_list_item(entity: dict[str, Any]) -> dict[str, Any]:
    """Shape an entity into the list-view item contract.

    Includes the full entity metadata plus an embedded
    primary_offering, and excludes offerings[] and alternatives[].
    """
    result = {
        key: value
        for key, value in entity.items()
        if key not in ("offerings", "alternatives")
    }
    offerings = entity.get("offerings", [])
    primary_provider = entity.get("primary_offering_provider")
    primary = next(
        (o for o in offerings if o.get("provider") == primary_provider),
        offerings[0] if offerings else None,
    )
    result["primary_offering"] = primary
    return result


def _find_entity(slug: str) -> dict[str, Any] | None:
    for entity in _entities():
        if entity.get("slug") == slug:
            return entity
    return None


def _sort_entities(
    entities: list[dict[str, Any]],
    sort: str,
    order: str,
) -> list[dict[str, Any]]:
    reverse = order == "desc"

    def _price(entity: dict[str, Any], field: str) -> float:
        item = _strip_to_list_item(entity)
        primary = item.get("primary_offering") or {}
        pricing = primary.get("pricing") or {}
        value = pricing.get(field)
        return float(value) if value is not None else float("inf")

    if sort == "input":
        return sorted(entities, key=lambda e: _price(e, "input"), reverse=reverse)
    if sort == "output":
        return sorted(entities, key=lambda e: _price(e, "output"), reverse=reverse)
    if sort == "context":
        return sorted(
            entities,
            key=lambda e: e.get("context_length") or 0,
            reverse=reverse,
        )
    return sorted(entities, key=lambda e: e.get("name", "").lower(), reverse=reverse)


# ---------- Endpoints ----------


@router.get("/entities")
def list_entities(
    q: str | None = Query(None, description="Substring search on name/canonical_id"),
    family: str | None = Query(None),
    maker: str | None = Query(None),
    capability: str | None = Query(None),
    min_context: int | None = Query(None),
    max_input_price: float | None = Query(None),
    sort: str = Query("name", pattern="^(name|input|output|context)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
) -> list[dict[str, Any]]:
    results = _entities()

    if q:
        ql = q.lower()
        results = [
            e
            for e in results
            if ql in e.get("name", "").lower()
            or ql in e.get("canonical_id", "").lower()
            or ql in e.get("family", "").lower()
        ]
    if family:
        results = [e for e in results if e.get("family") == family]
    if maker:
        results = [e for e in results if e.get("maker") == maker]
    if capability:
        results = [e for e in results if capability in (e.get("capabilities") or [])]
    if min_context is not None:
        results = [e for e in results if (e.get("context_length") or 0) >= min_context]
    if max_input_price is not None:
        def _input_price(entity: dict[str, Any]) -> float:
            item = _strip_to_list_item(entity)
            primary = item.get("primary_offering") or {}
            pricing = primary.get("pricing") or {}
            value = pricing.get("input")
            return float(value) if value is not None else float("inf")

        results = [e for e in results if _input_price(e) <= max_input_price]

    results = _sort_entities(results, sort, order)
    return [_strip_to_list_item(e) for e in results]


@router.get("/entities/{slug}")
def get_entity(slug: str) -> dict[str, Any]:
    entity = _find_entity(slug)
    if not entity:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "not_found",
                "message": f"Entity '{slug}' not found",
            },
        )
    return {
        "entity": {
            key: value
            for key, value in entity.items()
            if key not in ("offerings", "alternatives")
        },
        "offerings": entity.get("offerings", []),
        "alternatives": entity.get("alternatives", []),
    }


@router.get("/search")
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
) -> list[dict[str, Any]]:
    ql = q.lower()
    scored: list[tuple[int, dict[str, Any]]] = []

    for entity in _entities():
        name_lower = entity.get("name", "").lower()
        canonical_lower = entity.get("canonical_id", "").lower()

        if name_lower == ql or canonical_lower == ql:
            rank = 0
        elif name_lower.startswith(ql) or canonical_lower.startswith(ql):
            rank = 1
        elif ql in name_lower or ql in canonical_lower:
            rank = 2
        elif ql in entity.get("family", "").lower():
            rank = 3
        else:
            continue

        item = _strip_to_list_item(entity)
        primary = item.get("primary_offering") or {}
        pricing = primary.get("pricing") or {}
        scored.append(
            (
                rank,
                {
                    "canonical_id": entity["canonical_id"],
                    "slug": entity["slug"],
                    "name": entity["name"],
                    "family": entity.get("family"),
                    "maker": entity.get("maker"),
                    "primary_input_price": pricing.get("input"),
                    "primary_output_price": pricing.get("output"),
                },
            )
        )

    scored.sort(key=lambda pair: (pair[0], pair[1]["name"].lower()))
    return [item for _, item in scored[:limit]]


@router.get("/compare")
def compare(
    ids: str = Query(..., description="Comma-separated slugs, max 4"),
) -> dict[str, Any]:
    slugs = [s.strip() for s in ids.split(",") if s.strip()]
    if not slugs:
        raise HTTPException(
            status_code=400,
            detail={"code": "bad_request", "message": "ids must not be empty"},
        )
    if len(slugs) > MAX_COMPARE_IDS:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "too_many_ids",
                "message": f"compare supports up to {MAX_COMPARE_IDS} entities",
            },
        )

    entities: list[dict[str, Any]] = []
    missing: list[str] = []
    capability_sets: list[set[str]] = []

    for slug in slugs:
        entity = _find_entity(slug)
        if entity is None:
            missing.append(slug)
            continue
        entities.append(
            {
                "entity": {
                    key: value
                    for key, value in entity.items()
                    if key not in ("offerings", "alternatives")
                },
                "offerings": entity.get("offerings", []),
                "alternatives": entity.get("alternatives", []),
            }
        )
        capability_sets.append(set(entity.get("capabilities") or []))

    common = sorted(set.intersection(*capability_sets)) if capability_sets else []

    return {
        "entities": entities,
        "common_capabilities": common,
        "requested_ids": slugs,
        "missing_ids": missing,
    }


@router.get("/stats")
def stats() -> dict[str, Any]:
    fixture = _load_fixture()
    return fixture.get(
        "stats",
        {
            "total_entities": len(fixture.get("entities", [])),
            "total_offerings": sum(
                len(e.get("offerings", [])) for e in fixture.get("entities", [])
            ),
            "makers": len({e.get("maker") for e in fixture.get("entities", [])}),
            "families": len({e.get("family") for e in fixture.get("entities", [])}),
            "last_refresh": fixture.get("generated_at"),
            "fixture": True,
        },
    )


@router.get("/drift")
def drift() -> dict[str, Any]:
    return _load_fixture().get("drift", {})


@router.post("/refresh")
def refresh() -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={
            "ok": False,
            "reason": "phase_0_stub",
            "message": "v2 refresh pipeline is implemented in Phase 1",
        },
    )
