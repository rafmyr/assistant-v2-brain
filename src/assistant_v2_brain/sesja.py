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
from typing import Any

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


RunnerFn = Callable[[list[str], float, Path], Awaitable[tuple[int, str, str]]]


async def _uruchom(argv: list[str], timeout_s: float, cwd: Path) -> tuple[int, str, str]:
    # stdin=DEVNULL, bo CLI czeka 3 s na dane wejsciowe i dokleja ostrzezenie do stderr,
    # jesli deskryptor jest otwarty. Pod launchd to strata 3 s w kazdym wywolaniu,
    # a pod SSH ostrzezenie ladowalo w diagnozie zamiast prawdziwej przyczyny.
    # cwd JEST OBOWIĄZKOWE. CLI zapisuje transkrypt do katalogu wyliczonego ze SWOJEGO
    # katalogu roboczego; bez tego proces dziedziczył cwd rodzica (serve), transkrypty
    # lądowały pod innym slugiem niż ten, którego szuka `_transkrypt_istnieje`, więc
    # KAŻDA wiadomość startowała nową sesję (`wznowiona=False`) i rozmowa nie miała
    # historii. Zmierzone na prodzie 13.08: 6 wiadomości pod rząd, 6 różnych session_id,
    # a model odpowiadał „początek rozmowy jest pusty" na własne pytanie sprzed 10 sekund.
    cwd.mkdir(parents=True, exist_ok=True)
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(cwd),
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


def wyluskaj_json(tekst: str) -> dict[str, Any]:
    """Wydobywa obiekt JSON z odpowiedzi modelu.

    Model bywa uprzejmy: opakowuje wynik w blok markdown albo dokleja zdanie wstępne.
    Zamiast zakazywać mu tego w prompcie — zakaz bez egzekutora jest życzeniem —
    radzimy sobie z tym w kodzie.
    """
    surowy = tekst.strip()
    if surowy.startswith("```"):
        linie = surowy.splitlines()[1:]  # otwierający płotek, czasem z nazwą języka
        if linie and linie[-1].strip().startswith("```"):
            linie = linie[:-1]
        surowy = "\n".join(linie).strip()
    if not surowy.startswith("{"):
        poczatek, koniec = surowy.find("{"), surowy.rfind("}")
        if poczatek == -1 or koniec <= poczatek:
            raise BladSesji(f"w odpowiedzi nie ma obiektu JSON: {surowy[:120]}")
        surowy = surowy[poczatek : koniec + 1]
    try:
        dane = json.loads(surowy)
    except json.JSONDecodeError as exc:
        raise BladSesji(f"odpowiedź nie jest poprawnym JSON-em: {exc}") from exc
    if not isinstance(dane, dict):
        # Praktycznie nieosiągalne (wyżej wycinamy fragment od `{` do `}`), ale to jest
        # miejsce, w którym `Any` z `json.loads` zamienia się w konkretny typ — bez tego
        # zwracalibyśmy `Any` udające `dict`, co mypy słusznie odrzuca.
        raise BladSesji(f"oczekiwano obiektu JSON, jest {type(dane).__name__}")
    return dane


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

    async def odpowiedz_ze_struktura(
        self,
        wiadomosc: str,
        watek: str,
        prompt_systemowy: str,
        *,
        walidator: Callable[[dict[str, Any]], None],
        proby: int = 2,
        dzien: date | None = None,
    ) -> tuple[dict[str, Any], WynikSesji]:
        """Odpowiedź, która MUSI być strukturą przechodzącą walidację.

        Po co: ścieżki takie jak ekstrakcja z nagrań Plaud egzekwują kontrakt w KODZIE
        (`jsonschema`), a nie w prompcie. Bez tego trybu mózg nie może ich obsłużyć —
        `odpowiedz()` zwraca prozę.

        Dlaczego walidator jest WSTRZYKIWANY, a nie zaszyty tutaj: ta biblioteka ma zero
        zależności spoza stdlib i tak ma zostać (kontrakt A0.13). `jsonschema` mieszka
        w maszynowni, więc to ona podaje funkcję sprawdzającą; my odpowiadamy wyłącznie
        za pętlę prób.

        Poprawka leci jako KOLEJNA TURA tej samej sesji, nie jako nowe pytanie — model
        widzi własną odpowiedź i komunikat walidatora, więc poprawia konkret zamiast
        zgadywać od zera.
        """
        if proby < 1:
            raise ValueError("proby musi być >= 1")

        ostatni_blad = ""
        tresc_prosby = wiadomosc
        for nr in range(1, proby + 1):
            wynik = await self.odpowiedz(tresc_prosby, watek, prompt_systemowy, dzien=dzien)
            try:
                dane = wyluskaj_json(wynik.tresc)
                walidator(dane)
            except BladSesji as exc:
                ostatni_blad = str(exc)
            except Exception as exc:  # noqa: BLE001 — walidator jest cudzy, może rzucić czymkolwiek
                ostatni_blad = f"{type(exc).__name__}: {exc}"
            else:
                return dane, wynik

            if nr < proby:
                tresc_prosby = (
                    "Twoja poprzednia odpowiedź nie przeszła walidacji: "
                    f"{ostatni_blad}\n\n"
                    "Odpowiedz PONOWNIE, wyłącznie obiektem JSON zgodnym ze schematem. "
                    "Bez komentarza przed ani po, bez bloku markdown."
                )

        raise BladSesji(f"struktura nie przeszła walidacji po {proby} próbach: {ostatni_blad}")

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
                self._argv(wiadomosc, prompt_systemowy, sid), self._timeout, self._cwd
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
