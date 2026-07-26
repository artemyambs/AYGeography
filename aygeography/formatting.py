from __future__ import annotations


def format_population(population: int) -> str:
    """Formats an exact population value with readable group separators."""
    return f"{population:,}".replace(",", " ")
