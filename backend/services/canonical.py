"""Canonical resolver — maps any provider-specific model identifier
to a canonical_id that exists in the LiteLLM registry.

Resolution cascade (first hit wins):

1. Direct alias match via LiteLLMRegistry.resolve_alias(raw_id)
2. Strip common provider prefix (bedrock/, azure/, openrouter/, openai/,
   google/, anthropic/, x-ai/, deepseek/, mistralai/) then retry
3. Strip provider-dot-prefix form (anthropic.claude-sonnet-4-5-v1:0)
4. Strip version suffixes (-20250929, -v1:0, -latest, :beta)
5. Substring contains inside any canonical slug (last resort)
6. None — caller logs to drift report

The resolver never invents a canonical id. If none of the above matches,
it returns None and lets the merger decide whether to synthesize a
new entity from the raw data or skip it.
"""

from __future__ import annotations

import logging
import re
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

# Version / date / tag suffixes stripped during normalization.
VERSION_SUFFIX_RE = re.compile(
    r"(?:-v\d+(?:[-:]\d+)?|-\d{8}|-\d{4}-\d{2}-\d{2}|-latest|:beta|:free|:nitro|:extended)$"
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

        # Step 4: contains-match inside any canonical slug
        normalized = slugify(raw)
        if normalized:
            contains_hit = self._contains_match(normalized)
            if contains_hit:
                tried.append(f"contains:{normalized}")
                return Resolution(contains_hit, tried, "contains")

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

    def _contains_match(self, needle: str) -> Optional[str]:
        """Fallback: find a canonical slug that contains the needle exactly.

        This is a last-resort match. To avoid false positives we only accept
        matches where the needle is either (a) the full slug, (b) a prefix
        ending at a dash boundary, or (c) a suffix after a dash.
        """
        needle = needle.strip("-")
        if len(needle) < 4:
            return None
        for slug in self._canonical_slugs:
            if slug == needle:
                return slug
            if slug.startswith(f"{needle}-") or slug.endswith(f"-{needle}"):
                return slug
        return None


def build_resolver(registry: LiteLLMRegistry) -> CanonicalResolver:
    return CanonicalResolver(registry)
