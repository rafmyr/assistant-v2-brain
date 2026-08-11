"""Straznik kontraktu A0.13: granica brain <-> maszynownia.

Wariant A (biblioteka) daje granice MIEKKA — nic fizycznie nie blokuje siegniecia
do maszynowni, pilnuje jej wylacznie ten test. To jest jego jedyny powod istnienia
i dlatego stoi w repo od commita pierwszego, nie "kiedys pozniej".
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"

# Moduly maszynowni (`assistant-v2/src/`). Import ktoregokolwiek = zlamanie kontraktu.
ZAKAZANE = {"dispatcher", "gateway_lite", "memory", "scheduler", "shared", "policy", "reasoner"}


def _wszystkie_importy() -> set[str]:
    """Korzenie wszystkich importow w src/ (AST, nie grep — komentarz nie oszuka)."""
    korzenie: set[str] = set()
    for plik in SRC.rglob("*.py"):
        drzewo = ast.parse(plik.read_text(encoding="utf-8"), filename=str(plik))
        for wezel in ast.walk(drzewo):
            if isinstance(wezel, ast.Import):
                korzenie.update(alias.name.split(".")[0] for alias in wezel.names)
            elif isinstance(wezel, ast.ImportFrom) and wezel.level == 0 and wezel.module:
                korzenie.add(wezel.module.split(".")[0])
    return korzenie


def test_brain_nie_importuje_maszynowni() -> None:
    """Strzalka jest jednokierunkowa: assistant-v2 -> assistant_v2_brain, nigdy odwrotnie."""
    naruszenia = _wszystkie_importy() & ZAKAZANE
    assert not naruszenia, (
        f"KONTRAKT A0.13 ZLAMANY: brain importuje z maszynowni: {sorted(naruszenia)}. "
        "Brain nie wie o istnieniu assistant-v2 — dane wejsciowe dostaje w argumencie."
    )


def test_brain_stoi_na_stdlib() -> None:
    """Zaleznosci zewnetrzne wchodza SWIADOMIE, przez pyproject, nie przypadkiem.

    Startujemy z pustego `dependencies` (wzor: reasoner, 583 LOC na samym stdlib).
    Ten test pilnuje, ze nowa zaleznosc pojawia sie razem z wpisem w pyproject.
    """
    zadeklarowane = {"assistant_v2_brain"} | set(sys.stdlib_module_names)
    obce = {k for k in _wszystkie_importy() if k not in zadeklarowane}
    assert not obce, (
        f"Import spoza stdlib bez wpisu w pyproject.toml: {sorted(obce)}. "
        "Dodaj do [project].dependencies i przelockuj (`uv lock`)."
    )
