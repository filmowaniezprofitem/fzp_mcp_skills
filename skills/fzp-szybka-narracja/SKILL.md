---
name: "fzp-szybka-narracja"
description: "Składa gotową narrację z wypowiedzi (A-roll) w DaVinci Resolve Studio przez MCP: na podstawie briefu i założeń transkrybuje bin z wywiadami, proponuje narrację tekstowo z czasami, wskazuje braki względem briefu, a po akceptacji buduje nowy timeline cięty na granicach słów. Użyj, gdy ktoś prosi o ułożenie narracji, relacji albo filmu z wypowiedzi."
---

# Szybka narracja z wypowiedzi (wersja 1.0)

Autor: Filmowanie z Profitem (filmowaniezprofitem.pl). Licencja: MIT + Commons Clause.

Wymagania: DaVinci Resolve Studio 21.1+ z włączonym MCP (File > Setup AI Assistants), narzędzie `run_script_unsafe`. Liczenie (klatki, czasy, zapasy, składanie timeline'u, kontrola dziur) robi biblioteka `scripts/narracja_lib.py`. Model wybiera wypowiedzi, układa narrację i rozmawia.

## Zasady
- Narracja składa się **wyłącznie z wypowiedzi z materiału**. Nie dopisujesz lektora ani tekstu, którego nikt nie powiedział. Jeśli brief wymaga czegoś, czego w materiale nie ma, zgłaszasz to jako brak.
- Tylko A-roll. Przebitkami się nie zajmujesz.
- Timeline powstaje **dopiero po akceptacji** narracji tekstowej, zawsze jako **nowy** timeline o nazwie podanej przez użytkownika. Istniejących timeline'ów nigdy nie zmieniasz, poprawki to nowa wersja.
- Czasy i liczby (długość wypowiedzi, suma) bierzesz z wyników biblioteki, nie liczysz ich sam.
- Na koniec `restore(resolve, project, W)`: przywraca język transkrypcji i stronę Resolve.

## Krok 0 – biblioteka, środowisko, biny (bez pytań)
Uruchom przez `run_script_unsafe` poniższy skrypt **dokładnie w tej postaci** (wartości uzupełnia skrypt wydania repozytorium). Po `LIB_OK` wypisuje JSON: `env`, `project`, `bins` (biny z klipami z dźwiękiem) i `W` (folder roboczy tego przebiegu, zapamiętaj go).

<!-- LIB:BEGIN (generowane przez tools/build.py - nie edytuj recznie) -->
```python
import os, hashlib, subprocess, urllib.request
VER = "1.0"
SHA = "c20fdba8e9ac94d11ce5652c897c2107c4979b4492db308063c7f40b2ba5b303"
URL = "https://raw.githubusercontent.com/filmowaniezprofitem/fzp_mcp_skills/narracja-v1.0/skills/fzp-szybka-narracja/scripts/narracja_lib.py"
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
if ok:  # od razu srodowisko, biny i folder roboczy (Krok 0b)
    exec(open(P, encoding="utf-8").read(), globals())
    print(json.dumps(dict(env=check_env(resolve), project=project.GetName(), bins=list_bins(project),
                          W=new_workdir(project)), ensure_ascii=False))
```

Nagłówek każdego kolejnego skryptu (`run_script_unsafe`):
```python
import os
exec(open(os.path.join(os.path.expanduser("~"), ".fzp-szybka-narracja", "narracja_lib_1.0.py"), encoding="utf-8").read(), globals())
W = "<folder roboczy>"
```
<!-- LIB:END -->

Wynik:
- `LIB_OK` + JSON – dalej. `env.ok == False` → podaj `env.reason` i zakończ.
- `LIB_BLAD_POBRANIA` (brak internetu na komputerze z Resolve) – przeczytaj `scripts/narracja_lib.py` z folderu tego skilla, zapisz go przez `run_script_unsafe` w ścieżce `P` (`open(P, "w", encoding="utf-8", newline="\n").write(r'''<cały plik>''')`), bez zmian, i uruchom skrypt z Kroku 0 jeszcze raz. Jeśli zgłosi `LIB_ZLY_HASH`, usuń `P` i powiedz, że trzeba zainstalować bibliotekę ręcznie (README repozytorium).
- `LIB_ZLY_HASH` po pobraniu – zatrzymaj się i zgłoś.

## Krok 1 – brief i założenia
Brief użytkownik podaje w wiadomości albo w załączniku (przeczytaj go). Potrzebujesz:
1. **materiału:** który bin z wypowiedziami (`bins` z Kroku 0; gdy jest jeden albo bieżący wygląda na wywiady, przyjmij go),
2. **długości docelowej** (np. 60–90 s),
3. **celu i odbiorcy** (relacja z wydarzenia, promo, wywiad z firmą…),
4. opcjonalnie: **obowiązkowe treści i osoby**, czego unikać, zakończenie, ton, przerwy między sekcjami.

Jeśli brakuje 1 albo 2, a w mniejszym stopniu 3, zapytaj **jednym** wywołaniem AskUserQuestion (maks. 4 pytania, maks. 4 opcje). Resztę uzupełnij rozsądnie i wypisz przyjęte założenia jedną linią w propozycji. Nie pytaj o rzeczy, które da się wywnioskować z briefu albo nazw klipów.

## Krok 2 – transkrypcja
```python
print(json.dumps(inventory(project, W, "<ścieżka binu>"), ensure_ascii=False))
```
- Klipy z `transcribed: true` mają już transkrypcję w projekcie, Resolve ją pamięta.
- Jeśli któregoś brakuje: `print(transcribe_step(resolve, project, W))` powtarzaj, aż zwróci `status: "gotowe"`. Jedno wywołanie czeka do 50 s, nie dodawaj własnego czekania. Subclipy z jednego pliku transkrybują się raz. Status `bledy`/`blad` → zgłoś, których klipów dotyczy.
- Potem `print(export_units(project, W))`, a następnie `print(units_text(W))` – stronicuj (`offset=`), aż przeczytasz całość.

Jednostki mają postać `C03.U12 [TC źródła] (4,2 s) [mówca] tekst`. Mówcy z Resolve („Speaker 1”) są numerowani osobno w każdym klipie; nazwiska ustalasz z briefu, nazw klipów i treści, a gdy nie wiesz – piszesz „osoba z C03”.

## Krok 3 – narracja tekstowa (model)
Ułóż narrację jako plan:
```json
{"sections":[
  {"title":"Otwarcie","items":[{"from":"C03.U12"},{"from":"C03.U13","to":"C03.U15"}]},
  {"title":"Firmy","items":[{"from":"C05.U2","start_at":"dzisiaj mamy","end_at":"miejsc pracy."}]}]}
```
- `from`/`to` – zakres jednostek z jednego klipu (bez `to` = jedna jednostka).
- `start_at` – pierwsze słowa cytatu wewnątrz `from` (ucina początek: „no więc”, „yyy”, falstart). `end_at` – ostatnie słowa wewnątrz `to`. Wpisuj je dosłownie jak w jednostce.

Zasady redakcyjne:
- Struktura z briefu; bez wskazówek: otwarcie (co, gdzie, po co) → 2–3 sekcje treści → klamra/puenta.
- Pełne zdania, czyste wejścia i wyjścia. Bez powtórzeń tej samej myśli. Różni mówcy, jeśli materiał pozwala.
- Mieść się w długości docelowej (±10%).
- Nazwy własne, które w transkrypcji wyglądają na przekręcone, oznacz do sprawdzenia; nie poprawiaj ich po cichu.

Potem:
```python
r = preview(W, plan, gap_s=0.0)  # gap_s: przerwa między sekcjami w sekundach
print(r["errors"] or r["text"])
```
Przy błędach popraw plan (zwykle `start_at`/`end_at` nie pasuje dosłownie) i powtórz.

Pokaż użytkownikowi:
1. tekst z `preview` (sekcje, wypowiedzi z mówcą, klipem, TC, czasem; suma),
2. **braki względem briefu** – czego materiał nie pokrywa i co z tym zrobić (dograć, plansza, pominąć),
3. **do sprawdzenia** – podejrzane nazwy własne, słabe technicznie fragmenty,
4. przyjęte założenia jedną linią.

Następnie jedno AskUserQuestion z dwoma pytaniami:
- **Akceptacja:** „Buduję timeline” (Recommended) / „Chcę zmian” (szczegóły w Other albo w wiadomości),
- **Nazwa timeline'u:** 2–3 propozycje, np. „<nazwa projektu> narracja e01”, „Narracja e01”. Nazwa nie może być zajęta.

Zmiany: popraw plan, ponów `preview`, pokaż i zapytaj jeszcze raz.

## Krok 4 – timeline
```python
print(json.dumps(build_timeline(project, W, "Narracja e01", gap_s=0.0), ensure_ascii=False))  # nazwa od użytkownika, gap_s jak w preview
```
- Tworzy nowy timeline z ustawieniami projektu, dokłada fragmenty w kolejności planu z zapasami (0,3 s przed, 0,4 s po, bez wchodzenia na sąsiednie słowa), stawia marker na początku każdej sekcji i sprawdza dziury i nakładki.
- `ok: false` z `errors` → zgłoś (np. zajęta nazwa – zapytaj o inną).
- `warnings` z dziurami, nakładkami albo różnicą długości → zgłoś z timecode'ami.
- `restore(resolve, project, W)`.

Raport (krótko): nazwa timeline'u, długość, liczba fragmentów, ewentualne ostrzeżenia, przypomnienie braków z Kroku 3, jeśli były. Bez opisywania kroków, które przeszły.

## Zmiany po zbudowaniu
Użytkownik ogląda i prosi np. „skróć do 60 s”, „zamień drugą wypowiedź prezesa”, „zacznij od X”:
- popraw plan (zapisany w `W/plan.json`; `json.load(open(os.path.join(W, "plan.json")))`), `preview`, pokaż różnicę i nową sumę,
- po akceptacji `build_timeline` z **nową** nazwą (zaproponuj kolejny numer: e02, e03…). Poprzednich wersji nie ruszasz, bo użytkownik mógł już na nich pracować.

## Funkcje biblioteki (ściąga)
`check_env(resolve)`, `list_bins(project)`, `new_workdir(project)`, `inventory(project, W, bin_path=None, recursive=False)`, `transcribe_step(resolve, project, W, lang="pl")`, `export_units(project, W)`, `units_text(W, clip=None, offset=0, limit=400)`, `preview(W, plan, pre_s=0.3, post_s=0.4, gap_s=0.0)`, `build_timeline(project, W, name, plan=None, pre_s=0.3, post_s=0.4, gap_s=0.0)`, `restore(resolve, project, W)`.

## Fakty o Resolve 21.1 (sprawdzone)
- `TranscribeAudio` działa na stronie Edit i ignoruje In/Out subclipu (transkrybuje cały plik). Biblioteka transkrybuje każdy plik raz i przycina jednostki do In/Out klipu.
- Pierwsze słowo po ciszy bywa rozciągnięte na całą ciszę (biblioteka to koryguje).
- `CreateEmptyTimeline` potrafi zwrócić None, jeśli bieżący folder Media Poola nie jest rootem (biblioteka ustawia root i przywraca folder).
- Przy różnym FPS źródła i timeline'u kolejny fragment kładziemy od faktycznego `GetEnd()` poprzedniego, nie z arytmetyki (inaczej 1-klatkowe dziury).
