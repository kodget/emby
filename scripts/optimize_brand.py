"""Turn the raw 1024px brand renders into web-sized WebP assets.

The generator returns ~1.8 MB PNGs. Shipping 37 of those would add roughly 60 MB to the
app, so this trims each render to its actual content, emits a couple of sensible sizes as
WebP, and keeps a single PNG fallback for the logo.

    public/brand/logo-mark.png            ->  logo-mark.webp (+ @2x)
    public/brand/icons/<name>.png         ->  icons/<name>.webp      (192px, @2x 384px)
    public/brand/mascot/axo-<pose>.png    ->  mascot/axo-<pose>.webp (384px, @2x 768px)

Usage:
    python scripts/optimize_brand.py
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
BRAND = ROOT / "public" / "brand"
ICONS = BRAND / "icons"
MASCOT = BRAND / "mascot"

# (base width, also emit @2x)
ICON_SIZE = 192
MASCOT_SIZE = 384
LOGO_SIZE = 256

QUALITY = 88
# Alpha below this is treated as empty when trimming transparent margins.
ALPHA_FLOOR = 8


def trim(image: Image.Image, pad_ratio: float = 0.02) -> Image.Image:
    """Crop away fully transparent margins, leaving a small even breathing space."""
    alpha = image.getchannel("A")
    # point() maps faint glow pixels to 0 so a soft halo doesn't defeat getbbox().
    box = alpha.point(lambda a: 255 if a > ALPHA_FLOOR else 0).getbbox()
    if not box:
        return image

    cropped = image.crop(box)
    w, h = cropped.size
    side = max(w, h)
    pad = int(side * pad_ratio)
    canvas = Image.new("RGBA", (side + pad * 2, side + pad * 2), (0, 0, 0, 0))
    canvas.paste(cropped, ((canvas.width - w) // 2, (canvas.height - h) // 2))
    return canvas


def emit(src: pathlib.Path, size: int, retina: bool = True) -> int:
    with Image.open(src) as im:
        im = trim(im.convert("RGBA"))

        written = 0
        for scale, suffix in ((1, ""), (2, "@2x")) if retina else ((1, ""),):
            target = size * scale
            out = im.resize((target, target), Image.LANCZOS)
            dest = src.with_name(f"{src.stem}{suffix}.webp")
            out.save(dest, "WEBP", quality=QUALITY, method=6)
            written += dest.stat().st_size
        return written


def main() -> int:
    if not BRAND.exists():
        print("No public/brand directory; run scripts/gen_brand.py first.")
        return 1

    total_before = total_after = 0
    count = 0

    groups = [
        (sorted(ICONS.glob("*.png")), ICON_SIZE, "icons"),
        (sorted(MASCOT.glob("*.png")), MASCOT_SIZE, "mascot"),
        ([BRAND / "logo-mark.png"], LOGO_SIZE, "logo"),
    ]

    for files, size, label in groups:
        group_before = group_after = 0
        for src in files:
            if not src.exists():
                continue
            group_before += src.stat().st_size
            group_after += emit(src, size)
            count += 1
        if group_before:
            print(
                f"  {label:8} {group_before / 1e6:6.1f} MB -> {group_after / 1e6:5.2f} MB"
            )
        total_before += group_before
        total_after += group_after

    print(
        f"\noptimised {count} assets: "
        f"{total_before / 1e6:.1f} MB -> {total_after / 1e6:.2f} MB "
        f"({100 - total_after / max(1, total_before) * 100:.0f}% smaller)"
    )
    print("Raw PNGs are kept as the source of truth; ship the .webp files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
