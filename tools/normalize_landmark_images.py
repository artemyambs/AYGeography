"""Normalize landmark photos to the game's 16:9 image contract."""

from __future__ import annotations

import argparse
from pathlib import Path

import pygame


TARGET_SIZE = (960, 540)
CONTACT_COLUMNS = 3
CONTACT_ROWS = 5


def _center_crop(surface: pygame.Surface) -> pygame.Surface:
    width, height = surface.get_size()
    target_ratio = TARGET_SIZE[0] / TARGET_SIZE[1]
    if width / height > target_ratio:
        crop_width = round(height * target_ratio)
        area = pygame.Rect((width - crop_width) // 2, 0, crop_width, height)
    else:
        crop_height = round(width / target_ratio)
        area = pygame.Rect(0, (height - crop_height) // 2, width, crop_height)
    return surface.subsurface(area).copy()


def normalize(source: Path, destination: Path) -> None:
    image = pygame.image.load(source)
    if source.resolve() == destination.resolve() and image.get_size() == TARGET_SIZE:
        return
    cropped = _center_crop(image)
    normalized = pygame.transform.smoothscale(cropped, TARGET_SIZE)
    pygame.image.save(normalized, destination)


def parse_replacements(values: list[str]) -> dict[str, Path]:
    replacements: dict[str, Path] = {}
    for value in values:
        name, separator, source = value.partition("=")
        if not separator or not name or not source:
            raise ValueError(f"Invalid replacement: {value}")
        replacements[name] = Path(source)
    return replacements


def create_contact_sheets(directory: Path, output_directory: Path) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    files = sorted(directory.glob("*.jpg"))
    pygame.font.init()
    font = pygame.font.Font(None, 24)
    cell_width, cell_height = 320, 205
    page_size = CONTACT_COLUMNS * CONTACT_ROWS
    for page, offset in enumerate(range(0, len(files), page_size), start=1):
        sheet = pygame.Surface(
            (CONTACT_COLUMNS * cell_width, CONTACT_ROWS * cell_height)
        )
        sheet.fill("#101820")
        for index, path in enumerate(files[offset : offset + page_size]):
            column = index % CONTACT_COLUMNS
            row = index // CONTACT_COLUMNS
            image = pygame.image.load(path)
            thumbnail = pygame.transform.smoothscale(image, (300, 169))
            x = column * cell_width + 10
            y = row * cell_height + 8
            sheet.blit(thumbnail, (x, y))
            sheet.blit(font.render(path.stem, True, "white"), (x, y + 174))
        pygame.image.save(sheet, output_directory / f"landmarks_{page}.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--replace", action="append", default=[])
    parser.add_argument("--contact-sheet-dir", type=Path)
    parser.add_argument("--skip-normalize", action="store_true")
    args = parser.parse_args()
    replacements = parse_replacements(args.replace)

    if not args.skip_normalize:
        for destination in sorted(args.directory.glob("*.jpg")):
            source = replacements.get(destination.stem, destination)
            if not source.is_file():
                raise FileNotFoundError(source)
            normalize(source, destination)
    if args.contact_sheet_dir:
        create_contact_sheets(args.directory, args.contact_sheet_dir)


if __name__ == "__main__":
    main()
