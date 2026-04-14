"""Data sanity check for v2 popular models.

Run from backend/: uv run --active python scripts/sanity_check.py

Compares v2 entities.json against an expected roster of the core
first-party models users actually look up. Reports:
- MISSING: expected canonical_id not in v2 entities
- BAD_MAKER: entity exists but maker != expected
- NO_OFFERING: entity exists but has 0 offerings
- ORPHAN: entity exists but only has litellm_fallback offerings
- PRICE_NONE: primary offering has no input price
- OK: everything matches

No auto-fix. Pure reporter.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
ENTITIES = json.loads((ROOT / "data" / "v2" / "entities.json").read_text())
OFFERINGS = json.loads((ROOT / "data" / "v2" / "offerings.json").read_text())

BY_SLUG: Dict[str, Dict[str, Any]] = {e["slug"]: e for e in ENTITIES["entities"]}
OFF_BY_SLUG: Dict[str, List[Dict[str, Any]]] = OFFERINGS.get("by_entity", {})


def offerings_for(slug: str) -> List[Dict[str, Any]]:
    return OFF_BY_SLUG.get(slug, [])


def primary_offering(slug: str) -> Optional[Dict[str, Any]]:
    ent = BY_SLUG.get(slug)
    if not ent:
        return None
    offs = offerings_for(slug)
    primary_provider = ent.get("primary_offering_provider")
    for o in offs:
        if o.get("provider") == primary_provider:
            return o
    return offs[0] if offs else None


# ─── Expected roster ──────────────────────────────────────────────────
# Grouped by maker; slug is what v2 SHOULD produce. Price hints are
# the ballpark per-1M-token expectations we can eyeball.

EXPECTED = {
    "Anthropic": [
        "claude-opus-4-6",
        "claude-opus-4-1",
        "claude-opus-4",
        "claude-sonnet-4-6",
        "claude-sonnet-4-5",
        "claude-sonnet-4",
        "claude-haiku-4-5",
        "claude-3-7-sonnet",
        "claude-3-5-sonnet",
        "claude-3-5-haiku",
        "claude-3-opus",
        "claude-3-haiku",
    ],
    "OpenAI": [
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        "gpt-5-4",
        "gpt-5-4-mini",
        "gpt-5-4-nano",
        "gpt-4-1",
        "gpt-4-1-mini",
        "gpt-4-1-nano",
        "gpt-4o",
        "gpt-4o-mini",
        "o1",
        "o1-mini",
        "o1-pro",
        "o3",
        "o3-mini",
        "o3-pro",
        "o4-mini",
        "chatgpt-4o",
        "gpt-4-turbo",
        "gpt-4",
    ],
    "Google": [
        "gemini-3-pro",
        "gemini-3-flash",
        "gemini-2-5-pro",
        "gemini-2-5-flash",
        "gemini-2-5-flash-lite",
        "gemini-2-0-flash",
        "gemini-2-0-flash-lite",
        "gemini-1-5-pro",
        "gemini-1-5-flash",
    ],
    "xAI": [
        "grok-4",
        "grok-4-1",
        "grok-4-1-fast",
        "grok-4-fast",
        "grok-4-fast-reasoning",
        "grok-4-fast-non-reasoning",
        "grok-code-fast",
        "grok-3",
        "grok-3-mini",
    ],
    "Meta": [
        "llama-4-maverick-17b",
        "llama-4-scout-17b",
        "llama-3-3-70b",
        "llama-3-1-405b",
        "llama-3-1-70b",
        "llama-3-1-8b",
    ],
    "DeepSeek": [
        "deepseek-chat",
        "deepseek-reasoner",
        "deepseek-v3",
        "deepseek-r1",
    ],
    "Moonshot AI": [
        "kimi-k2",
        "kimi-k2-5",
        "kimi-k2-thinking",
        "moonshot-v1-8k",
        "moonshot-v1-32k",
        "moonshot-v1-128k",
    ],
    "Alibaba": [
        "qwen-max",
        "qwen-plus",
        "qwen-turbo",
        "qwen3-max",
        "qwen3-plus",
        "qwen3-coder",
        "qwen-vl-max",
    ],
    "Z.AI": [
        "glm-4-6",
        "glm-4-5",
        "glm-4-5-air",
        "glm-4-plus",
    ],
    "MiniMax": [
        "minimax-m2",
        "minimax-m1",
        "abab6-5",
    ],
}


def check(slug: str, expected_maker: str) -> tuple[str, str]:
    """Return (status_code, message)."""
    ent = BY_SLUG.get(slug)
    if ent is None:
        return "MISSING", ""
    maker = ent.get("maker") or "Unknown"
    offs = offerings_for(slug)
    if not offs:
        return "NO_OFFERING", f"maker={maker}"
    primary = primary_offering(slug)
    sources = {o.get("source") for o in offs}
    real_providers = sorted({o.get("provider") for o in offs if o.get("source") != "litellm_fallback"})
    pricing = primary.get("pricing", {}) if primary else {}
    in_price = pricing.get("input")
    out_price = pricing.get("output")

    issues: List[str] = []
    if maker != expected_maker:
        issues.append(f"maker={maker}≠{expected_maker}")
    if sources == {"litellm_fallback"}:
        issues.append("orphan(litellm-only)")
    if in_price is None:
        issues.append("input=None")
    if issues:
        tag = "ISSUE"
    else:
        tag = "OK"
    providers = ",".join(real_providers) or "(litellm)"
    return tag, f"{providers} in=${in_price} out=${out_price} {' '.join(issues)}"


def main() -> None:
    totals: Dict[str, int] = defaultdict(int)
    missing_by_maker: Dict[str, List[str]] = defaultdict(list)
    issues_by_maker: Dict[str, List[str]] = defaultdict(list)

    print(f"total entities in v2: {len(ENTITIES['entities'])}\n")
    for maker, slugs in EXPECTED.items():
        print(f"── {maker} " + "─" * (60 - len(maker)))
        for slug in slugs:
            status, msg = check(slug, maker)
            totals[status] += 1
            mark = {
                "OK": "✓",
                "MISSING": "✗",
                "ISSUE": "⚠",
                "NO_OFFERING": "⚠",
            }.get(status, "?")
            line = f"  {mark} {slug:35s} {msg}"
            print(line)
            if status == "MISSING":
                missing_by_maker[maker].append(slug)
            elif status != "OK":
                issues_by_maker[maker].append(f"{slug} {msg}")
        print()

    print("── Summary " + "─" * 55)
    for status, count in sorted(totals.items()):
        print(f"  {status}: {count}")

    total_expected = sum(totals.values())
    hit_rate = totals.get("OK", 0) / max(total_expected, 1) * 100
    print(f"  hit rate: {hit_rate:.1f}% ({totals.get('OK', 0)}/{total_expected})")


if __name__ == "__main__":
    main()
