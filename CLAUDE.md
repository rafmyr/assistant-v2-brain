# CLAUDE.md — working memory assistant-v2-brain

> Czytaj na początku KAŻDEJ sesji w tym repo. **Limit: 120 linii.**
> Przekroczenie = najpierw wytnij, potem dopisz (precedens z maszynowni: plik urósł do
> 1236 linii przy deklarowanym limicie 80, łamanym 15-krotnie, i nikt tego nie zobaczył).

## ⚠️ TO REPO JEST PUBLICZNE, JEGO KONSUMENT NIE JEST

Wszystko, co tu wpiszesz, czyta cały świat. Nie przenoś tu z repo prywatnych: nazw plików
i modułów, identyfikatorów findingów, opisów incydentów produkcyjnych, nazw mechanizmów
nadzoru. Nie wklejaj danych osobowych, ścieżek z własnego terminala, hostów sieci domowej
ani nazw klientów — także do fixture'ów testowych, bo tam trafiają najłatwiej.

Egzekutor: `tests/test_brak_wyciekow.py`. W `pre-push` stoi **poza** warstwowością
dokumentacyjną, czyli biegnie także wtedy, gdy pushujesz sam plik `.md`. Tak ma być:
dokumentacja jest najbardziej prawdopodobnym nośnikiem wycieku, więc bramka pomijana
dla `.md` byłaby bramką wyłączoną dokładnie tam, gdzie jest potrzebna.

Skan nie widzi historii gita. Sekret raz zacommitowany zostaje w historii nawet po
usunięciu z drzewa — wtedy potrzebny jest rewrite historii, nie kolejny commit.

## Czym to repo jest

Mózg sesyjny Jarvisa 2.5 jako **biblioteka** (`assistant_v2_brain`), konsumowana przez
maszynownię przez pin w `uv.lock`. Nie usługa, nie proces, nie serwer MCP.

**Kanon**: `README.md` (konstytucja K3/K5/K8/K9 + B1-B5) · dokument kontraktu granicy
(wariant A) i plan toru A — oba po stronie maszynowni.

## Start sesji

```
git fetch --all --prune && git status -sb
gh run list --branch main --limit 3      # ostatni run MUSI byc success
gh pr list
```

**CZERWONY MAIN MA PIERWSZEŃSTWO** przed wszystkim. Main jest chroniony rulesetem
(`can_bypass: never`), więc `git push origin main` zostanie odrzucony — każda zmiana
idzie przez branch + PR + zielony `lint-and-test`.

Praca na styku z maszynownią = przeczytaj też jej working memory, ale **zacznij od repo
zadania**. Precedens: równoległe sesje w jednym klonie skończyły się commitem na cudzym
branchu.

## Granica — jedyna reguła, której złamanie psuje wszystko

Ten pakiet **nie importuje niczego z maszynowni**. Dane wejściowe dostaje w argumencie;
wysyłkę, mutacje i konektory robi maszynownia. Mózg **proponuje** akcję, nie wykonuje jej.

Egzekutor: `tests/test_granica_kontraktu.py` (AST, nie grep — komentarz go nie oszuka).
Wariant A daje granicę miękką i ten test jest jej jedynym strażnikiem. Jeśli kiedyś
zacznie przeszkadzać, to jest sygnał, że kontrakt się zmienił — wtedy decyzja PO
i rewizja kontraktu, nigdy ciche wyłączenie testu.

## Bramki

| Reguła | Egzekutor | Przy naruszeniu |
|---|---|---|
| Lock = jedno źródło prawdy o wersjach | `uv lock --check` (hook + CI) | blokuje push i merge |
| ruff + mypy **baseline 0** + pytest, `--frozen` | `scripts/hooks/pre-push` + `ci.yml` | blokuje push i merge |
| Main zawsze zielony | ruleset GitHub | `push declined due to repository rule violations` |
| Granica kontraktu | `test_granica_kontraktu.py` | czerwony test |
| Brak danych prywatnych | `test_brak_wyciekow.py` (hook **zawsze** + CI) | blokuje push i merge |

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
- **Flip na prod = osobne GO PO** po bramce A0 (dowody + tydzień shadow + niezależny audyt).
  Całe to repo jest nową powierzchnią, więc pierwszy flip nie odbywa się bez audytu.

## Czego tu świadomie NIE ma

- **Deployu.** Skrypt deployu maszynowni jest zahardkodowany na nią i przy wariancie A
  nie potrzebuje zmian: `uv sync --frozen` dociąga pin sam.
- **Orkiestry subagentów** w hot-path (B4) i **heartbeatu** (B2).
- **Limitu LOC.** Powstanie po pierwszym pilocie, z realnego kodu — nie z sufitu.
