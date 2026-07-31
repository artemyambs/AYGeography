"""Генерирует единый SVG-набор иконок AYGeography."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets/icons"

ICONS = {
    "game": '<path d="M24 37h48c10 0 16 8 14 18l-5 19c-2 8-12 10-17 4l-8-9H40l-8 9c-5 6-15 4-17-4l-5-19c-2-10 4-18 14-18Z"/><path d="M29 49v14M22 56h14"/><circle cx="67" cy="52" r="3" fill="#76c52b"/><circle cx="75" cy="61" r="3" fill="#39d7ee"/>',
    "statistics": '<path d="M18 77V55h13v22M42 77V38h13v39M66 77V19h13v58"/><path d="M12 82h72"/>',
    "profile": '<circle cx="48" cy="32" r="16"/><path d="M18 80c2-20 13-30 30-30s28 10 30 30"/>',
    "settings": '<circle cx="48" cy="48" r="13"/><path d="M48 10v10M48 76v10M10 48h10M76 48h10M21 21l8 8M67 67l8 8M75 21l-8 8M29 67l-8 8"/><circle cx="48" cy="48" r="30"/>',
    "exit": '<path d="M49 16H22v64h27"/><path d="M40 48h43M68 33l15 15-15 15"/>',
    "flags": '<path d="M24 84V16"/><path d="M27 20c20-10 26 11 47 1v32c-21 10-27-11-47-1Z" fill="url(#g)" stroke="none"/>',
    "capitals": '<path d="M12 79h72M18 36h60L48 14 18 36ZM25 40v31M40 40v31M56 40v31M71 40v31"/>',
    "population": '<circle cx="48" cy="29" r="12"/><circle cx="22" cy="38" r="9"/><circle cx="74" cy="38" r="9"/><path d="M29 78c0-18 7-28 19-28s19 10 19 28M8 77c0-14 5-23 15-23 6 0 10 3 13 8M88 77c0-14-5-23-15-23-6 0-10 3-13 8"/>',
    "countries": '<circle cx="48" cy="48" r="35"/><path d="M13 48h70M48 13c12 11 18 23 18 35S60 72 48 83M48 13C36 24 30 36 30 48s6 24 18 35M19 30h58M19 66h58"/>',
    "waters": '<path d="M10 29c12-11 20 11 32 0s20 11 32 0 16 0 16 0M10 48c12-11 20 11 32 0s20 11 32 0 16 0 16 0M10 67c12-11 20 11 32 0s20 11 32 0 16 0 16 0"/>',
    "fullscreen": '<path d="M15 39V15h24M57 15h24v24M81 57v24H57M39 81H15V57"/>',
    "confirm": '<path d="M48 10 79 22v23c0 21-12 34-31 41-19-7-31-20-31-41V22Z"/><path d="m31 48 11 11 24-25"/>',
    "correct": '<path d="M24 10h37l15 15v61H24Z"/><path d="M60 10v16h16M35 53l9 9 20-21"/>',
    "animations": '<path d="m48 10 7 23 23 7-23 7-7 23-7-23-23-7 23-7ZM76 63l3 10 10 3-10 3-3 10-3-10-10-3 10-3Z"/>',
    "trophy": '<path d="M28 16h40v19c0 18-8 28-20 28S28 53 28 35Z" fill="url(#gold)" stroke="#f6b817"/><path d="M28 24H14v10c0 12 6 19 18 19M68 24h14v10c0 12-6 19-18 19M48 63v13M30 82h36"/>',
    "timer": '<circle cx="48" cy="52" r="33"/><path d="M38 10h20M48 19V9M72 27l7-7M48 52V31M48 52l14 9"/>',
    "streak": '<path d="m54 8-28 45h21l-5 35 29-48H50Z" fill="url(#gold)" stroke="#f6b817"/>',
    "pause": '<rect x="25" y="17" width="15" height="62" rx="5"/><rect x="56" y="17" width="15" height="62" rx="5"/>',
    "play": '<path d="m30 15 50 33-50 33Z" fill="url(#g)" stroke="none"/>',
    "back": '<path d="M78 48H18M38 27 17 48l21 21"/>',
    "next": '<path d="M18 48h60M58 27l21 21-21 21"/>',
    "document": '<path d="M24 10h38l14 14v62H24Z"/><path d="M61 10v16h15M36 45h28M36 58h28M36 71h20"/>',
    "zoom_in": '<circle cx="41" cy="41" r="26"/><path d="m61 61 22 22M41 27v28M27 41h28"/>',
    "zoom_out": '<circle cx="41" cy="41" r="26"/><path d="m61 61 22 22M27 41h28"/>',
    "reset": '<circle cx="48" cy="48" r="28"/><circle cx="48" cy="48" r="6" fill="#39d7ee"/><path d="M48 7v13M48 76v13M7 48h13M76 48h13"/>',
    "rotate_left": '<path d="M21 34A31 31 0 1 1 18 58"/><path d="M10 19v23h23"/>',
    "rotate_right": '<path d="M75 34A31 31 0 1 0 78 58"/><path d="M86 19v23H63"/>',
    "arrow_up": '<path d="m17 61 31-31 31 31"/>',
    "arrow_down": '<path d="m17 35 31 31 31-31"/>',
    "arrow_left": '<path d="m61 17-31 31 31 31"/>',
    "arrow_right": '<path d="m35 17 31 31-31 31"/>',
    "atlas": '<path d="M11 22c13-6 25-3 37 7 12-10 24-13 37-7v55c-13-5-25-2-37 8-12-10-24-13-37-8V22Z"/><path d="M48 29v56M22 37c7-2 13-1 19 3M22 49c7-2 13-1 19 3M56 40c6-4 12-5 19-4M56 52c6-4 12-5 19-4"/><circle cx="70" cy="66" r="9" stroke="#76c52b"/><path d="m70 58 3 7-3 9-3-9 3-7Z" fill="#76c52b" stroke="none"/>',
    "achievements": '<path d="M29 12h15l4 17-13 9-12-13 6-13ZM67 12H52l-4 17 13 9 12-13-6-13Z" fill="url(#g)" stroke="none"/><path d="m48 28 25 14v27L48 84 23 69V42l25-14Z" fill="url(#gold)" stroke="#f6b817"/><path d="m48 42 5 10 12 2-9 8 3 12-11-6-11 6 3-12-9-8 12-2 5-10Z" fill="#071c28" stroke="#071c28"/>',
    "mastery": '<circle cx="48" cy="47" r="34"/><path d="M14 47h68M48 13c11 10 17 21 17 34S59 71 48 81c-11-10-17-21-17-34s6-24 17-34Z"/><path d="m68 58 4 8 9 1-6 6 2 9-9-4-8 4 2-9-7-6 9-1 4-8Z" fill="#76c52b" stroke="#76c52b"/>',
    "wonders": '<path d="M10 78h76L60 35 48 52 36 17 10 78Z"/><path d="m36 17 7 20-8-5-8 6 9-21Z" fill="#76c52b" stroke="none"/><path d="m73 10 3 10 10 3-10 3-3 10-3-10-10-3 10-3 3-10Z" fill="#f6b817" stroke="#f6b817"/>',
    "profile_add": '<circle cx="36" cy="31" r="15"/><path d="M10 78c2-20 11-30 26-30 9 0 16 4 20 12"/><circle cx="70" cy="66" r="17" stroke="#76c52b"/><path d="M70 56v20M60 66h20" stroke="#76c52b"/>',
    "profile_import": '<circle cx="31" cy="30" r="14"/><path d="M9 75c2-18 10-27 22-27 9 0 15 4 19 12"/><path d="M70 14v43M55 42l15 15 15-15M52 78h36" stroke="#76c52b"/>',
}

TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">
<defs>
 <linearGradient id="g" x1="8" y1="8" x2="88" y2="88"><stop stop-color="#7ef4ff"/><stop offset=".58" stop-color="#39d7ee"/><stop offset="1" stop-color="#1683a4"/></linearGradient>
 <linearGradient id="gold" x2="1" y2="1"><stop stop-color="#fff08a"/><stop offset="1" stop-color="#f39b08"/></linearGradient>
</defs>
<g fill="none" stroke="url(#g)" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round">{body}</g>
</svg>
"""


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, body in ICONS.items():
        (OUTPUT / f"{name}.svg").write_text(TEMPLATE.format(body=body), encoding="utf-8")
    print(f"Built {len(ICONS)} SVG icons")


if __name__ == "__main__":
    main()
