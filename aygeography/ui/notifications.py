from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import pygame

from ..progression import AchievementDefinition
from .components import (
    GREEN,
    FONT_SIZES,
    MUTED,
    PANEL_ALT,
    TEXT,
    blit_image,
    draw_multiline,
    draw_native_line,
    draw_native_rect,
    draw_text,
)


@dataclass(slots=True)
class AchievementNotification:
    definition: AchievementDefinition
    opened_at: float | None = None
    closing_at: float | None = None


class AchievementNotificationCenter:
    """Owns the independent lifetime and animation of achievement cards."""

    DISPLAY_SECONDS = 10.0
    ANIMATION_SECONDS = 0.35
    CARD_SIZE = (430, 104)
    CARD_GAP = 12
    MARGIN = 20
    MAX_VISIBLE = 7

    def __init__(
        self,
        clock: Callable[[], float],
        icon_provider: Callable[[str, tuple[int, int]], pygame.Surface],
    ) -> None:
        self._clock = clock
        self._icon_provider = icon_provider
        self._items: list[AchievementNotification] = []
        self._close_rects: list[tuple[pygame.Rect, AchievementNotification]] = []

    @property
    def items(self) -> tuple[AchievementNotification, ...]:
        return tuple(self._items)

    def add(self, definitions: Iterable[AchievementDefinition]) -> None:
        now = self._clock()
        existing = {item.definition.id for item in self._items}
        for definition in definitions:
            if definition.id not in existing:
                self._items.append(AchievementNotification(definition))
                existing.add(definition.id)
        self._activate_pending(now)

    def close_at(self, position: tuple[int, int]) -> bool:
        now = self._clock()
        for rect, item in reversed(self._close_rects):
            if rect.collidepoint(position):
                item.closing_at = now
                return True
        return False

    def interactive_at(self, position: tuple[int, int]) -> bool:
        return any(rect.collidepoint(position) for rect, _ in self._close_rects)

    def update(self) -> None:
        now = self._clock()
        self._items = [
            item
            for item in self._items
            if item.opened_at is None
            or self._age(item, now) < self.DISPLAY_SECONDS
            and (
                item.closing_at is None
                or now - item.closing_at < self.ANIMATION_SECONDS
            )
        ]
        self._activate_pending(now)

    def draw(self, surface: pygame.Surface) -> None:
        self.update()
        self._close_rects.clear()
        now = self._clock()
        width, height = self.CARD_SIZE
        visible = [item for item in self._items if item.opened_at is not None]
        for index, item in enumerate(visible):
            age = self._age(item, now)
            enter = min(1.0, age / self.ANIMATION_SECONDS)
            exit_progress = self._exit_progress(item, now)
            eased_enter = 1 - (1 - enter) ** 3
            x = 1600 - self.MARGIN - width + round((1 - eased_enter) * (width + 30))
            x += round(exit_progress * (width + 30))
            y = self.MARGIN + index * (height + self.CARD_GAP)
            rect = pygame.Rect(x, y, width, height)
            self._draw_card(surface, rect, item.definition)
            self._close_rects.append(
                (pygame.Rect(rect.right - 38, rect.top + 10, 28, 28), item)
            )

    @staticmethod
    def _age(item: AchievementNotification, now: float) -> float:
        opened_at = now if item.opened_at is None else item.opened_at
        return max(0.0, now - opened_at)

    def _activate_pending(self, now: float) -> None:
        active_count = sum(item.opened_at is not None for item in self._items)
        for item in self._items:
            if active_count >= self.MAX_VISIBLE:
                break
            if item.opened_at is None:
                item.opened_at = now
                active_count += 1

    def _exit_progress(
        self,
        item: AchievementNotification,
        now: float,
    ) -> float:
        auto_exit = max(
            0.0,
            (self._age(item, now) - self.DISPLAY_SECONDS + self.ANIMATION_SECONDS)
            / self.ANIMATION_SECONDS,
        )
        manual_exit = (
            max(0.0, (now - item.closing_at) / self.ANIMATION_SECONDS)
            if item.closing_at is not None
            else 0.0
        )
        return min(1.0, max(auto_exit, manual_exit))

    def _draw_card(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        definition: AchievementDefinition,
    ) -> None:
        draw_native_rect(surface, PANEL_ALT, rect, border_radius=10)
        draw_native_rect(surface, GREEN, rect, 2, border_radius=10)
        icon = self._icon_provider(definition.icon, (64, 64))
        blit_image(
            surface,
            icon,
            pygame.Rect(rect.left + 18, rect.top + 20, 64, 64),
        )
        draw_text(
            surface,
            "НОВОЕ ДОСТИЖЕНИЕ",
            (rect.left + 98, rect.top + 14),
            FONT_SIZES["small"],
            GREEN,
            bold=True,
        )
        draw_text(
            surface,
            definition.title,
            (rect.left + 98, rect.top + 37),
            FONT_SIZES["body"],
            TEXT,
            bold=True,
        )
        draw_multiline(
            surface,
            definition.description,
            pygame.Rect(rect.left + 98, rect.top + 64, rect.width - 146, 30),
            FONT_SIZES["small"],
            MUTED,
            align="left",
            line_gap=1,
        )
        close_rect = pygame.Rect(rect.right - 38, rect.top + 10, 28, 28)
        draw_native_line(
            surface,
            MUTED,
            (close_rect.left + 8, close_rect.top + 8),
            (close_rect.right - 8, close_rect.bottom - 8),
            2,
        )
        draw_native_line(
            surface,
            MUTED,
            (close_rect.right - 8, close_rect.top + 8),
            (close_rect.left + 8, close_rect.bottom - 8),
            2,
        )
