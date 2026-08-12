"""Montaż kontekstu na start sesji (A1, tor A planu Jarvis 2.5).

Teza całego pilota: jakość Coworka nie bierze się z długości sesji — v1 umarło na wiecznej
(saturacja 82%/200k, 8 s → 60 s) — tylko z tego, CO wchodzi na jej start. Ten moduł jest
tym "co".

Cztery źródła, każde dostarczane przez maszynownię (kontrakt A0.13: brain nie sięga
po dane sam):
  1. persona prozą        — kim jest Jarvis, jak mówi
  2. pamięć relacji       — co wie o PO i o Waszej historii
  3. stan dnia            — kalendarz, zobowiązania, otwarte wątki
  4. historia wątku       — ostatnie tury rozmowy

K3 (persona ≤300 linii) jest tu egzekwowane, nie deklarowane: przekroczenie = twardy błąd
przy montażu, nie ciche obcięcie. Lekcja v1: persona 5 408 linii dała robotyczność, nie mniej.
"""

from __future__ import annotations

from dataclasses import dataclass, field

LIMIT_PERSONY_LINII = 300  # K3
LIMIT_PAMIECI_ZNAKOW = 12_000  # ~3k tokenów; indeks + fakty, nie cała historia
LIMIT_STANU_ZNAKOW = 4_000
LIMIT_HISTORII_TUR = 12


class BladMontazu(ValueError):
    """Kontekst nie spełnia kontraktu. Świadomie twardy: cicha degradacja promptu
    jest gorsza od jawnej odmowy — nie wiedzielibyśmy, czemu odpowiedzi zgłupiały."""


@dataclass(frozen=True)
class Tura:
    """Jedna wymiana w wątku."""

    pytanie: str
    odpowiedz: str


@dataclass(frozen=True)
class DaneWejsciowe:
    """Wszystko, co maszynownia podaje mózgowi. Brain niczego nie dociąga sam.

    `braki` to lista źródeł, które zawiodły przy zbieraniu — mózg ma o nich powiedzieć
    PO wprost, zamiast udawać, że ich nie potrzebował (runtime-gate A1.3: koniec cichej
    degradacji do "pewnie brzmiącego czatu bez danych").
    """

    persona: str
    pamiec_relacji: str = ""
    stan_dnia: str = ""
    historia: tuple[Tura, ...] = ()
    braki: tuple[str, ...] = field(default=())


def _przytnij(tekst: str, limit: int, etykieta: str) -> str:
    """Przycięcie z JAWNYM śladem — model ma wiedzieć, że coś ucięto, i móc dopytać."""
    tekst = tekst.strip()
    if len(tekst) <= limit:
        return tekst
    return tekst[:limit].rstrip() + f"\n\n[…{etykieta} przycięte do {limit} znaków…]"


def zbuduj_prompt_systemowy(dane: DaneWejsciowe) -> str:
    """Złóż prompt systemowy sesji z czterech źródeł.

    Kolejność jest celowa: najpierw kim jesteś, potem co wiesz o człowieku, potem co dziś,
    na końcu zasady operacyjne. Model czyta od góry i pierwsze sekcje ważą najwięcej.
    """
    linie_persony = dane.persona.strip().splitlines()
    if len(linie_persony) > LIMIT_PERSONY_LINII:
        raise BladMontazu(
            f"persona ma {len(linie_persony)} linii, limit K3 to {LIMIT_PERSONY_LINII}. "
            "Skróć CORE.md — obcięcie w locie dałoby inną osobowość bez śladu w logu."
        )

    czesci: list[str] = [dane.persona.strip()]

    if dane.pamiec_relacji.strip():
        czesci.append(
            "## Co wiesz o Rafale i o Waszej historii\n\n"
            + _przytnij(dane.pamiec_relacji, LIMIT_PAMIECI_ZNAKOW, "pamięć")
            + "\n\nTo jest pamięć trwała, nie kontekst rozmowy. Możesz się do niej odwoływać "
            "wprost (na przykład: pamiętam, że...), ale nie cytuj jej mechanicznie — "
            "to Twoja wiedza, nie ściąga."
        )

    if dane.stan_dnia.strip():
        czesci.append(
            "## Stan na dziś\n\n" + _przytnij(dane.stan_dnia, LIMIT_STANU_ZNAKOW, "stan dnia")
        )

    if dane.braki:
        czesci.append(
            "## Czego dziś nie masz\n\n"
            + "\n".join(f"- {b}" for b in dane.braki)
            + "\n\n**Powiedz o tym wprost**, jeśli pytanie tego dotyczy. Nie zgaduj i nie udawaj, "
            "że masz komplet — lepiej 'nie mam dziś dostępu do X' niż pewnie brzmiąca bzdura."
        )

    czesci.append(_ZASADY_ROZMOWY)
    return "\n\n---\n\n".join(czesci)


_ZASADY_ROZMOWY = """## Jak rozmawiasz

Piszesz na WhatsAppie, więc krótko: kilka zdań, nie esej. Bez nagłówków i list, chyba że
Rafał prosi o zestawienie. Bez korpo-języka i bez 'chętnie pomogę'.

Gdy czegoś nie wiesz albo nie masz danych — mówisz to w pierwszym zdaniu, nie na końcu.
Gdy coś jest Twoim domysłem — oznaczasz to słowem, nie zostawiasz do odgadnięcia.

Możesz PROPONOWAĆ działania (zadanie w OmniFocus, notatka, przypomnienie), ale ich nie
wykonujesz — od tego jest reszta systemu i potwierdzenie Rafała. Propozycję formułuj
jako jedno konkretne zdanie, nie jako listę opcji."""
