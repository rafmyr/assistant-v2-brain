"""Testy mózgu sesyjnego — każdy pilnuje konkretnego wyniku macierzy A0.2.

Nie są to testy 'czy kod się uruchamia'. Każdy odpowiada jednemu zmierzonemu zachowaniu CLI,
które potrafiło nas ugryźć — z numerem scenariusza w nazwie, żeby przy przyszłej zmianie
było wiadomo, co dokładnie się psuje.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path

import pytest

from assistant_v2_brain.kontekst import (
    BladMontazu,
    DaneWejsciowe,
    Tura,
    zbuduj_prompt_systemowy,
)
from assistant_v2_brain.sesja import BladSesji, MozgSesyjny, klucz_sesji


def _odp(result: str = "ok", sid: str = "sid-1", koszt: float = 0.01, tury: int = 1) -> str:
    return json.dumps(
        {"result": result, "session_id": sid, "total_cost_usd": koszt, "num_turns": tury}
    )


def _mozg(runner, tmp_path: Path) -> MozgSesyjny:
    return MozgSesyjny(katalog_roboczy=tmp_path, runner=runner, claude_bin="/bin/echo")


# --- montaż kontekstu -------------------------------------------------------------


def test_persona_ponad_limit_K3_to_twardy_blad() -> None:
    """Ciche obcięcie dałoby inną osobowość bez śladu — lekcja v1 (persona 5408 linii)."""
    with pytest.raises(BladMontazu, match="limit K3"):
        zbuduj_prompt_systemowy(DaneWejsciowe(persona="x\n" * 301))


def test_prompt_zawiera_wszystkie_cztery_zrodla() -> None:
    out = zbuduj_prompt_systemowy(
        DaneWejsciowe(
            persona="Jestem Jarvis.",
            pamiec_relacji="Rafał prowadzi projekt iXPOS.",
            stan_dnia="Jutro spotkanie o 10.",
            historia=(Tura("a", "b"),),
        )
    )
    assert "Jestem Jarvis." in out
    assert "iXPOS" in out
    assert "spotkanie o 10" in out
    assert "Jak rozmawiasz" in out


def test_braki_zrodel_trafiaja_do_promptu_jako_polecenie_powiedzenia_wprost() -> None:
    """Runtime-gate A1.3: koniec cichej degradacji do pewnie brzmiącego czatu bez danych."""
    out = zbuduj_prompt_systemowy(DaneWejsciowe(persona="x", braki=("kalendarz nie odpowiada",)))
    assert "kalendarz nie odpowiada" in out
    assert "Powiedz o tym wprost" in out


def test_dluga_pamiec_jest_przycieta_ze_sladem_nie_po_cichu() -> None:
    out = zbuduj_prompt_systemowy(DaneWejsciowe(persona="x", pamiec_relacji="a" * 20_000))
    assert "przycięte do" in out


# --- sesja: scenariusze macierzy A0.2 ---------------------------------------------


def test_s5_dwa_rownolegle_wywolania_w_jednym_watku_sa_serializowane(tmp_path: Path) -> None:
    """FAIL macierzy: równoległe --resume rozwidlają transkrypt i CICHO gubią gałąź."""
    rownoczesne = 0
    szczyt = 0

    async def runner(argv, timeout):  # noqa: ANN001, ARG001
        nonlocal rownoczesne, szczyt
        rownoczesne += 1
        szczyt = max(szczyt, rownoczesne)
        await asyncio.sleep(0.02)
        rownoczesne -= 1
        return 0, _odp(), ""

    async def scenariusz() -> None:
        mozg = _mozg(runner, tmp_path)
        await asyncio.gather(
            *(mozg.odpowiedz(f"pytanie {i}", "watek-po", "persona") for i in range(4))
        )

    asyncio.run(scenariusz())
    assert szczyt == 1, "wywołania w jednym wątku muszą iść po kolei, inaczej gubimy kontekst"


def test_rozne_watki_nie_blokuja_sie_nawzajem(tmp_path: Path) -> None:
    """Serializacja jest per wątek — globalna zamieniłaby kanał w kolejkę jednoosobową."""
    rownoczesne = 0
    szczyt = 0

    async def runner(argv, timeout):  # noqa: ANN001, ARG001
        nonlocal rownoczesne, szczyt
        rownoczesne += 1
        szczyt = max(szczyt, rownoczesne)
        await asyncio.sleep(0.02)
        rownoczesne -= 1
        return 0, _odp(), ""

    async def scenariusz() -> None:
        mozg = _mozg(runner, tmp_path)
        await asyncio.gather(
            mozg.odpowiedz("a", "watek-1", "p"), mozg.odpowiedz("b", "watek-2", "p")
        )

    asyncio.run(scenariusz())
    assert szczyt == 2


def test_s2_blad_cli_z_golym_tekstem_nie_wywraca_sie_na_json(tmp_path: Path) -> None:
    """Przy nieznanym session_id CLI łamie własny kontrakt --output-format json."""

    async def runner(argv, timeout):  # noqa: ANN001, ARG001
        return 1, "No conversation found with session ID: 000", ""

    mozg = _mozg(runner, tmp_path)
    with pytest.raises(BladSesji, match="No conversation found"):
        asyncio.run(mozg.odpowiedz("czesc", "w", "p"))


def test_blad_sesji_kasuje_id_zeby_kolejna_proba_zaczela_od_nowa(tmp_path: Path) -> None:
    mozg = _mozg(None, tmp_path)  # runner podmieniany niżej
    klucz = klucz_sesji("w")
    mozg.sesje.zapamietaj(klucz, "stare-id")
    (tmp_path / "x").write_text("")  # transkryptu i tak nie ma → id zostanie wyczyszczone

    async def runner(argv, timeout):  # noqa: ANN001, ARG001
        return 2, "", "cokolwiek padlo"

    mozg._runner = runner  # noqa: SLF001 — celowo, to test jednostkowy
    with pytest.raises(BladSesji):
        asyncio.run(mozg.odpowiedz("x", "w", "p"))
    assert mozg.sesje.pobierz(klucz) is None


def test_is_error_przy_exit_0_to_awaria_a_nie_tresc_odpowiedzi(tmp_path: Path) -> None:
    """Regresja zmierzona na prodzie 12.08: wygasly token = exit 0 + poprawny JSON.

    CLI ustawia `subtype: success` i wpisuje komunikat bledu w pole `result`. Bez tego
    sprawdzenia awaria autoryzacji poszlaby do PO jako wiadomosc od Jarvisa (brief poranny),
    a fallback na stara sciezke nie odpalilby sie, bo nie byloby wyjatku.
    """
    ladunek = json.dumps(
        {
            "is_error": True,
            "subtype": "success",
            "api_error_status": 401,
            "session_id": "f9b41c75",
            "result": "Failed to authenticate. API Error: 401 OAuth access token has expired.",
            "total_cost_usd": 0,
            "num_turns": 1,
        }
    )

    async def runner(argv, timeout):  # noqa: ANN001, ARG001
        return 0, ladunek, ""

    mozg = _mozg(runner, tmp_path)
    with pytest.raises(BladSesji, match="HTTP 401"):
        asyncio.run(mozg.odpowiedz("x", "w", "p"))


def test_ostrzezenie_cli_nie_przeslania_prawdziwej_przyczyny(tmp_path: Path) -> None:
    """Ostrzezenia wypadaja przed bledem; branie pierwszej linii dawalo mylna diagnoze."""

    async def runner(argv, timeout):  # noqa: ANN001, ARG001
        return 1, "", "Warning: no stdin data received in 3s\nprawdziwa przyczyna awarii"

    mozg = _mozg(runner, tmp_path)
    with pytest.raises(BladSesji, match="prawdziwa przyczyna awarii"):
        asyncio.run(mozg.odpowiedz("x", "w", "p"))


def test_stdin_jest_zamkniety_zeby_cli_nie_czekalo(tmp_path: Path) -> None:
    """Otwarty deskryptor = 3 s czekania w KAZDYM wywolaniu pod launchd."""
    src = (
        Path(__file__).resolve().parent.parent / "src" / "assistant_v2_brain" / "sesja.py"
    ).read_text(encoding="utf-8")
    assert "stdin=asyncio.subprocess.DEVNULL" in src


def test_pusta_odpowiedz_to_blad_a_nie_cisza_do_PO(tmp_path: Path) -> None:
    async def runner(argv, timeout):  # noqa: ANN001, ARG001
        return 0, _odp(result="   "), ""

    mozg = _mozg(runner, tmp_path)
    with pytest.raises(BladSesji, match="pustą odpowiedź"):
        asyncio.run(mozg.odpowiedz("x", "w", "p"))


def test_pierwsze_wywolanie_niesie_persone_wznowienie_juz_nie(tmp_path: Path) -> None:
    """Persona jest w transkrypcie po starcie; powtarzanie jej dokładałoby kontekst co turę."""
    argvy: list[list[str]] = []

    async def runner(argv, timeout):  # noqa: ANN001, ARG001
        argvy.append(argv)
        return 0, _odp(sid="sid-abc"), ""

    async def scenariusz() -> None:
        mozg = _mozg(runner, tmp_path)
        await mozg.odpowiedz("pierwsze", "w", "PERSONA-TU")
        # podstawiamy istniejący transkrypt, żeby wznowienie nie zostało zresetowane
        slug = str(tmp_path.resolve()).replace("/", "-")
        kat = Path.home() / ".claude" / "projects" / slug
        kat.mkdir(parents=True, exist_ok=True)
        (kat / "sid-abc.jsonl").write_text('{"x":1}\n')
        try:
            await mozg.odpowiedz("drugie", "w", "PERSONA-TU")
        finally:
            (kat / "sid-abc.jsonl").unlink(missing_ok=True)

    asyncio.run(scenariusz())
    assert "--append-system-prompt" in argvy[0]
    assert "--resume" not in argvy[0]
    assert "--resume" in argvy[1]
    assert "--append-system-prompt" not in argvy[1]


def test_budzet_jest_w_kazdym_wywolaniu(tmp_path: Path) -> None:
    """K5: zimne wznowienie przy 320k kontekstu kosztowało $1,91 za jedną wiadomość."""
    argvy: list[list[str]] = []

    async def runner(argv, timeout):  # noqa: ANN001, ARG001
        argvy.append(argv)
        return 0, _odp(), ""

    mozg = _mozg(runner, tmp_path)
    asyncio.run(mozg.odpowiedz("x", "w", "p"))
    assert "--max-budget-usd" in argvy[0]


def test_klucz_sesji_rotuje_sie_co_dobe() -> None:
    """B1: sesja per wątek-dzień. CLI nie zna pojęcia doby — szew jest wyłącznie u nas."""
    assert klucz_sesji("w", date(2026, 8, 12)) != klucz_sesji("w", date(2026, 8, 13))
