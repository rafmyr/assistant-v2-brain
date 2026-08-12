"""Sesja rozmowy przez `claude -p --resume` (A1, tor A planu Jarvis 2.5).

Każdy element tego modułu ma źródło w zmierzonym zachowaniu CLI — macierz A0.2 z 12.08
(`assistant-v2/docs/A0.2-WYNIKI-RESUME.md`, 68 wywołań, $23,51):

  * **kolejka per wątek** — dwa równoległe `--resume` tej samej sesji rozwidlają transkrypt
    w drzewo, a kolejne wznowienie idzie JEDNYM ramieniem i cicho gubi drugie. Bez błędu,
    `is_error: false`. Wzorzec produkcyjny: PO wysyła dwie wiadomości pod rząd. To warunek
    poprawności, nie optymalizacja (scenariusz 5, jedyny FAIL macierzy);
  * **parser czytający najpierw kod wyjścia** — przy nieznanym `session_id` CLI łamie własny
    kontrakt `--output-format json` i zwraca goły tekst. `json.loads` dałoby `JSONDecodeError`
    zamiast czytelnej diagnozy (scenariusz 2);
  * **rozróżnienie 'sesji nie było' od 'transkrypt uszkodzony'** — CLI daje na to identyczny
    komunikat, więc robi to nasz kod, sprawdzając plik przed wywołaniem (scenariusz 3);
  * **budżet per wywołanie** — `--max-budget-usd`. Zimne wznowienie przy 320k kontekstu
    kosztowało $1,91 za jedną wiadomość (§3 macierzy);
  * **sesja per wątek-dzień** — B1. CLI nie zna pojęcia doby (jeden plik per `session_id`,
    bez daty w nazwie), więc szew jest wyłącznie tutaj.

K9 zostaje: proces LLM żyje jedno zadanie. Ciągłość niesie transkrypt i pliki, nie demon.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

TIMEOUT_S = 180.0  # macierz A0.2 §8: kompaktowanie potrafi trwać 89 s; 60 s ucinało w pół zdania
BUDZET_USD = 0.60  # K5; przekroczenie = twardy błąd CLI, nie cichy koszt


class BladSesji(RuntimeError):
    """Awaria mózgu. Typowana z rozmysłem: maszynownia ma po niej wrócić na starą ścieżkę
    (flaga `V2_SESSION_BRAIN`), a nie odpowiedzieć ciszą albo zmyśloną treścią."""


@dataclass(frozen=True)
class WynikSesji:
    tresc: str
    session_id: str
    koszt_usd: float
    tury: int
    wznowiona: bool


def klucz_sesji(watek: str, dzien: date | None = None) -> str:
    """Identyfikator sesji per wątek-dzień (B1). Rotacja o północy jest NASZA — CLI jej nie ma."""
    return f"{watek}:{(dzien or date.today()).isoformat()}"


class Sesje:
    """Mapa wątek-dzień → `session_id` + zamki serializujące wywołania.

    Trzymana w pamięci procesu świadomie: `session_id` jest odtwarzalny (przy braku wpisu
    startujemy nową sesję, tracąc co najwyżej ciągłość jednej wymiany), a trwały magazyn
    dokładałby stan do synchronizacji między `serve` a `tick`. Gdyby ciągłość po restarcie
    okazała się potrzebna — to jest miejsce na sqlite, nie cały moduł.
    """

    def __init__(self) -> None:
        self._id: dict[str, str] = {}
        self._zamki: dict[str, asyncio.Lock] = {}

    def zamek(self, klucz: str) -> asyncio.Lock:
        return self._zamki.setdefault(klucz, asyncio.Lock())

    def pobierz(self, klucz: str) -> str | None:
        return self._id.get(klucz)

    def zapamietaj(self, klucz: str, session_id: str) -> None:
        self._id[klucz] = session_id

    def zapomnij(self, klucz: str) -> None:
        self._id.pop(klucz, None)


def _transkrypt_istnieje(session_id: str, cwd: Path) -> bool:
    """Czy transkrypt tej sesji jest na dysku i niepusty.

    CLI daje ten sam komunikat dla 'sesji nigdy nie było' (normalne) i 'plik uszkodzony'
    (utrata danych). Rozróżnienie musi dać nasz kod — stąd ten check przed wywołaniem.
    Slug katalogu to ścieżka robocza z zamienionymi `/` na `-` (zmierzone w A0.2).
    """
    slug = str(cwd.resolve()).replace("/", "-")
    plik = Path.home() / ".claude" / "projects" / slug / f"{session_id}.jsonl"
    try:
        return plik.is_file() and plik.stat().st_size > 0
    except OSError:
        return False


RunnerFn = Callable[[list[str], float], Awaitable[tuple[int, str, str]]]


async def _uruchom(argv: list[str], timeout_s: float) -> tuple[int, str, str]:
    # stdin=DEVNULL, bo CLI czeka 3 s na dane wejsciowe i dokleja ostrzezenie do stderr,
    # jesli deskryptor jest otwarty. Pod launchd to strata 3 s w kazdym wywolaniu,
    # a pod SSH ostrzezenie ladowalo w diagnozie zamiast prawdziwej przyczyny.
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise BladSesji(f"sesja przekroczyła {timeout_s:.0f} s i została ubita") from None
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


class MozgSesyjny:
    """Prowadzi rozmowę w jednym wątku. Jedna instancja na proces."""

    def __init__(
        self,
        *,
        katalog_roboczy: Path,
        profil_mcp: Path | None = None,
        model: str = "sonnet",
        budzet_usd: float = BUDZET_USD,
        timeout_s: float = TIMEOUT_S,
        claude_bin: str | None = None,
        runner: RunnerFn | None = None,
    ) -> None:
        self._cwd = katalog_roboczy
        self._profil = profil_mcp
        self._model = model
        self._budzet = budzet_usd
        self._timeout = timeout_s
        self._bin = claude_bin or shutil.which("claude") or "claude"
        self._runner = runner or _uruchom
        self.sesje = Sesje()

    def _argv(self, pytanie: str, prompt_systemowy: str, session_id: str | None) -> list[str]:
        argv = [self._bin, "-p", pytanie, "--model", self._model, "--output-format", "json"]
        # Persona idzie w --append-system-prompt tylko przy STARCIE sesji. Przy wznowieniu
        # jest już w transkrypcie; powtórzenie dokładałoby ją do kontekstu przy każdej turze.
        if session_id is None:
            argv += ["--append-system-prompt", prompt_systemowy]
        else:
            argv += ["--resume", session_id]
        argv += ["--max-budget-usd", f"{self._budzet:.2f}"]
        if self._profil is not None:
            argv += ["--mcp-config", str(self._profil), "--strict-mcp-config"]
        return argv

    async def odpowiedz(
        self, wiadomosc: str, watek: str, prompt_systemowy: str, *, dzien: date | None = None
    ) -> WynikSesji:
        """Jedna wymiana. Wywołania w obrębie wątku są SERIALIZOWANE (scenariusz 5 macierzy)."""
        klucz = klucz_sesji(watek, dzien)
        async with self.sesje.zamek(klucz):
            sid = self.sesje.pobierz(klucz)
            if sid is not None and not _transkrypt_istnieje(sid, self._cwd):
                # Transkrypt zniknął albo jest pusty — startujemy nową sesję zamiast dostawać
                # mylące 'No conversation found'. Ciągłość przepadła, ale rozmowa idzie dalej.
                self.sesje.zapomnij(klucz)
                sid = None

            kod, out, err = await self._runner(
                self._argv(wiadomosc, prompt_systemowy, sid), self._timeout
            )

            if kod != 0:
                # NAJPIERW kod wyjścia, dopiero potem JSON — przy błędzie CLI zwraca goły tekst
                # i `json.loads` dałoby JSONDecodeError zamiast diagnozy (scenariusz 2).
                # Ostrzeżenia CLI (np. o stdin) wypadają PRZED właściwym błędem, więc branie
                # pierwszej linii pokazywało w diagnozie nie tę awarię, która wystąpiła.
                linie = [
                    lin.strip()
                    for lin in (err or out).strip().splitlines()
                    if lin.strip() and not lin.strip().startswith("Warning:")
                ]
                powod = linie[0] if linie else f"exit {kod}"
                if sid is not None:
                    self.sesje.zapomnij(klucz)
                raise BladSesji(f"claude -p zakończył się błędem: {powod}")

            try:
                dane = json.loads(out)
            except json.JSONDecodeError as exc:
                raise BladSesji(f"odpowiedź nie jest JSON-em mimo exit 0: {exc}") from exc

            # Kod wyjścia NIE WYSTARCZA. Zmierzone na prodzie 12.08 przy wygasłym tokenie:
            # exit 0, poprawny JSON, `subtype: success` — i komunikat błędu API wpisany
            # w pole `result`. Bez tego sprawdzenia awaria autoryzacji wychodzi do PO jako
            # treść wiadomości od Jarvisa, a fallback na starą ścieżkę się NIE odpala,
            # bo nie ma wyjątku. Pole `is_error` jest jedynym wiarygodnym sygnałem.
            if dane.get("is_error"):
                status = dane.get("api_error_status")
                opis = str(dane.get("result") or "").strip() or "bez opisu"
                sufiks = f" (HTTP {status})" if status else ""
                if sid is not None:
                    self.sesje.zapomnij(klucz)
                raise BladSesji(f"CLI zgłosiło błąd mimo exit 0{sufiks}: {opis}")

            tresc = str(dane.get("result") or "").strip()
            if not tresc:
                raise BladSesji("model zwrócił pustą odpowiedź")

            nowy_sid = str(dane.get("session_id") or sid or "")
            if nowy_sid:
                self.sesje.zapamietaj(klucz, nowy_sid)

            return WynikSesji(
                tresc=tresc,
                session_id=nowy_sid,
                koszt_usd=float(dane.get("total_cost_usd") or 0.0),
                tury=int(dane.get("num_turns") or 0),
                wznowiona=sid is not None,
            )


def katalog_roboczy_z_env() -> Path:
    """Katalog, w którym CLI trzyma transkrypty i własną auto-pamięć.

    Osobny od repo maszynowni z rozmysłem: auto-pamięć CLI jest kluczowana katalogiem
    roboczym (znalezisko A0.2 §4) i pisze pliki autonomicznie, poza `policy` i walidatorem.
    Trzymamy ją w jednym, jawnym miejscu zamiast pozwolić jej powstać w drzewie repo.
    """
    domyslny = Path.home() / "dev/assistant-v2-channels/brain"
    return Path(os.environ.get("V2_BRAIN_CWD", str(domyslny)))
