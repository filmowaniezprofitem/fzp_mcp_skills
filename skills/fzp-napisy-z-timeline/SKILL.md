---
name: "fzp-napisy-z-timeline"
description: "Robi polskie napisy SRT z dialogów bieżącego timeline'u DaVinci Resolve Studio przez MCP: transkrypcja w Resolve, czasy z pojedynczych słów, polskie zasady podziału i łamania, korekty do akceptacji, wstawienie po timecodzie. Użyj, gdy ktoś prosi o napisy, transkrypcję albo plik SRT do materiału z Resolve."
---

# Napisy z timeline'u DaVinci Resolve (wersja 3.1)

Autor: Filmowanie z Profitem (filmowaniezprofitem.pl). Licencja: MIT + Commons Clause.

Wymagania: DaVinci Resolve Studio 21.1+ z włączonym MCP (File > Setup AI Assistants), narzędzia `run_script` i `run_script_unsafe`. Cała logika liczona (czasy, podział, łamanie, walidacja, SRT, operacje w Resolve) jest w bibliotece `scripts/napisy_lib.py`. Model zajmuje się tylko językiem i rozmową.

## Podział ról
- **Biblioteka:** zapis i przywrócenie stanu projektu, render audio dialogów, transkrypcja, cięcia, domyślny podział na zdania składowe, podział i łamanie wierszy, czasy, walidacja, pliki SRT, import, weryfikacja.
- **Model:** korekty transkrypcji, granice zdań składowych, usunięcie tekstu piosenek i szumów, przypisanie mówców, gdy wykrywanie zawiodło, rozmowa z użytkownikiem.
- Czasy słów nigdy nie przechodzą przez rozmowę. Do modelu trafia tylko tekst jednostek `U1…Un`, podgląd napisów i ostrzeżenia.
- Nie piszesz własnego kodu do rzeczy, które robi biblioteka. Skrypty to krótkie wywołania jej funkcji.

## Zasady
- Tekst bierzesz wyłącznie ze ścieżek audio z dialogiem. Klipy na ścieżkach wideo służą tylko do wyznaczenia cięć. Muzyka jest ignorowana.
- Korekty, które zmieniają sens albo są niepewne, wprowadzasz dopiero po akceptacji użytkownika.
- Nie ruszasz zadań renderu ani istniejących napisów użytkownika. Nowe napisy trafiają na nową ścieżkę.
- Na końcu i po każdym błędzie w połowie wywołujesz `restore(resolve, project, W)`. Przywraca ścieżki, ustawienia renderu, język transkrypcji, folder Media Poola i stronę oraz usuwa z Media Poola tymczasowy WAV.

## Krok 0 – biblioteka, środowisko, inwentarz (bez pytań)

### 0a. Instalacja biblioteki
Biblioteka leży na komputerze użytkownika w `~/.napisy-z-timeline/`. Uruchom przez `run_script_unsafe` poniższy skrypt **dokładnie w tej postaci** (wartości uzupełnia skrypt wydania repozytorium, nie zmieniaj ich):

<!-- LIB:BEGIN (generowane przez tools/build.py - nie edytuj recznie) -->
```python
import os, hashlib, subprocess, urllib.request
VER = "3.1"
SHA = "b91973a43ea919f29fb83b303ff770019023fd8aaffa3337b084ec6aa3621f0f"
URL = "https://raw.githubusercontent.com/filmowaniezprofitem/fzp_mcp_skills/napisy-v3.1/skills/fzp-napisy-z-timeline/scripts/napisy_lib.py"
D = os.path.join(os.path.expanduser("~"), ".napisy-z-timeline")
P = os.path.join(D, "napisy_lib_%s.py" % VER)
h = lambda b: hashlib.sha256(b).hexdigest()
if os.path.exists(P) and h(open(P, "rb").read()) == SHA:
    print("LIB_OK zainstalowana", P)
else:
    b, err = None, []
    try:
        b = urllib.request.urlopen(URL, timeout=30).read()
    except Exception as e:
        err.append("urllib: %s" % e)
        try:  # np. Python bez certyfikatow na macOS - systemowy curl ma certyfikaty systemu
            b = subprocess.run(["curl", "-fsSL", "--max-time", "30", URL], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
        except Exception as e2:
            err.append("curl: %s" % e2)
    if b is None:
        print("LIB_BLAD_POBRANIA", " | ".join(err))
    elif h(b) != SHA:
        print("LIB_ZLY_HASH", h(b))
    else:
        os.makedirs(D, exist_ok=True)
        open(P, "wb").write(b)
        print("LIB_OK pobrana", P)
```

Nagłówek każdego kolejnego skryptu (`run_script_unsafe`):
```python
import os
exec(open(os.path.join(os.path.expanduser("~"), ".napisy-z-timeline", "napisy_lib_3.1.py"), encoding="utf-8").read(), globals())
W = "<folder roboczy>"
```
<!-- LIB:END -->

Wynik:
- `LIB_OK` – idziesz dalej.
- `LIB_BLAD_POBRANIA` (brak internetu na komputerze z Resolve) – fallback: przeczytaj `scripts/napisy_lib.py` z folderu tego skilla i zapisz go przez `run_script_unsafe` w ścieżce `P` poleceniem `open(P, "w", encoding="utf-8", newline="\n").write(r'''<cały plik>''')`. Przepisz kod dokładnie, bez zmian. Potem uruchom skrypt instalacyjny jeszcze raz. Jeśli zgłosi `LIB_ZLY_HASH`, usuń plik `P`, nie próbuj poprawiać i powiedz użytkownikowi, że trzeba zainstalować bibliotekę ręcznie (instrukcja w README repozytorium).
- `LIB_ZLY_HASH` po pobraniu – zatrzymaj się i zgłoś. Nie uruchamiaj pliku, którego hash się nie zgadza.

`resolve` i `project` to obiekty, które środowisko `run_script` udostępnia skryptom. Funkcje biblioteki dostają je jako argumenty.

### 0b. Środowisko i inwentarz – jeden skrypt
```python
print(json.dumps(dict(env=check_env(resolve), inv=inventory(project), abandoned=find_abandoned(project),
                      folder=default_folder(project.GetCurrentTimeline().GetName())), ensure_ascii=False))
```
- `env.ok == False` → podaj `env.reason` i zakończ.
- `abandoned.preset == True` albo niepuste `abandoned.workdirs` → poprzedni przebieg nie posprzątał po sobie. Zapytaj jednym pytaniem: **„Przywrócić ustawienia sprzed poprzedniego przebiegu?”** (Recommended) albo „Obecne ustawienia renderu są poprawne”. Przy pierwszej opcji `restore(resolve, project, abandoned["workdirs"][0])`, a jeśli nie ma folderu, tylko `project.LoadRenderPreset("_napisy_backup")` i `project.DeleteRenderPreset("_napisy_backup")`. Przy drugiej w Kroku 2 użyj `snapshot(..., force=True)`.

## Krok 1 – jedno pytanie startowe
Jedno wywołanie AskUserQuestion, **maksymalnie 4 pytania po maks. 4 opcje** (opcja „Other” dochodzi sama):
1. **Profil:** „montażowy” (Recommended) – napisy stykają się, przy ciszy > 1 s napis trwa jeszcze maks. 1 s; „netflix” – przerwa 2 klatki, przerwy < 0,5 s domykane, podtrzymanie 0,5 s. Oba: przyciąganie do cięć 0,5 s, napis 5/6–7 s, maks. 17 zn/s.
2. **Układ:** „<preset z inv.layout> (Recommended)” np. „42 zn × 2 wiersze”, oraz „1 wiersz”. Własne wartości użytkownik wpisuje w „Other”. Wskazówka dla siebie: znaki ≈ szer_px × procent_kadru / (rozmiar_czcionki_px × 0,5).
3. **Ścieżki dialogowe:** pytanie wielokrotnego wyboru z ścieżkami audio z `inv.audio` (nazwa + klipy). Jeśli jest ich więcej niż 4, pierwsza opcja to „Wszystkie z mową: A1, A3…” (Twój wybór na podstawie nazw), druga „Wybiorę sam (wpisz w Other)”. Pomijasz muzykę i efekty.
4. **Mówcy:** „jedna ścieżka napisów” (Recommended) albo „osobna ścieżka napisów na każdą ścieżkę dialogową”. Pytanie pomijasz, gdy jest tylko jedna ścieżka dialogowa.

Bez pytania:
- Folder: `folder` z kroku 0b. Inny tylko na wyraźną prośbę.
- Słownik nazw własnych: jeśli użytkownik go podał, użyjesz go w Kroku 3. Nie pytasz o niego osobno.

Każde uruchomienie dostaje nowy folder roboczy: `W = new_workdir(folder, nazwa_timeline)`.

## Krok 2 – render i transkrypcja
1. `snapshot(resolve, project, W)`, potem `r = start_render(project, W, [numery ścieżek dialogowych])` → `job`, `wav`.
   - Przy „osobnych ścieżkach” renderujesz i transkrybujesz każdą ścieżkę po kolei: `start_render(project, W, [i])`.
2. `render_done(project, job)` (czeka do 45 s w jednym wywołaniu) powtarzaj, aż zwróci `"Complete"`. Potem `import_and_transcribe(resolve, project, W, wav, speakers=True)`.
   - Funkcja przywraca ścieżki i ustawienia renderu, importuje WAV do binu „Napisy”, przełącza na stronę Edit (na Deliver transkrypcja nie działa) i startuje transkrypcję.
   - Przekroczenie limitu czasu skryptu w tym miejscu jest normalne, bo transkrypcja trwa dalej.
3. `print(wait_transcription(project, wav, wait_s=50))` powtarzaj, aż zwróci > 0. Jedno wywołanie czeka do 50 s, nie dodawaj własnego czekania. Limit łączny: 20 min. Po nim zgłoś problem i zrób restore.
4. `export_words(project, W, wav)`. Przy osobnych ścieżkach z `track_label="A<i>"` dla każdego WAV.
5. `print(prepare(W, profil))` zwraca jednostki `U<n> <TC> [mówca] tekst`.

Między krokami nie piszesz nic do użytkownika, chyba że coś poszło nie tak.

## Krok 3 – przegląd językowy (model)
Domyślnie **tryb szybki**:
- **Stosujesz od razu, bez pytania:** oczywiste literówki ASR, wielkie litery w nazwach własnych ze słownika, interpunkcję. Na końcu podajesz je jedną zbiorczą linią w raporcie („+ 23 drobne korekty interpunkcji i wielkich liter”).
- **Pokazujesz do decyzji** w jednej tabeli: U | TC | oryginał | propozycja | pewność. Tylko pozycje o średniej i niskiej pewności, zmiany słów, które mogą zmienić sens, nazwy własne spoza słownika.
- Jeśli materiał zaczyna się w połowie zdania, proponujesz wielokropek.
- Gwarę i mowę potoczną zostawiasz, chyba że użytkownik zdecyduje inaczej.
- **Podziały:** jednostka z więcej niż jednym zdaniem składowym (nowe orzeczenie po przecinku, wtrącenie typu „tak jak powiedziałam”) dostaje `split`. Błędny domyślny podział dostaje `join`. Stosujesz bez pytania, to sprawa redakcyjna.
- **Usunięcia:** tekst piosenek, szumy, przypadkowe słowa z tła dostają `drop`. Pokazujesz je w tabeli.
- **Mówcy:** jeśli wykryto jednego mówcę, a tekst wygląda na rozmowę (pytania i odpowiedzi), pytasz, kto mówi które kwestie, i używasz `speakers`.
- Przy długim materiale tabela zawiera tylko pozycje do decyzji. Gdy jest ich ponad ~40, pokazujesz partiami.
- Jeśli nic nie wymaga decyzji, nie pytasz, tylko od razu budujesz.

Jeśli użytkownik poprosi o pełny przegląd (każda korekta osobno), przechodzisz na tryb pełny: tabela ze wszystkimi korektami, interpunkcja zebrana w jedną pozycję.

Plan (biblioteka zapisuje go w `W/plan.json` przy `build`):
```json
{"edits":[{"u":3,"old":"odra","new":"Odra"}],
 "split":[{"u":9,"before":"miałam"}],
 "join":[4], "drop":[12], "speakers":{"31":"B"}}
```
- `old` to dokładny fragment jednostki `u`. `new` może mieć inną liczbę słów, czasy rozkładają się proporcjonalnie.
- `split.before` to fragment, od którego zaczyna się nowa jednostka.
- `join: [n]` łączy Un z Un+1.

## Krok 4 – budowa SRT
1. `r = build(W, plan, profil, max_chars, max_lines, merge=True, per_speaker=False)`.
   - Jeśli `r["errors"]` nie jest puste, popraw plan (zwykle `old` nie pasuje dosłownie) i powtórz.
2. Dla każdego pliku z `r["files"]` wywołaj `import_srt(project, plik)`. Klip trafia do binu „Napisy” i zostaje zaznaczony, a playhead staje na początku timeline'u.
3. Pokaż użytkownikowi:
   - podgląd (`r["preview"]`; przy dużej liczbie pierwsze 20 napisów),
   - wszystkie `r["warnings"]`, krótko pogrupowane,
   - ścieżki plików.

Pliki:
- `files`: SRT do wstawienia w Resolve. Czasy są bezwzględnym timecode'em timeline'u, bo tak czyta je „Insert … Using Timecode”.
- `delivery`: wersja od 00:00:00 dla klienta (`*_od_zera.srt`). Powstaje tylko wtedy, gdy timeline nie startuje od zera.

Co już robi biblioteka: przyciąganie do cięć, styk i podtrzymanie, łączenie krótkich części jednego zdania (każda w osobnym wierszu), pożyczanie czasu od sąsiadów, osobny napis przy zmianie mówcy, dzielenie zbyt długich napisów, timecode drop-frame w podglądzie.

## Krok 5 – wstawienie i weryfikacja
1. Poproś użytkownika o jeden klik: w Media Poolu prawy klik na zaznaczonym klipie SRT → **Insert Selected Subtitles to Timeline Using Timecode**.
   - Nie używaj `AppendToTimeline`, bo dokłada napisy na koniec timeline'u.
   - Sterowanie ekranem tylko na wyraźną prośbę użytkownika.
2. `verify(project, plik)` zwraca `ok`, liczbę napisów i przesunięcie pierwszego i ostatniego.
   - Jeśli przesunięcie jest różne od zera, a FPS nie jest całkowity (23,976 / 29,97 / 59,94): poproś o usunięcie wstawionych napisów, `rebuild(W, tc_clock=True)`, zaimportuj, poproś o ponowne wstawienie i sprawdź jeszcze raz.
   - W innym wypadku zgłoś przesunięcie użytkownikowi.
3. `restore(resolve, project, W)`.

## Przebudowa (bez renderu i transkrypcji)
Gdy użytkownik po obejrzeniu chce coś zmienić w tym samym przebiegu:
- inne parametry: `rebuild(W, profile="netflix")`, `rebuild(W, max_chars=37, max_lines=1)`;
- dodatkowe korekty: `rebuild(W, plan_patch={"edits":[...], "drop":[...]})`.

Potem `import_srt`, prośba o usunięcie poprzedniej ścieżki napisów i wstawienie nowej, `verify`. Każda przebudowa zapisuje nowy plik `_v2`, `_v3`…; poprzednie zostają.

## Raport końcowy (krótko)
- pliki SRT (do Resolve i dla klienta), ścieżka napisów,
- profil, znaki × wiersze, liczba napisów, liczba korekt (przyjęte do decyzji + drobne automatyczne),
- ostrzeżenia z timecode'ami,
- nic o krokach, które przeszły bez problemu.

## Funkcje biblioteki (ściąga)
`check_env(resolve)`, `inventory(project)`, `find_abandoned(project, folder=None)`, `default_folder(nazwa)`, `new_workdir(folder, nazwa)`, `snapshot(resolve, project, W, force=False)`, `start_render(project, W, ścieżki)`, `render_done(project, job)`, `import_and_transcribe(resolve, project, W, wav, speakers=True)`, `wait_transcription(project, wav, wait_s=50)`, `export_words(project, W, wav, track_label=None)`, `prepare(W, profil)`, `build(W, plan, profile, max_chars, max_lines, merge=True, per_speaker=False, tc_clock=False)`, `rebuild(W, plan_patch=None, **parametry)`, `import_srt(project, plik)`, `verify(project, plik)`, `restore(resolve, project, W)`.

## Fakty o Resolve 21.1 (sprawdzone)
- `TranscribeAudio` działa tylko na stronie Edit. Daje czasy pojedynczych słów, ale pierwsze słowo po ciszy bywa rozciągnięte (biblioteka to koryguje).
- Render WAV: `SetCurrentRenderFormatAndCodec("wav", …)` zwraca False, więc biblioteka ustawia format przez `SetRenderSettings` i tryb Single clip.
- SRT importuje się przez `ImportMedia([ścieżka])`. Forma ze słownikiem `{"FilePath": …}` nie działa.
- Create Subtitles from Audio: polski wymaga włączenia „Use experimental languages” w Resolve. Nie daje czasu słów, więc używaj tylko na życzenie, jako kontrolę brakujących słów, na duplikacie timeline'u.
