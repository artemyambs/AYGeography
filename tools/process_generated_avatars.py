from pathlib import Path

from PIL import Image, ImageDraw


def add_badge_alpha(path: Path) -> None:
    image = Image.open(path).convert("RGBA")
    rim_points = [
        (x, y)
        for y in range(image.height)
        for x in range(image.width)
        if (colour := image.getpixel((x, y)))[0] < 100
        and colour[1] > 115
        and colour[2] > 115
    ]
    if not rim_points:
        raise ValueError(f"Не найден бирюзовый обод: {path}")
    bounds = (
        max(0, min(x for x, _ in rim_points) - 3),
        max(0, min(y for _, y in rim_points) - 3),
        min(image.width - 1, max(x for x, _ in rim_points) + 3),
        min(image.height - 1, max(y for _, y in rim_points) + 3),
    )
    mask = Image.new("L", (image.width * 4, image.height * 4), 0)
    ImageDraw.Draw(mask).ellipse(tuple(value * 4 for value in bounds), fill=255)
    image.putalpha(mask.resize(image.size, Image.Resampling.LANCZOS))
    image.save(path, optimize=True)


if __name__ == "__main__":
    avatar_dir = Path(__file__).resolve().parent.parent / "assets" / "avatars"
    for avatar_path in sorted(avatar_dir.glob("avatar_*.png")):
        add_badge_alpha(avatar_path)
