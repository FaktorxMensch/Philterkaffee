# -*- coding: utf-8 -*-
"""Name, Version, Urheber und Symbol des Addons."""

from __future__ import annotations

import os

from aqt.qt import QIcon, QPixmap

ADDON_NAME = "Philterkaffee"
TAGLINE = "Lernplan-Auswahlstapel für AnkiPhil"
MENU_TITLE = "Philterkaffee"
VERSION = "1.0.1"
AUTHOR_COMPANY = "Faktor Mensch MEDIA UG (haftungsbeschränkt)"
AUTHOR_PERSON = "Emanuel Leube"
AUTHOR = f"{AUTHOR_COMPANY} — {AUTHOR_PERSON}"
LICENSE = "AGPL-3.0-or-later"

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_ICON_SIZES = (16, 32, 64, 128, 256)

_icon: QIcon | None = None


def icon() -> QIcon:
    """Fensterymbol, aus den PNG-Größen zusammengesetzt.

    Bewusst nicht direkt aus der SVG: Qt braucht dafür das SVG-Bildmodul, und
    ein fehlendes Symbol wäre ein dummer Grund für eine Fehlermeldung.
    """
    global _icon
    if _icon is None:
        _icon = QIcon()
        for size in _ICON_SIZES:
            path = os.path.join(ASSETS, f"logo-{size}.png")
            if os.path.exists(path):
                _icon.addPixmap(QPixmap(path))
    return _icon
