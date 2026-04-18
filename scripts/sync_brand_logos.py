"""
Sinkronizon logot e markës në static/img/logo_biblioteka.png dhe static/img/logo_kamez.png.

1) Nëse gjenden në dosjen e Cursor-it `assets` (nga imazhet e ngarkuara në chat), kopjohen.
2) Përndryshe, nëse mungojnë skedarët, krijohen placeholder me Pillow (zëvendësoji me PNG të vërtetë).

Nga rrënja e projektit:
  python scripts/sync_brand_logos.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "static" / "img"
BIB = OUT_DIR / "logo_biblioteka.png"
KAM = OUT_DIR / "logo_kamez.png"


def _cursor_assets_dirs() -> list[Path]:
    home = Path.home()
    projects = home / ".cursor" / "projects"
    if not projects.is_dir():
        return []
    out: list[Path] = []
    for child in projects.iterdir():
        if not child.is_dir():
            continue
        if "biblioteka" not in child.name.lower():
            continue
        a = child / "assets"
        if a.is_dir():
            out.append(a)
    return out


def _copy_glob(src_dir: Path, pattern: str, dest: Path) -> bool:
    matches = sorted(src_dir.glob(pattern))
    if not matches:
        return False
    src = matches[0]
    if not src.is_file():
        return False
    shutil.copy2(src, dest)
    return True


def _try_copy_from_cursor() -> tuple[bool, bool]:
    ok_b, ok_k = False, False
    for d in _cursor_assets_dirs():
        ok_b = ok_b or _copy_glob(d, "*logo_biblioteka*.png", BIB)
        ok_k = ok_k or _copy_glob(d, "*Logo_kamez*.png", KAM) or _copy_glob(d, "*logo_kamez*.png", KAM)
    return ok_b, ok_k


def _pillow_placeholders() -> None:
    from PIL import Image, ImageDraw, ImageFont

    def font(size: int):
        for name in ("arial.ttf", "SegoeUI.ttf", "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not BIB.exists():
        w, h = 320, 72
        im = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((0, 0, w - 1, h - 1), radius=12, fill=(49, 145, 137, 255))
        f = font(20)
        dr.text((16, 24), "Biblioteka Kamëz", fill=(255, 255, 255, 255), font=f)
        im.save(BIB, format="PNG")
        print(f"Created placeholder {BIB}")
    if not KAM.exists():
        w, h = 96, 112
        im = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((0, 0, w - 1, h - 1), radius=8, fill=(30, 64, 175, 255))
        f = font(12)
        dr.text((12, 44), "Kamëz", fill=(250, 204, 21, 255), font=f)
        im.save(KAM, format="PNG")
        print(f"Created placeholder {KAM}")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cb, ck = _try_copy_from_cursor()
    if cb:
        print(f"Copied logo_biblioteka → {BIB}")
    if ck:
        print(f"Copied logo_kamez → {KAM}")
    if not BIB.exists() or not KAM.exists():
        try:
            _pillow_placeholders()
        except ImportError:
            print("Mungon Pillow; vendos manualisht logo_biblioteka.png dhe logo_kamez.png në static/img/", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
