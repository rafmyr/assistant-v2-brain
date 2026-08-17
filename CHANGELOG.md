# CHANGELOG

Konwencja: wpis przy KAŻDEJ zmianie (K8). Najnowsze na górze.

## 2026-08-17 — bramka anty-wyciekowa + sanityzacja dokumentacji

Powód: przegląd PO wykazał, że repo jest publiczne, a jego konsument prywatny, i że
czystość repo była **wynikiem jednorazowego przeglądu przy publikacji, nie mechanizmu**.
Nic nie stało na drodze, żeby kolejna sesja wkleiła realne dane do fixture'a i wypchnęła
je na publicznego maina.

- **`tests/test_brak_wyciekow.py`**: skan plików śledzonych przez gita na adresy e-mail,
  ścieżki domowe, hosty sieci domowej, numery telefonów, klucze API i tokeny oraz na listę
  zakazanych nazw własnych. Nazwy trzymane jako skrócone SHA-256 z solą, bo sama LISTA
  nazw jest tym, czego nie chcemy publikować. To zaciemnienie, nie kryptografia — sól leży
  w pliku obok, więc atak słownikowy jest trywialny; celem jest nieczytelność przy
  przeglądaniu repo, nie odporność na atak.
- **Skan biegnie w `pre-push` POZA warstwowością dokumentacyjną**, czyli także przy pushu
  samego `.md`. Krok 0 hooka pomija `mypy` i `pytest`, gdy zakres to sama dokumentacja —
  a dokumentacja jest najbardziej prawdopodobnym nośnikiem wycieku. Bramka zostawiona
  w zwykłym `pytest` byłaby więc wyłączona dokładnie w tym scenariuszu, dla którego
  powstała. W CI osobny krok, żeby komunikat nie ginął wśród pozostałych testów.
- **Dwa testy pilnują METODY, nie tylko wyniku**: jeden sprawdza, że skaner łapie
  kontrolny wyciek (bez tego zepsuty regex dawałby zieleń nie do odróżnienia od prawdziwej),
  drugi że nie krzyczy na zwykły kod (fałszywka uczy `--no-verify`, czyli daje zero
  kontroli zamiast proporcjonalnej).
- **Sanityzacja `README.md`, `CLAUDE.md`, `CHANGELOG.md`**: usunięte nazwy plików i modułów
  z repo prywatnych, identyfikatory findingów, daty i opisy incydentów produkcyjnych oraz
  nazwy mechanizmów nadzoru. Zastąpione neutralnym odsyłaczem do maszynowni. To nie były
  dane wrażliwe — to był **spis treści prywatnego systemu**, gotowy materiał rozpoznawczy.
  Pełna mapa nazw zostaje po stronie maszynowni, gdzie i tak jest czytana.
- **Czego to NIE załatwia** (jawnie, żeby nikt nie wziął tego za komplet): skan dotyczy
  drzewa roboczego, nie historii gita; lista zakazanych nazw jest skończona i pisana ręcznie;
  treść generowana w runtime (persona, pamięć relacji) przychodzi z zewnątrz i nie ma jej
  w repo.

## 2026-08-12 — bootstrap repo (A0.14)

- Repo utworzone z decyzji PO D-A (mózg w osobnym repo) + kontraktu A0.13 wariant A
  (biblioteka pinowana w `uv.lock`, nie osobny proces).
- Nazwa `assistant-v2-brain`: pierwotnie planowana alternatywa była **zajęta** przez
  starsze repo z ery v1. Decyzja PO 12.08: nowe repo pod inną nazwą, stare nietknięte.
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
- Kontrakt A0.13 zaktualizowany po stronie maszynowni w tym samym dniu
  (kanon nie może kłamać nawet przez jeden dzień).
- Weryfikacja: `uv lock` wymienił dystrybucję, ruff clean, mypy 0, pytest 2 passed,
  import smoke `assistant_v2_brain.__version__` = 0.0.1.

## 2026-08-12c — WERSJA_KONTRAKTU + v0.0.2

- Pierwszy element publicznego API: `WERSJA_KONTRAKTU = "1.0"`. Wersja KONTRAKTU (A0.13),
  nie pakietu — rosnie tylko przy lamiacej zmianie powierzchni. Maszynownia sprawdza to
  przy starcie, bo przy wariancie A granica jest miekka i nic poza umowa jej nie pilnuje
  w runtime.
- Wersja pakietu 0.0.1 -> 0.0.2 (pierwsze realne wydanie, sluzy tez za pomiar cyklu).
