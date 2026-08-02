from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import pygame

from ..config import ASSETS_DIR, COLORS, UI_SETTINGS
from ..domain.questions import MapOverlay
from ..waters import WaterCatalog
from .theme import UITheme

class FontToken(int):
    """Integer-compatible semantic reference to a configured font size."""

    role: str

    def __new__(cls, value: int, role: str) -> FontToken:
        instance = int.__new__(cls, value)
        instance.role = role
        return instance


UI_THEME = UITheme.from_settings({**UI_SETTINGS, "colours": COLORS})
LAYOUT_STYLE = UI_THEME.layout
TYPOGRAPHY_STYLE = UI_THEME.typography
FONT_SIZES: dict[str, FontToken] = {
    str(name): FontToken(int(value), str(name))
    for name, value in TYPOGRAPHY_STYLE["sizes"].items()
}
PANEL_STYLE = UI_THEME.component("panel")
BUTTON_STYLE = UI_THEME.component("button")
CHECKBOX_STYLE = UI_THEME.component("checkbox")
NAVIGATION_STYLE = UI_THEME.component("navigation")

LOGICAL_SIZE = tuple(int(value) for value in LAYOUT_STYLE["logical_size"])
SIDEBAR_WIDTH = int(LAYOUT_STYLE["sidebar_width"])
FOOTER_HEIGHT = int(LAYOUT_STYLE["footer_height"])
FONT_SCALE = float(TYPOGRAPHY_STYLE["scale"])
FONT_FAMILY = str(TYPOGRAPHY_STYLE["family"])

BG = pygame.Color(COLORS["background"])
SIDEBAR = pygame.Color(COLORS["sidebar"])
PANEL = pygame.Color(COLORS["panel"])
PANEL_ALT = pygame.Color(COLORS["panel_alt"])
BORDER = pygame.Color(COLORS["border"])
TEXT = pygame.Color(COLORS["text"])
MUTED = pygame.Color(COLORS["muted"])
CYAN = pygame.Color(COLORS["cyan"])
CYAN_DARK = pygame.Color(COLORS["cyan_dark"])
GREEN = pygame.Color(COLORS["green"])
GREEN_DARK = pygame.Color(COLORS["green_dark"])
YELLOW = pygame.Color(COLORS["yellow"])
RED = pygame.Color(COLORS["red"])
WATER = pygame.Color(COLORS["water"])
MAP_FILL = pygame.Color(COLORS["map"])
MAP_BORDER = pygame.Color(COLORS["map_border"])
SELECTED_PANEL = UI_THEME.colour("selected_panel")
CARD_BACKGROUND = UI_THEME.colour("card_background")
CARD_BORDER = UI_THEME.colour("card_border")
QUESTION_PANEL = UI_THEME.colour("question_panel")
MAP_CONTROL = UI_THEME.colour("map_control")
TOOLTIP = UI_THEME.colour("tooltip")
ACHIEVEMENT_COMPLETE = UI_THEME.colour("achievement_complete")
MAP_SELECTION_FILL = tuple(UI_THEME.colour("map_selection_fill"))
MAP_SELECTION_BORDER = tuple(UI_THEME.colour("map_selection_border"))
RIVER_STYLE = UI_THEME.visualizations["river"]
RIVER_BORDER_WIDTH = int(RIVER_STYLE["border_width"])
RIVER_FILL_WIDTH = int(RIVER_STYLE["fill_width"])
RIVER_CURVE_SAMPLES = int(RIVER_STYLE["curve_samples"])
RIVER_RENDER_SCALE = int(RIVER_STYLE["render_scale"])

_SCALED_IMAGE_CACHE: dict[
    tuple[int, tuple[int, int]],
    tuple[pygame.Surface, pygame.Surface],
] = {}
_COVER_IMAGE_CACHE: dict[
    tuple[int, tuple[int, int]],
    tuple[pygame.Surface, pygame.Surface],
] = {}


def render_scale(surface: pygame.Surface) -> float:
    """Scale from design coordinates to the current physical render target."""
    return surface.get_width() / LOGICAL_SIZE[0]


def physical_length(surface: pygame.Surface, value: float) -> int:
    return max(1, round(value * render_scale(surface)))


def physical_point(
    surface: pygame.Surface,
    point: tuple[float, float],
) -> tuple[int, int]:
    scale = render_scale(surface)
    return round(point[0] * scale), round(point[1] * scale)


def physical_rect(
    surface: pygame.Surface,
    rect: pygame.Rect | tuple[float, float, float, float],
) -> pygame.Rect:
    logical = pygame.Rect(rect)
    scale = render_scale(surface)
    return pygame.Rect(
        round(logical.x * scale),
        round(logical.y * scale),
        max(1, round(logical.width * scale)),
        max(1, round(logical.height * scale)),
    )


def scaled_camera(camera: MapCamera, scale: float) -> MapCamera:
    return MapCamera(camera.zoom, camera.offset * scale)


def blit_image(
    surface: pygame.Surface,
    image: pygame.Surface,
    rect: pygame.Rect,
) -> pygame.Rect:
    destination = physical_rect(surface, rect)
    if image.get_size() == destination.size:
        scaled = image
    else:
        key = (id(image), destination.size)
        cached = _SCALED_IMAGE_CACHE.get(key)
        if cached is None or cached[0] is not image:
            scaled = pygame.transform.smoothscale(image, destination.size)
            if len(_SCALED_IMAGE_CACHE) >= 512:
                _SCALED_IMAGE_CACHE.clear()
            _SCALED_IMAGE_CACHE[key] = (image, scaled)
        else:
            scaled = cached[1]
    surface.blit(scaled, destination)
    return destination


def draw_native_rect(
    surface: pygame.Surface,
    colour,
    rect,
    width: int = 0,
    *,
    border_radius: int = 0,
) -> pygame.Rect:
    return pygame.draw.rect(
        surface,
        colour,
        physical_rect(surface, rect),
        0 if width == 0 else physical_length(surface, width),
        border_radius=physical_length(surface, border_radius)
        if border_radius
        else 0,
    )


def draw_native_line(
    surface: pygame.Surface,
    colour,
    start,
    end,
    width: int = 1,
) -> None:
    pygame.draw.line(
        surface,
        colour,
        physical_point(surface, start),
        physical_point(surface, end),
        physical_length(surface, width),
    )


def draw_native_circle(
    surface: pygame.Surface,
    colour,
    center,
    radius: float,
    width: int = 0,
) -> None:
    pygame.draw.circle(
        surface,
        colour,
        physical_point(surface, center),
        physical_length(surface, radius),
        0 if width == 0 else physical_length(surface, width),
    )


def draw_native_polygon(
    surface: pygame.Surface,
    colour,
    points,
    width: int = 0,
) -> None:
    pygame.draw.polygon(
        surface,
        colour,
        [physical_point(surface, point) for point in points],
        0 if width == 0 else physical_length(surface, width),
    )


def draw_native_lines(
    surface: pygame.Surface,
    colour,
    closed: bool,
    points,
    width: int = 1,
    *,
    antialiased: bool = False,
) -> None:
    physical = [physical_point(surface, point) for point in points]
    if antialiased:
        pygame.draw.aalines(surface, colour, closed, physical)
    else:
        pygame.draw.lines(
            surface,
            colour,
            closed,
            physical,
            physical_length(surface, width),
        )


def draw_native_ellipse(
    surface: pygame.Surface,
    colour,
    rect,
    width: int = 0,
) -> None:
    pygame.draw.ellipse(
        surface,
        colour,
        physical_rect(surface, rect),
        0 if width == 0 else physical_length(surface, width),
    )


def draw_native_arc(
    surface: pygame.Surface,
    colour,
    rect,
    start_angle: float,
    stop_angle: float,
    width: int = 1,
) -> None:
    pygame.draw.arc(
        surface,
        colour,
        physical_rect(surface, rect),
        start_angle,
        stop_angle,
        physical_length(surface, width),
    )


def draw_progress_ring(
    surface: pygame.Surface,
    center: tuple[int, int],
    radius: int,
    progress_percent: float,
    colour: pygame.Color,
    track_colour: pygame.Color,
    width: int = 5,
) -> None:
    progress = max(0.0, min(100.0, progress_percent))
    draw_native_circle(surface, track_colour, center, radius, width)
    if progress == 0:
        return
    if progress == 100:
        draw_native_circle(surface, colour, center, radius, width)
        return

    sweep = math.tau * progress / 100
    diameter = radius * 2
    draw_native_arc(
        surface,
        colour,
        (center[0] - radius, center[1] - radius, diameter, diameter),
        math.pi / 2 - sweep,
        math.pi / 2,
        width,
    )


@lru_cache(maxsize=128)
def font(size: int, bold: bool = False) -> pygame.font.Font:
    scaled_size = max(size + 1, round(size * FONT_SCALE))
    return pygame.font.SysFont(FONT_FAMILY, scaled_size, bold=bold)


def configured_font_size(size: int | FontToken) -> int:
    if isinstance(size, FontToken):
        return int(size)
    legacy_roles = TYPOGRAPHY_STYLE["legacy_size_roles"]
    try:
        return UI_THEME.font_size(str(legacy_roles[str(size)]))
    except KeyError as error:
        raise ValueError(f"Размер текста {size} не зарегистрирован в UI-конфиге") from error


def draw_text(
    surface: pygame.Surface,
    value: str,
    position: tuple[int, int],
    size: int = FONT_SIZES["primary_action"],
    colour: pygame.Color = TEXT,
    *,
    bold: bool = False,
    anchor: str = "topleft",
) -> pygame.Rect:
    size = configured_font_size(size)
    scale = render_scale(surface)
    image = font(max(1, round(size * scale)), bold).render(value, True, colour)
    rect = image.get_rect()
    setattr(rect, anchor, physical_point(surface, position))
    surface.blit(image, rect)
    return rect


def draw_multiline(
    surface: pygame.Surface,
    value: str,
    rect: pygame.Rect,
    size: int,
    colour: pygame.Color = TEXT,
    *,
    bold: bool = False,
    align: str = "center",
    line_gap: int = 4,
) -> None:
    size = configured_font_size(size)
    scale = render_scale(surface)
    target_rect = physical_rect(surface, rect)
    lines = value.splitlines()
    fitted_size = size
    available_width = max(1, target_rect.width - physical_length(surface, 24))
    minimum_size = int(TYPOGRAPHY_STYLE["minimum_fitted_size"])
    while fitted_size > minimum_size:
        images = [
            font(max(1, round(fitted_size * scale)), bold).render(
                line,
                True,
                colour,
            )
            for line in lines
        ]
        if all(image.get_width() <= available_width for image in images):
            break
        fitted_size -= 1
    else:
        images = [
            font(max(1, round(fitted_size * scale)), bold).render(
                line,
                True,
                colour,
            )
            for line in lines
        ]
    physical_gap = physical_length(surface, line_gap)
    total = (
        sum(image.get_height() for image in images)
        + physical_gap * (len(images) - 1)
    )
    y = target_rect.centery - total // 2
    for image in images:
        x = {
            "left": target_rect.left,
            "center": target_rect.centerx - image.get_width() // 2,
            "right": target_rect.right - image.get_width(),
        }[align]
        surface.blit(image, (x, y))
        y += image.get_height() + physical_gap


def panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    *,
    fill: pygame.Color = PANEL,
    border: pygame.Color = BORDER,
    radius: int = int(PANEL_STYLE["corner_radius"]),
    width: int = int(PANEL_STYLE["border_width"]),
) -> None:
    draw_native_rect(surface, fill, rect, border_radius=radius)
    draw_native_rect(
        surface,
        border,
        rect,
        width=width,
        border_radius=radius,
    )


def draw_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    *,
    primary: bool = False,
    danger: bool = False,
    selected: bool = False,
    disabled: bool = False,
    hovered: bool = False,
    size: int = FONT_SIZES["button_default"],
    bold: bool = False,
    fill_colour: pygame.Color | None = None,
    border_colour: pygame.Color | None = None,
) -> None:
    if primary:
        variant_name = "primary_hover" if hovered else "primary"
    elif danger:
        variant_name = "danger_hover" if hovered else "danger"
    elif selected:
        variant_name = "selected"
    else:
        variant_name = "hover" if hovered else "normal"
    variant = BUTTON_STYLE[variant_name]
    fill = UI_THEME.colour(str(variant["fill"]))
    border = UI_THEME.colour(str(variant["border"]))
    if disabled:
        variant = BUTTON_STYLE["disabled"]
        fill = UI_THEME.colour(str(variant["fill"]))
        border = UI_THEME.colour(str(variant["border"]))
    else:
        fill = fill if fill_colour is None else fill_colour
        border = border if border_colour is None else border_colour
    panel(
        surface,
        rect,
        fill=fill,
        border=border,
        radius=int(BUTTON_STYLE["corner_radius"]),
        width=int(BUTTON_STYLE["border_width"]),
    )
    draw_multiline(
        surface,
        label,
        rect,
        size,
        UI_THEME.colour(str(variant["text"])),
        bold=bold or primary or danger or selected,
    )


def pygame_gui_theme() -> dict[str, object]:
    """Transparent interaction widgets styled from the shared UI config."""
    transparent = str(UI_THEME.colours["transparent"])
    hidden_colours = {
        key: transparent
        for key in (
            "normal_bg",
            "hovered_bg",
            "disabled_bg",
            "selected_bg",
            "active_bg",
            "normal_text",
            "hovered_text",
            "selected_text",
            "disabled_text",
            "normal_border",
            "hovered_border",
            "active_border",
        )
    }
    hidden_entry_colours = {
        key: transparent
        for key in (
            "dark_bg",
            "normal_text",
            "selected_text",
            "selected_bg",
            "normal_border",
            "text_cursor",
        )
    }
    radius = str(BUTTON_STYLE["corner_radius"])
    return {
        "#hitbox": {
            "colours": hidden_colours,
            "misc": {
                "shape": "rounded_rectangle",
                "shape_corner_radius": radius,
                "border_width": "0",
                "shadow_width": "0",
            },
        },
        "#profile_entry": {
            "colours": hidden_entry_colours,
            "font": {
                "name": FONT_FAMILY,
                "size": str(FONT_SIZES["country_card_title"]),
            },
            "misc": {
                "shape": "rounded_rectangle",
                "shape_corner_radius": radius,
                "border_width": "0",
                "shadow_width": "0",
            },
        },
    }


def draw_document_icon(
    surface: pygame.Surface,
    center: tuple[int, int],
    colour: pygame.Color = TEXT,
    scale: float = 1.0,
) -> None:
    x, y = physical_point(surface, center)
    scale *= render_scale(surface)
    rect = pygame.Rect(x - 24 * scale, y - 31 * scale, 48 * scale, 62 * scale)
    pygame.draw.rect(surface, colour, rect, max(2, round(3 * scale)), border_radius=round(3 * scale))
    pygame.draw.polygon(
        surface,
        colour,
        [(x + 5 * scale, y - 31 * scale), (x + 24 * scale, y - 12 * scale), (x + 5 * scale, y - 12 * scale)],
        max(2, round(3 * scale)),
    )
    for offset in (-2, 10, 22):
        pygame.draw.line(
            surface,
            colour,
            (x - 13 * scale, y + offset * scale),
            (x + 13 * scale, y + offset * scale),
            max(1, round(2 * scale)),
        )


def draw_question_count_icon(
    surface: pygame.Surface,
    center: tuple[int, int],
    count: int,
    colour: pygame.Color = CYAN,
) -> None:
    """Crisp scalable card stack whose depth reflects round length."""
    layers = {10: 1, 25: 2, 50: 3, 100: 4}[count]
    x, y = center
    for layer in reversed(range(layers)):
        offset = layer * 4
        card = pygame.Rect(x - 28 - offset, y - 31 + offset, 54, 62)
        draw_native_rect(
            surface,
            PANEL_ALT,
            card,
            border_radius=5,
        )
        draw_native_rect(
            surface,
            colour,
            card,
            2,
            border_radius=5,
        )
    front = pygame.Rect(x - 28, y - 31, 54, 62)
    progress_width = round(36 * count / 100)
    for line_index in range(3):
        line_y = front.top + 15 + line_index * 11
        draw_native_circle(surface, colour, (front.left + 11, line_y), 2)
        draw_native_line(
            surface,
            colour,
            (front.left + 18, line_y),
            (front.right - 9, line_y),
            2,
        )
    draw_native_rect(
        surface,
        UI_THEME.colour("progress_track"),
        (front.left + 9, front.bottom - 11, 36, 4),
        border_radius=2,
    )
    draw_native_rect(
        surface,
        GREEN,
        (front.left + 9, front.bottom - 11, progress_width, 4),
        border_radius=2,
    )


def draw_checkbox(
    surface: pygame.Surface,
    rect: pygame.Rect,
    selected: bool,
) -> None:
    """Единый чекбокс без внешнего свечения для всех экранов выбора."""
    rect = physical_rect(surface, rect)
    scale = render_scale(surface)
    if selected:
        pygame.draw.rect(
            surface,
            GREEN_DARK,
            rect,
            border_radius=max(1, round(int(CHECKBOX_STYLE["corner_radius"]) * scale)),
        )
        pygame.draw.rect(
            surface,
            GREEN,
            rect,
            max(1, round(int(CHECKBOX_STYLE["border_width"]) * scale)),
            border_radius=max(1, round(int(CHECKBOX_STYLE["corner_radius"]) * scale)),
        )
        points = [
            (rect.left + rect.width * 0.23, rect.top + rect.height * 0.53),
            (rect.left + rect.width * 0.43, rect.top + rect.height * 0.72),
            (rect.left + rect.width * 0.78, rect.top + rect.height * 0.29),
        ]
        pygame.draw.aalines(surface, TEXT, False, points)
        pygame.draw.lines(
            surface,
            TEXT,
            False,
            points,
            max(1, round(int(CHECKBOX_STYLE["check_width"]) * scale)),
        )
    else:
        pygame.draw.rect(
            surface,
            UI_THEME.colour("checkbox_background"),
            rect,
            border_radius=max(1, round(int(CHECKBOX_STYLE["corner_radius"]) * scale)),
        )
        pygame.draw.rect(
            surface,
            UI_THEME.colour("checkbox_border"),
            rect,
            max(1, round(int(CHECKBOX_STYLE["border_width"]) * scale)),
            border_radius=max(1, round(int(CHECKBOX_STYLE["corner_radius"]) * scale)),
        )


@lru_cache(maxsize=1)
def _logo_source() -> pygame.Surface:
    return pygame.image.load(ASSETS_DIR / "logo.png")


def draw_logo(
    surface: pygame.Surface,
    center: tuple[int, int],
    radius: int = 48,
) -> None:
    size = max(1, round(radius * 2 * render_scale(surface)))
    logo = pygame.transform.smoothscale(
        _logo_source(),
        (size, size),
    )
    x, y = physical_point(surface, center)
    surface.blit(logo, logo.get_rect(center=(x, y)))


def _nav_icon(surface: pygame.Surface, name: str, center: tuple[int, int], colour: pygame.Color) -> None:
    x, y = center
    if name == "game":
        draw_native_rect(
            surface,
            colour,
            (x - 10, y - 6, 20, 12),
            2,
            border_radius=4,
        )
        draw_native_line(surface, colour, (x - 4, y), (x + 4, y), 2)
        draw_native_line(surface, colour, (x, y - 4), (x, y + 4), 2)
        draw_native_circle(surface, colour, (x + 6, y - 1), 2)
    elif name == "statistics":
        for index, height in enumerate((7, 13, 18)):
            draw_native_rect(
                surface,
                colour,
                (x - 10 + index * 7, y + 9 - height, 4, height),
                border_radius=1,
            )
    elif name in {"achievements", "mastery"}:
        for index, height in enumerate((6, 12, 19)):
            x_position = x - 10 + index * 8
            draw_native_line(
                surface,
                colour,
                (x_position, y + 9),
                (x_position, y + 9 - height),
                2,
            )
        draw_native_line(surface, colour, (x - 11, y + 9), (x + 11, y + 9), 2)
    elif name == "profile":
        draw_native_circle(surface, colour, (x, y - 5), 6)
        draw_native_arc(
            surface,
            colour,
            (x - 11, y + 1, 22, 14),
            math.pi,
            math.tau,
            2,
        )
    elif name == "settings":
        draw_native_circle(surface, colour, (x, y), 9, 2)
        draw_native_circle(surface, colour, (x, y), 3, 2)
        for angle in range(0, 360, 45):
            dx, dy = math.cos(math.radians(angle)) * 13, math.sin(math.radians(angle)) * 13
            draw_native_line(
                surface,
                colour,
                (x + dx * .7, y + dy * .7),
                (x + dx, y + dy),
                3,
            )
    else:
        draw_native_rect(
            surface,
            colour,
            (x - 8, y - 10, 14, 20),
            2,
            border_radius=2,
        )
        draw_native_line(surface, colour, (x - 1, y), (x + 11, y), 2)
        draw_native_line(surface, colour, (x + 6, y - 5), (x + 11, y), 2)
        draw_native_line(surface, colour, (x + 6, y + 5), (x + 11, y), 2)


NAV_ITEMS = [
    ("game", "Игра"),
    ("atlas", "Атлас мира"),
    ("statistics", "Статистика"),
    ("achievements", "Достижения"),
    ("mastery", "Прогресс"),
    ("profile", "Профиль"),
    ("settings", "Настройки"),
    ("exit", "Выход"),
]


def navigation_item_rect(index: int) -> pygame.Rect:
    margin = int(NAVIGATION_STYLE["horizontal_margin"])
    height = int(NAVIGATION_STYLE["item_height"])
    pitch = height + int(NAVIGATION_STYLE["item_gap"])
    return pygame.Rect(
        margin,
        int(NAVIGATION_STYLE["item_top"]) + index * pitch,
        SIDEBAR_WIDTH - margin * 2,
        height,
    )


def navigation_profile_rect() -> pygame.Rect:
    margin = int(NAVIGATION_STYLE["horizontal_margin"])
    return pygame.Rect(
        margin,
        int(NAVIGATION_STYLE["profile_top"]),
        SIDEBAR_WIDTH - margin * 2,
        int(NAVIGATION_STYLE["profile_height"]),
    )


def draw_sidebar(
    surface: pygame.Surface,
    active: str,
    profile: dict[str, object],
    avatar: pygame.Surface | None = None,
    icon_provider=None,
) -> None:
    draw_native_rect(
        surface,
        SIDEBAR,
        (0, 0, SIDEBAR_WIDTH, LOGICAL_SIZE[1] - FOOTER_HEIGHT),
    )
    draw_native_line(
        surface,
        BORDER,
        (SIDEBAR_WIDTH, 0),
        (SIDEBAR_WIDTH, LOGICAL_SIZE[1] - FOOTER_HEIGHT),
    )
    draw_logo(surface, (SIDEBAR_WIDTH // 2, 74), 47)
    for index, (key, label) in enumerate(NAV_ITEMS):
        rect = navigation_item_rect(index)
        selected = key == active
        if selected:
            corner_radius = int(NAVIGATION_STYLE["corner_radius"])
            draw_native_rect(surface, GREEN_DARK, rect, border_radius=corner_radius)
            draw_native_rect(surface, GREEN, rect, 1, border_radius=corner_radius)
        colour = TEXT if selected else UI_THEME.colour("navigation_text")
        if icon_provider:
            icon = icon_provider(key, (27, 27))
            icon_rect = pygame.Rect(0, 0, 27, 27)
            icon_rect.center = (35, rect.centery)
            blit_image(surface, icon, icon_rect)
        else:
            _nav_icon(surface, key, (35, rect.centery), colour)
        draw_text(
            surface,
            label,
            (58, rect.centery),
            FONT_SIZES["body"],
            colour,
            bold=True,
            anchor="midleft",
        )
    profile_card = navigation_profile_rect()
    panel(
        surface,
        profile_card,
        fill=UI_THEME.colour("profile_panel"),
        border=UI_THEME.colour("profile_border"),
        radius=8,
    )
    if avatar:
        blit_image(surface, avatar, pygame.Rect(20, 754, 50, 50))
    else:
        draw_native_circle(surface, CYAN_DARK, (45, 779), 24)
    nickname = str(profile.get("nickname", "ExplorerAY"))
    xp = int(profile.get("xp", 0))
    level = int(profile.get("level", 1))
    required_xp = max(1, int(profile.get("required_xp", 1000)))
    title = str(profile.get("title", "Новичок"))
    draw_text(surface, nickname, (79, 754), FONT_SIZES["secondary"], TEXT, bold=True)
    draw_text(surface, title, (79, 778), FONT_SIZES["micro"], GREEN, bold=True)
    draw_text(surface, f"Уровень {level}", (20, 811), FONT_SIZES["small"], MUTED)
    draw_text(
        surface,
        f"{xp:,} / {required_xp:,} XP".replace(",", " "),
        (profile_card.right - 9, 811),
        FONT_SIZES["micro"],
        MUTED,
        anchor="topright",
    )
    draw_native_rect(
        surface,
        PANEL_ALT,
        (20, 830, profile_card.width - 16, 5),
        border_radius=3,
    )
    draw_native_rect(
        surface,
        CYAN,
        (
            20,
            830,
            int((profile_card.width - 16) * min(1.0, xp / required_xp)),
            5,
        ),
        border_radius=3,
    )


def draw_footer(surface: pygame.Surface, icon_provider=None) -> None:
    rect = pygame.Rect(0, LOGICAL_SIZE[1] - FOOTER_HEIGHT, LOGICAL_SIZE[0], FOOTER_HEIGHT)
    draw_native_rect(surface, SIDEBAR, rect)
    draw_native_line(surface, BORDER, rect.topleft, rect.topright)
    draw_text(surface, "AY", (18, rect.centery), FONT_SIZES["footer"], CYAN, bold=True, anchor="midleft")
    draw_text(surface, "Geography", (40, rect.centery), FONT_SIZES["footer"], TEXT, anchor="midleft")
    draw_text(surface, "v1.0.0", (128, rect.centery), FONT_SIZES["caption"], MUTED, anchor="midleft")
    draw_text(
        surface,
        "Developed by Artem Yambs.",
        (LOGICAL_SIZE[0] - 50, rect.centery),
        12,
        MUTED,
        anchor="midright",
    )
    if icon_provider:
        icon = icon_provider("countries", (24, 24))
        icon_rect = pygame.Rect(0, 0, 24, 24)
        icon_rect.midright = (LOGICAL_SIZE[0] - 12, rect.centery)
        blit_image(surface, icon, icon_rect)


@dataclass(slots=True)
class MapCamera:
    zoom: float = 1.0
    offset: pygame.Vector2 = field(default_factory=pygame.Vector2)

    def reset(self) -> None:
        self.zoom = 1.0
        self.offset.update(0, 0)

    def pan(self, dx: float, dy: float) -> None:
        self.offset.x += dx
        self.offset.y += dy

    def zoom_by(
        self,
        factor: float,
        rect: pygame.Rect,
        focus: tuple[int, int] | None = None,
    ) -> None:
        old_zoom = self.zoom
        new_zoom = max(0.65, min(16.0, old_zoom * factor))
        if math.isclose(old_zoom, new_zoom):
            return
        if focus is not None:
            relative = pygame.Vector2(focus) - pygame.Vector2(rect.center) - self.offset
            base = relative / old_zoom
            projected = base * new_zoom
            self.offset = pygame.Vector2(focus) - pygame.Vector2(rect.center) - projected
        self.zoom = new_zoom


class MapRenderer:
    def __init__(
        self,
        geometry_path: Path,
        water_catalog: WaterCatalog,
    ) -> None:
        self.water_catalog = water_catalog
        self.geometry: dict[str, list[list[list[float]]]] = json.loads(
            geometry_path.read_text(encoding="utf-8")
        )
        land_path = geometry_path.with_name("land_geometry.json")
        self.land_geometry: list[list[list[float]]] = (
            json.loads(land_path.read_text(encoding="utf-8"))
            if land_path.exists()
            else []
        )
        centers_path = geometry_path.with_name("centers.json")
        self.centers: dict[str, list[float]] = (
            json.loads(centers_path.read_text(encoding="utf-8"))
            if centers_path.exists()
            else {}
        )
        self._cache: dict[tuple[int, int], pygame.Surface] = {}
        self._ring_bounds = {
            iso3: [
                (
                    min(point[0] for point in ring),
                    min(point[1] for point in ring),
                    max(point[0] for point in ring),
                    max(point[1] for point in ring),
                )
                for ring in rings
            ]
            for iso3, rings in self.geometry.items()
        }
        self._country_bounds = {
            iso3: (
                min(bounds[0] for bounds in ring_bounds),
                min(bounds[1] for bounds in ring_bounds),
                max(bounds[2] for bounds in ring_bounds),
                max(bounds[3] for bounds in ring_bounds),
            )
            for iso3, ring_bounds in self._ring_bounds.items()
        }
        self._land_bounds = [
            (
                min(point[0] for point in ring),
                min(point[1] for point in ring),
                max(point[0] for point in ring),
                max(point[1] for point in ring),
            )
            for ring in self.land_geometry
        ]
        self._view_cache_key: tuple | None = None
        self._view_cache: pygame.Surface | None = None
        self._mastery_cache_key: tuple | None = None
        self._mastery_cache: pygame.Surface | None = None
        self._atlas_base_key: tuple | None = None
        self._atlas_base_layers: dict[int, pygame.Surface] = {}
        self._atlas_continents: dict[str, str] = {}
        self._atlas_palette: dict[str, str] = {}
        self._atlas_view_key: tuple | None = None
        self._atlas_view_cache: pygame.Surface | None = None
        self._atlas_highlight_cache: dict[
            tuple, tuple[pygame.Surface, tuple[int, int]]
        ] = {}

    def focus_country(
        self,
        camera: MapCamera,
        iso3: str,
        rect: pygame.Rect,
        zoom: float = 9.0,
    ) -> None:
        center = self.centers.get(iso3)
        if center is None:
            points = [
                point
                for ring in self.geometry.get(iso3, [])
                for point in ring
            ]
            if not points:
                return
            center = [
                (min(point[0] for point in points) + max(point[0] for point in points)) / 2,
                (min(point[1] for point in points) + max(point[1] for point in points)) / 2,
            ]
        self.focus_position(camera, center, rect, zoom)

    @staticmethod
    def focus_position(
        camera: MapCamera,
        position: Iterable[float],
        rect: pygame.Rect,
        zoom: float,
    ) -> None:
        """Centers the camera on geographic coordinates at the requested zoom."""
        longitude, latitude = position
        base = pygame.Vector2(
            rect.left + (longitude + 180.0) / 360.0 * rect.width,
            rect.top + (90.0 - latitude) / 180.0 * rect.height,
        )
        camera.zoom = zoom
        camera.offset = -(base - pygame.Vector2(rect.center)) * zoom

    @staticmethod
    def project(
        point: Iterable[float],
        rect: pygame.Rect,
        camera: MapCamera | None = None,
    ) -> tuple[int, int]:
        lon, lat = point
        base = pygame.Vector2(
            rect.left + (lon + 180.0) / 360.0 * rect.width,
            rect.top + (90.0 - lat) / 180.0 * rect.height,
        )
        if camera is None:
            return round(base.x), round(base.y)
        relative = (base - pygame.Vector2(rect.center)) * camera.zoom
        result = pygame.Vector2(rect.center) + camera.offset + relative
        return round(result.x), round(result.y)

    def _draw_vector_countries(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        camera: MapCamera,
        *,
        highlight_country: str | None = None,
    ) -> None:
        """Рисует исходные полигоны сразу в текущем масштабе без растеризации."""
        viewport = rect.inflate(8, 8)
        default_camera = (
            math.isclose(camera.zoom, 1.0)
            and camera.offset.length_squared() < 0.01
        )
        if default_camera and highlight_country is None:
            surface.blit(self.base_surface(rect.size), rect)
            return

        def projected_bounds(
            bounds: tuple[float, float, float, float],
        ) -> pygame.Rect:
            corners = (
                (bounds[0], bounds[1]),
                (bounds[0], bounds[3]),
                (bounds[2], bounds[1]),
                (bounds[2], bounds[3]),
            )
            projected = [self.project(point, rect, camera) for point in corners]
            left = min(point[0] for point in projected)
            right = max(point[0] for point in projected)
            top = min(point[1] for point in projected)
            bottom = max(point[1] for point in projected)
            return pygame.Rect(left, top, max(1, right - left), max(1, bottom - top))

        for ring, bounds in zip(self.land_geometry, self._land_bounds):
            if not viewport.colliderect(projected_bounds(bounds)):
                continue
            points = [self.project(point, rect, camera) for point in ring]
            if len(points) >= 3:
                pygame.draw.polygon(surface, MAP_FILL, points)
                pygame.draw.aalines(surface, MAP_BORDER, True, points)

        highlighted_polygons: list[list[tuple[int, int]]] = []
        for iso3, rings in self.geometry.items():
            if not viewport.colliderect(projected_bounds(self._country_bounds[iso3])):
                continue
            minimum_detail = 5 if camera.zoom < 2.0 else 2
            for ring, bounds in zip(rings, self._ring_bounds[iso3]):
                projected_ring = projected_bounds(bounds)
                if (
                    not viewport.colliderect(projected_ring)
                    or (
                        projected_ring.width <= minimum_detail
                        and projected_ring.height <= minimum_detail
                    )
                ):
                    continue
                points = [self.project(point, rect, camera) for point in ring]
                if len(points) >= 3:
                    if iso3 == highlight_country:
                        highlighted_polygons.append(points)
                    pygame.draw.polygon(surface, MAP_FILL, points)
                    pygame.draw.aalines(surface, MAP_BORDER, True, points)

        if highlighted_polygons:
            self._draw_region_selection(
                surface,
                highlighted_polygons,
            )

    @staticmethod
    def _draw_region_selection(
        surface: pygame.Surface,
        polygons: list[list[tuple[int, int]]],
    ) -> None:
        highlight = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for points in polygons:
            pygame.draw.polygon(
                highlight,
                MAP_SELECTION_FILL,
                points,
            )
            pygame.draw.lines(
                highlight,
                MAP_SELECTION_BORDER,
                True,
                points,
                1,
            )
            pygame.draw.aalines(
                highlight,
                MAP_SELECTION_BORDER,
                True,
                points,
            )
        surface.blit(highlight, (0, 0))

    @staticmethod
    def _water_polygon(region, rect: pygame.Rect, camera: MapCamera) -> list[tuple[int, int]]:
        points = []
        for step in range(64):
            angle = math.tau * step / 64
            point = (
                region.longitude + math.cos(angle) * region.radius_x,
                region.latitude + math.sin(angle) * region.radius_y,
            )
            points.append(MapRenderer.project(point, rect, camera))
        return points

    def base_surface(self, size: tuple[int, int]) -> pygame.Surface:
        if size in self._cache:
            return self._cache[size]
        canvas = pygame.Surface(size, pygame.SRCALPHA)
        rect = canvas.get_rect()
        for ring in self.land_geometry:
            points = [self.project(point, rect) for point in ring]
            if len(points) >= 3:
                pygame.draw.polygon(canvas, MAP_FILL, points)
                pygame.draw.aalines(canvas, MAP_BORDER, True, points)
        for rings in self.geometry.values():
            for ring in rings:
                points = [self.project(point, rect) for point in ring]
                if len(points) >= 3:
                    pygame.draw.polygon(canvas, MAP_FILL, points)
                    pygame.draw.aalines(canvas, MAP_BORDER, True, points)
        self._cache[size] = canvas
        return canvas

    def draw_base(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        target = physical_rect(surface, rect)
        surface.blit(self.base_surface(target.size), target)

    def draw(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        *,
        highlight_country: str | None = None,
        highlight_water: str | None = None,
        overlay: MapOverlay | None = None,
        camera: MapCamera | None = None,
    ) -> None:
        camera = camera or MapCamera()
        scale = render_scale(surface)
        target_rect = physical_rect(surface, rect)
        render_camera = scaled_camera(camera, scale)
        cache_key = (
            target_rect.size,
            round(render_camera.zoom, 5),
            round(render_camera.offset.x, 2),
            round(render_camera.offset.y, 2),
            highlight_country,
            highlight_water,
            overlay,
        )
        if cache_key == self._view_cache_key and self._view_cache is not None:
            surface.blit(self._view_cache, target_rect)
            return
        canvas = pygame.Surface(target_rect.size)
        canvas.fill(WATER)
        local_rect = canvas.get_rect()
        grid_step = max(1, round(50 * scale))
        for x in range(0, local_rect.width, grid_step):
            pygame.draw.line(canvas, UI_THEME.colour("chart_grid"), (x, 0), (x, local_rect.height))
        for y in range(0, local_rect.height, grid_step):
            pygame.draw.line(canvas, UI_THEME.colour("chart_grid"), (0, y), (local_rect.width, y))
        self._draw_vector_countries(
            canvas,
            local_rect,
            render_camera,
            highlight_country=highlight_country,
        )
        if highlight_water:
            region = self.water_catalog.get(highlight_water)
            if region is not None:
                points = self._water_polygon(region, local_rect, render_camera)
                self._draw_region_selection(
                    canvas,
                    [points],
                )
        if overlay:
            self._draw_overlay(canvas, local_rect, render_camera, overlay)
        pygame.draw.rect(
            canvas,
            BORDER,
            local_rect,
            max(1, round(scale)),
            border_radius=max(1, round(7 * scale)),
        )
        self._view_cache_key = cache_key
        self._view_cache = canvas
        surface.blit(canvas, target_rect)

    def _draw_overlay(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        camera: MapCamera,
        overlay: MapOverlay,
    ) -> None:
        kind = overlay.kind
        if kind == "point" and overlay.point:
            layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            center = self.project(overlay.point, rect, camera)
            pygame.draw.circle(layer, MAP_SELECTION_BORDER, center, 13)
            pygame.draw.circle(layer, MAP_SELECTION_FILL, center, 11)
            surface.blit(layer, (0, 0))
            return
        if kind != "line":
            return
        layer_size = (
            surface.get_width() * RIVER_RENDER_SCALE,
            surface.get_height() * RIVER_RENDER_SCALE,
        )
        layer = pygame.Surface(layer_size, pygame.SRCALPHA)
        for line in overlay.lines:
            points = [self.project(point, rect, camera) for point in line]
            if len(points) < 2:
                continue
            smooth_points = self._smooth_polyline(points)
            render_points = [
                (
                    round(point[0] * RIVER_RENDER_SCALE),
                    round(point[1] * RIVER_RENDER_SCALE),
                )
                for point in smooth_points
            ]
            self._draw_rounded_polyline(
                layer,
                MAP_SELECTION_BORDER,
                render_points,
                RIVER_BORDER_WIDTH * RIVER_RENDER_SCALE,
            )
            self._draw_rounded_polyline(
                layer,
                MAP_SELECTION_FILL,
                render_points,
                RIVER_FILL_WIDTH * RIVER_RENDER_SCALE,
            )
        surface.blit(
            pygame.transform.smoothscale(layer, surface.get_size()),
            (0, 0),
        )

    @staticmethod
    def _smooth_polyline(
        points: list[tuple[int, int]],
        samples_per_segment: int = RIVER_CURVE_SAMPLES,
    ) -> list[tuple[float, float]]:
        """Interpolate a river through its control points without sharp joints."""
        if len(points) < 3:
            return [(float(x), float(y)) for x, y in points]
        controls = [pygame.Vector2(point) for point in points]
        result = [tuple(controls[0])]
        samples = max(1, samples_per_segment)
        for index in range(len(controls) - 1):
            previous = controls[max(0, index - 1)]
            start = controls[index]
            end = controls[index + 1]
            following = controls[min(len(controls) - 1, index + 2)]
            for step in range(1, samples + 1):
                time = step / samples
                time_squared = time * time
                time_cubed = time_squared * time
                point = 0.5 * (
                    2 * start
                    + (end - previous) * time
                    + (
                        2 * previous
                        - 5 * start
                        + 4 * end
                        - following
                    )
                    * time_squared
                    + (
                        -previous
                        + 3 * start
                        - 3 * end
                        + following
                    )
                    * time_cubed
                )
                result.append((point.x, point.y))
        return result

    @staticmethod
    def _draw_rounded_polyline(
        surface: pygame.Surface,
        colour: tuple[int, int, int, int],
        points: list[tuple[int, int]],
        width: int,
    ) -> None:
        pygame.draw.lines(surface, colour, False, points, width)
        radius = width // 2
        pygame.draw.circle(surface, colour, points[0], radius)
        pygame.draw.circle(surface, colour, points[-1], radius)

    def draw_mastery_map(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        ratings: dict[str, int],
        rating_colors: dict[int, str],
        camera: MapCamera | None = None,
    ) -> None:
        """Draw a cached world map coloured by permanent country mastery."""
        target = physical_rect(surface, rect)
        physical_camera = scaled_camera(
            camera or MapCamera(),
            render_scale(surface),
        )
        key = (
            target.size,
            tuple(sorted(ratings.items())),
            tuple(sorted(rating_colors.items())),
            round(physical_camera.zoom, 4),
            round(physical_camera.offset.x, 2),
            round(physical_camera.offset.y, 2),
        )
        if key != self._mastery_cache_key or self._mastery_cache is None:
            canvas = pygame.Surface(target.size)
            canvas.fill(WATER)
            local = canvas.get_rect()
            for x in range(0, local.width, max(1, local.width // 12)):
                pygame.draw.line(canvas, UI_THEME.colour("chart_grid"), (x, 0), (x, local.height))
            for y in range(0, local.height, max(1, local.height // 6)):
                pygame.draw.line(canvas, UI_THEME.colour("chart_grid"), (0, y), (local.width, y))
            for iso3, rings in self.geometry.items():
                colour = pygame.Color(
                    rating_colors.get(ratings.get(iso3, 0), COLORS["map"])
                )
                for ring in rings:
                    points = [
                        self.project(point, local, physical_camera)
                        for point in ring
                    ]
                    if len(points) >= 3:
                        pygame.draw.polygon(canvas, colour, points)
                        pygame.draw.aalines(canvas, MAP_BORDER, True, points)
            pygame.draw.rect(
                canvas,
                BORDER,
                local,
                1,
                border_radius=7,
            )
            self._mastery_cache_key = key
            self._mastery_cache = canvas
        surface.blit(self._mastery_cache, target)

    def draw_atlas_map(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        continents: dict[str, str],
        camera: MapCamera,
        hovered_country: str | None = None,
    ) -> None:
        palette = dict(UI_THEME.visualizations["atlas_continent_colors"])
        target = physical_rect(surface, rect)
        physical_camera = scaled_camera(camera, render_scale(surface))
        continent_key = tuple(sorted(continents.items()))
        base_key = (target.size, continent_key)
        if base_key != self._atlas_base_key:
            self._atlas_continents = continents.copy()
            self._atlas_palette = palette.copy()
            self._atlas_base_layers = self._build_atlas_layers(
                target.size,
                continents,
                palette,
            )
            self._atlas_base_key = base_key
            self._atlas_view_key = None
            self._atlas_view_cache = None
            self._atlas_highlight_cache.clear()

        view_key = (
            target.size,
            round(physical_camera.zoom, 4),
            round(physical_camera.offset.x, 2),
            round(physical_camera.offset.y, 2),
        )
        if view_key != self._atlas_view_key or self._atlas_view_cache is None:
            canvas = self._sample_atlas_view(
                target.size,
                physical_camera,
            )
            self._draw_atlas_boundaries(canvas, physical_camera)
            local = canvas.get_rect()
            pygame.draw.rect(
                canvas,
                BORDER,
                local,
                2,
                border_radius=7,
            )
            self._atlas_view_key = view_key
            self._atlas_view_cache = canvas

        surface.blit(self._atlas_view_cache, target)
        if hovered_country in self.geometry:
            highlight, position = self._atlas_highlight(
                target.size,
                physical_camera,
                hovered_country,
            )
            surface.blit(
                highlight,
                (target.left + position[0], target.top + position[1]),
            )

    def _atlas_highlight(
        self,
        size: tuple[int, int],
        camera: MapCamera,
        iso3: str,
    ) -> tuple[pygame.Surface, tuple[int, int]]:
        key = (
            size,
            round(camera.zoom, 4),
            round(camera.offset.x, 2),
            round(camera.offset.y, 2),
            iso3,
        )
        cached = self._atlas_highlight_cache.get(key)
        if cached is not None:
            return cached

        map_rect = pygame.Rect((0, 0), size)
        polygons = [
            [self.project(point, map_rect, camera) for point in ring]
            for ring in self.geometry[iso3]
            if len(ring) >= 3
        ]
        bounds = [
            pygame.Rect(
                min(point[0] for point in points),
                min(point[1] for point in points),
                max(point[0] for point in points)
                - min(point[0] for point in points)
                + 1,
                max(point[1] for point in points)
                - min(point[1] for point in points)
                + 1,
            )
            for points in polygons
        ]
        region = bounds[0].unionall(bounds).inflate(6, 6).clip(map_rect)
        if region.width <= 0 or region.height <= 0:
            result = pygame.Surface((1, 1), pygame.SRCALPHA), (0, 0)
        else:
            layer = pygame.Surface(region.size, pygame.SRCALPHA)
            for points in polygons:
                local_points = [
                    (x - region.left, y - region.top)
                    for x, y in points
                ]
                pygame.draw.polygon(
                    layer,
                    UI_THEME.colour("map_selection_fill"),
                    local_points,
                )
                pygame.draw.lines(
                    layer,
                    UI_THEME.colour("map_glow"),
                    True,
                    local_points,
                    2,
                )
                pygame.draw.aalines(
                    layer,
                    UI_THEME.colour("map_glow_bright"),
                    True,
                    local_points,
                )
            result = layer, region.topleft
        if len(self._atlas_highlight_cache) >= 12:
            self._atlas_highlight_cache.pop(
                next(iter(self._atlas_highlight_cache))
            )
        self._atlas_highlight_cache[key] = result
        return result

    def _build_atlas_layers(
        self,
        size: tuple[int, int],
        continents: dict[str, str],
        palette: dict[str, str],
    ) -> dict[int, pygame.Surface]:
        """Rasterize country geometry once; camera movement reuses these layers."""
        return {
            1: self._render_atlas_layer(
                size,
                1,
                continents,
                palette,
            )
        }

    def _render_atlas_layer(
        self,
        size: tuple[int, int],
        detail: int,
        continents: dict[str, str],
        palette: dict[str, str],
    ) -> pygame.Surface:
        detailed_size = (size[0] * detail, size[1] * detail)
        detailed = pygame.Surface(detailed_size)
        detailed.fill(WATER)
        detailed_rect = detailed.get_rect()
        for iso3, rings in self.geometry.items():
            colour = pygame.Color(
                palette.get(
                    continents.get(iso3, ""),
                    COLORS["atlas_default_country"],
                )
            )
            for ring in rings:
                points = [self.project(point, detailed_rect) for point in ring]
                if len(points) >= 3:
                    pygame.draw.polygon(detailed, colour, points)
        return detailed

    def _draw_atlas_boundaries(
        self,
        canvas: pygame.Surface,
        camera: MapCamera,
    ) -> None:
        """Draw crisp one-pixel borders over the cached, scaled country fills."""
        map_rect = canvas.get_rect()
        border_colour = MAP_BORDER
        for iso3, rings in self.geometry.items():
            min_lon, min_lat, max_lon, max_lat = self._country_bounds[iso3]
            top_left = self.project((min_lon, max_lat), map_rect, camera)
            bottom_right = self.project((max_lon, min_lat), map_rect, camera)
            country_rect = pygame.Rect(
                top_left,
                (
                    max(1, bottom_right[0] - top_left[0] + 1),
                    max(1, bottom_right[1] - top_left[1] + 1),
                ),
            )
            if not map_rect.colliderect(country_rect):
                continue
            for ring in rings:
                if len(ring) >= 3:
                    pygame.draw.aalines(
                        canvas,
                        border_colour,
                        True,
                        [self.project(point, map_rect, camera) for point in ring],
                    )

    def _sample_atlas_view(
        self,
        size: tuple[int, int],
        camera: MapCamera,
    ) -> pygame.Surface:
        """Crop only the visible raster area instead of scaling the whole world."""
        canvas = pygame.Surface(size)
        canvas.fill(WATER)
        width, height = size
        world = pygame.Rect(
            round(width / 2 + camera.offset.x - width * camera.zoom / 2),
            round(height / 2 + camera.offset.y - height * camera.zoom / 2),
            max(1, round(width * camera.zoom)),
            max(1, round(height * camera.zoom)),
        )
        visible = canvas.get_rect().clip(world)
        if not visible.width or not visible.height:
            return canvas

        detail = 1 if camera.zoom <= 1.5 else 2 if camera.zoom <= 3.0 else 4
        source = self._atlas_base_layers.get(detail)
        if source is None:
            source = self._render_atlas_layer(
                size,
                detail,
                self._atlas_continents,
                self._atlas_palette,
            )
            self._atlas_base_layers[detail] = source
        source_rect = pygame.Rect(
            max(
                0,
                math.floor(
                    (visible.left - world.left) / world.width
                    * source.get_width()
                ),
            ),
            max(
                0,
                math.floor(
                    (visible.top - world.top) / world.height
                    * source.get_height()
                ),
            ),
            1,
            1,
        )
        source_right = min(
            source.get_width(),
            math.ceil(
                (visible.right - world.left) / world.width
                * source.get_width()
            ),
        )
        source_bottom = min(
            source.get_height(),
            math.ceil(
                (visible.bottom - world.top) / world.height
                * source.get_height()
            ),
        )
        source_rect.width = max(1, source_right - source_rect.left)
        source_rect.height = max(1, source_bottom - source_rect.top)
        cropped = source.subsurface(source_rect)
        canvas.blit(
            pygame.transform.smoothscale(cropped, visible.size),
            visible,
        )
        return canvas

    def country_at(
        self,
        position: tuple[int, int],
        rect: pygame.Rect,
        camera: MapCamera | None = None,
    ) -> str | None:
        if not rect.collidepoint(position):
            return None
        camera = camera or MapCamera()
        screen = pygame.Vector2(position)
        base = (
            pygame.Vector2(rect.center)
            + (screen - pygame.Vector2(rect.center) - camera.offset)
            / camera.zoom
        )
        longitude = (base.x - rect.left) / rect.width * 360.0 - 180.0
        latitude = 90.0 - (base.y - rect.top) / rect.height * 180.0
        for iso3, bounds in self._country_bounds.items():
            if not (
                bounds[0] <= longitude <= bounds[2]
                and bounds[1] <= latitude <= bounds[3]
            ):
                continue
            if any(
                self._point_in_ring((longitude, latitude), ring)
                for ring in self.geometry[iso3]
            ):
                return iso3
        nearest = min(
            (
                (
                    pygame.Vector2(
                        self.project(center, rect, camera)
                    ).distance_to(position),
                    iso3,
                )
                for iso3, center in self.centers.items()
            ),
            default=(float("inf"), None),
        )
        if nearest[0] <= max(5.0, 7.0 * min(2.0, camera.zoom)):
            return nearest[1]
        return None

    @staticmethod
    def _point_in_ring(
        point: tuple[float, float],
        ring: list[list[float]],
    ) -> bool:
        x, y = point
        inside = False
        previous = ring[-1]
        for current in ring:
            x1, y1 = previous
            x2, y2 = current
            if (y1 > y) != (y2 > y):
                intersection = (x2 - x1) * (y - y1) / (y2 - y1) + x1
                if x < intersection:
                    inside = not inside
            previous = current
        return inside

def draw_earth_hero(
    surface: pygame.Surface,
    rect: pygame.Rect,
    image: pygame.Surface,
) -> None:
    """Render the cinematic Earth background without distorting its aspect ratio."""
    destination = physical_rect(surface, rect)
    key = (id(image), destination.size)
    cached = _COVER_IMAGE_CACHE.get(key)
    if cached is None or cached[0] is not image:
        scale = max(
            destination.width / image.get_width(),
            destination.height / image.get_height(),
        )
        scaled_size = (
            max(destination.width, round(image.get_width() * scale)),
            max(destination.height, round(image.get_height() * scale)),
        )
        scaled = pygame.transform.smoothscale(image, scaled_size)
        crop = pygame.Rect(
            (scaled.get_width() - destination.width) // 2,
            (scaled.get_height() - destination.height) // 2,
            destination.width,
            destination.height,
        )
        hero = scaled.subsurface(crop).copy()
        if len(_COVER_IMAGE_CACHE) >= 6:
            _COVER_IMAGE_CACHE.clear()
        _COVER_IMAGE_CACHE[key] = (image, hero)
    else:
        hero = cached[1]
    surface.blit(hero, destination)
