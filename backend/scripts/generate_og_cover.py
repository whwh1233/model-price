"""Generate the Open Graph / Twitter Card cover image.

Renders a 1200×630 PNG into frontend/public/og-cover.png using Pillow.
The result is committed to the repo — Render / Vercel don't need to
run this script. Regenerate locally via:

    uv run --active python scripts/generate_og_cover.py

whenever the tagline, brand, or accent color changes.
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1200, 630
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT = REPO_ROOT / "frontend" / "public" / "og-cover.png"

# Colors match the dark-theme tokens used by the site itself.
BG = (10, 11, 13)
CARD = (17, 18, 22)
FG_0 = (245, 246, 248)
FG_1 = (220, 222, 228)
FG_2 = (154, 160, 173)
FG_3 = (106, 113, 128)
ACCENT = (124, 155, 255)

FONT_BOLD_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",  # macOS, index 1 = Bold
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux fallback
]
FONT_REGULAR_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",  # index 0 = Regular
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def find_font(candidates: list[str]) -> str | None:
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def load(path: str | None, size: int, ttc_index: int = 0) -> ImageFont.FreeTypeFont:
    if path is None:
        return ImageFont.load_default()
    try:
        return ImageFont.truetype(path, size, index=ttc_index)
    except (OSError, ValueError):
        return ImageFont.load_default()


def text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def draw_centered(draw, text: str, y: int, font, fill):
    width = text_width(draw, text, font)
    draw.text(((W - width) // 2, y), text, fill=fill, font=font)


def main() -> None:
    bold_path = find_font(FONT_BOLD_CANDIDATES)
    reg_path = find_font(FONT_REGULAR_CANDIDATES)

    bold_idx = 1 if bold_path and bold_path.endswith(".ttc") else 0

    brand_font = load(bold_path, 56, bold_idx)
    hero_font = load(bold_path, 108, bold_idx)
    tagline_font = load(reg_path, 38, 0)
    families_font = load(reg_path, 26, 0)
    url_font = load(reg_path, 24, 0)

    # Base background
    img = Image.new("RGB", (W, H), BG)

    # Subtle top glow using a blurred RGBA overlay
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse([(-200, -520), (W + 200, 260)], fill=(124, 155, 255, 55))
    glow = glow.filter(ImageFilter.GaussianBlur(140))
    composed = Image.alpha_composite(img.convert("RGBA"), glow)
    img = composed.convert("RGB")

    draw = ImageDraw.Draw(img)

    # Top-left brand mark + name
    draw.text((90, 72), "⬡", fill=ACCENT, font=brand_font)
    draw.text((158, 80), "Model Price", fill=FG_0, font=brand_font)

    # Hero title — centered vertically in the middle of the card
    draw_centered(draw, "Compare 650+ LLMs", 220, hero_font, FG_0)
    draw_centered(draw, "side by side.", 340, hero_font, FG_0)

    # Tagline below the hero
    draw_centered(
        draw,
        "Real pricing · real capabilities · keyboard-first",
        475,
        tagline_font,
        FG_2,
    )

    # Families strip just above the footer
    families = "Claude · GPT · Gemini · Grok · DeepSeek · Kimi · Llama · Mistral · Qwen"
    draw_centered(draw, families, 528, families_font, FG_3)

    # URL at the very bottom
    draw_centered(draw, "modelprice.boxtech.icu", 582, url_font, ACCENT)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUTPUT, "PNG", optimize=True)
    print(f"Wrote {OUTPUT} ({W}x{H})")


if __name__ == "__main__":
    main()
