from __future__ import annotations


def format_population(population: int) -> str:
    """Rounds a population for concise, consistent answer feedback."""
    quantum = 100_000 if population < 1_000_000 else 1_000_000
    rounded = ((population + quantum // 2) // quantum) * quantum
    return f"{rounded:,}".replace(",", " ")
