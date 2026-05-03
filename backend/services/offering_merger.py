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
    DISPLAY_CAPABILITIES,
    LiteLLMEntry,
    LiteLLMRegistry,
    detect_family_maker,
    get_registry,
    slugify,
    strip_version_suffix,
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


AUTHOR_PREFIX_TO_MAKER = {
    "aionlabs": "AionLabs",
    "allenai": "AllenAI",
    "alibaba": "Alibaba",
    "qwen": "Alibaba",
    "anthropic": "Anthropic",
    "arcee-ai": "Arcee AI",
    "arcee": "Arcee AI",
    "baidu": "Baidu",
    "bytedance": "ByteDance",
    "bytedance-research": "ByteDance",
    "cognitivecomputations": "Cognitive Computations",
    "cohere": "Cohere",
    "deepcogito": "Deep Cogito",
    "deepseek": "DeepSeek",
    "deepseek-ai": "DeepSeek",
    "deepseek-v3": "DeepSeek",
    "eleutherai": "EleutherAI",
    "fireworks": "Fireworks",
    "google": "Google",
    "inflection": "Inflection",
    "liquid": "Liquid AI",
    "meta": "Meta",
    "meta-llama": "Meta",
    "microsoft": "Microsoft",
    "minimax": "MiniMax",
    "mistralai": "Mistral",
    "mistral": "Mistral",
    "moonshotai": "Moonshot AI",
    "moonshot": "Moonshot AI",
    "neversleep": "NeverSleep",
    "nousresearch": "Nous Research",
    "nous": "Nous Research",
    "nvidia": "NVIDIA",
    "openai": "OpenAI",
    "openchat": "OpenChat",
    "opengvlab": "OpenGVLab",
    "perplexity": "Perplexity",
    "qwen": "Alibaba",
    "reka": "Reka",
    "sao10k": "Sao10k",
    "snowflake": "Snowflake",
    "stabilityai": "Stability AI",
    "stepfun-ai": "StepFun",
    "tencent": "Tencent",
    "thedrummer": "TheDrummer",
    "thudm": "THUDM",
    "together": "Together",
    "upstage": "Upstage",
    "venice": "Venice",
    "xai": "xAI",
    "x-ai": "xAI",
    "z-ai": "Z.AI",
    "zai": "Z.AI",
    "01-ai": "01.AI",
    "01.ai": "01.AI",
    "ai21": "AI21",
    "amazon": "Amazon",
}


def _maker_from_model_id(model_id: Optional[str]) -> Optional[str]:
    if not model_id:
        return None
    lowered = model_id.lower()
    for sep in ("/", "."):
        if sep in lowered:
            head = lowered.split(sep, 1)[0].strip()
            mapped = AUTHOR_PREFIX_TO_MAKER.get(head)
            if mapped:
                return mapped
            # Fall back to simple title case of the prefix itself
            if len(head) >= 2 and head.replace("-", "").replace("_", "").isalnum():
                return head.replace("-", " ").replace("_", " ").title()
    return None


def _family_from_model_name(name: Optional[str]) -> Optional[str]:
    """Deprecated — kept for reference. We now prefer maker-as-family
    in the synthetic path because this function produced too many
    ugly labels ("Aionlabs:", "Body", "Seed").
    """
    return None


def _unmatched_cluster_key(model: ModelPricing) -> str:
    """Derive a stable cluster key from an unmatched v1 record so that
    the same underlying model from different providers ends up in one
    synthetic entity, while distinct versions (K2, K2.5, K2 Thinking)
    remain separate.

    Priority: model_id slug (most stable across providers, carries the
    version bits like ".5" or "-thinking") → fallback to model_name slug
    if the id isn't informative enough.
    """
    id_candidate = slugify(model.model_id or "")
    name_candidate = slugify(model.model_name or "")
    # A good id_candidate has at least two dash-separated segments
    # ("kimi-k2-5" good, "chat" bad).
    if len(id_candidate) >= 4 and "-" in id_candidate:
        return id_candidate
    if len(name_candidate) >= 4:
        return name_candidate
    return id_candidate or name_candidate

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


def _is_stub_offering_set(offerings: List[OfferingV2]) -> bool:
    """True if the entity has only LiteLLM-fallback placeholder offerings.

    A "stub" is an entity whose every offering is:
    - sourced from litellm_fallback (no real provider ever confirmed
      the pricing), AND
    - has both input and output price equal to 0 or missing.

    These come from LiteLLM stub entries for newly-announced models
    (no price known yet) or per-request APIs like text-moderation /
    rerank whose pricing model doesn't fit per-1M-token. Showing them
    as "free $0" misleads users — we drop them entirely. Real free
    models come in through OpenRouter's provider_api (e.g. the
    *-free variants), which passes this check and is preserved.
    """
    if not offerings:
        return False
    for offering in offerings:
        if offering.source != "litellm_fallback":
            return False
        input_price = offering.pricing.input or 0
        output_price = offering.pricing.output or 0
        if input_price != 0 or output_price != 0:
            return False
    return True


# Sanity envelope for embedding input prices, in $/M tokens.
# Cheapest real embedding on the market is ~$0.01/M (Voyage Lite,
# text-embedding-3-small). $100/M is 100x the most expensive real
# embedding (Cohere embed-v4 at $0.12). Anything outside this range
# almost always traces to a provider scraper unit bug (AWS returning
# per-1k prices as per-token) or a stale LiteLLM entry that nobody
# noticed. We null the price rather than dropping the offering so the
# drift report keeps a record.
EMBEDDING_INPUT_PRICE_MIN = 0.001   # $0.001 / M
EMBEDDING_INPUT_PRICE_MAX = 10.0    # $10 / M


def _is_embedding_price_outlier(
    offering: OfferingV2, mode: str
) -> bool:
    """True if an embedding offering's input price is wildly out of range.

    Embedding input prices cluster in a narrow band ($0.01 – $1 per
    million tokens). Values far outside that band are almost always
    data bugs — TwelveLabs Marengo scraped as $0.0001/M (AWS parser
    unit error) and Cohere embed-multilingual-light stamped at $100/M
    (stale/bogus LiteLLM entry). Both used to surface as "cheap
    alternatives" for other embeddings, poisoning the alternatives list.
    """
    if mode != "embedding":
        return False
    inp = offering.pricing.input
    if inp is None:
        return False
    return inp < EMBEDDING_INPUT_PRICE_MIN or inp > EMBEDDING_INPUT_PRICE_MAX


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
        unmatched_buckets: Dict[str, List[Tuple[str, ModelPricing]]] = {}

        for provider_name, models in v1_models_by_provider.items():
            for model in models:
                resolution = self.resolver.resolve(provider_name, model.model_id)
                canonical_id = resolution.canonical_id if resolution.matched() else None

                # If the resolver matched an alias that points at a
                # canonical_id with no actual registry entry behind it
                # (a "dangling alias"), treat it as unmatched so the
                # record can still be promoted into a synthetic entity.
                if canonical_id is not None and canonical_id not in entities:
                    entry = self.registry.get(canonical_id)
                    if entry is None:
                        canonical_id = None

                if canonical_id is None:
                    cluster_key = _unmatched_cluster_key(model)
                    unmatched_buckets.setdefault(cluster_key, []).append(
                        (provider_name, model)
                    )
                    self.drift.record_unmatched(
                        provider=provider_name,
                        model_id=model.model_id,
                        tried=resolution.tried,
                    )
                    continue

                if canonical_id not in entities:
                    entry = self.registry.get(canonical_id)
                    if entry is None:
                        continue
                    entities[canonical_id] = self._entity_from_litellm(entry, now)
                    offerings_by_entity.setdefault(canonical_id, [])

                offering = self._offering_from_v1(model, provider_name, now)
                offerings_by_entity[canonical_id].append(offering)
                self.registry.register_alias(model.model_id, canonical_id)
                self.registry.register_alias(
                    f"{provider_name}:{model.model_id}", canonical_id
                )
                attach_counts[provider_name] = attach_counts.get(provider_name, 0) + 1

        # ─── Pass 2b: promote unmatched clusters to synthetic entities
        synthetic_count = 0
        for cluster_key, bucket in unmatched_buckets.items():
            if not cluster_key:
                continue
            # Use the bare cluster_key as slug first so models like
            # "claude-3-5-sonnet" and "llama-4-maverick" — which LiteLLM
            # doesn't expose as first-party canonicals — still get the
            # clean URL users expect. Only prefix with "v1-" if a slug
            # collision would shadow a real canonical entry.
            slug = cluster_key
            if slug in entities:
                slug = f"v1-{cluster_key}"
            if slug in entities:
                slug = f"v1-{cluster_key}-{bucket[0][0]}"
            synthetic_entity = self._synthetic_entity_from_v1(slug, bucket, now)
            if synthetic_entity is None:
                continue
            entities[slug] = synthetic_entity
            offerings_by_entity[slug] = [
                self._offering_from_v1(m, p, now) for p, m in bucket
            ]
            synthetic_count += 1

        # ─── Pass 2c: drop embedding price outliers
        # Prices 1000x cheaper or 100x more expensive than the real
        # market are almost always scraper unit bugs. We run this BEFORE
        # Pass 3 so entities whose only provider offering was an outlier
        # get a chance to fall back to the LiteLLM reference price, and
        # the stub filter handles any that are left with nothing.
        outlier_dropped = 0
        outlier_log: List[tuple[str, str, float]] = []
        for slug, offs in list(offerings_by_entity.items()):
            entity = entities.get(slug)
            if entity is None:
                continue
            kept: List[OfferingV2] = []
            for offering in offs:
                if _is_embedding_price_outlier(offering, entity.mode):
                    outlier_dropped += 1
                    outlier_log.append((slug, offering.provider, offering.pricing.input or 0.0))
                    continue
                kept.append(offering)
            offerings_by_entity[slug] = kept
        if outlier_log:
            logger.warning(
                "OfferingMerger: dropped %s embedding price outliers: %s",
                outlier_dropped,
                outlier_log[:10],
            )

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
            # Guard: don't synthesize a fallback whose LiteLLM price is
            # itself an outlier (embed-multilingual-light at $100/M).
            if (
                entity.mode == "embedding"
                and fallback.pricing.input is not None
                and (
                    fallback.pricing.input < EMBEDDING_INPUT_PRICE_MIN
                    or fallback.pricing.input > EMBEDDING_INPUT_PRICE_MAX
                )
            ):
                continue
            offerings_by_entity.setdefault(slug, []).append(fallback)
            synthesized += 1

        # ─── Pass 4: prune entities without any usable offering
        # Also drop "stubs" — entities whose only offerings are
        # litellm_fallback placeholders with no real price data
        # ($0 input AND $0 output). LiteLLM routinely publishes empty
        # entries for brand-new model releases before upstream pricing
        # is known, and for per-request APIs (moderation, rerank)
        # whose pricing model doesn't fit our per-token schema at all.
        # Keeping them surfaces misleading "free" entries to users
        # and creates phantom duplicates like kimi-k2-thinking-251104
        # alongside the real kimi-k2-thinking. Real free models
        # (OpenRouter's *-free variants) come through as provider_api
        # offerings and are preserved.
        final_slugs: set[str] = set()
        stub_count = 0
        for slug, offs in offerings_by_entity.items():
            if not offs:
                continue
            if _is_stub_offering_set(offs):
                stub_count += 1
                continue
            final_slugs.add(slug)
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
            "provider attach: %s; litellm_fallback: %s; v1_synthetic: %s; "
            "stubs pruned: %s",
            len(pruned_entities),
            len(entities),
            attach_counts,
            synthesized,
            synthetic_count,
            stub_count,
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

    def _synthetic_entity_from_v1(
        self,
        slug: str,
        bucket: List[Tuple[str, ModelPricing]],
        now: datetime,
    ) -> Optional[EntityCoreV2]:
        """Build an entity from v1 records that didn't match any LiteLLM
        canonical entry. Picks a representative record for the base fields
        and merges capabilities / modalities across the cluster.
        """
        if not bucket:
            return None

        # Pick the record with the richest metadata as the base
        base_provider, base = max(
            bucket,
            key=lambda pair: (
                (pair[1].context_length or 0),
                len(pair[1].capabilities or []),
                -len(pair[1].model_id),
            ),
        )

        display_name = (base.model_name or base.model_id).strip()
        # OpenRouter and similar aggregators prefix display names with the
        # maker ("AionLabs: Aion-1.0"). Strip it so the UI shows a clean
        # product name — the maker already renders alongside.
        if ": " in display_name:
            _prefix, _rest = display_name.split(": ", 1)
            if _prefix and _rest:
                display_name = _rest.strip()
        family, maker = detect_family_maker(slug, display_name)

        # When detect_family_maker can't place this model, fall back to the
        # author prefix from the v1 model_id (OpenRouter-style: "allenai/olmo-…").
        if maker == "Unknown":
            maker = _maker_from_model_id(base.model_id) or "Unknown"
        if family == "Other":
            # Prefer reusing maker as family when we can't detect a real
            # family name — avoids junk labels like "Aionlabs:" or "Body"
            # leaking into the dropdown.
            if maker != "Unknown":
                family = maker

        caps: set[str] = set()
        in_mods: set[str] = set()
        out_mods: set[str] = set()
        ctx = 0
        max_out = 0
        for _provider, model in bucket:
            for cap in model.capabilities or []:
                if cap in DISPLAY_CAPABILITIES:
                    caps.add(cap)
            for m in model.input_modalities or []:
                in_mods.add(m)
            for m in model.output_modalities or []:
                out_mods.add(m)
            if (model.context_length or 0) > ctx:
                ctx = model.context_length or 0
            if (model.max_output_tokens or 0) > max_out:
                max_out = model.max_output_tokens or 0

        if not caps:
            caps.add("text")
        if not in_mods:
            in_mods = {"text"}
        if not out_mods:
            out_mods = {"text"}

        # Primary offering follows authority order, or first bucket entry
        provider_order = AUTHORITY_BY_MAKER.get(maker, [])
        providers_present = {p for p, _ in bucket}
        primary_provider = next(
            (p for p in provider_order if p in providers_present),
            base_provider,
        )

        return EntityCoreV2(
            canonical_id=slug,
            slug=slug,
            name=display_name,
            family=family,
            maker=maker,
            context_length=ctx or None,
            max_output_tokens=max_out or None,
            capabilities=sorted(caps),
            input_modalities=sorted(in_mods),
            output_modalities=sorted(out_mods),
            mode="chat",
            is_open_source=self._guess_open_source(maker),
            primary_offering_provider=primary_provider,
            sources=sorted({"v1_synthetic", *[p for p, _ in bucket]}),
            last_refreshed=now,
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
        by_provider = {o.provider: o for o in offerings}
        preference = AUTHORITY_BY_MAKER.get(entity.maker, [])

        def has_token_price(off: OfferingV2) -> bool:
            return off.pricing.input is not None and off.pricing.output is not None

        # Prefer the highest-authority provider with complete token pricing,
        # so a partial upstream entry (e.g. Bedrock's pricing API publishing
        # output but not input for a freshly-launched model) doesn't shadow
        # a sibling offering that does have both numbers.
        for candidate in preference:
            off = by_provider.get(candidate)
            if off and has_token_price(off):
                return candidate
        for candidate in preference:
            if candidate in by_provider:
                return candidate
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
