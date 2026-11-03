---
name: "fzp-katalog-wypowiedzi"
description: "Katalog wypowiedzi (A-roll) z DaVinci Resolve Studio przez MCP, dla reżysera, producenta albo klienta: transkrybuje bin z wywiadami, opisuje osoby i tematy w metadanych, stawia markery z ID na najlepszych cytatach i tworzy dokument DOCX do pracy offline. Z odesłanego, wypełnionego dokumentu składa nowy timeline w wybranej kolejności. Użyj przy przeglądzie nagranego materiału, przygotowaniu wyboru wypowiedzi albo gdy ktoś przysyła wypełniony katalog."
---

# Katalog wypowiedzi (wersja 1.0)

Autor: Filmowanie z Profitem (filmowaniezprofitem.pl). Licencja: MIT + Commons Clause.

Wymagania: DaVinci Resolve Studio 21.1+ z włączonym MCP (File > Setup AI Assistants), narzędzie `run_script_unsafe`. Liczenie, metadane, markery, dokument DOCX i składanie timeline'u robi biblioteka `scripts/katalog_lib.py` na komputerze z Resolve. Model analizuje treść i rozmawia.

Skill ma **dwa tryby**:
- **Katalog** – materiał → metadane + markery + dokument DOCX dla osoby decydującej.
- **Zwrotka** – odesłany, wypełniony DOCX → nowy timeline w wybranej kolejności.

Rozpoznajesz tryb po prośbie: „zrób katalog / przegląd materiału / przygotuj dla reżysera” → Katalog. Załączony albo wskazany wypełniony katalog, „złóż z tego timeline” → Zwrotka.

## Zasady
- Tylko A-roll (wypowiedzi). Przebitkami się nie zajmujesz poza podpowiedziami fraz do IntelliSearch.
- Cytaty są dosłowne z transkrypcji. Nie poprawiasz sensu i nie dopisujesz tekstu. Podejrzane nazwy własne oznaczasz w przeglądzie.
- Cudzych metadanych i markerów nie usuwasz. Biblioteka dopisuje słowa kluczowe, opis ustawia tylko w pustym polu, a przy ponownym uruchomieniu wymienia wyłącznie markery katalogu.
- Timeline powstaje tylko w Zwrotce, po akceptacji, zawsze jako **nowy**, o nazwie podanej przez użytkownika.
- Czasy i liczby bierzesz z wyników biblioteki.
- Na koniec `restore(resolve, project, W)`.

## Krok 0 – biblioteka, środowisko, biny (oba tryby)
Uruchom przez `run_script_unsafe` poniższy skrypt **dokładnie w tej postaci**. Po `LIB_OK` wypisuje JSON: `env`, `project`, `bins`, `W` (folder roboczy, zapamiętaj).

<!-- LIB:BEGIN (generowane przez tools/build.py - nie edytuj recznie) -->
```python
import os, hashlib, subprocess, urllib.request
VER = "1.0"
SHA = "62f821f169de01e073fd1296d4e0399c9b728d4e00008b0308bdce093fa67aca"
URL = "https://raw.githubusercontent.com/filmowaniezprofitem/fzp_mcp_skills/katalog-v1.0/skills/fzp-katalog-wypowiedzi/scripts/katalog_lib.py"
D = os.path.join(os.path.expanduser("~"), ".fzp-katalog-wypowiedzi")
P = os.path.join(D, "katalog_lib_%s.py" % VER)
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
if ok:  # od razu srodowisko, biny i folder roboczy (Krok 0)
    exec(open(P, encoding="utf-8").read(), globals())
    print(json.dumps(dict(env=check_env(resolve), project=project.GetName(), bins=list_bins(project),
                          W=new_workdir(project)), ensure_ascii=False))
```

Nagłówek każdego kolejnego skryptu (`run_script_unsafe`):
```python
import os
exec(open(os.path.join(os.path.expanduser("~"), ".fzp-katalog-wypowiedzi", "katalog_lib_1.0.py"), encoding="utf-8").read(), globals())
W = "<folder roboczy>"
```
<!-- LIB:END -->

- `env.ok == False` → podaj `env.reason` i zakończ.
- `LIB_BLAD_POBRANIA` → przeczytaj `scripts/katalog_lib.py` z folderu skilla, zapisz w `P` przez `run_script_unsafe` (`open(P, "w", encoding="utf-8", newline="\n").write(r'''<cały plik>''')`) bez zmian i uruchom Krok 0 ponownie. `LIB_ZLY_HASH` → usuń `P`, odeślij do README.
- `LIB_ZLY_HASH` po pobraniu → zatrzymaj się i zgłoś.

---

# Tryb KATALOG

## K1 – materiał i kontekst
Potrzebujesz binu z wywiadami (`bins`; jeśli jest oczywisty, przyjmij go). Brief jest opcjonalny, ale jeśli jest, przeczytaj go: kieruje wyborem cytatów i listą braków. Jeśli bin jest niejasny, zadaj jedno AskUserQuestion, w którym możesz też zapytać o:
- **docelową długość filmu** (wpływa na liczbę cytatów; bez niej przyjmij ok. 30 cytatów),
- **IntelliSearch z twarzami** na binie („Tak” Recommended – wyszukiwarka i kolumna People w Resolve; wymaga pakietu „AI IntelliSearch – Faster” z Extras).

Nazwiska i role osób: z briefu, nazw klipów i treści. Jeśli nie da się ich ustalić, użyj „osoba z C03” i wymień to w przeglądzie jako do uzupełnienia.

## K2 – transkrypcja i jednostki
```python
print(json.dumps(inventory(project, W, "practise footage/Wywiady"), ensure_ascii=False))  # ścieżka binu z K1
```
Brakujące transkrypcje: `print(transcribe_step(resolve, project, W))` w pętli do `status: "gotowe"` (do 50 s na wywołanie). Potem `print(export_units(project, W))` i `print(units_text(W))`, stronicując (`offset=`), aż przeczytasz całość.

## K3 – analiza (model)
Przygotuj katalog:
```json
{"title": "Katalog wypowiedzi: KADR FEST 2026",
 "subtitle": "4 rozmówców, 12 min materiału, stan na 03.11.2026",
 "people": {"C01": {"name": "Anna Nowak", "role": "organizatorka", "summary": "Frekwencja, idea festiwalu, plany.", "topics": ["frekwencja"]}},
 "overview": [
   {"heading": "Kto wystąpił", "bullets": ["Anna Nowak (organizatorka) – frekwencja, idea, plany"]},
   {"heading": "Tematy", "bullets": ["Frekwencja – Anna Nowak (Q001–Q003)"]},
   {"heading": "Braki względem briefu", "paragraphs": ["..."]},
   {"heading": "Możliwe osie opowieści", "bullets": ["..."]},
   {"heading": "Do sprawdzenia", "bullets": ["„Monika Zawacka” – pisownia nazwiska z transkrypcji"]}],
 "quotes": [{"id": "Q001", "topic": "Frekwencja", "from": "C01.U4", "to": "C01.U6", "start_at": "mieliśmy", "broll": "tłum, pełna sala"}]}
```
- **Cytaty:** najmocniejsze, kompletne myśli, o czystym wejściu i wyjściu (`start_at`/`end_at` ucinają „no więc”, falstarty), ok. 3× docelowej długości filmu. Pogrupuj je w tematy. ID nadawaj kolejno `Q001…` w kolejności tematów.
- **Przebitki do szukania:** 2–4 krótkie frazy z treści wypowiedzi, które montażysta wklei do IntelliSearch („hala produkcyjna, maszyny”).
- **Przegląd:** kto wystąpił, tematy i to, kto o nich mówi (z ID), braki względem briefu (jeśli był), 2–3 osie opowieści, rzeczy do sprawdzenia. Krótko, konkretnie, bez oceniania rozmówców.

## K4 – zapis
```python
r = apply_catalog(project, W, cat, intellisearch=True)  # intellisearch zgodnie z K1
print(json.dumps(r, ensure_ascii=False))
```
- `ok: false` → popraw katalog (zwykle `from`/`start_at` nie pasuje) i powtórz.
- Dokument trafia na Pulpit: `~/Desktop/Katalog_<projekt>/<projekt>_katalog_<data>.docx`.
- `restore(resolve, project, W)`.

Raport (krótko): ścieżka DOCX, liczba cytatów i tematów, markery, gdzie zapisano metadane, a gdzie zostawiono istniejący opis, IntelliSearch (czy wystartował; analiza trwa w tle), braki i rzeczy do sprawdzenia w jednym zdaniu. Przypomnij, jak działa zwrotka: wypełniony dokument wystarczy wrzucić do czatu.

---

# Tryb ZWROTKA

## Z1 – dokument
Wypełniony DOCX użytkownik:
- **załącza w czacie** – czytasz go w swoim środowisku: uruchom `scripts/katalog_lib.py` ze skilla lokalnie (np. `python3 -c` z `exec(open(...).read())`) i wywołaj `selection_from_docx(ścieżka)`,
- albo **wskazuje plik na komputerze z Resolve** – wtedy przez `run_script_unsafe` z nagłówkiem biblioteki: `print(json.dumps(selection_from_docx(os.path.expanduser("~/Desktop/…docx")), ensure_ascii=False))`.

Wynik: `items` w kolejności z kolumny „Kol.” (z tabel cytatów i aneksu), `errors`, `warnings`. Każda pozycja ma `clip`, `tc_in`, `tc_out`, `text` (bez skreśleń) i `notes`.

## Z2 – plan (model)
Dla każdej pozycji:
- **uwagi** („tylko pierwsze zdanie”, „bez końcówki”) i **skreślenia** (tekst krótszy niż oryginalny cytat) zamieniasz na `start_at`/`end_at` – dosłowne słowa z tekstu,
- uwagi, których nie da się wykonać cięciem („tu muzyka”, „dać planszę”), przenosisz do raportu jako zadania dla montażysty,
- jeśli wybór ma wyraźne bloki, nadaj pozycjom `section` (stanie się markerem na timeline'ie); bez tego jedna sekcja „Wybór”.

```python
items = [{"section": "Otwarcie", "clip": "Organizatorka", "tc_in": "00:01:02:04", "tc_out": "00:01:13:00",
          "id": "Q001", "who": "Anna Nowak", "start_at": "mieliśmy"}]
r = preview_items(project, items, gap_s=0.0)
print(r["errors"] or r["text"])
```
Pokaż podgląd, zadania dla montażysty i ostrzeżenia (np. dwa razy ten sam numer). Potem jedno AskUserQuestion: **akceptacja** („Buduję timeline” Recommended / „Chcę zmian”) i **nazwa timeline'u** (2–3 propozycje, np. „<projekt> wybór reżysera e01”).

## Z3 – timeline
```python
print(json.dumps(build_from_items(project, "Wybór reżysera e01", items, gap_s=0.0), ensure_ascii=False))
```
Zapasy 0,3 s / 0,4 s bez wchodzenia na sąsiednie słowa, sąsiednie fragmenty jednego klipu łączone, markery sekcji, kontrola dziur i nakładek. `ok: false` → zgłoś błędy (zajęta nazwa → zapytaj o inną). Na koniec `restore(resolve, project, W)`.

Raport: nazwa, długość, liczba fragmentów, ostrzeżenia, zadania dla montażysty z uwag.

Kolejne zmiany: popraw `items`, `preview_items`, akceptacja, nowy timeline z kolejnym numerem (e02…). Poprzednich nie ruszasz.

---

## Funkcje biblioteki (ściąga)
Wspólne: `check_env(resolve)`, `list_bins(project)`, `new_workdir(project)`, `inventory(project, W, bin_path)`, `transcribe_step(resolve, project, W)`, `export_units(project, W)`, `units_text(W, clip=None, offset=0, limit=400)`, `restore(resolve, project, W)`.
Katalog: `apply_catalog(project, W, cat, docx_path=None, write_metadata=True, write_markers=True, intellisearch=False)`.
Zwrotka: `selection_from_docx(path)`, `read_docx_tables(path)`, `preview_items(project, items, gap_s=0.0)`, `build_from_items(project, name, items, gap_s=0.0)`.

## Fakty o Resolve 21.1 (sprawdzone)
- IntelliSearch to wyszukiwarka semantyczna: opisów obiektów i scen nie zapisuje w metadanych. Do metadanych (i eksportu CSV) trafia tylko kolumna People, i tylko przy analizie z rozpoznawaniem twarzy. Twarze nazywa się w Face Gallery.
- Pola `Description`, `Keywords`, `Comments` ustawione przez API trafiają do eksportu metadanych CSV (UTF-16). „Third-party metadata” z API do eksportu nie trafia.
- `TranscribeAudio` ignoruje In/Out subclipu. Biblioteka transkrybuje plik raz i przycina do In/Out.
- Markery na klipach źródłowych (Media Pool) idą za klipem do każdego timeline'u. Katalog oznacza swoje markery w `customData` (`fzp-katalog:{id,s,e}`).
