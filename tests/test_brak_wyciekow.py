"""Bramka anty-wyciekowa: to repo jest PUBLICZNE, jego konsument nie jest.

Powód powstania (16.08.2026, przegląd PO): repo było czyste PRZYPADKIEM, nie mechanizmem.
Zawartość sprawdzono ręcznie raz, przy publikacji. Nic nie stało na drodze, żeby następna
sesja wkleiła fragment realnych danych do fixture'a testowego i wypchnęła to na publicznego
maina. Ten test zamienia "uważamy, żeby nic nie wsypać" w egzekutor.

CO SKANUJE: wyłącznie pliki śledzone przez gita (`git ls-files`). Katalogi robocze
(`.venv-uv/`, cache) są z definicji poza zakresem — one nigdy nie trafiają na origin.

CZEGO NIE ZAŁATWIA (jawnie, żeby nikt nie brał tego za komplet):
  * Historii gita. Skan dotyczy drzewa roboczego. Sekret zacommitowany i usunięty
    w kolejnym commicie zostaje w historii i ten test go NIE zobaczy.
  * Danych, które nie pasują do żadnego wzorca poniżej. Lista zakazanych nazw jest
    skończona i pisana ręcznie.
  * Treści, którą model wygeneruje dopiero w runtime. Persona i pamięć relacji przychodzą
    z zewnątrz (kontrakt A0.13), więc ich tu nie ma i nie ma czego skanować.

Zaciemnienie, nie kryptografia: zakazane nazwy własne trzymamy jako skrócone SHA-256
z solą, bo sama LISTA nazw (klienci, projekty) jest tym, czego nie chcemy publikować.
Sól leży obok w pliku, więc atak słownikowy jest trywialny. Cel jest inny: żeby lista nie
była CZYTELNA dla kogoś, kto po prostu przegląda repo.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Ten plik z definicji zawiera wzorce, którymi się skanuje, więc skanowanie go sobą samym
# dałoby trafienie na własną definicję. Świadomy i JEDYNY wyjątek; jego treści pilnuje
# przegląd PR, nie automat.
POMIJANE = {"tests/test_brak_wyciekow.py"}

SOL = "assistant-v2-brain/anty-wyciek/v1"

# sha256(SOL + token)[:16] dla nazwisk, nazw klientów i nazw prywatnych systemów.
ZAKAZANE_TOKENY = {
    "0c9524f7cc7cd0a7",
    "1309e3bd6fa85336",
    "1ba508c702e000c7",
    "55bc9f167186b4b5",
    "5ad1c168e2419477",
    "5c1f6ec023453bec",
    "68eaf6885994cf64",
    "6baca5c096059b0a",
    "8d11259d93b51bc7",
    "97cb2d25c37ddd43",
    "a6ff00218664bb48",
    "c37bedefa0f49232",
}

TOKENIZATOR = re.compile(r"[A-Za-z0-9_-]+")

# Klasy techniczne. Te wzorce nie ujawniają niczego, więc stoją jawnie.
WZORCE: list[tuple[str, re.Pattern[str]]] = [
    (
        "adres e-mail",
        # noreply GitHuba jest w git logu z założenia i nie jest danymi osobowymi
        re.compile(r"\b[A-Za-z0-9._%+-]+@(?!users\.noreply\.github\.com)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
    ("ścieżka domowa macOS", re.compile(r"/Users/[A-Za-z0-9._-]+")),
    ("ścieżka domowa Linuksa", re.compile(r"/home/[A-Za-z0-9._-]+")),
    # Wymagamy myślnika w nazwie hosta (rafals-mac-mini.local), żeby nie łapać
    # zwykłych atrybutów w kodzie w rodzaju `wersja.local`. Ograniczenie świadome:
    # jednoczłonowy hostname .local przejdzie.
    ("host .local w sieci domowej", re.compile(r"\b[a-z0-9]+(?:-[a-z0-9]+)+\.local\b")),
    ("numer telefonu", re.compile(r"(?<![\d.])(?:\+48[ -]?)?(?:\d{3}[ -]){2}\d{3}(?![\d.])")),
    ("klucz API Anthropic", re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}")),
    ("token GitHuba", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{16,}\b")),
    ("token GitHuba (PAT v2)", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("klucz AWS", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("token Slacka", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("klucz prywatny", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    (
        "sekret przypisany do zmiennej",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|haslo)\b\s*[:=]\s*"
            r"[\"'][^\"'\s]{12,}[\"']"
        ),
    ),
]


def _pliki_repo() -> list[str]:
    wynik = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    )
    return [s for s in wynik.stdout.splitlines() if s and s not in POMIJANE]


def _skan(sciezka: str, tresc: str) -> list[str]:
    trafienia: list[str] = []
    for numer, linia in enumerate(tresc.splitlines(), start=1):
        for etykieta, wzorzec in WZORCE:
            if wzorzec.search(linia):
                trafienia.append(f"{sciezka}:{numer} — {etykieta}")
        for token in TOKENIZATOR.findall(linia):
            odcisk = hashlib.sha256((SOL + token.lower()).encode()).hexdigest()[:16]
            if odcisk in ZAKAZANE_TOKENY:
                trafienia.append(f"{sciezka}:{numer} — zakazana nazwa własna (odcisk {odcisk})")
    return trafienia


def skan_repo() -> list[str]:
    """Zwraca listę trafień. Pusta lista = repo czyste w chwili pomiaru."""
    trafienia: list[str] = []
    for wzgledna in _pliki_repo():
        plik = REPO / wzgledna
        try:
            tresc = plik.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue  # binarny albo usunięty w drzewie roboczym: nie ma czego czytać
        trafienia.extend(_skan(wzgledna, tresc))
    return trafienia


def test_repo_nie_zawiera_danych_prywatnych() -> None:
    trafienia = skan_repo()
    assert not trafienia, "wyciek do publicznego repo:\n" + "\n".join(trafienia)


def test_skaner_lapie_kontrolny_wyciek() -> None:
    """Weryfikacja METODY, nie tylko wyniku.

    Zielony skan znaczy "czysto" tylko wtedy, gdy skaner w ogóle potrafi coś złapać.
    Bez tego testu zepsuty regex dawałby zieleń nie do odróżnienia od prawdziwej.
    """
    probka = "\n".join(
        [
            "kontakt: ktos@example.com",
            "cd /Users/ktos/dev",
            "ssh nazwa-hosta-testowa.local",
            "API_KEY = 'abcdefghijklmnopqrst'",
            "AKIAIOSFODNN7EXAMPLE",
        ]
    )
    trafienia = _skan("probka.txt", probka)
    etykiety = {t.split("— ", 1)[1] for t in trafienia}
    assert "adres e-mail" in etykiety
    assert "ścieżka domowa macOS" in etykiety
    assert "host .local w sieci domowej" in etykiety
    assert "sekret przypisany do zmiennej" in etykiety
    assert "klucz AWS" in etykiety


def test_skaner_nie_lapie_zwyklego_kodu() -> None:
    """Fałszywka jest tu droższa niż gdzie indziej: bramka, która krzyczy bez powodu,
    uczy używania `--no-verify`, czyli daje zero kontroli zamiast proporcjonalnej.
    """
    probka = "\n".join(
        [
            "PATH=$HOME/.local/bin",
            "if wersja.local is None:",
            "autor <133030376+rafmyr@users.noreply.github.com>",
            "token = os.environ['TOKEN']",
            "wersja = '0.3.0'",
        ]
    )
    assert _skan("probka.py", probka) == []
