"""Jarvis 2.5 — mozg sesyjny.

Biblioteka montujaca kontekst sesji i prowadzaca rozmowe w kanale PO.
Konsument: `assistant-v2` (maszynownia), przez zaleznosc pinowana w `uv.lock`.

KONSTYTUCJA (pelna tresc + uzasadnienia: README.md):
  K3  persona <=300 linii, prompt <=80     K9  sesja bounded, ciaglosc w plikach
  K5  budzet per wywolanie                 B1  sesja per watek-dzien
  K8  CHANGELOG zawsze                     B2  zero heartbeatu (2-3 sesje/dzien)
  B3  minimalny profil narzedzi            B4  jedna sesja, zero orkiestry subagentow
  B5  zapis pamieci wylacznie przez staging

GRANICA (kontrakt A0.13): ten pakiet NIE importuje niczego z `assistant-v2`.
Dane wejsciowe i wysylka naleza do maszynowni; mozg dostaje kontekst i zwraca tresc.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.0.1"
