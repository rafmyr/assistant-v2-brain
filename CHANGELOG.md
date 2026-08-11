# CHANGELOG

Konwencja: wpis przy KAŻDEJ zmianie (K8). Najnowsze na górze.

## 2026-08-12 — bootstrap repo (A0.14)

- Repo utworzone z decyzji PO D-A (mózg w osobnym repo) + kontraktu A0.13 wariant A
  (biblioteka pinowana w `uv.lock`, nie osobny proces).
- Nazwa `assistant-v2-brain` zamiast planowanej `jarvis-brain`: ta druga była **zajęta**
  przez repo z ery v1 (Tier 2 governance backup, ostatni push 06.06.2026, tydzień przed
  dekomisją v1). Decyzja PO 12.08: nowe repo pod inną nazwą, stare nietknięte.
  Pakiet Pythona zostaje `jarvis_brain` — tak nazywa go kontrakt A0.13.
- Bramki od commita pierwszego: `uv.lock` + pre-push (ruff/mypy/pytest, `--frozen`)
  + CI `lint-and-test` + ruleset „main zawsze zielony".
- **mypy baseline 0**, nie 34 jak w maszynowni. Repo startuje czyste, więc każdy błąd
  typów jest nowy. Nie ma czego amnestionować.
- `tests/test_granica_kontraktu.py`: strażnik jednokierunkowej strzałki
  (`assistant-v2` → `jarvis_brain`, nigdy odwrotnie) + kontrola, że zależności spoza
  stdlib wchodzą świadomie, przez `pyproject.toml`. Wariant A daje granicę miękką,
  ten test jest jej jedynym egzekutorem.
- Zero kodu funkcjonalnego. Sam szkielet i bramki.
