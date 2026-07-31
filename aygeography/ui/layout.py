from __future__ import annotations

import pygame

from ..config import ASSETS_DIR
from .components import (
    CYAN_DARK,
    FOOTER_HEIGHT,
    LOGICAL_SIZE,
    PANEL,
    SIDEBAR_WIDTH,
    blit_image,
    panel,
    render_scale,
)

CONTENT = pygame.Rect(
    SIDEBAR_WIDTH,
    0,
    LOGICAL_SIZE[0] - SIDEBAR_WIDTH,
    LOGICAL_SIZE[1] - FOOTER_HEIGHT,
)
GAMEPLAY_AREA = pygame.Rect(
    CONTENT.left,
    70,
    CONTENT.width,
    CONTENT.height - 70,
)
PAGE_TITLE_FONT_SIZE = 27
PRIMARY_ACTION_SIZE = (270, 52)
PRIMARY_ACTION_FONT_SIZE = 19
QUESTION_FLAG_IMAGE_SIZE = (280, 180)
QUESTION_FLAG_PANEL_SIZE = (300, 200)
CAPITAL_LABEL_FONT_SIZE = 26


def primary_action_rect(center_x: int, top: int) -> pygame.Rect:
    rect = pygame.Rect((0, top), PRIMARY_ACTION_SIZE)
    rect.centerx = center_x
    return rect


def blit_centered(
    surface: pygame.Surface,
    image: pygame.Surface,
    center: tuple[int, int],
    size: tuple[int, int] | None = None,
) -> pygame.Rect:
    if size is None:
        scale = render_scale(surface)
        size = (
            max(1, round(image.get_width() / scale)),
            max(1, round(image.get_height() / scale)),
        )
    rect = pygame.Rect((0, 0), size)
    rect.center = center
    return blit_image(surface, image, rect)


def draw_question_flag(
    surface: pygame.Surface,
    app,
    iso3: str,
    center: tuple[int, int],
) -> pygame.Rect:
    flag_panel = pygame.Rect((0, 0), QUESTION_FLAG_PANEL_SIZE)
    flag_panel.center = center
    panel(
        surface,
        flag_panel,
        fill=PANEL,
        border=CYAN_DARK,
        radius=7,
    )
    flag_path = ASSETS_DIR / "flags_png" / f"{iso3}.png"
    flag = app.assets.image(flag_path)
    blit_centered(surface, flag, flag_panel.center, QUESTION_FLAG_IMAGE_SIZE)
    return flag_panel
