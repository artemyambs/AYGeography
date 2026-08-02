from __future__ import annotations

import pygame

from ..config import ASSETS_DIR
from .components import (
    CYAN_DARK,
    FONT_SIZES,
    FOOTER_HEIGHT,
    LOGICAL_SIZE,
    PANEL,
    SIDEBAR_WIDTH,
    UI_THEME,
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
PAGE_TITLE_FONT_SIZE = FONT_SIZES["page_title"]
PRIMARY_ACTION_SIZE = UI_THEME.component_size("button")
PRIMARY_ACTION_FONT_SIZE = FONT_SIZES[
    str(UI_THEME.component("button")["font_size"])
]
QUESTION_FLAG_STYLE = UI_THEME.component("question_flag")
QUESTION_FLAG_IMAGE_SIZE = tuple(QUESTION_FLAG_STYLE["image_size"])
QUESTION_FLAG_PANEL_SIZE = tuple(QUESTION_FLAG_STYLE["panel_size"])
COUNTRY_FLAG_NAME_TOP = 142
COUNTRY_FLAG_NAME_FONT_SIZE = FONT_SIZES["country_name"]
COUNTRY_FLAG_CENTER_Y = 300
CAPITAL_LABEL_FONT_SIZE = FONT_SIZES["capital_label"]


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
