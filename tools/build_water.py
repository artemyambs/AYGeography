"""Создаёт расширяемые SVG-слои морей и океанов из каталога областей."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aygeography.waters import WATER_REGIONS

OUTPUT = ROOT / "assets/maps/water"


def ellipse(region) -> str:
    x = (region.longitude + 180) * 5.333333
    y = (90 - region.latitude) * 5.333333
    rx = region.radius_x * 5.333333
    ry = region.radius_y * 5.333333
    return (
        f'<ellipse id="{region.key}" cx="{x:.2f}" cy="{y:.2f}" '
        f'rx="{rx:.2f}" ry="{ry:.2f}"/>'
    )


def document(regions) -> str:
    shapes = "\n".join(ellipse(region) for region in regions)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 960">\n'
        '<g fill="#39d7ee" fill-opacity=".2" stroke="#39d7ee">\n'
        f"{shapes}\n</g>\n</svg>\n"
    )


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    seas = [region for region in WATER_REGIONS if region.kind == "Море"]
    oceans = [region for region in WATER_REGIONS if region.kind == "Океан"]
    (OUTPUT / "seas.svg").write_text(document(seas), encoding="utf-8")
    (OUTPUT / "oceans.svg").write_text(document(oceans), encoding="utf-8")
    centers = {
        region.key: {
            "name": region.name,
            "kind": region.kind,
            "longitude": region.longitude,
            "latitude": region.latitude,
        }
        for region in WATER_REGIONS
    }
    (OUTPUT / "centers.json").write_text(
        json.dumps(centers, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for name, regions in (("sea_borders.json", seas), ("ocean_borders.json", oceans)):
        borders = {
            region.key: [
                region.longitude - region.radius_x,
                region.latitude - region.radius_y,
                region.longitude + region.radius_x,
                region.latitude + region.radius_y,
            ]
            for region in regions
        }
        (OUTPUT / name).write_text(
            json.dumps(borders, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(f"Built {len(seas)} sea regions and {len(oceans)} ocean regions")


if __name__ == "__main__":
    main()
