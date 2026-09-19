from pathlib import Path

from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_brand_asset_dimensions() -> None:
    avatar = Image.open(ROOT_DIR / "assets/avatar.png")
    telegram_avatar = Image.open(ROOT_DIR / "assets/avatar.jpg")
    cover = Image.open(ROOT_DIR / "assets/start-cover.png")

    assert avatar.size == (512, 512)
    assert telegram_avatar.size == (512, 512)
    assert telegram_avatar.format == "JPEG"
    assert cover.size == (1280, 720)
