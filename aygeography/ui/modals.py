from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from .components import (
    CYAN,
    FONT_SIZES,
    MUTED,
    PANEL,
    PANEL_ALT,
    RED,
    TEXT,
    UI_THEME,
    draw_button,
    draw_multiline,
    draw_native_circle,
    draw_text,
    panel,
)

_MODAL_STYLE = UI_THEME.component("modal")
_MODAL_SIZE = tuple(int(value) for value in _MODAL_STYLE["panel_size"])
_BUTTON_SIZE = tuple(int(value) for value in _MODAL_STYLE["button_size"])


@dataclass(slots=True)
class ConfirmationModal:
    """Независимое от pygame_gui модальное подтверждение."""

    title: str
    description: str
    action_name: str
    cancel_name: str = "Отмена"
    danger: bool = False
    panel_rect: pygame.Rect = field(
        default_factory=lambda: pygame.Rect((455, 275), _MODAL_SIZE)
    )
    cancel_rect: pygame.Rect = field(
        default_factory=lambda: pygame.Rect((505, 505), _BUTTON_SIZE)
    )
    confirm_rect: pygame.Rect = field(
        default_factory=lambda: pygame.Rect((825, 505), _BUTTON_SIZE)
    )

    def handle_event(self, event: pygame.event.Event) -> str | None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "cancel"
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return "confirm"
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.confirm_rect.collidepoint(event.pos):
                return "confirm"
            if self.cancel_rect.collidepoint(event.pos):
                return "cancel"
        return None

    def draw(
        self,
        surface: pygame.Surface,
        mouse_position: tuple[int, int] | None = None,
    ) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill(UI_THEME.colour("modal_overlay"))
        surface.blit(overlay, (0, 0))

        panel(surface, self.panel_rect, fill=PANEL_ALT, border=CYAN, radius=10)
        accent = RED if self.danger else CYAN
        draw_native_circle(surface, PANEL, (800, 335), 34)
        draw_native_circle(surface, accent, (800, 335), 34, 2)
        draw_text(
            surface,
            "!" if self.danger else "✓",
            (800, 335),
            FONT_SIZES["page_title"],
            accent,
            bold=True,
            anchor="center",
        )
        draw_text(
            surface,
            self.title.upper(),
            (800, 390),
            FONT_SIZES["country_name"],
            TEXT,
            bold=True,
            anchor="center",
        )
        draw_multiline(
            surface,
            self.description,
            pygame.Rect(610, 415, 380, 62),
            FONT_SIZES["button"],
            MUTED,
        )
        cancel_hovered = bool(
            mouse_position
            and self.cancel_rect.collidepoint(mouse_position)
        )
        confirm_hovered = bool(
            mouse_position
            and self.confirm_rect.collidepoint(mouse_position)
        )
        draw_button(
            surface,
            self.cancel_rect,
            self.cancel_name,
            hovered=cancel_hovered,
            size=FONT_SIZES["button"],
        )
        draw_button(
            surface,
            self.confirm_rect,
            self.action_name,
            primary=not self.danger,
            danger=self.danger,
            hovered=confirm_hovered,
            size=FONT_SIZES["button"],
        )
