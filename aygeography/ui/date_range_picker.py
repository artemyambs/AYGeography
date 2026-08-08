from __future__ import annotations

import calendar
from datetime import date

import pygame

from .components import (
    BORDER,
    CYAN,
    CYAN_DARK,
    FONT_SIZES,
    GREEN,
    MUTED,
    PANEL,
    PANEL_ALT,
    SELECTED_PANEL,
    TEXT,
    UI_THEME,
    draw_native_polygon,
    draw_native_rect,
    draw_text,
    panel,
)


class DateRangePicker:
    """Compact calendar that selects one day or an inclusive range."""

    MONTH_NAMES = (
        "",
        "Январь",
        "Февраль",
        "Март",
        "Апрель",
        "Май",
        "Июнь",
        "Июль",
        "Август",
        "Сентябрь",
        "Октябрь",
        "Ноябрь",
        "Декабрь",
    )
    WEEKDAY_NAMES = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")

    def __init__(self, field_rect: pygame.Rect) -> None:
        self.field_rect = field_rect
        self.popup_rect = pygame.Rect(field_rect.left, field_rect.bottom + 8, 370, 344)
        self.start_date: date | None = None
        self.end_date: date | None = None
        self.visible_month = date.today().replace(day=1)
        self.is_open = False
        self._selecting_end = False
        self._day_rects: list[tuple[pygame.Rect, date]] = []
        self.previous_rect = pygame.Rect(0, 0, 34, 30)
        self.next_rect = pygame.Rect(0, 0, 34, 30)
        self.clear_rect = pygame.Rect(0, 0, 104, 30)

    @property
    def label(self) -> str:
        if self.start_date is None:
            return "За всё время"
        start = self.start_date.strftime("%d.%m.%Y")
        if self.end_date is None or self.end_date == self.start_date:
            return start
        return f"{start} — {self.end_date.strftime('%d.%m.%Y')}"

    def _change_month(self, offset: int) -> None:
        month_index = (
            self.visible_month.year * 12 + self.visible_month.month - 1 + offset
        )
        year, month = divmod(month_index, 12)
        self.visible_month = date(year, month + 1, 1)

    def _select(self, selected: date) -> bool:
        if not self._selecting_end:
            self.start_date = selected
            self.end_date = selected
            self._selecting_end = True
            return True
        if self.start_date is None:
            self.start_date = selected
        self.start_date, self.end_date = sorted((self.start_date, selected))
        self._selecting_end = False
        self.is_open = False
        return True

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type != pygame.MOUSEBUTTONUP or event.button != 1:
            return False
        if self.field_rect.collidepoint(event.pos):
            self.is_open = not self.is_open
            self._selecting_end = False
            return False
        if not self.is_open:
            return False
        if self.previous_rect.collidepoint(event.pos):
            self._change_month(-1)
            return False
        if self.next_rect.collidepoint(event.pos):
            self._change_month(1)
            return False
        if self.clear_rect.collidepoint(event.pos):
            changed = self.start_date is not None
            self.start_date = None
            self.end_date = None
            self._selecting_end = False
            self.is_open = False
            return changed
        for rect, day in self._day_rects:
            if rect.collidepoint(event.pos):
                return self._select(day)
        if not self.popup_rect.collidepoint(event.pos):
            self.is_open = False
            self._selecting_end = False
        return False

    def interactive_at(self, position: tuple[int, int]) -> bool:
        if self.field_rect.collidepoint(position):
            return True
        if not self.is_open:
            return False
        return any(
            rect.collidepoint(position)
            for rect in (self.previous_rect, self.next_rect, self.clear_rect)
        ) or any(rect.collidepoint(position) for rect, _ in self._day_rects)

    @staticmethod
    def _hovered(
        rect: pygame.Rect,
        mouse_position: tuple[int, int] | None,
    ) -> bool:
        return bool(mouse_position and rect.collidepoint(mouse_position))

    def draw(
        self,
        surface: pygame.Surface,
        mouse_position: tuple[int, int] | None = None,
    ) -> None:
        field_fill = (
            UI_THEME.colour("button_hover")
            if self._hovered(self.field_rect, mouse_position)
            else PANEL_ALT
        )
        panel(surface, self.field_rect, fill=field_fill, border=CYAN_DARK)
        draw_text(
            surface,
            self.label,
            (self.field_rect.left + 14, self.field_rect.centery),
            FONT_SIZES["secondary"],
            TEXT,
            bold=True,
            anchor="midleft",
        )
        caret_x = self.field_rect.right - 17
        caret_y = self.field_rect.centery
        points = (
            (
                (caret_x - 5, caret_y + 3),
                (caret_x, caret_y - 3),
                (caret_x + 5, caret_y + 3),
            )
            if self.is_open
            else (
                (caret_x - 5, caret_y - 3),
                (caret_x, caret_y + 3),
                (caret_x + 5, caret_y - 3),
            )
        )
        draw_native_polygon(surface, CYAN, points)
        if not self.is_open:
            return
        self._draw_popup(surface, mouse_position)

    def _draw_popup(
        self,
        surface: pygame.Surface,
        mouse_position: tuple[int, int] | None,
    ) -> None:
        panel(surface, self.popup_rect, fill=PANEL, border=CYAN_DARK, radius=10)
        self.previous_rect.topleft = (
            self.popup_rect.left + 14,
            self.popup_rect.top + 14,
        )
        self.next_rect.topright = (self.popup_rect.right - 14, self.popup_rect.top + 14)
        self.clear_rect.bottomright = (
            self.popup_rect.right - 14,
            self.popup_rect.bottom - 12,
        )
        for rect, label in ((self.previous_rect, "‹"), (self.next_rect, "›")):
            fill = (
                UI_THEME.colour("button_hover")
                if self._hovered(rect, mouse_position)
                else PANEL_ALT
            )
            draw_native_rect(surface, fill, rect, border_radius=6)
            draw_native_rect(surface, BORDER, rect, 1, border_radius=6)
            draw_text(
                surface,
                label,
                rect.center,
                FONT_SIZES["result_percent"],
                TEXT,
                bold=True,
                anchor="center",
            )
        draw_text(
            surface,
            f"{self.MONTH_NAMES[self.visible_month.month]} {self.visible_month.year}",
            (self.popup_rect.centerx, self.popup_rect.top + 29),
            FONT_SIZES["body"],
            TEXT,
            bold=True,
            anchor="center",
        )
        grid_left = self.popup_rect.left + 18
        grid_top = self.popup_rect.top + 62
        cell_width = 47
        cell_height = 35
        for column, label in enumerate(self.WEEKDAY_NAMES):
            draw_text(
                surface,
                label,
                (grid_left + column * cell_width + cell_width // 2, grid_top),
                FONT_SIZES["small"],
                MUTED,
                bold=True,
                anchor="midtop",
            )
        self._day_rects.clear()
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(
            self.visible_month.year,
            self.visible_month.month,
        )
        for row, week in enumerate(weeks):
            for column, day in enumerate(week):
                rect = pygame.Rect(
                    grid_left + column * cell_width + 4,
                    grid_top + 23 + row * cell_height,
                    cell_width - 8,
                    cell_height - 5,
                )
                self._day_rects.append((rect, day))
                in_range = bool(
                    self.start_date
                    and self.end_date
                    and self.start_date <= day <= self.end_date
                )
                is_edge = day in (self.start_date, self.end_date)
                if in_range:
                    draw_native_rect(
                        surface,
                        GREEN if is_edge else SELECTED_PANEL,
                        rect,
                        border_radius=6,
                    )
                elif self._hovered(rect, mouse_position):
                    draw_native_rect(
                        surface,
                        UI_THEME.colour("button_hover"),
                        rect,
                        border_radius=6,
                    )
                colour = TEXT if day.month == self.visible_month.month else MUTED
                if is_edge:
                    colour = PANEL
                draw_text(
                    surface,
                    str(day.day),
                    rect.center,
                    FONT_SIZES["caption"],
                    colour,
                    bold=is_edge or day == date.today(),
                    anchor="center",
                )
        clear_fill = (
            UI_THEME.colour("button_hover")
            if self._hovered(self.clear_rect, mouse_position)
            else PANEL_ALT
        )
        draw_native_rect(surface, clear_fill, self.clear_rect, border_radius=6)
        draw_native_rect(surface, BORDER, self.clear_rect, 1, border_radius=6)
        draw_text(
            surface,
            "Сбросить",
            self.clear_rect.center,
            FONT_SIZES["caption"],
            TEXT,
            bold=True,
            anchor="center",
        )
        hint = (
            "Выберите конец периода"
            if self._selecting_end
            else "Выберите дату или начало периода"
        )
        draw_text(
            surface,
            hint,
            (self.popup_rect.left + 16, self.clear_rect.centery),
            FONT_SIZES["small"],
            MUTED,
            anchor="midleft",
        )
