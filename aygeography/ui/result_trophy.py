from __future__ import annotations

import math
from functools import lru_cache

import pygame

from .components import blit_image, physical_rect


TROPHY_EFFECT_KEYS = frozenset({"none", "radiant"})
_RADIANT_FRAME_COUNT = 16


def draw_result_trophy(
    surface: pygame.Surface,
    trophy: pygame.Surface,
    rect: pygame.Rect,
    effect_key: str,
    elapsed_seconds: float,
) -> None:
    if effect_key not in TROPHY_EFFECT_KEYS:
        raise ValueError(f"Неизвестный эффект кубка: {effect_key}")

    destination = rect.copy()
    if effect_key == "radiant":
        bounds = physical_rect(surface, rect.inflate(110, 110))
        frame = int(elapsed_seconds * 12) % _RADIANT_FRAME_COUNT
        surface.blit(_radiant_frame(bounds.size, frame), bounds)
        pulse = (math.sin(elapsed_seconds * 2.6) + 1) / 2
        growth = round(pulse * 5)
        destination.inflate_ip(growth, growth)
        destination.y += round(math.sin(elapsed_seconds * 2.1) * 3)

    blit_image(surface, trophy, destination)


@lru_cache(maxsize=32)
def _radiant_frame(size: tuple[int, int], frame: int) -> pygame.Surface:
    layer = pygame.Surface(size, pygame.SRCALPHA)
    center = pygame.Vector2(size[0] / 2, size[1] / 2)
    progress = frame / _RADIANT_FRAME_COUNT
    pulse = (math.sin(progress * math.tau) + 1) / 2
    maximum_radius = min(size) * 0.46

    for step in range(18, 0, -1):
        ratio = step / 18
        radius = round(maximum_radius * ratio)
        alpha = round((5 + 17 * pulse) * (1 - ratio * 0.72))
        pygame.draw.circle(layer, (255, 190, 45, alpha), center, radius)

    ray_offset = progress * math.tau / 12
    for index in range(12):
        angle = ray_offset + index * math.tau / 12
        inner_radius = maximum_radius * 0.61
        outer_radius = maximum_radius * (0.87 + 0.07 * (index % 2))
        start = center + pygame.Vector2(
            math.cos(angle) * inner_radius,
            math.sin(angle) * inner_radius,
        )
        end = center + pygame.Vector2(
            math.cos(angle) * outer_radius,
            math.sin(angle) * outer_radius,
        )
        pygame.draw.line(
            layer,
            (255, 211, 91, round(35 + 45 * pulse)),
            start,
            end,
            max(1, round(min(size) / 220)),
        )
    return layer
