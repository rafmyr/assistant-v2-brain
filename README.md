# assistant-v2-brain — mózg sesyjny Jarvisa 2.5

> Pakiet Pythona `jarvis_brain`. Biblioteka, nie usługa.
> Konsument: `assistant-v2` (maszynownia), przez zależność pinowaną w `uv.lock`.
> Powstało 12.08.2026 z decyzji PO D-A (plan `assistant-v2/docs/PLAN-JARVIS-2.5-2026-08-11.md` v1.2).

## Co to robi

Montuje kontekst na start sesji i prowadzi rozmowę w kanale PO. Cztery źródła kontekstu:
persona prozą, pamięć relacji z plików vaulta, stan dnia (kalendarz, zobowiązania, follow-upy),
historia wątku.

Teza, z której to wyrosło: jakość Coworka nie bierze się z długości sesji — v1 umarło na wiecznej
sesji (saturacja 82%/200k, 8 s → 60 s) — tylko z tego, CO wchodzi na jej start.

## Czego to NIE robi (granica, kontrakt A0.13)

Ten pakiet **nie importuje niczego z `assistant-v2`** i nie wie o jego istnieniu. Strzałka biegnie
w jedną stronę. Pilnuje tego `tests/test_granica_kontraktu.py` — stoi w repo od pierwszego commita,
bo wariant A daje granicę miękką i test jest jej jedynym egzekutorem.

Do maszynowni należą: dane wejściowe (konektory), wysyłka (`push_gate`), mutacje (OmniFocus,
promocja, rewert). Mózg może **proponować** akcję; wykonuje ją maszynownia przez istniejącą śluzę.

## Konstytucja

Odziedziczone z `assistant-v2` (kanon: `docs/GREENFIELD-V2-DESIGN.md` §2):

| | |
|---|---|
| **K3** | persona ≤300 linii, prompt ≤80. Lekcja v1: 5 408 linii persony dało robotyczność, nie mniej |
| **K5** | budżet per wywołanie (`--max-budget-usd`) |
| **K8** | CHANGELOG zawsze |
| **K9** | sesja bounded; ciągłość w plikach, nie w procesie. Żaden proces LLM nie żyje dłużej niż jedno zadanie |

Własne, z researchu 11.08:

| | |
|---|---|
| **B1** | sesja per wątek-dzień, nie wieczna |
| **B2** | zero heartbeatu. Proaktywność = 2-3 zaplanowane sesje dziennie, **cisza jest pełnoprawnym wynikiem**. Ciągła pętla kosztowała użytkowników OpenClaw $300-3600/mies. |
| **B3** | minimalny profil narzędzi per typ pytania; rozszerzenie tylko na jawny brak danych. MCP-tax: 66k tokenów startu, spadek celności powyżej 30-50 narzędzi |
| **B4** | jedna sesja, zero orkiestry subagentów w hot-path. Multi-agent „z rozpędu" przegrywa z lepszym promptem na jednym agencie (~15× koszt) |
| **B5** | zapis pamięci wyłącznie przez staging z przeglądem, nigdy wprost z treści rozmowy. Memory poisoning zademonstrowany (MINJA >95%) |

**Limitu rozmiaru repo NIE ustalamy z góry.** Powstanie po pierwszym pilocie, z realnego kodu.
K2 w maszynowni był rewidowany 5 razy w 2 miesiące — liczba z sufitu generuje tylko rewizje.

## Bramki (od dnia pierwszego, nie „kiedyś potem")

| Bramka | Egzekutor |
|---|---|
| lock = jedno źródło prawdy o wersjach | `uv lock --check` w pre-push i CI |
| ruff + mypy (**baseline 0**) + pytest, wszystko `--frozen` | `scripts/hooks/pre-push` + `.github/workflows/ci.yml` |
| main zawsze zielony | ruleset GitHub, `can_bypass: never` |
| granica kontraktu | `tests/test_granica_kontraktu.py` |

Powód, dla którego to jest tu od początku, a nie „jak ruszy": `assistant-v2` dorobiło się tych
bramek po **3 dobach czerwonego maina** (29.07-01.08). Repo bez bramek dorabia je za późno.

Instalacja hooka po klonie:

```
ln -sf ../../scripts/hooks/pre-push .git/hooks/pre-push
```

## Stan

**Pilot, tor A planu Jarvis 2.5.** Flip na prod wymaga osobnego GO po bramce A0
(dowody + tydzień shadow + audyt nadzoru). Całe repo jest nową powierzchnią w rozumieniu
sekwencji C-line, więc pierwszy flip nie odbywa się bez audytu.
