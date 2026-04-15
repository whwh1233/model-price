"""Canonical resolver — maps any provider-specific model identifier
to a canonical_id that exists in the LiteLLM registry.

Resolution cascade (first hit wins):

1. Direct alias match via LiteLLMRegistry.resolve_alias(raw_id)
2. Strip common provider prefix (bedrock/, azure/, openrouter/, openai/,
   google/, anthropic/, x-ai/, deepseek/, mistralai/) then retry
3. Strip provider-dot-prefix form (anthropic.claude-sonnet-4-5-v1:0)
4. Strip version suffixes (-20250929, -v1:0, -latest, :beta) and
   check against the exact canonical slug set
5. None — caller logs to drift report; offering_merger Pass 2b
   promotes it into a synthetic entity from the raw data

The resolver never invents a canonical id and never accepts a
prefix/suffix boundary match ("kimi-k2" is NOT a match for
"kimi-k2-5"). Those heuristic matches routinely collapsed distinct
models (kimi-k2 vs kimi-k2.5, qwen3-coder vs qwen3-coder-plus,
veo-3 vs veo-3.1) into a single entity with mixed pricing. Anything
that needs fuzzy matching belongs in the LiteLLM registry's own
alias table, not here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from .litellm_registry import LiteLLMRegistry, slugify, strip_version_suffix

logger = logging.getLogger(__name__)

PROVIDER_PREFIXES_SLASH = (
    "openrouter/",
    "bedrock/",
    "bedrock_converse/",
    "azure/",
    "azure_openai/",
    "azure_ai/",
    "vertex_ai/",
    "google/",
    "openai/",
    "anthropic/",
    "x-ai/",
    "xai/",
    "deepseek/",
    "deepseek-ai/",
    "mistralai/",
    "mistral/",
    "meta/",
    "meta-llama/",
    "cohere/",
    "ai21/",
    "amazon/",
    "nvidia/",
    "perplexity/",
    "together_ai/",
    "fireworks_ai/",
    "groq/",
    "replicate/",
)

DOT_PREFIXES = (
    "anthropic.",
    "amazon.",
    "meta.",
    "mistral.",
    "cohere.",
    "ai21.",
    "stability.",
    "deepseek.",
)


@dataclass
class Resolution:
    canonical_id: Optional[str]
    tried: List[str]
    strategy: str  # debugging aid: which step hit

    def matched(self) -> bool:
        return self.canonical_id is not None


class CanonicalResolver:
    """Stateful resolver bound to a LiteLLMRegistry instance."""

    def __init__(self, registry: LiteLLMRegistry) -> None:
        self.registry = registry
        self._canonical_slugs = {e.canonical_id for e in registry.iter_canonical()}

    # ─── Public API ──────────────────────────────────────────

    def resolve(self, provider: str, provider_model_id: str) -> Resolution:
        tried: List[str] = []
        raw = (provider_model_id or "").strip()
        if not raw:
            return Resolution(None, tried, "empty")

        # Step 1: direct alias hit (on raw and normalized forms)
        for candidate in self._candidates(raw):
            if candidate in tried:
                continue
            tried.append(candidate)
            hit = self.registry.resolve_alias(candidate)
            if hit:
                return Resolution(hit, tried, "alias")

        # Step 2: strip provider-specific prefixes then retry
        for candidate in self._strip_prefix_variants(raw):
            if candidate in tried:
                continue
            tried.append(candidate)
            hit = self.registry.resolve_alias(candidate)
            if hit:
                return Resolution(hit, tried, "prefix_strip")

        # Step 3: version-suffix-stripped form against canonical set
        stripped = strip_version_suffix(slugify(raw))
        if stripped and stripped not in tried:
            tried.append(stripped)
            if stripped in self._canonical_slugs:
                return Resolution(stripped, tried, "version_strip")
            hit = self.registry.resolve_alias(stripped)
            if hit:
                return Resolution(hit, tried, "version_strip_alias")

        return Resolution(None, tried, "miss")

    # ─── Internals ───────────────────────────────────────────

    def _candidates(self, raw: str) -> List[str]:
        """Variants that might directly match registry aliases."""
        out = [raw]
        lowered = raw.lower()
        if lowered != raw:
            out.append(lowered)
        slug = slugify(raw)
        if slug and slug != lowered:
            out.append(slug)
        stripped = strip_version_suffix(slug)
        if stripped and stripped != slug:
            out.append(stripped)
        return out

    def _strip_prefix_variants(self, raw: str) -> List[str]:
        """Try removing known provider prefixes; return cascading candidates."""
        variants: List[str] = []
        lowered = raw.lower()

        for prefix in PROVIDER_PREFIXES_SLASH:
            if lowered.startswith(prefix):
                rest = raw[len(prefix):]
                variants.extend(self._candidates(rest))

        for prefix in DOT_PREFIXES:
            if lowered.startswith(prefix):
                rest = raw[len(prefix):]
                variants.extend(self._candidates(rest))

        # Also try interpreting "a/b/c" by dropping only the first segment
        if "/" in raw:
            first_drop = raw.split("/", 1)[1]
            variants.extend(self._candidates(first_drop))
            # And dropping any leading "a/b/" pair if present
            if "/" in first_drop:
                variants.extend(self._candidates(first_drop.split("/", 1)[1]))

        # And the inverse for dot notation: anthropic.claude... → claude...
        if "." in raw:
            head, tail = raw.split(".", 1)
            if head.lower() in {"anthropic", "amazon", "meta", "mistral", "cohere", "ai21"}:
                variants.extend(self._candidates(tail))

        # Deduplicate while preserving order
        seen = set()
        ordered: List[str] = []
        for v in variants:
            if v and v not in seen:
                ordered.append(v)
                seen.add(v)
        return ordered

def build_resolver(registry: LiteLLMRegistry) -> CanonicalResolver:
    return CanonicalResolver(registry)
