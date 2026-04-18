"""
Krijon versione të lehta WebP për faqen kryesore (galeri + foto kryesore).

- static/img/home-gallery/1.jpg … 4.jpg  →  1_thumb.webp … 4_thumb.webp (~420px gjerësi)
- static/img/kamez-library.png (ose .jpg)  →  kamez-library_thumb.webp (~960px)

Pastaj `collectstatic` / deploy. Në kod, `cms.views` zgjedh automatikisht *_thumb.webp nëse ekziston.

  python scripts/build_image_thumbs.py
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Instaloni Pillow: pip install Pillow", file=sys.stderr)
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "static" / "img"
GAL = IMG / "home-gallery"


def _to_rgb(im: Image.Image) -> Image.Image:
    if im.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        return bg
    if im.mode == "P":
        return im.convert("RGBA").convert("RGB")
    return im.convert("RGB")


def save_webp(src: Path, dest: Path, max_w: int, quality: int = 82) -> None:
    if not src.is_file():
        return
    im = Image.open(src)
    im = _to_rgb(im)
    w, h = im.size
    if w > max_w:
        nh = max(1, int(h * (max_w / w)))
        im = im.resize((max_w, nh), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "WEBP", quality=quality, method=6)
    print(f"OK {dest.name} ({dest.stat().st_size // 1024} KB) <- {src.name}")


def main() -> int:
    for i in range(1, 5):
        src = None
        for ext in ("jpg", "jpeg", "png", "webp"):
            p = GAL / f"{i}.{ext}"
            if p.is_file():
                src = p
                break
        if src:
            save_webp(src, GAL / f"{i}_thumb.webp", max_w=420, quality=82)
        else:
            print(f"skip gallery {i}: no {GAL}/{i}.(jpg|jpeg|png|webp)")

    hero = None
    for name in ("kamez-library.png", "kamez-library.jpg", "kamez-library.jpeg"):
        p = IMG / name
        if p.is_file():
            hero = p
            break
    if hero:
        save_webp(hero, IMG / "kamez-library_thumb.webp", max_w=960, quality=80)
    else:
        print("skip hero: no static/img/kamez-library.png|.jpg")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
