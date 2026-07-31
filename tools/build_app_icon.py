from __future__ import annotations

import io
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pygame

from aygeography.ui.components import BG, draw_logo


ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
OUTPUT_PATH = ROOT / "assets" / "app_icon.ico"
PREVIEW_PATH = ROOT / "assets" / "app_icon.png"
ICON_CANVAS_SIZE = 1600
ICON_RADIUS = 790
LOGO_RADIUS = 740


def _alpha_centroid(surface: pygame.Surface) -> tuple[float, float]:
    """Return the visual centre of a transparent logo by alpha weight."""
    weighted_x = 0
    weighted_y = 0
    total_alpha = 0
    for y in range(surface.get_height()):
        for x in range(surface.get_width()):
            alpha = surface.get_at((x, y)).a
            weighted_x += x * alpha
            weighted_y += y * alpha
            total_alpha += alpha
    if total_alpha == 0:
        return surface.get_width() / 2, surface.get_height() / 2
    return weighted_x / total_alpha, weighted_y / total_alpha


def _render_logo() -> pygame.Surface:
    canvas = pygame.Surface((ICON_CANVAS_SIZE, ICON_CANVAS_SIZE), pygame.SRCALPHA)
    canvas_center = pygame.Vector2(ICON_CANVAS_SIZE / 2)
    pygame.draw.circle(canvas, BG, canvas_center, ICON_RADIUS)

    source = pygame.image.load(ROOT / "assets" / "logo.png")
    visual_center = pygame.Vector2(_alpha_centroid(source))
    source_center = pygame.Vector2(source.get_width(), source.get_height()) / 2
    scale = LOGO_RADIUS * 2 / source.get_width()
    logo_center = canvas_center + (source_center - visual_center) * scale
    draw_logo(canvas, logo_center, LOGO_RADIUS)
    return canvas


def _png_bytes(surface: pygame.Surface) -> bytes:
    output = io.BytesIO()
    pygame.image.save(surface, output, ".png")
    return output.getvalue()


def _build_ico(images: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(images))
    directory_size = 6 + 16 * len(images)
    entries: list[bytes] = []
    payloads: list[bytes] = []
    offset = directory_size
    for size, payload in images:
        dimension = 0 if size == 256 else size
        entries.append(
            struct.pack(
                "<BBBBHHII",
                dimension,
                dimension,
                0,
                0,
                1,
                32,
                len(payload),
                offset,
            )
        )
        payloads.append(payload)
        offset += len(payload)
    return header + b"".join(entries) + b"".join(payloads)


def main() -> None:
    pygame.init()
    try:
        logo = _render_logo()
        rendered = {
            size: pygame.transform.smoothscale(logo, (size, size))
            for size in ICON_SIZES
        }
        images = [(size, _png_bytes(rendered[size])) for size in ICON_SIZES]
        OUTPUT_PATH.write_bytes(_build_ico(images))
        pygame.image.save(rendered[256], PREVIEW_PATH)
    finally:
        pygame.quit()
    print(f"Готово: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
