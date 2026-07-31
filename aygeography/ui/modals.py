from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from .components import (
    CYAN,
    MUTED,
    PANEL,
    PANEL_ALT,
    RED,
    TEXT,
    draw_button,
    draw_multiline,
    draw_native_circle,
    draw_text,
    panel,
)


@dataclass(slots=True)
class ConfirmationModal:
    """Независимое от pygame_gui модальное подтверждение."""

    title: str
    description: str
    action_name: str
    danger: bool = False
    panel_rect: pygame.Rect = field(
        default_factory=lambda: pygame.Rect(570, 275, 460, 330)
    )
    cancel_rect: pygame.Rect = field(
        default_factory=lambda: pygame.Rect(610, 505, 170, 52)
    )
    confirm_rect: pygame.Rect = field(
        default_factory=lambda: pygame.Rect(820, 505, 170, 52)
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
        overlay.fill((0, 7, 11, 220))
        surface.blit(overlay, (0, 0))

        panel(surface, self.panel_rect, fill=PANEL_ALT, border=CYAN, radius=10)
        accent = RED if self.danger else CYAN
        draw_native_circle(surface, PANEL, (800, 335), 34)
        draw_native_circle(surface, accent, (800, 335), 34, 2)
        draw_text(
            surface,
            "!" if self.danger else "✓",
            (800, 335),
            27,
            accent,
            bold=True,
            anchor="center",
        )
        draw_text(
            surface,
            self.title.upper(),
            (800, 390),
            28,
            TEXT,
            bold=True,
            anchor="center",
        )
        draw_multiline(
            surface,
            self.description,
            pygame.Rect(610, 415, 380, 62),
            17,
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
        if cancel_hovered:
            panel(
                surface,
                self.cancel_rect,
                fill=pygame.Color("#0b3141"),
                border=CYAN,
                radius=7,
            )
            draw_text(
                surface,
                "Отмена",
                self.cancel_rect.center,
                17,
                TEXT,
                anchor="center",
            )
        else:
            draw_button(surface, self.cancel_rect, "Отмена", size=17)
        if self.danger:
            panel(
                surface,
                self.confirm_rect,
                fill=(
                    pygame.Color("#3a1820")
                    if confirm_hovered
                    else PANEL
                ),
                border=RED,
                radius=7,
            )
            draw_text(
                surface,
                self.action_name,
                self.confirm_rect.center,
                17,
                RED,
                bold=True,
                anchor="center",
            )
        else:
            if confirm_hovered:
                panel(
                    surface,
                    self.confirm_rect,
                    fill=pygame.Color("#438f19"),
                    border=CYAN,
                    radius=7,
                )
                draw_text(
                    surface,
                    self.action_name,
                    self.confirm_rect.center,
                    17,
                    TEXT,
                    bold=True,
                    anchor="center",
                )
            else:
                draw_button(
                    surface,
                    self.confirm_rect,
                    self.action_name,
                    primary=True,
                    size=17,
                )
