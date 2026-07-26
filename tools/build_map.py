"""Подготавливает облегчённую карту из Natural Earth без внешних библиотек."""

from __future__ import annotations

import json
import math
import struct
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZIP_PATH = ROOT / "assets/maps/ne_10m_admin_0_countries.zip"
COUNTRIES_PATH = ROOT / "configs/countries_by_iso3.json"
MAP_DIR = ROOT / "assets/maps"
TINY_COUNTRY_CENTERS = {
    "MCO": (7.4246, 43.7384),
    "NRU": (166.9315, -0.5228),
    "SMR": (12.4578, 43.9424),
    "TUV": (179.1940, -8.5210),
    "VAT": (12.4534, 41.9029),
}
SIMPLIFY_TOLERANCE = 0.025


def dbf_records(data: bytes) -> list[dict[str, str]]:
    record_count = struct.unpack_from("<I", data, 4)[0]
    header_length, record_length = struct.unpack_from("<HH", data, 8)
    fields: list[tuple[str, int]] = []
    offset = 32
    while offset < header_length - 1:
        chunk = data[offset : offset + 32]
        name = chunk[:11].split(b"\0", 1)[0].decode("ascii")
        fields.append((name, chunk[16]))
        offset += 32
    records = []
    for index in range(record_count):
        row = data[header_length + index * record_length : header_length + (index + 1) * record_length]
        cursor = 1
        record: dict[str, str] = {}
        for name, length in fields:
            record[name] = (
                row[cursor : cursor + length]
                .decode("utf-8", "ignore")
                .strip(" \0")
            )
            cursor += length
        records.append(record)
    return records


def shp_records(data: bytes) -> list[list[list[tuple[float, float]]]]:
    result = []
    offset = 100
    while offset + 8 <= len(data):
        _, word_length = struct.unpack_from(">ii", data, offset)
        payload = data[offset + 8 : offset + 8 + word_length * 2]
        offset += 8 + word_length * 2
        if len(payload) < 44 or struct.unpack_from("<i", payload, 0)[0] not in (5, 15, 25):
            result.append([])
            continue
        part_count, point_count = struct.unpack_from("<ii", payload, 36)
        parts = list(struct.unpack_from(f"<{part_count}i", payload, 44))
        points_offset = 44 + part_count * 4
        points = [
            struct.unpack_from("<dd", payload, points_offset + index * 16)
            for index in range(point_count)
        ]
        rings = []
        for part_index, start in enumerate(parts):
            end = parts[part_index + 1] if part_index + 1 < len(parts) else len(points)
            rings.append(points[start:end])
        result.append(rings)
    return result


def perpendicular_distance(point, start, end) -> float:
    if start == end:
        return math.dist(point, start)
    dx, dy = end[0] - start[0], end[1] - start[1]
    return abs(dy * point[0] - dx * point[1] + end[0] * start[1] - end[1] * start[0]) / math.hypot(dx, dy)


def simplify(
    points: list[tuple[float, float]],
    tolerance: float = SIMPLIFY_TOLERANCE,
):
    if len(points) <= 4:
        return points
    first, last = points[0], points[-1]
    distance, split = 0.0, 0
    for index in range(1, len(points) - 1):
        candidate = perpendicular_distance(points[index], first, last)
        if candidate > distance:
            distance, split = candidate, index
    if distance > tolerance:
        left = simplify(points[: split + 1], tolerance)
        right = simplify(points[split:], tolerance)
        return left[:-1] + right
    return [first, last]


def svg_path(rings):
    chunks = []
    for ring in rings:
        if len(ring) < 3:
            continue
        coords = [((lon + 180) * 5.333333, (90 - lat) * 5.333333) for lon, lat in ring]
        chunks.append("M" + " ".join(f"{x:.1f},{y:.1f}" for x, y in coords) + "Z")
    return "".join(chunks)


def resolve_country_iso(record: dict[str, str], allowed: set[str]) -> str | None:
    """Maps special Natural Earth areas to a playable sovereign state."""
    for field in ("ADM0_A3", "ISO_A3", "ADM0_A3_RU", "ADM0_ISO"):
        candidate = record.get(field)
        if candidate in allowed:
            return candidate
    return None


def main() -> None:
    allowed = set(json.loads(COUNTRIES_PATH.read_text(encoding="utf-8")))
    with zipfile.ZipFile(ZIP_PATH) as archive:
        dbf_name = next(name for name in archive.namelist() if name.endswith(".dbf"))
        shp_name = next(name for name in archive.namelist() if name.endswith(".shp"))
        records = dbf_records(archive.read(dbf_name))
        shapes = shp_records(archive.read(shp_name))
    geometry: dict[str, list[list[list[float]]]] = defaultdict(list)
    land_geometry: list[list[list[float]]] = []
    labels: dict[str, list[float]] = {}
    for record, rings in zip(records, shapes):
        iso3 = resolve_country_iso(record, allowed)
        for ring in rings:
            reduced = simplify(ring)
            if len(reduced) >= 3:
                target = geometry[iso3] if iso3 else land_geometry
                target.append([[round(x, 4), round(y, 4)] for x, y in reduced])
        if iso3 and iso3 in (record.get("ADM0_A3"), record.get("ISO_A3")):
            try:
                labels[iso3] = [float(record["LABEL_X"]), float(record["LABEL_Y"])]
            except (KeyError, ValueError):
                pass
    for iso3 in allowed - set(geometry):
        if iso3 not in TINY_COUNTRY_CENTERS:
            continue
        longitude, latitude = TINY_COUNTRY_CENTERS[iso3]
        size = 0.32
        geometry[iso3] = [[
            [longitude, latitude - size],
            [longitude + size, latitude],
            [longitude, latitude + size],
            [longitude - size, latitude],
            [longitude, latitude - size],
        ]]
        labels[iso3] = [longitude, latitude]
    missing = sorted(allowed - set(geometry))
    if missing:
        print("No country shape:", ", ".join(missing))
    MAP_DIR.mkdir(parents=True, exist_ok=True)
    (MAP_DIR / "world_geometry.json").write_text(
        json.dumps(geometry, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    (MAP_DIR / "land_geometry.json").write_text(
        json.dumps(land_geometry, separators=(",", ":")), encoding="utf-8"
    )
    (MAP_DIR / "centers.json").write_text(
        json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    bins: dict[tuple[int, int], set[str]] = defaultdict(set)
    for iso3, rings in geometry.items():
        for ring in rings:
            for lon, lat in ring[:: max(1, len(ring) // 80)]:
                bins[(round(lon * 2), round(lat * 2))].add(iso3)
    neighbors: dict[str, set[str]] = {iso3: set() for iso3 in geometry}
    for countries in bins.values():
        for iso3 in countries:
            neighbors[iso3].update(countries - {iso3})
    (MAP_DIR / "neighbors.json").write_text(
        json.dumps({key: sorted(value) for key, value in neighbors.items()}, indent=2),
        encoding="utf-8",
    )
    paths = "\n".join(
        f'<path id="{iso3}" d="{svg_path(rings)}"/>' for iso3, rings in geometry.items()
    )
    land_paths = "\n".join(
        f'<path d="{svg_path([ring])}"/>' for ring in land_geometry
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 960">\n'
        '<rect width="1920" height="960" fill="#031b29"/>\n'
        '<g fill="#0a5572" stroke="#1683a4" stroke-width="0.7">\n'
        f"{land_paths}\n{paths}\n</g>\n</svg>\n"
    )
    (MAP_DIR / "world.svg").write_text(svg, encoding="utf-8")
    borders = svg.replace('fill="#0a5572"', 'fill="none"')
    (MAP_DIR / "world_borders.svg").write_text(borders, encoding="utf-8")
    print(f"Built {len(geometry)} country shapes")


if __name__ == "__main__":
    main()
