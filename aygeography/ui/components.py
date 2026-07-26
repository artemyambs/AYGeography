from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import pygame

from ..config import COLORS

LOGICAL_SIZE = (1600, 900)
SIDEBAR_WIDTH = 205
FOOTER_HEIGHT = 34
FONT_SCALE = 1.08

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


@lru_cache(maxsize=128)
def font(size: int, bold: bool = False) -> pygame.font.Font:
    scaled_size = max(size + 1, round(size * FONT_SCALE))
    return pygame.font.SysFont("Segoe UI", scaled_size, bold=bold)


def draw_text(
    surface: pygame.Surface,
    value: str,
    position: tuple[int, int],
    size: int = 20,
    colour: pygame.Color = TEXT,
    *,
    bold: bool = False,
    anchor: str = "topleft",
) -> pygame.Rect:
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
    scale = render_scale(surface)
    target_rect = physical_rect(surface, rect)
    lines = value.splitlines()
    fitted_size = size
    available_width = max(1, target_rect.width - physical_length(surface, 24))
    while fitted_size > 13:
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
    radius: int = 8,
    width: int = 1,
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
    selected: bool = False,
    disabled: bool = False,
    size: int = 18,
) -> None:
    if primary:
        fill, border = GREEN_DARK, GREEN
    elif selected:
        fill, border = pygame.Color("#123927"), GREEN
    else:
        fill, border = PANEL, BORDER
    if disabled:
        fill, border = PANEL, pygame.Color("#18313a")
    panel(surface, rect, fill=fill, border=border, radius=7)
    draw_multiline(
        surface,
        label,
        rect,
        size,
        MUTED if disabled else TEXT,
        bold=primary or selected,
    )


def draw_mode_icon(
    surface: pygame.Surface,
    key: str,
    center: tuple[int, int],
    colour: pygame.Color = CYAN,
    scale: float = 1.0,
) -> None:
    x, y = physical_point(surface, center)
    scale *= render_scale(surface)
    width = max(2, round(3 * scale))
    if key == "flags":
        pygame.draw.line(surface, colour, (x - 22 * scale, y - 28 * scale), (x - 22 * scale, y + 30 * scale), width)
        pygame.draw.polygon(
            surface,
            colour,
            [(x - 19 * scale, y - 25 * scale), (x + 25 * scale, y - 17 * scale), (x + 8 * scale, y + 3 * scale), (x - 19 * scale, y - 3 * scale)],
        )
    elif key == "capitals":
        pygame.draw.polygon(surface, colour, [(x - 32 * scale, y - 16 * scale), (x, y - 35 * scale), (x + 32 * scale, y - 16 * scale)])
        pygame.draw.rect(surface, colour, (x - 37 * scale, y + 22 * scale, 74 * scale, 7 * scale))
        for dx in (-24, -8, 8, 24):
            pygame.draw.rect(surface, colour, (x + dx * scale - 3 * scale, y - 12 * scale, 6 * scale, 34 * scale))
    elif key == "population":
        for dx, dy, radius in ((-27, -5, 11), (0, -14, 13), (27, -5, 11)):
            pygame.draw.circle(surface, colour, (round(x + dx * scale), round(y + dy * scale)), round(radius * scale))
        for dx, w in ((-29, 28), (0, 34), (29, 28)):
            rect = pygame.Rect(0, 0, w * scale, 25 * scale)
            rect.midtop = (x + dx * scale, y + 8 * scale)
            pygame.draw.rect(surface, colour, rect, border_radius=round(10 * scale))
    elif key == "countries":
        pygame.draw.circle(surface, colour, (x, y), round(34 * scale), width)
        pygame.draw.ellipse(surface, colour, (x - 17 * scale, y - 34 * scale, 34 * scale, 68 * scale), width)
        pygame.draw.line(surface, colour, (x - 32 * scale, y), (x + 32 * scale, y), width)
        pygame.draw.arc(surface, colour, (x - 31 * scale, y - 19 * scale, 62 * scale, 38 * scale), 0, math.pi, width)
    else:
        for offset in (-17, 0, 17):
            points = [
                (x - 34 * scale, y + offset * scale),
                (x - 19 * scale, y + (offset - 7) * scale),
                (x - 4 * scale, y + offset * scale),
                (x + 11 * scale, y + (offset + 7) * scale),
                (x + 28 * scale, y + offset * scale),
            ]
            pygame.draw.lines(surface, colour, False, points, width + 1)


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
        pygame.Color("#103544"),
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
            border_radius=max(1, round(5 * scale)),
        )
        pygame.draw.rect(
            surface,
            GREEN,
            rect,
            max(1, round(2 * scale)),
            border_radius=max(1, round(5 * scale)),
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
            max(1, round(3 * scale)),
        )
    else:
        pygame.draw.rect(
            surface,
            pygame.Color("#04131c"),
            rect,
            border_radius=max(1, round(5 * scale)),
        )
        pygame.draw.rect(
            surface,
            pygame.Color("#7f9aa5"),
            rect,
            max(1, round(2 * scale)),
            border_radius=max(1, round(5 * scale)),
        )


def draw_logo(surface: pygame.Surface, center: tuple[int, int], radius: int = 48) -> None:
    scale = render_scale(surface)
    x, y = physical_point(surface, center)
    radius = max(1, round(radius * scale))
    margin = max(1, round(10 * scale))
    overlay = pygame.Surface(
        (radius * 2 + margin * 2, radius * 2 + margin * 2),
        pygame.SRCALPHA,
    )
    c = radius + margin
    unit = lambda value: max(1, round(value * scale))

    pygame.draw.circle(
        overlay,
        (0, 0, 0, 75),
        (c + unit(2), c + unit(3)),
        radius,
    )
    for extra, alpha in ((8, 16), (4, 34)):
        pygame.draw.circle(
            overlay,
            (*CYAN[:3], alpha),
            (c, c),
            radius + unit(extra),
        )
    pygame.draw.circle(overlay, pygame.Color("#041a25"), (c, c), radius)
    pygame.draw.circle(
        overlay,
        CYAN,
        (c, c),
        radius,
        unit(2),
    )
    pygame.draw.circle(
        overlay,
        pygame.Color("#0a6075"),
        (c, c),
        radius - unit(5),
        unit(1),
    )

    globe_radius = radius - unit(10)
    globe_rect = pygame.Rect(
        c - globe_radius,
        c - globe_radius,
        globe_radius * 2,
        globe_radius * 2,
    )
    grid = pygame.Color("#13778b")
    pygame.draw.circle(overlay, pygame.Color("#062d3b"), (c, c), globe_radius)
    pygame.draw.circle(overlay, grid, (c, c), globe_radius, unit(1))
    pygame.draw.ellipse(
        overlay,
        grid,
        pygame.Rect(
            c - globe_radius // 2,
            c - globe_radius,
            globe_radius,
            globe_radius * 2,
        ),
        unit(1),
    )
    pygame.draw.ellipse(
        overlay,
        grid,
        pygame.Rect(
            c - globe_radius,
            c - globe_radius // 2,
            globe_radius * 2,
            globe_radius,
        ),
        unit(1),
    )

    needle = [
        (c, c - globe_radius + unit(3)),
        (c + unit(7), c - unit(4)),
        (c, c - unit(9)),
        (c - unit(7), c - unit(4)),
    ]
    pygame.draw.polygon(overlay, GREEN, needle)
    pygame.draw.polygon(
        overlay,
        pygame.Color("#1d5362"),
        [
            (c, c + globe_radius - unit(3)),
            (c + unit(6), c + unit(4)),
            (c, c + unit(9)),
            (c - unit(6), c + unit(4)),
        ],
    )

    band = pygame.Rect(c - unit(36), c - unit(14), unit(72), unit(29))
    pygame.draw.rect(
        overlay,
        pygame.Color("#03131d"),
        band,
        border_radius=unit(7),
    )
    pygame.draw.rect(
        overlay,
        pygame.Color("#0c5265"),
        band,
        unit(1),
        border_radius=unit(7),
    )
    logo_font_size = max(unit(18), radius // 2)
    image = font(logo_font_size, True).render("AYG", True, TEXT)
    overlay.blit(
        image,
        image.get_rect(center=(c, c)),
    )
    pygame.draw.line(
        overlay,
        GREEN,
        (c - unit(15), c + unit(17)),
        (c + unit(15), c + unit(17)),
        unit(2),
    )
    surface.blit(overlay, (x - c, y - c))


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
    ("statistics", "Статистика"),
    ("achievements", "Достижения"),
    ("mastery", "Прогресс"),
    ("profile", "Профиль"),
    ("settings", "Настройки"),
    ("exit", "Выход"),
]


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
    top = 156
    for index, (key, label) in enumerate(NAV_ITEMS):
        rect = pygame.Rect(12, top + index * 54, SIDEBAR_WIDTH - 24, 44)
        selected = key == active
        if selected:
            draw_native_rect(surface, GREEN_DARK, rect, border_radius=6)
            draw_native_rect(surface, GREEN, rect, 1, border_radius=6)
        colour = TEXT if selected else pygame.Color("#d4dfe4")
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
            16,
            colour,
            bold=True,
            anchor="midleft",
        )
    if avatar:
        blit_image(surface, avatar, pygame.Rect(18, 756, 56, 56))
    else:
        draw_native_circle(surface, CYAN_DARK, (46, 784), 27)
    nickname = str(profile.get("nickname", "ExplorerAY"))
    xp = int(profile.get("xp", 0))
    level = xp // 500 + 1
    draw_text(surface, nickname, (80, 764), 14, TEXT, bold=True)
    draw_text(surface, f"Уровень {level}", (80, 785), 12, MUTED)
    draw_text(surface, f"{xp:,} / {(level * 500):,} XP".replace(",", " "), (80, 804), 11, MUTED)
    draw_native_rect(
        surface,
        PANEL_ALT,
        (80, 825, 102, 5),
        border_radius=3,
    )
    draw_native_rect(
        surface,
        CYAN,
        (80, 825, int(102 * ((xp % 500) / 500)), 5),
        border_radius=3,
    )


def draw_footer(surface: pygame.Surface, icon_provider=None) -> None:
    rect = pygame.Rect(0, LOGICAL_SIZE[1] - FOOTER_HEIGHT, LOGICAL_SIZE[0], FOOTER_HEIGHT)
    draw_native_rect(surface, SIDEBAR, rect)
    draw_native_line(surface, BORDER, rect.topleft, rect.topright)
    draw_text(surface, "AY", (18, rect.centery), 14, CYAN, bold=True, anchor="midleft")
    draw_text(surface, "Geography", (40, rect.centery), 14, TEXT, anchor="midleft")
    draw_text(surface, "v1.0.0", (128, rect.centery), 12, MUTED, anchor="midleft")
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
    def __init__(self, geometry_path: Path) -> None:
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
                (171, 211, 42, 150),
                points,
            )
            pygame.draw.lines(
                highlight,
                (239, 255, 104, 255),
                True,
                points,
                1,
            )
            pygame.draw.aalines(
                highlight,
                (239, 255, 104, 255),
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
        )
        if cache_key == self._view_cache_key and self._view_cache is not None:
            surface.blit(self._view_cache, target_rect)
            return
        canvas = pygame.Surface(target_rect.size)
        canvas.fill(WATER)
        local_rect = canvas.get_rect()
        grid_step = max(1, round(50 * scale))
        for x in range(0, local_rect.width, grid_step):
            pygame.draw.line(canvas, pygame.Color("#0e3747"), (x, 0), (x, local_rect.height))
        for y in range(0, local_rect.height, grid_step):
            pygame.draw.line(canvas, pygame.Color("#0e3747"), (0, y), (local_rect.width, y))
        self._draw_vector_countries(
            canvas,
            local_rect,
            render_camera,
            highlight_country=highlight_country,
        )
        if highlight_water:
            from ..waters import WATER_REGIONS

            region = next(
                (item for item in WATER_REGIONS if item.key == highlight_water),
                None,
            )
            if region is not None:
                points = self._water_polygon(region, local_rect, render_camera)
                self._draw_region_selection(
                    canvas,
                    [points],
                )
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

    def draw_mastery_map(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        levels: dict[str, int],
        colors: dict[int, str],
    ) -> None:
        """Draw a cached world map coloured by permanent country mastery."""
        target = physical_rect(surface, rect)
        key = (
            target.size,
            tuple(sorted(levels.items())),
            tuple(sorted(colors.items())),
        )
        if key != self._mastery_cache_key or self._mastery_cache is None:
            canvas = pygame.Surface(target.size)
            canvas.fill(WATER)
            local = canvas.get_rect()
            for x in range(0, local.width, max(1, local.width // 12)):
                pygame.draw.line(canvas, pygame.Color("#0e3747"), (x, 0), (x, local.height))
            for y in range(0, local.height, max(1, local.height // 6)):
                pygame.draw.line(canvas, pygame.Color("#0e3747"), (0, y), (local.width, y))
            for iso3, rings in self.geometry.items():
                colour = pygame.Color(colors.get(levels.get(iso3, 0), "#0a5572"))
                for ring in rings:
                    points = [self.project(point, local) for point in ring]
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

    def country_at(
        self,
        position: tuple[int, int],
        rect: pygame.Rect,
    ) -> str | None:
        if not rect.collidepoint(position):
            return None
        longitude = (position[0] - rect.left) / rect.width * 360.0 - 180.0
        latitude = 90.0 - (position[1] - rect.top) / rect.height * 180.0
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
