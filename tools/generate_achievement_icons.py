from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ACHIEVEMENTS_PATH = ROOT / "configs" / "achievements.json"
ICONS_DIR = ROOT / "assets" / "icons"

CATEGORY_COLOURS = {
    "Общие": ("#39d7ee", "#146a80"),
    "Точность": ("#76c52b", "#397f24"),
    "Скорость": ("#f6b817", "#c56d1d"),
    "Сложность": ("#f1845f", "#a83c56"),
    "Режимы": ("#59cde8", "#586fc8"),
    "Континенты": ("#9adf43", "#248a75"),
    "Регулярность": ("#b17ae6", "#5e55b9"),
}

SYMBOL_BY_ID = {
    "first_round": "flag",
    "rounds_10": "compass",
    "rounds_50": "route",
    "rounds_250": "crown",
    "correct_100": "book",
    "correct_1000": "brain",
    "correct_5000": "scroll",
    "all_modes": "orbit",
    "marathon_100": "mountain",
    "accuracy_80": "target",
    "accuracy_95": "bullseye",
    "perfect_25": "medal",
    "streak_10": "spark",
    "streak_25": "flame",
    "streak_50": "phoenix",
    "fast_answer": "bolt",
    "fast_streak_10": "stopwatch",
    "fast_round": "rocket",
    "hard_first": "mountain",
    "hard_accuracy_80": "diamond",
    "hard_perfect_25": "shield",
    "hard_rounds_50": "summit",
    "flags_50": "flag",
    "capitals_50": "temple",
    "population_50": "people",
    "countries_50": "map",
    "waters_50": "wave",
    "master_europe": "europe",
    "master_asia": "asia",
    "master_north_america": "north_america",
    "master_south_america": "south_america",
    "master_africa": "africa",
    "master_oceania": "oceania",
    "master_world": "globe",
    "days_3": "calendar",
    "days_7": "sunrise",
    "active_20": "constellation",
}

SYMBOLS = {
    "flag": '<path d="M22 45V17m1 2c10-7 13 5 23-1v17c-10 6-13-6-23 1" fill="none" stroke="{accent}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>',
    "compass": '<circle cx="32" cy="32" r="14" fill="none" stroke="{accent}" stroke-width="3"/><path d="m39 22-4 13-13 7 5-13 12-7Z" fill="{accent2}" stroke="{accent}" stroke-width="2"/>',
    "route": '<path d="M17 43c2-14 13-6 15-19 2-10 13-7 15 1" fill="none" stroke="{accent}" stroke-width="4" stroke-linecap="round" stroke-dasharray="2 5"/><circle cx="17" cy="44" r="4" fill="{accent2}"/><path d="m47 17 5 8-6 7" fill="none" stroke="{accent2}" stroke-width="3"/>',
    "crown": '<path d="m16 23 8 8 8-14 8 14 8-8-3 21H19l-3-21Z" fill="{accent2}" stroke="{accent}" stroke-width="3" stroke-linejoin="round"/><path d="M20 48h24" stroke="{accent}" stroke-width="3" stroke-linecap="round"/>',
    "book": '<path d="M15 19c8-2 13 1 17 5v24c-5-4-10-6-17-4V19Zm34 0c-8-2-13 1-17 5v24c5-4 10-6 17-4V19Z" fill="none" stroke="{accent}" stroke-width="3" stroke-linejoin="round"/><path d="m21 32 5 5 9-11" fill="none" stroke="{accent2}" stroke-width="3"/>',
    "brain": '<path d="M27 19c-8-5-15 5-10 11-5 6 2 14 9 11 2 7 12 6 13 0 8 3 13-7 8-12 4-7-5-14-11-9-2-6-8-5-9-1Z" fill="none" stroke="{accent}" stroke-width="3"/><path d="M31 21v21m-10-9h10m7-8-7 5m8 8-8-3" fill="none" stroke="{accent2}" stroke-width="2.5" stroke-linecap="round"/>',
    "scroll": '<path d="M21 18h25v27H21c-7 0-7-9 0-9h21M21 18c-7 0-7 9 0 9h20" fill="none" stroke="{accent}" stroke-width="3" stroke-linejoin="round"/><path d="M27 31h10M27 37h8" stroke="{accent2}" stroke-width="2.5" stroke-linecap="round"/>',
    "orbit": '<circle cx="32" cy="32" r="7" fill="{accent2}"/><ellipse cx="32" cy="32" rx="20" ry="10" fill="none" stroke="{accent}" stroke-width="2.5" transform="rotate(25 32 32)"/><ellipse cx="32" cy="32" rx="20" ry="10" fill="none" stroke="{accent}" stroke-width="2.5" transform="rotate(-35 32 32)"/><circle cx="49" cy="26" r="3" fill="{accent}"/>',
    "mountain": '<path d="m12 46 15-27 7 12 6-8 13 23H12Z" fill="{accent2}" opacity=".45" stroke="{accent}" stroke-width="3" stroke-linejoin="round"/><path d="m23 27 4-8 5 9-5-2-4 1Z" fill="{accent}"/>',
    "target": '<circle cx="32" cy="32" r="17" fill="none" stroke="{accent}" stroke-width="3"/><circle cx="32" cy="32" r="10" fill="none" stroke="{accent2}" stroke-width="3"/><circle cx="32" cy="32" r="4" fill="{accent}"/><path d="m43 21 8-8m-7 0h7v7" fill="none" stroke="{accent2}" stroke-width="3"/>',
    "bullseye": '<circle cx="30" cy="34" r="17" fill="none" stroke="{accent}" stroke-width="3"/><circle cx="30" cy="34" r="9" fill="{accent2}" opacity=".5"/><path d="m30 34 18-18m-1-5 6 1 1 6-7-7Z" fill="{accent}" stroke="{accent}" stroke-width="2"/>',
    "medal": '<path d="m23 14 9 13 9-13M26 17l-5 13m17-13 5 13" fill="none" stroke="{accent2}" stroke-width="4"/><circle cx="32" cy="39" r="13" fill="{accent2}" opacity=".45" stroke="{accent}" stroke-width="3"/><path d="m32 31 2.5 5 5.5.8-4 3.9.9 5.5-4.9-2.6-4.9 2.6.9-5.5-4-3.9 5.5-.8 2.5-5Z" fill="{accent}"/>',
    "spark": '<path d="m32 13 4.2 12.8L49 30l-12.8 4.2L32 47l-4.2-12.8L15 30l12.8-4.2L32 13Z" fill="{accent2}" stroke="{accent}" stroke-width="2.5"/><circle cx="49" cy="18" r="3" fill="{accent}"/>',
    "flame": '<path d="M33 13c3 10-6 11-2 19 2-4 6-5 8-10 9 10 6 26-7 28-14-1-17-18-7-26 0 6 3 7 4 8-2-9 1-13 4-19Z" fill="{accent2}" opacity=".65" stroke="{accent}" stroke-width="3"/>',
    "phoenix": '<path d="M32 17c2 8-5 9-1 15 2-4 6-5 8-9 5 8 2 19-7 23-9-3-13-14-7-22 0 6 4 7 5 9-2-8 0-12 2-16Z" fill="{accent2}" stroke="{accent}" stroke-width="2.5"/><path d="m21 38-9 7m31-7 9 7" stroke="{accent}" stroke-width="3" stroke-linecap="round"/>',
    "bolt": '<path d="M36 12 19 35h11l-3 17 18-25H34l2-15Z" fill="{accent2}" stroke="{accent}" stroke-width="3" stroke-linejoin="round"/>',
    "stopwatch": '<circle cx="32" cy="35" r="16" fill="none" stroke="{accent}" stroke-width="3"/><path d="M27 14h10m-5 5v16l9-6m4-9 4 4" fill="none" stroke="{accent2}" stroke-width="3" stroke-linecap="round"/>',
    "rocket": '<path d="M24 40c-2-14 5-23 17-28 5 12 1 22-11 29l-6-1Z" fill="{accent2}" opacity=".55" stroke="{accent}" stroke-width="3"/><circle cx="36" cy="24" r="4" fill="#071c28" stroke="{accent}" stroke-width="2"/><path d="m24 34-8 3 5 5-2 8 10-9m-5 3-5 5" fill="none" stroke="{accent}" stroke-width="3"/>',
    "diamond": '<path d="m15 25 7-10h20l7 10-17 24L15 25Z" fill="{accent2}" opacity=".45" stroke="{accent}" stroke-width="3"/><path d="m15 25 17 4 17-4M22 15l10 14 10-14" fill="none" stroke="{accent}" stroke-width="2"/>',
    "shield": '<path d="M32 13c7 5 12 5 17 6v11c0 11-7 17-17 21-10-4-17-10-17-21V19c5-1 10-1 17-6Z" fill="{accent2}" opacity=".4" stroke="{accent}" stroke-width="3"/><path d="m23 32 6 6 12-14" fill="none" stroke="{accent}" stroke-width="4" stroke-linecap="round"/>',
    "summit": '<path d="m11 47 18-31 8 13 5-7 12 25H11Z" fill="{accent2}" opacity=".4" stroke="{accent}" stroke-width="3"/><path d="M29 16v15m0-14h13l-4 5 4 5H29" fill="{accent}" stroke="{accent}" stroke-width="2"/>',
    "temple": '<path d="m14 27 18-12 18 12H14Zm4 4h28M20 31v15m8-15v15m8-15v15m8-15v15M16 49h32" fill="none" stroke="{accent}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><circle cx="32" cy="24" r="3" fill="{accent2}"/>',
    "people": '<circle cx="32" cy="23" r="7" fill="{accent2}" stroke="{accent}" stroke-width="2.5"/><circle cx="18" cy="28" r="5" fill="none" stroke="{accent}" stroke-width="2.5"/><circle cx="46" cy="28" r="5" fill="none" stroke="{accent}" stroke-width="2.5"/><path d="M20 48c1-10 6-14 12-14s11 4 12 14M8 48c1-8 5-12 10-12m38 12c-1-8-5-12-10-12" fill="none" stroke="{accent}" stroke-width="3" stroke-linecap="round"/>',
    "map": '<path d="m14 20 12-5 12 5 12-5v30l-12 5-12-5-12 5V20Z" fill="{accent2}" opacity=".35" stroke="{accent}" stroke-width="3" stroke-linejoin="round"/><path d="M26 15v30m12-25v30" stroke="{accent}" stroke-width="2"/><path d="m31 31 4 4 8-9" fill="none" stroke="{accent2}" stroke-width="3"/>',
    "wave": '<path d="M11 29c6 0 6-6 12-6s6 6 12 6 6-6 12-6 6 6 8 6M9 38c6 0 6-6 12-6s6 6 12 6 6-6 12-6 6 6 10 6M13 47c6 0 6-6 12-6s6 6 12 6 6-6 13-6" fill="none" stroke="{accent}" stroke-width="3" stroke-linecap="round"/>',
    "globe": '<circle cx="32" cy="32" r="19" fill="{accent2}" opacity=".25" stroke="{accent}" stroke-width="3"/><path d="M13 32h38M32 13c7 6 10 12 10 19s-3 13-10 19c-7-6-10-12-10-19s3-13 10-19Z" fill="none" stroke="{accent}" stroke-width="2.5"/>',
    "calendar": '<rect x="15" y="18" width="34" height="31" rx="5" fill="{accent2}" opacity=".3" stroke="{accent}" stroke-width="3"/><path d="M15 28h34M23 14v9m18-9v9" stroke="{accent}" stroke-width="3" stroke-linecap="round"/><path d="m23 38 5 5 12-12" fill="none" stroke="{accent2}" stroke-width="3"/>',
    "sunrise": '<path d="M12 44h40M20 40a12 12 0 0 1 24 0M32 14v8M15 24l6 6m28-6-6 6" fill="none" stroke="{accent}" stroke-width="3" stroke-linecap="round"/><path d="M23 40a9 9 0 0 1 18 0" fill="{accent2}" opacity=".6"/>',
    "constellation": '<path d="m16 40 9-17 13 7 10-13m-23 6 4 21 9-14 10 12" fill="none" stroke="{accent}" stroke-width="2"/><circle cx="16" cy="40" r="4" fill="{accent2}"/><circle cx="25" cy="23" r="3" fill="{accent}"/><circle cx="38" cy="30" r="4" fill="{accent2}"/><circle cx="48" cy="17" r="3" fill="{accent}"/><circle cx="29" cy="44" r="3" fill="{accent}"/><circle cx="48" cy="42" r="4" fill="{accent2}"/>',
}

for continent in (
    "europe",
    "asia",
    "north_america",
    "south_america",
    "africa",
    "oceania",
):
    SYMBOLS[continent] = (
        SYMBOLS["globe"]
        + '<path d="m32 18 3.2 6.5 7.2 1-5.2 5.1 1.2 7.2-6.4-3.4-6.4 3.4 1.2-7.2-5.2-5.1 7.2-1L32 18Z" fill="{accent2}" stroke="{accent}" stroke-width="1.5"/>'
    )


def build_svg(achievement_id: str, category: str, index: int) -> str:
    accent, accent2 = CATEGORY_COLOURS[category]
    symbol = SYMBOLS[SYMBOL_BY_ID[achievement_id]].format(
        accent=accent,
        accent2=accent2,
    )
    marker_angle = (index * 47) % 360
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="badge-{index}" x1="8" y1="8" x2="56" y2="56">
      <stop stop-color="#123541"/>
      <stop offset="1" stop-color="#061923"/>
    </linearGradient>
  </defs>
  <circle cx="32" cy="32" r="29" fill="url(#badge-{index})" stroke="{accent2}" stroke-width="2"/>
  <circle cx="32" cy="32" r="25" fill="none" stroke="{accent}" stroke-width="1" opacity=".45" stroke-dasharray="{3 + index % 4} {4 + index % 3}" transform="rotate({marker_angle} 32 32)"/>
  {symbol}
  <circle cx="{15 + index % 4 * 11}" cy="{10 + index % 3 * 3}" r="2" fill="{accent}" opacity=".9"/>
</svg>
"""


def main() -> None:
    achievements = json.loads(ACHIEVEMENTS_PATH.read_text(encoding="utf-8"))
    for index, item in enumerate(achievements):
        achievement_id = str(item["id"])
        icon_name = f"achievement_{achievement_id}"
        item["icon"] = icon_name
        (ICONS_DIR / f"{icon_name}.svg").write_text(
            build_svg(achievement_id, str(item["category"]), index),
            encoding="utf-8",
        )
    ACHIEVEMENTS_PATH.write_text(
        json.dumps(achievements, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
