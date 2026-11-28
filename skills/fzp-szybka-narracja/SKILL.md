---
name: "fzp-szybka-narracja"
description: "Składa gotową narrację z wypowiedzi (A-roll) w DaVinci Resolve Studio przez MCP: transkrybuje wypowiedzi z timeline'u albo binu, dzieli je na wątki, proponuje narrację tekstowo z czasami, a po akceptacji buduje nowy timeline cięty na granicach słów. Użyj, gdy ktoś prosi o ułożenie narracji, relacji albo filmu z wypowiedzi."
---

# Szybka narracja z wypowiedzi (wersja 1.1)

Autor: Filmowanie z Profitem (filmowaniezprofitem.pl). Licencja: MIT + Commons Clause.

Wymagania: DaVinci Resolve Studio 21.1+ z włączonym MCP (File > Setup AI Assistants), narzędzie `run_script_unsafe`. Liczenie (klatki, czasy, zapasy, składanie timeline'u, kontrola dziur) robi biblioteka `scripts/narracja_lib.py`. Model dzieli materiał na wątki, wybiera wypowiedzi, układa narrację i rozmawia.

## Zasady
- Narracja składa się **wyłącznie z wypowiedzi z materiału**. Nie dopisujesz lektora ani tekstu, którego nikt nie powiedział. Jeśli brief wymaga czegoś, czego w materiale nie ma, zgłaszasz to jako brak.
- Tylko A-roll. Przebitkami się nie zajmujesz.
- O kolejności i doborze decyduje użytkownik. Proponujesz, nie przesądzasz.
- Timeline powstaje **dopiero po akceptacji** narracji tekstowej, zawsze jako **nowy** timeline o nazwie podanej przez użytkownika. Istniejących timeline'ów nie zmieniasz, chyba że użytkownik wprost o to poprosi.
- Czasy i liczby (długość wypowiedzi, suma) bierzesz z wyników biblioteki, nie liczysz ich sam.
- Na koniec `restore(resolve, project, W)`: przywraca ustawienia języka transkrypcji i stronę Resolve.

## Krok 0 – biblioteka, środowisko, materiał (bez pytań)
Uruchom przez `run_script_unsafe` poniższy skrypt **dokładnie w tej postaci** (wartości uzupełnia skrypt wydania repozytorium). Po `LIB_OK` wypisuje JSON: `env`, `project`, `bins` (biny z klipami z dźwiękiem), `timelines` i `W` (folder roboczy tego przebiegu, zapamiętaj go).

<!-- LIB:BEGIN (generowane przez tools/build.py - nie edytuj recznie) -->
```python
import os, hashlib, subprocess, urllib.request
VER = "1.1"
SHA = "236d17f7ee8bee63a0babb4819ef5320ea8008614a1a02fa5ffbd27330dd1abb"
URL = "https://raw.githubusercontent.com/filmowaniezprofitem/fzp_mcp_skills/narracja-v1.1/skills/fzp-szybka-narracja/scripts/narracja_lib.py"
D = os.path.join(os.path.expanduser("~"), ".fzp-szybka-narracja")
P = os.path.join(D, "narracja_lib_%s.py" % VER)
h = lambda b: hashlib.sha256(b).hexdigest()
ok = os.path.exists(P) and h(open(P, "rb").read()) == SHA
if ok:
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
        ok = True
if ok:  # od razu srodowisko, biny, timeline'y i folder roboczy (Krok 0b)
    exec(open(P, encoding="utf-8").read(), globals())
    print(json.dumps(dict(env=check_env(resolve), project=project.GetName(), bins=list_bins(project),
                          timelines=list_timelines(project), W=new_workdir(project)), ensure_ascii=False))
```

Nagłówek każdego kolejnego skryptu (`run_script_unsafe`):
```python
import os
exec(open(os.path.join(os.path.expanduser("~"), ".fzp-szybka-narracja", "narracja_lib_1.1.py"), encoding="utf-8").read(), globals())
W = "<folder roboczy>"
```
<!-- LIB:END -->

Wynik:
- `LIB_OK` + JSON – dalej. `env.ok == False` → podaj `env.reason` i zakończ.
- `LIB_BLAD_POBRANIA` (brak internetu na komputerze z Resolve) – przeczytaj `scripts/narracja_lib.py` z folderu tego skilla, zapisz go przez `run_script_unsafe` w ścieżce `P` (`open(P, "w", encoding="utf-8", newline="\n").write(r'''<cały plik>''')`), bez zmian, i uruchom skrypt z Kroku 0 jeszcze raz. Jeśli zgłosi `LIB_ZLY_HASH`, usuń `P` i powiedz, że trzeba zainstalować bibliotekę ręcznie (README repozytorium).
- `LIB_ZLY_HASH` po pobraniu – zatrzymaj się i zgłoś.

## Krok 1 – brief, materiał, język
Brief użytkownik podaje w wiadomości albo w załączniku (przeczytaj go). Potrzebujesz:
1. **materiału:** timeline z wypowiedziami (gdy użytkownik go wskazał albo w `timelines` jest oczywisty kandydat) albo bin (`bins`),
2. **języka wypowiedzi** – domyślnie polski (`pl`),
3. **długości docelowej** (np. 60–90 s, 4–7 min),
4. **celu i odbiorcy** (relacja z wydarzenia, promo, wywiad z firmą…),
5. opcjonalnie: obowiązkowe treści i osoby, czego unikać, zakończenie, ton.

Zapytaj **jednym** wywołaniem AskUserQuestion (maks. 4 pytania, maks. 4 opcje) o to, czego brakuje. **Język pytaj zawsze**, z opcją „Polski” (Recommended) na pierwszym miejscu; w tym samym wywołaniu dopytaj materiał i długość, jeśli ich nie ma. Kody języka: ISO 639-1 (`pl`, `en`, `de`…). Resztę uzupełnij rozsądnie i wypisz przyjęte założenia jedną linią.

## Krok 2 – transkrypcja
Materiał z timeline'u (kolejność = kolejność na osi czasu, każdy klip na timeline'ie to osobne C01, C02…, z zakresem użytym na timeline'ie):
```python
print(json.dumps(inventory_timeline(project, W, "<nazwa timeline'u>"), ensure_ascii=False))
```
Materiał z binu (kolejność = data nagrania pliku, potem Start TC):
```python
print(json.dumps(inventory(project, W, "<ścieżka binu>", order="date"), ensure_ascii=False))
```
- `transcribed: true` z `transcription_lang` równym wybranemu językowi – transkrypcja jest gotowa. Transkrypcja w innym języku (np. błędnie rozpoznany angielski) jest czyszczona i robiona od nowa.
- `print(transcribe_step(resolve, project, W, lang="pl"))` powtarzaj, aż zwróci `status: "gotowe"`. Jedno wywołanie czeka do 50 s, nie dodawaj własnego czekania. Status `bledy`/`blad` → zgłoś, których klipów dotyczy (albo że Resolve nie przyjął języka).
- Potem `print(export_units(project, W))`, a następnie `print(units_text(W))` – stronicuj (`offset=`), aż przeczytasz całość.

Jednostki mają postać `C03.U12 [TC źródła] (4,2 s) [mówca] tekst`. Mówców („Speaker 1”) Resolve numeruje w całym projekcie, ale bywa, że myli osoby albo przypisuje pytanie operatora rozmówcy – traktuj to jako wskazówkę. Imiona ustalasz z briefu, nazw klipów i treści; gdy nie wiesz – „osoba z C03”.

## Krok 3 – pełna transkrypcja?
Jedno AskUserQuestion: „Pokazać pełną transkrypcję?” – „Nie, od razu wątki” (Recommended) / „Tak”. Przy „Tak” pokaż `units_text` w całości (bez zmian), potem przejdź dalej.

## Krok 4 – wątki
Podziel materiał na wątki tematyczne w kolejności materiału (timeline albo data nagrania). Dla każdego wątku:
- tytuł, mówca, zakres jednostek (`C07.U5–U17`) i przybliżony czas (z długości jednostek),
- 1–2 zdania treści, najmocniejsze cytaty dosłownie,
- dublujące się podejścia (to samo powiedziane kilka razy) – wskaż czystszy,
- śmieci (rozmowy na planie, falstarty) – jednym zdaniem, że są.

Na końcu: **do sprawdzenia** (przekręcone nazwy własne, niepewni mówcy) i ile jest materiału nadającego się do użytku względem długości docelowej. Nie układasz jeszcze narracji – czekasz, aż użytkownik poda strukturę (kolejność, co zostawić, co wyciąć).

## Krok 5 – narracja: zarys albo pełna treść
Ułóż plan według struktury od użytkownika:
```json
{"sections":[
  {"title":"Intro","items":[{"from":"C03.U12"},{"from":"C03.U13","to":"C03.U15"}]},
  {"title":"Wstęp","items":[{"from":"C05.U2","start_at":"dzisiaj mamy","end_at":"miejsc pracy."}]}]}
```
- `from`/`to` – zakres jednostek z jednego klipu (bez `to` = jedna jednostka).
- `start_at` – pierwsze słowa cytatu wewnątrz `from`. `end_at` – ostatnie słowa wewnątrz `to`. Wpisuj je dosłownie jak w jednostce. Z jednej jednostki można wyciąć kilka fragmentów i ustawić je w innej kolejności (kilka pozycji z tym samym `from` i różnymi `start_at`/`end_at`).

Zasady redakcyjne: pełne zdania, czyste wejścia i wyjścia, bez powtórzeń tej samej myśli (chyba że to celowa zapowiedź w intro – wtedy to zaznacz), różni mówcy, długość docelowa ±10%. Nazwy własne, które wyglądają na przekręcone, oznacz do sprawdzenia; nie poprawiaj ich po cichu.

```python
r = preview(W, plan, gap_s=0.0)
print(r["errors"] or r["text"])
```
Przy błędach popraw plan (zwykle `start_at`/`end_at` nie pasuje dosłownie) i powtórz.

Forma prezentacji – zapytaj AskUserQuestion, jeśli użytkownik nie powiedział: „Zarys” (Recommended: sekcje, mówca, streszczenie lub cytat skrócony, czas sekcji, suma) / „Pełna treść” (cały tekst z `preview`). Do tego zawsze: braki względem briefu, rzeczy do sprawdzenia (np. cięcie w środku zdania), przyjęte założenia jedną linią.

## Krok 6 – poprawki
Użytkownik zmienia kolejność, wymienia albo skraca fragmenty. Popraw plan, `preview`, pokaż tylko to, co się zmieniło, i nową sumę. Powtarzaj, aż zaakceptuje. Przy akceptacji zapytaj o nazwę timeline'u (2–3 propozycje, np. „<projekt> narracja e01”, „Edit02”; nazwa nie może być zajęta), chyba że ją podał.

## Krok 7 – timeline (bez markerów)
```python
print(json.dumps(build_timeline(project, W, "<nazwa>", gap_s=0.0), ensure_ascii=False))
```
- Tworzy nowy timeline z ustawieniami projektu i dokłada fragmenty w kolejności planu z zapasami (0,3 s przed, 0,4 s po, bez wchodzenia na sąsiednie słowa). Markerów nie stawia. Sprawdza dziury, nakładki i stopklatki.
- `ok: false` z `errors` → zgłoś (np. zajęta nazwa – zapytaj o inną).
- `warnings` (dziury, nakładki, różnica długości, „stopklatka?”) → zgłoś z timecode'ami.
- `restore(resolve, project, W)`.

Raport (krótko): nazwa timeline'u, długość, liczba fragmentów, ewentualne ostrzeżenia, przypomnienie braków. Bez opisywania kroków, które przeszły.

## Zmiany po zbudowaniu
Plan jest w `W/plan.json` (`json.load(open(os.path.join(W, "plan.json")))`). Popraw, `preview`, pokaż różnicę i nową sumę, po akceptacji `build_timeline` z **nową** nazwą (kolejny numer). Poprzednich wersji nie ruszasz, chyba że użytkownik wprost poprosi o dołożenie czegoś do istniejącego timeline'u.

## Funkcje biblioteki (ściąga)
`check_env(resolve)`, `list_bins(project)`, `list_timelines(project)`, `new_workdir(project)`, `inventory(project, W, bin_path=None, recursive=False, order="date")` (`order`: `date`/`tc`/`name`), `inventory_timeline(project, W, timeline_name=None)`, `set_transcription_language(project, lang)`, `transcribe_step(resolve, project, W, lang="pl")`, `export_units(project, W)`, `units_text(W, clip=None, offset=0, limit=400)`, `preview(W, plan, pre_s=0.3, post_s=0.4, gap_s=0.0)`, `build_timeline(project, W, name, plan=None, pre_s=0.3, post_s=0.4, gap_s=0.0, markers=False)`, `restore(resolve, project, W)`.

## Fakty o Resolve 21.1 (sprawdzone)
- Polski (i inne języki z listy rozszerzonej) da się ustawić w `transcriptionLanguage` dopiero po `transcriptionExtendedLanguageSupport = "1"`; bez tego `SetSetting` zwraca False i zostaje `auto`, a `auto` potrafi rozpoznać polski jako angielski. Biblioteka włącza to sama i przywraca w `restore`.
- `TranscribeAudio` na subclipie transkrybuje tylko jego zakres; każdy subclip ma własną transkrypcję (21.1.2).
- `AppendToTimeline` dla subclipu liczy `startFrame`/`endFrame` w klatkach pliku (od In subclipu w górę). Klatki poniżej In są dociskane do In i fragment staje się stopklatką o poprawnej długości. Biblioteka bierze przesunięcie z timeline'u źródłowego (`GetSourceStartFrame() - GetLeftOffset()`) albo kalibruje je próbnym wstawieniem.
- `TranscribeAudio` działa na stronie Edit.
- Pierwsze słowo po ciszy bywa rozciągnięte na całą ciszę (biblioteka to koryguje).
- `CreateEmptyTimeline` potrafi zwrócić None, jeśli bieżący folder Media Poola nie jest rootem (biblioteka ustawia root i przywraca folder).
- Przy różnym FPS źródła i timeline'u kolejny fragment kładziemy od faktycznego `GetEnd()` poprzedniego, nie z arytmetyki (inaczej 1-klatkowe dziury).
