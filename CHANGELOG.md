# CHANGELOG

Konwencja: wpis przy KAŻDEJ zmianie (K8). Najnowsze na górze.

## 2026-08-12 — bootstrap repo (A0.14)

- Repo utworzone z decyzji PO D-A (mózg w osobnym repo) + kontraktu A0.13 wariant A
  (biblioteka pinowana w `uv.lock`, nie osobny proces).
- Nazwa `assistant-v2-brain` zamiast planowanej `assistant-v2-brain`: ta druga była **zajęta**
  przez repo z ery v1 (Tier 2 governance backup, ostatni push 06.06.2026, tydzień przed
  dekomisją v1). Decyzja PO 12.08: nowe repo pod inną nazwą, stare nietknięte.
  Pakiet Pythona zostaje `assistant_v2_brain` — tak nazywa go kontrakt A0.13.
- Bramki od commita pierwszego: `uv.lock` + pre-push (ruff/mypy/pytest, `--frozen`)
  + CI `lint-and-test` + ruleset „main zawsze zielony".
- **mypy baseline 0**, nie 34 jak w maszynowni. Repo startuje czyste, więc każdy błąd
  typów jest nowy. Nie ma czego amnestionować.
- `tests/test_granica_kontraktu.py`: strażnik jednokierunkowej strzałki
  (`assistant-v2` → `assistant_v2_brain`, nigdy odwrotnie) + kontrola, że zależności spoza
  stdlib wchodzą świadomie, przez `pyproject.toml`. Wariant A daje granicę miękką,
  ten test jest jej jedynym egzekutorem.
- Zero kodu funkcjonalnego. Sam szkielet i bramki.
- **Ruleset „main zawsze zielony" aktywny i udowodniony**: pusty commit na `main`
  odrzucony (`push declined due to repository rule violations`), `can_bypass: never`.
- **FIX pre-push, złapany na własnej skórze przy commicie bootstrapującym**: pusta lista
  plików w zakresie pushu była traktowana jako „sama dokumentacja" i wyłączała mypy+pytest.
  Dla pierwszego commita w repo `base` równa się `lsha`, więc `git diff` zwracał pustkę,
  a pusty zbiór trywialnie spełnia warunek „wszystko pasuje do wzorca". Efekt: push
  z `.py`, `.toml` i `.yml` przeszedł jako dokumentacja. Nieznany zakres = pełna bramka.

## 2026-08-12b — spójność nazw (decyzja PO)

- Pakiet Pythona `jarvis_brain` → `assistant_v2_brain`, nazwa instalacyjna
  `jarvis-brain` → `assistant-v2-brain`. Powód: repo, pakiet i nazwa instalacyjna
  mówiły trzema różnymi nazwami, co przy dwóch repo jest zaproszeniem do pomyłki.
- Ograniczenie techniczne, dlatego podkreślenia zamiast myślników w imporcie:
  `import assistant-v2-brain` interpreter czyta jako odejmowanie. Nazwa instalacyjna
  może mieć myślniki, nazwa importowana nie.
- Kontrakt A0.13 zaktualizowany po stronie `assistant-v2` w tym samym dniu
  (kanon nie może kłamać nawet przez jeden dzień).
- Weryfikacja: `uv lock` wymienił dystrybucję, ruff clean, mypy 0, pytest 2 passed,
  import smoke `assistant_v2_brain.__version__` = 0.0.1.
