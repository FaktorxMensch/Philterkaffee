#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Baut die verteilbare ``.ankiaddon``-Datei.

    python3 tools/build_ankiaddon.py

Eine ``.ankiaddon`` ist ein ZIP, dessen Dateien **direkt** an der Wurzel liegen
(``__init__.py``, ``manifest.json``, …) — ohne umschließenden Ordner. Anki
lehnt das Paket sonst ab.

``meta.json`` darf nicht mit hinein: Anki schreibt die Datei selbst in den
Addon-Ordner, und eine mitgelieferte würde die lokalen Angaben des Benutzers
überschreiben.
"""

from __future__ import annotations

import json
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "ankiphil_lernplan"
DIST = ROOT / "dist"

EXCLUDED_NAMES = {"meta.json", ".DS_Store"}
EXCLUDED_DIRS = {"__pycache__"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def collect() -> list[pathlib.Path]:
    files = []
    for path in sorted(PACKAGE.rglob("*")):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.name in EXCLUDED_NAMES or path.suffix in EXCLUDED_SUFFIXES:
            continue
        files.append(path)
    return files


def main() -> int:
    manifest_path = PACKAGE / "manifest.json"
    if not manifest_path.exists():
        print("manifest.json fehlt", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = manifest.get("human_version", "0.0.0")

    files = collect()
    if not any(path.name == "__init__.py" and path.parent == PACKAGE for path in files):
        print("__init__.py fehlt an der Paketwurzel", file=sys.stderr)
        return 1

    DIST.mkdir(exist_ok=True)
    target = DIST / f"ankiphil-lernplan-{version}.ankiaddon"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(PACKAGE).as_posix())

    size = target.stat().st_size
    print(f"{target.relative_to(ROOT)}  ({len(files)} Dateien, {size / 1024:.0f} KB)")
    print()
    print("Weitergeben: Datei verschicken. Installieren in Anki über")
    print("Extras → Add-ons → „Aus Datei installieren …“, danach Anki neu starten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
