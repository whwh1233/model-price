"""Offering merger — orchestrates v2 refresh pipeline.

Pipeline:
1. Load / refresh LiteLLM registry → canonical Entity skeletons
2. Run the existing v1 provider fetchers (unchanged) → List[ModelPricing]
3. For each v1 record, resolve to canonical_id via CanonicalResolver
4. Attach as Offering to the matching Entity; misses go to drift report
5. For any canonical Entity with zero provider offerings, synthesize
   a litellm_fallback Offering from the LiteLLM registry itself so the
   entity is still visible in the UI
6. Write entities.json + offerings.json + drift.json
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from models import ModelPricing
from models.v2 import (
    BatchPricingV2,
    EntityCoreV2,
    EntityStoreSnapshot,
    OfferingV2,
    PricingV2,
)
from providers.registry import ProviderRegistry

from .canonical import CanonicalResolver, build_resolver
from .drift_reporter import DriftReporter
from .litellm_registry import (
    APP_PROVIDER_TO_LITELLM,
    LiteLLMEntry,
    LiteLLMRegistry,
    get_registry,
)

logger = logging.getLogger(__name__)

V2_DATA_DIR = Path(__file__).parent.parent / "data" / "v2"
ENTITIES_PATH = V2_DATA_DIR / "entities.json"
OFFERINGS_PATH = V2_DATA_DIR / "offerings.json"
INDEX_PATH = V2_DATA_DIR / "index.json"


def _round_price(value: Optional[float]) -> Optional[float]:
    """Normalize float representation so JSON doesn't show 0.19999…"""
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None

# When multiple canonical providers offer the same entity, the UI needs
# one "primary" to show. We derive it from the entity's maker, falling
# back to whichever offering comes first.
AUTHORITY_BY_MAKER: Dict[str, List[str]] = {
    "Anthropic": ["anthropic", "aws_bedrock", "azure_openai", "openrouter"],
    "OpenAI": ["openai", "azure_openai", "openrouter"],
    "Google": ["google_gemini", "google_vertex_ai", "openrouter"],
    "xAI": ["xai", "openrouter"],
    "DeepSeek": ["deepseek", "openrouter"],
    "Meta": ["aws_bedrock", "openrouter"],
    "Mistral": ["aws_bedrock", "openrouter"],
    "Amazon": ["aws_bedrock"],
    "Cohere": ["aws_bedrock", "openrouter"],
    "AI21": ["aws_bedrock", "openrouter"],
    "NVIDIA": ["openrouter"],
}


class OfferingMerger:
    def __init__(
        self,
        registry: LiteLLMRegistry,
        resolver: CanonicalResolver,
    ) -> None:
        self.registry = registry
        self.resolver = resolver
        self.drift = DriftReporter()

    async def build_snapshot(
        self,
        v1_models_by_provider: Dict[str, List[ModelPricing]],
    ) -> Tuple[EntityStoreSnapshot, Dict[str, List[OfferingV2]]]:
        now = datetime.utcnow()
        entities: Dict[str, EntityCoreV2] = {}
        offerings_by_entity: Dict[str, List[OfferingV2]] = {}

        # ─── Pass 1: bootstrap entities from canonical LiteLLM entries
        for entry in self.registry.iter_canonical():
            slug = entry.canonical_id
            if slug in entities:
                continue
            entities[slug] = self._entity_from_litellm(entry, now)
            offerings_by_entity[slug] = []

        # ─── Pass 2: attach provider offerings
        attach_counts: Dict[str, int] = {}
        for provider_name, models in v1_models_by_provider.items():
            for model in models:
                resolution = self.resolver.resolve(provider_name, model.model_id)
                if not resolution.matched():
                    self.drift.record_unmatched(
                        provider=provider_name,
                        model_id=model.model_id,
                        tried=resolution.tried,
                    )
                    continue
                canonical_id = resolution.canonical_id
                assert canonical_id is not None
                if canonical_id not in entities:
                    entry = self.registry.get(canonical_id)
                    if entry is None:
                        continue
                    entities[canonical_id] = self._entity_from_litellm(entry, now)
                    offerings_by_entity.setdefault(canonical_id, [])

                offering = self._offering_from_v1(model, provider_name, now)
                offerings_by_entity[canonical_id].append(offering)
                # Also register the raw id as an alias for future lookups
                self.registry.register_alias(model.model_id, canonical_id)
                self.registry.register_alias(
                    f"{provider_name}:{model.model_id}", canonical_id
                )
                attach_counts[provider_name] = attach_counts.get(provider_name, 0) + 1

        # ─── Pass 3: synthesize LiteLLM-fallback offerings
        synthesized = 0
        for slug, entity in entities.items():
            if offerings_by_entity.get(slug):
                continue
            litellm_entry = self.registry.get(slug)
            if litellm_entry is None:
                continue
            fallback = self._offering_from_litellm(litellm_entry, now)
            if fallback is None:
                continue
            offerings_by_entity.setdefault(slug, []).append(fallback)
            synthesized += 1

        # ─── Pass 4: prune entities without any usable offering
        final_slugs = {
            slug for slug, offs in offerings_by_entity.items() if offs
        }
        pruned_entities = [entities[s] for s in sorted(final_slugs)]
        pruned_offerings: Dict[str, List[OfferingV2]] = {
            s: offerings_by_entity[s] for s in final_slugs
        }

        # ─── Pass 5: decide primary offering per entity and finalize sources
        for entity in pruned_entities:
            offs = pruned_offerings.get(entity.slug, [])
            primary = self._choose_primary(entity, offs)
            entity.primary_offering_provider = primary
            entity.sources = sorted({"litellm", *[o.provider for o in offs]})
            entity.last_refreshed = now

        flat_offerings: List[OfferingV2] = []
        for slug in sorted(pruned_offerings.keys()):
            flat_offerings.extend(pruned_offerings[slug])

        logger.info(
            "OfferingMerger: %s entities kept (of %s canonical); "
            "provider attach counts: %s; synthesized: %s",
            len(pruned_entities),
            len(entities),
            attach_counts,
            synthesized,
        )

        snapshot = EntityStoreSnapshot(
            version="v2.0",
            generated_at=now,
            entities=pruned_entities,
            offerings=flat_offerings,
        )
        return snapshot, pruned_offerings

    # ─── Helpers ─────────────────────────────────────────────

    def _entity_from_litellm(
        self, entry: LiteLLMEntry, now: datetime
    ) -> EntityCoreV2:
        return EntityCoreV2(
            canonical_id=entry.canonical_id,
            slug=entry.slug,
            name=self._pretty_model_name(entry),
            family=entry.family,
            maker=entry.maker,
            context_length=entry.context_length,
            max_output_tokens=entry.max_output_tokens,
            capabilities=entry.capabilities,
            input_modalities=entry.input_modalities,
            output_modalities=entry.output_modalities,
            mode=entry.mode,
            is_open_source=self._guess_open_source(entry.maker),
            primary_offering_provider="litellm",
            sources=["litellm"],
            last_refreshed=now,
        )

    def _offering_from_v1(
        self, model: ModelPricing, provider_name: str, now: datetime
    ) -> OfferingV2:
        # v1 Pricing maps cached_input → cache_read (best-effort guess)
        v1p = model.pricing
        pricing = PricingV2(
            input=_round_price(v1p.input),
            output=_round_price(v1p.output),
            cache_read=_round_price(v1p.cached_input),
            cache_write=_round_price(getattr(v1p, "cached_write", None)),
            image_input=_round_price(v1p.image_input),
            audio_input=_round_price(v1p.audio_input),
            audio_output=_round_price(v1p.audio_output),
            embedding=_round_price(v1p.embedding),
        )
        batch = None
        if model.batch_pricing is not None:
            batch = BatchPricingV2(
                input=_round_price(model.batch_pricing.input),
                output=_round_price(model.batch_pricing.output),
            )
        return OfferingV2(
            provider=provider_name,
            provider_model_id=model.model_id,
            pricing=pricing,
            batch_pricing=batch,
            availability="ga",
            region=None,
            notes=None,
            last_updated=model.last_updated or now,
            source="provider_api",
        )

    def _offering_from_litellm(
        self, entry: LiteLLMEntry, now: datetime
    ) -> Optional[OfferingV2]:
        if entry.input_price is None and entry.output_price is None:
            return None
        pricing = PricingV2(
            input=entry.input_price,
            output=entry.output_price,
            cache_read=entry.cache_read_price,
            cache_write=entry.cache_write_price,
            image_input=entry.image_input_price,
            audio_input=entry.audio_input_price,
            audio_output=entry.audio_output_price,
            embedding=entry.embedding_price,
        )
        batch = None
        if entry.batch_input_price is not None or entry.batch_output_price is not None:
            batch = BatchPricingV2(
                input=entry.batch_input_price,
                output=entry.batch_output_price,
            )
        return OfferingV2(
            provider="litellm",
            provider_model_id=entry.raw_key,
            pricing=pricing,
            batch_pricing=batch,
            availability="ga",
            region=None,
            notes="Price inherited from LiteLLM registry (no first-party fetch)",
            last_updated=now,
            source="litellm_fallback",
        )

    def _choose_primary(
        self, entity: EntityCoreV2, offerings: List[OfferingV2]
    ) -> str:
        if not offerings:
            return "litellm"
        providers_present = {o.provider for o in offerings}
        preference = AUTHORITY_BY_MAKER.get(entity.maker, [])
        for candidate in preference:
            if candidate in providers_present:
                return candidate
        # Fallback: prefer a non-fallback offering, else first
        non_fallback = [o for o in offerings if o.source != "litellm_fallback"]
        return (non_fallback[0] if non_fallback else offerings[0]).provider

    def _pretty_model_name(self, entry: LiteLLMEntry) -> str:
        # Titled variant of canonical slug, keeping version numbers.
        # e.g. claude-sonnet-4-5 → Claude Sonnet 4.5
        # This is a heuristic; users will see the real LiteLLM key in offerings.
        parts = entry.canonical_id.split("-")
        pretty: List[str] = []
        for part in parts:
            if part.isdigit():
                pretty.append(part)
            elif len(part) <= 3 and part.isalnum():
                pretty.append(part.upper() if part.islower() else part)
            else:
                pretty.append(part.capitalize())
        base = " ".join(pretty)
        # Reassemble trailing digit groups as version numbers with dots:
        # "Claude Sonnet 4 5" → "Claude Sonnet 4.5"
        tokens = base.split(" ")
        merged: List[str] = []
        for token in tokens:
            if token.isdigit() and merged and merged[-1][-1:].isdigit():
                merged[-1] = f"{merged[-1]}.{token}"
            else:
                merged.append(token)
        return " ".join(merged)

    def _guess_open_source(self, maker: str) -> Optional[bool]:
        open_makers = {"Meta", "Mistral", "DeepSeek", "Alibaba", "NVIDIA", "Cohere"}
        if maker in open_makers:
            return True
        if maker in {"Anthropic", "OpenAI", "Google", "xAI", "Amazon", "AI21"}:
            return False
        return None


async def run_refresh_pipeline(
    *, force_network: bool = True
) -> Tuple[EntityStoreSnapshot, "DriftReportV2", Dict[str, List[OfferingV2]]]:  # noqa: F821
    """Single entry point that ties everything together.

    Returns the built snapshot, the drift report, and the offerings_by_entity
    map so callers can persist both to disk and surface the counts to API
    endpoints without rebuilding the reverse index themselves.
    """
    from models.v2 import DriftReportV2  # noqa: F401 - used in annotation

    registry = await get_registry(force_network=force_network)
    resolver = build_resolver(registry)
    merger = OfferingMerger(registry, resolver)

    # Run all v1 provider fetchers via the existing ProviderRegistry.
    # Falls back to per-provider fallback data on any network/parse error.
    logger.info("v2 pipeline: starting v1 provider fetch")
    try:
        v1_models_by_provider = await ProviderRegistry.fetch_all_grouped()
    except Exception as exc:
        logger.warning("v1 fetch_all_grouped failed (%s); using fallback data", exc)
        v1_models_by_provider = {}
        for provider in ProviderRegistry.all():
            try:
                v1_models_by_provider[provider.name] = provider.load_fallback_data()
            except Exception as inner:
                logger.error("fallback load failed for %s: %s", provider.name, inner)
                v1_models_by_provider[provider.name] = []

    total_v1 = sum(len(m) for m in v1_models_by_provider.values())
    logger.info(
        "v2 pipeline: v1 fetch done, %s models across %s providers",
        total_v1,
        len(v1_models_by_provider),
    )

    snapshot, offerings_by_entity = await merger.build_snapshot(v1_models_by_provider)

    previous_slugs = DriftReporter.load_previous_slugs()
    current_slugs = {e.slug for e in snapshot.entities}

    report = merger.drift.build_report(
        entities=snapshot.entities,
        offerings_by_entity=offerings_by_entity,
        previous_slugs=previous_slugs,
        registry=registry,
    )

    save_snapshot(snapshot, offerings_by_entity)
    DriftReporter.save_report(report, current_slugs)

    return snapshot, report, offerings_by_entity


def save_snapshot(
    snapshot: EntityStoreSnapshot,
    offerings_by_entity: Dict[str, List[OfferingV2]],
) -> None:
    V2_DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = snapshot.model_dump(mode="json")
    with ENTITIES_PATH.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "version": snapshot.version,
                "generated_at": payload["generated_at"],
                "entities": payload["entities"],
            },
            handle,
            indent=2,
            ensure_ascii=False,
        )
    # offerings.json is keyed by entity slug so load_snapshot() can rebuild
    # the reverse index without needing the LiteLLM registry or a resolver.
    by_slug_serialized: Dict[str, List[dict]] = {}
    for slug, offs in offerings_by_entity.items():
        by_slug_serialized[slug] = [o.model_dump(mode="json") for o in offs]
    with OFFERINGS_PATH.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "version": snapshot.version,
                "generated_at": payload["generated_at"],
                "by_entity": by_slug_serialized,
            },
            handle,
            indent=2,
            ensure_ascii=False,
        )
    with INDEX_PATH.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "version": snapshot.version,
                "generated_at": payload["generated_at"],
                "entities_count": len(snapshot.entities),
                "offerings_count": len(snapshot.offerings),
            },
            handle,
            indent=2,
        )


def load_snapshot() -> Optional[
    Tuple[EntityStoreSnapshot, Dict[str, List[OfferingV2]]]
]:
    if not ENTITIES_PATH.exists() or not OFFERINGS_PATH.exists():
        return None
    try:
        with ENTITIES_PATH.open("r", encoding="utf-8") as handle:
            ent_data = json.load(handle)
        with OFFERINGS_PATH.open("r", encoding="utf-8") as handle:
            off_data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None

    entities = [EntityCoreV2.model_validate(e) for e in ent_data.get("entities", [])]
    by_entity_raw = off_data.get("by_entity", {})
    offerings_by_entity: Dict[str, List[OfferingV2]] = {}
    flat: List[OfferingV2] = []
    for slug, items in by_entity_raw.items():
        parsed = [OfferingV2.model_validate(item) for item in items]
        offerings_by_entity[slug] = parsed
        flat.extend(parsed)

    snapshot = EntityStoreSnapshot(
        version=ent_data.get("version", "v2.0"),
        generated_at=ent_data.get("generated_at") or datetime.utcnow().isoformat() + "Z",
        entities=entities,
        offerings=flat,
    )
    return snapshot, offerings_by_entity
