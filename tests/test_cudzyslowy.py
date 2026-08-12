"""Strażnik cudzysłowów typograficznych WEWNĄTRZ literałów stringowych.

POWÓD (12.08.2026): polski cudzysłów otwierający U+201E wygląda jak część tekstu, ale
domykany bywa zwykłym `"` — a ten kończy literał w Pythonie. Skutek to `SyntaxError`
w miejscu oddalonym od przyczyny albo, gorzej, string urwany w połowie zdania.

DLACZEGO WĄSKO: w docstringach `\"\"\"…\"\"\"` i w komentarzach `# …` te znaki są
całkowicie bezpieczne i jest ich w repo setki — szeroki zakaz dałby 388 fałszywych
alarmów i wylądowałby w koszu po tygodniu. Sprawdzamy więc wyłącznie tokeny STRING
o pojedynczym ograniczniku, czyli dokładnie ten wzorzec, który potrafi urwać treść.

Reguła istniała wcześniej w pamięci projektu jako gotcha o cudzysłowach w skryptach
patchujących. Nie zadziałała, bo była węższa niż problem i nie miała egzekutora.
To jest ten egzekutor — lekcja własna: reguła bez punktu egzekucji jest życzeniem.
"""

from __future__ import annotations

import io
import tokenize
from pathlib import Path

import pytest

# Kodami, nie literalnie — inaczej ten plik nie przeszedłby własnego testu.
TYPOGRAFICZNE = (chr(0x201E), chr(0x201C), chr(0x201D))

KORZEN = Path(__file__).resolve().parent.parent
POMIJAJ = {".venv", ".venv-uv", "node_modules", ".git", "__pycache__", "build", "dist"}


def _pliki_py() -> list[Path]:
    return [p for p in KORZEN.rglob("*.py") if not any(c in POMIJAJ for c in p.parts)]


def _ryzykowne_stringi(plik: Path) -> list[tuple[int, str]]:
    """Tokeny STRING z pojedynczym ogranicznikiem, zawierające znak typograficzny."""
    trafienia: list[tuple[int, str]] = []
    tekst = plik.read_text(encoding="utf-8")
    try:
        tokeny = list(tokenize.generate_tokens(io.StringIO(tekst).readline))
    except (tokenize.TokenError, SyntaxError):
        # Plik i tak nie przejdzie ruffa ani importu — nie dublujemy tamtego błędu.
        return []
    for tok in tokeny:
        if tok.type != tokenize.STRING:
            continue
        surowy = tok.string
        if surowy.count('"""') or surowy.count("'''"):
            continue  # docstring / string wieloliniowy: bezpieczny
        if any(znak in surowy for znak in TYPOGRAFICZNE):
            trafienia.append((tok.start[0], surowy.strip()[:90]))
    return trafienia


def test_brak_cudzyslowow_typograficznych_w_literalach_stringowych() -> None:
    znalezione: list[str] = []
    for plik in _pliki_py():
        for nr, fragment in _ryzykowne_stringi(plik):
            znalezione.append(f"{plik.relative_to(KORZEN)}:{nr} → {fragment}")

    if znalezione:
        pytest.fail(
            "Cudzysłów typograficzny w jednolinijkowym literale stringowym — potrafi urwać "
            "treść na zamykającym znaku:\n"
            + "\n".join(f"  {t}" for t in znalezione)
            + "\n\nW takich miejscach używaj apostrofów albo zwykłych cudzysłowów. "
            "W docstringach i komentarzach znaki typograficzne są w porządku."
        )
