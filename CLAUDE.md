# CLAUDE.md — working memory assistant-v2-brain

> Czytaj na początku KAŻDEJ sesji w tym repo. **Limit: 120 linii.**
> Przekroczenie = najpierw wytnij, potem dopisz (precedens F-0726-8 w maszynowni:
> plik urósł do 1236 linii przy deklarowanym limicie 80, łamanym 15-krotnie).

## Czym to repo jest

Mózg sesyjny Jarvisa 2.5 jako **biblioteka** (`jarvis_brain`), konsumowana przez
`assistant-v2` przez pin w `uv.lock`. Nie usługa, nie proces, nie serwer MCP.

**Kanon**: `README.md` (konstytucja K3/K5/K8/K9 + B1-B5) ·
`assistant-v2/docs/KONTRAKT-BRAIN-MASZYNOWNIA.md` (granica, wariant A) ·
`assistant-v2/docs/PLAN-JARVIS-2.5-2026-08-11.md` v1.2 (tor A, etapy A0-A4).

## Start sesji

```
git fetch --all --prune && git status -sb
gh run list --branch main --limit 3      # ostatni run MUSI byc success
gh pr list
```

**CZERWONY MAIN MA PIERWSZEŃSTWO** przed wszystkim. Main jest chroniony rulesetem
(`can_bypass: never`), więc `git push origin main` zostanie odrzucony — każda zmiana
idzie przez branch + PR + zielony `lint-and-test`.

Praca na styku z maszynownią = przeczytaj też `assistant-v2/CLAUDE.md`, ale **zacznij
od repo zadania**. Precedens: równoległe sesje w jednym klonie (18.07) skończyły się
commitem na cudzym branchu.

## Granica — jedyna reguła, której złamanie psuje wszystko

Ten pakiet **nie importuje niczego z `assistant-v2`**. Dane wejściowe dostaje
w argumencie; wysyłkę, mutacje i konektory robi maszynownia. Mózg **proponuje** akcję,
nie wykonuje jej.

Egzekutor: `tests/test_granica_kontraktu.py` (AST, nie grep — komentarz go nie oszuka).
Wariant A daje granicę miękką i ten test jest jej jedynym strażnikiem. Jeśli kiedyś
zacznie przeszkadzać, to jest sygnał, że kontrakt się zmienił — wtedy decyzja PO
i rewizja `KONTRAKT-BRAIN-MASZYNOWNIA.md`, nigdy ciche wyłączenie testu.

## Bramki

| Reguła | Egzekutor | Przy naruszeniu |
|---|---|---|
| Lock = jedno źródło prawdy o wersjach | `uv lock --check` (hook + CI) | blokuje push i merge |
| ruff + mypy **baseline 0** + pytest, `--frozen` | `scripts/hooks/pre-push` + `ci.yml` | blokuje push i merge |
| Main zawsze zielony | ruleset GitHub | `push declined due to repository rule violations` |
| Granica kontraktu | `test_granica_kontraktu.py` | czerwony test |

Instalacja hooka po klonie: `ln -sf ../../scripts/hooks/pre-push .git/hooks/pre-push`

**Baseline mypy = 0 i tak zostaje.** Maszynownia schodziła 52 → 34 przez dwa miesiące;
tutaj nie ma czego schodzić, więc podniesienie progu wymaga jawnej decyzji, nie „na razie".

## Stan (12.08.2026)

- **Repo świeże, zero kodu funkcjonalnego.** A0.14 domknięte: szkielet + bramki + ruleset.
- **Następny krok**: pomiar cyklu wydania ze stoperem (zobowiązanie z nagłówka kontraktu
  A0.13) — commit → tag → bump pinu w maszynowni → PR → CI → merge → deploy. To jedyna
  niezmierzona niewiadoma wariantu A. Bolesny wynik = powrót do decyzji **z danymi**.
- **Potem** A1: montaż kontekstu (4 źródła), `session_id` per wątek-dzień, rotacja, `--resume`.
  Uwaga: `--resume` i `session_id` **nie istnieją w kodzie maszynowni** (grep bez trafień) —
  budujemy od zera, nie rozszerzamy.
- **Flip na prod = osobne GO PO** po bramce A0 (dowody + tydzień shadow + audyt nadzoru).
  Całe to repo jest nową powierzchnią w sekwencji C-line; licznik naruszeń = 3, czwartego nie ma.

## Czego tu świadomie NIE ma

- **Deployu.** `assistant-v2/scripts/deploy_mini.sh` jest zahardkodowany na maszynownię
  i przy wariancie A nie potrzebuje zmian: `uv sync --frozen` dociąga pin sam.
- **Orkiestry subagentów** w hot-path (B4) i **heartbeatu** (B2).
- **Limitu LOC.** Powstanie po pierwszym pilocie, z realnego kodu — nie z sufitu.
