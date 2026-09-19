from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_FONT = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")
DEFAULT_FONT_BLACK = Path("/System/Library/Fonts/Supplemental/Arial Black.ttf")


def build_avatar(source: Image.Image, destination: Path) -> None:
    crop = source.crop((145, 20, 880, 755))
    avatar = crop.resize((512, 512), Image.Resampling.LANCZOS)
    if destination.suffix.lower() == ".jpg":
        avatar.save(destination, format="JPEG", quality=94, optimize=True)
    else:
        avatar.save(destination, format="PNG", optimize=True)


def build_cover(source: Image.Image, destination: Path, font_dir: Path | None) -> None:
    canvas = Image.new("RGB", (1280, 720), "#101012")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((52, 52, 1228, 668), radius=42, fill="#19191C")
    draw.rounded_rectangle((610, 88, 1188, 146), radius=20, fill="#F66048")

    cat = source.crop((100, 0, 925, 765))
    cat.thumbnail((570, 610), Image.Resampling.LANCZOS)
    canvas.paste(cat, (58, 65))

    font_bold = _font_path(font_dir, DEFAULT_FONT)
    font_black = _font_path(font_dir, DEFAULT_FONT_BLACK)
    kicker = ImageFont.truetype(font_bold, 30)
    title = ImageFont.truetype(font_black, 73)
    subtitle = ImageFont.truetype(font_bold, 35)
    author = ImageFont.truetype(font_bold, 29)

    draw.text(
        (899, 116),
        "SQA DAYS",
        font=kicker,
        fill="white",
        anchor="mm",
    )
    draw.multiline_text(
        (650, 205),
        "ДУХ\nМЕТОДОЛОГА",
        font=title,
        fill="white",
        spacing=-5,
    )
    draw.multiline_text(
        (653, 420),
        "ДЕМОНСТРАЦИОННЫЙ\nTELEGRAM-БОТ",
        font=subtitle,
        fill="#F66048",
        spacing=8,
    )
    draw.line((653, 548, 1155, 548), fill="#49494E", width=3)
    draw.text(
        (653, 580),
        "Доклад Сергея Лебедева",
        font=author,
        fill="#D8D8DC",
    )
    canvas.save(destination, format="PNG", optimize=True)


def _font_path(font_dir: Path | None, fallback: Path) -> Path:
    if font_dir:
        candidate = font_dir / fallback.name
        if candidate.exists():
            return candidate
    if not fallback.exists():
        raise FileNotFoundError(
            f"Шрифт {fallback} не найден. Передайте --font-dir с Arial Bold.ttf "
            "и Arial Black.ttf."
        )
    return fallback


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--font-dir", type=Path)
    args = parser.parse_args()

    destination_dir = ROOT_DIR / "assets"
    destination_dir.mkdir(parents=True, exist_ok=True)
    source = Image.open(args.source).convert("RGB")
    build_avatar(source, destination_dir / "avatar.png")
    build_avatar(source, destination_dir / "avatar.jpg")
    build_cover(source, destination_dir / "start-cover.png", args.font_dir)
    print(f"Created assets in {destination_dir}")


if __name__ == "__main__":
    main()
