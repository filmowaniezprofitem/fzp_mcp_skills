# fzp_mcp_skills

Zestaw skilli do pracy z MCP DaVinci Resolve z użyciem Claude. Przygotowane przez [Filmowanie z Profitem](https://filmowaniezprofitem.pl).

| Skill | Co robi | Wersja | Tag wydania |
|---|---|---|---|
| [fzp-katalog-wypowiedzi](skills/fzp-katalog-wypowiedzi/SKILL.md) | Katalog wypowiedzi dla reżysera, producenta albo klienta: metadane osób i tematów, markery z ID na cytatach, dokument DOCX do pracy offline; z odesłanego dokumentu nowy timeline w wybranej kolejności | 1.0 | `katalog-v…` |
| [fzp-szybka-narracja](skills/fzp-szybka-narracja/SKILL.md) | Gotowa narracja z wypowiedzi według briefu: transkrypcja binu, propozycja tekstowa z czasami i brakami, po akceptacji nowy timeline cięty na granicach słów | 1.0 | `narracja-v…` |
| [fzp-napisy-z-timeline](skills/fzp-napisy-z-timeline/SKILL.md) | Polskie napisy SRT z dialogów bieżącego timeline'u: transkrypcja w Resolve, czasy z pojedynczych słów, polskie zasady łamania wierszy, korekty do akceptacji, wstawienie po timecodzie | 3.1.1 | `napisy-v…` |

## Wymagania (wszystkie skille)

- **DaVinci Resolve Studio 21.1 lub nowszy** (wersja darmowa nie ma potrzebnego API).
- Włączone MCP w Resolve: **File > Setup AI Assistants**.
- Claude z dostępem do Resolve przez MCP (aplikacja Claude na komputerze, na którym działa Resolve) i z obsługą skilli.
- Internet na komputerze z Resolve przy pierwszym uruchomieniu skilla (pobranie jego biblioteki, kilkadziesiąt kB).

## Instalacja

1. Otwórz [Releases](../../releases) i znajdź najnowsze wydanie wybranego skilla (po tagu z tabeli, np. `narracja-v1.0`). W sekcji **Assets** pobierz plik `<nazwa-skilla>.zip`.
   **Nie** pobieraj „Source code (zip)”, bo to archiwum całego repozytorium i Claude go nie przyjmie. Pliku nie rozpakowuj.
2. W Claude otwórz [Customize > Skills](https://claude.ai/customize/skills) (nie sekcję pluginów) i wgraj ZIP jako własny skill.
3. Włącz skill przełącznikiem. Jeśli masz starszą wersję, najpierw ją wyłącz albo usuń, żeby nie mieć dwóch skilli o tej samej nazwie.
4. Gotowe. Przy pierwszym użyciu skill sam pobierze swoją bibliotekę do folderu w katalogu domowym i sprawdzi jej sumę SHA-256.

---

## fzp-katalog-wypowiedzi

Przegląd nagranych wypowiedzi dla kogoś, kto decyduje o kształcie filmu, ale nie siedzi w programie. Skill transkrybuje bin z wywiadami i przygotowuje trzy rzeczy:

- **dokument DOCX** (A4 w poziomie, na Pulpicie): kto wystąpił, tematy i kto o nich mówi, braki względem briefu, możliwe osie opowieści, rzeczy do sprawdzenia, a pod spodem tabele wybranych cytatów pogrupowane po tematach oraz aneks z pełnym zapisem każdego zdania,
- **metadane klipów** w Resolve: `Keywords` z `osoba:` i `temat:` (do Smart Binów i eksportu CSV), `Description` z rolą i streszczeniem (tylko gdy pole jest puste),
- **markery z ID** na klipach źródłowych przy każdym wybranym cytacie; idą za klipem do każdego timeline'u.

Opcjonalnie uruchamia IntelliSearch z rozpoznawaniem twarzy na binie, żeby wyszukiwarka i kolumna People były gotowe.

### Praca z dokumentem (dla osoby decydującej)

1. W żółtej kolumnie **„Kol.”** wpisz numery w kolejności, w jakiej wypowiedzi mają pójść w filmie (1, 2, 3…; wstawka: 2.5). Można wybierać z cytatów i z aneksu.
2. W **„Uwagach”** dopisz, co zmienić („tylko pierwsze zdanie”, „bez końcówki”). Można też skreślić słowa w cytacie.
3. Nie usuwaj kolumn **„ID”** i **„Klip / TC”**. Odeślij plik montażyście.

### Zwrotka (dla montażysty)

Wrzuć odesłany DOCX do czatu (albo wskaż plik na dysku) i napisz „złóż z tego timeline”. Claude pokaże wybór z czasami, przetłumaczy uwagi i skreślenia na cięcia, uwagi niewykonalne cięciem („tu muzyka”) wypisze jako zadania, a po akceptacji zbuduje nowy timeline pod nazwą, którą podasz. Odtworzenie opiera się na kolumnie „Klip / TC”, więc działa nawet po usunięciu markerów.

### Przykład

> Zrób katalog wypowiedzi z binu Wywiady dla reżysera. Film ma mieć ok. 2 min. Brief w załączniku.

---

## fzp-szybka-narracja

Składa film z samych wypowiedzi (A-roll) według briefu. Claude czyta brief, dopytuje tylko o to, czego brakuje (bin z wywiadami, długość, cel), transkrybuje bin, a potem pokazuje narrację tekstowo: sekcje, cytaty z mówcą, klipem, timecode'em i czasem trwania, sumę oraz braki względem briefu. Timeline powstaje dopiero po twojej akceptacji, zawsze jako nowy, pod nazwą, którą podasz.

### Użycie

Otwórz projekt z wywiadami i napisz do Claude, np.:

> Ułóż narrację z binu Wywiady, 60–90 s, relacja z konferencji dla organizatora. Brief w załączniku.

- Cięcia są na granicach słów, z zapasami na oddech (0,3 s przed, 0,4 s po), które nie wchodzą na sąsiednie słowa. Na początku każdej sekcji stoi marker.
- Poprawki („skróć do 60 s”, „zamień drugą wypowiedź prezesa”) Claude wprowadza w planie, pokazuje nową wersję tekstową i po akceptacji buduje **nowy** timeline (e02, e03…). Poprzednich wersji nie rusza.
- Transkrypcja zostaje zapisana w projekcie Resolve, więc kolejne narracje z tego samego materiału startują od razu.
- Subclipy z jednego pliku (np. kilka osób w jednym nagraniu z rejestratora) są obsługiwane: plik jest transkrybowany raz, a każdy subclip dostaje swój fragment według In/Out.

Przebitkami skill się nie zajmuje. Do ich szukania służy IntelliSearch w Resolve.

### Prywatność

Transkrypcja odbywa się lokalnie w DaVinci Resolve. Do Claude trafia tekst wypowiedzi oraz nazwy projektu, binów i klipów. Pliki audio i wideo zostają na twoim komputerze.

---

## fzp-napisy-z-timeline

Claude renderuje ścieżki dialogowe do WAV, uruchamia transkrypcję w Resolve, poprawia tekst (o niepewne poprawki pyta), dzieli go na napisy zgodnie z polskimi zasadami i cięciami montażowymi, a gotowy SRT importuje do Media Poola. Ty robisz jeden klik, żeby wstawić napisy na timeline. Na koniec projekt wraca do stanu sprzed pracy skilla: ustawienia renderu, ścieżki, folder, strona.

### Użycie

Otwórz w Resolve timeline z dialogami i napisz do Claude, np.:

> Zrób napisy do bieżącego timeline'u.

Claude zada jedno pytanie startowe (profil czasów, układ wierszy, ścieżki dialogowe, mówcy), pokaże do decyzji tylko niepewne korekty i poprosi o jeden klik:
**Media Pool → prawy klik na zaznaczonym pliku SRT → Insert Selected Subtitles to Timeline Using Timecode.**

Po obejrzeniu możesz poprosić o zmiany bez ponownej transkrypcji, np. „przebuduj na 37 znaków” albo „profil netflix”.

Pliki trafiają do `Pulpit/Napisy_<timeline>/<timeline>_<data>/`:
- `*_v1.srt` – do Resolve (bezwzględny timecode timeline'u),
- `*_v1_od_zera.srt` – dla klienta, od 00:00:00 (gdy timeline nie startuje od zera).

### Profile czasów

| | montażowy (domyślny) | netflix |
|---|---|---|
| Przerwa między napisami | 0 klatek (styk) | 2 klatki |
| Domykanie przerw | krótszych niż 1 s | krótszych niż 0,5 s |
| Podtrzymanie po ostatnim słowie | do 1 s | do 0,5 s |
| Czas napisu | 5/6 s – 7 s | 5/6 s – 7 s |
| Szybkość czytania | maks. 17 zn/s | maks. 17 zn/s |

### Prywatność

Transkrypcja odbywa się lokalnie w DaVinci Resolve. Do Claude trafia tekst dialogów (do korekty) oraz nazwy timeline'u, ścieżek i klipów. Czasy słów i pliki audio zostają na twoim komputerze.

---

## Instalacja biblioteki bez internetu

Jeśli komputer z Resolve nie ma dostępu do sieci, skopiuj plik biblioteki z wydania (folder `scripts/` w ZIP-ie skilla) do katalogu domowego, bajt w bajt, bez otwierania w edytorze, który zmienia końce linii:

| Skill | Plik w ZIP | Gdzie skopiować |
|---|---|---|
| fzp-katalog-wypowiedzi | `scripts/katalog_lib.py` | `~/.fzp-katalog-wypowiedzi/katalog_lib_1.0.py` |
| fzp-szybka-narracja | `scripts/narracja_lib.py` | `~/.fzp-szybka-narracja/narracja_lib_1.0.py` |
| fzp-napisy-z-timeline | `scripts/napisy_lib.py` | `~/.napisy-z-timeline/napisy_lib_3.1.1.py` |

Na Windows `~` to `C:\Users\<nazwa>`.

## Zgłaszanie problemów

[Issues](../../issues). Podaj nazwę i wersję skilla, wersję Resolve, system, FPS i timecode startu timeline'u oraz komunikat błędu.

## Licencja

[MIT + Commons Clause](LICENSE).

- Możesz używać skilli za darmo, także w płatnej pracy dla klientów. To, co zrobisz z ich pomocą, jest twoje.
- Możesz kopiować i modyfikować kod, zachowując informację o autorze i licencji.
- **Nie możesz sprzedawać** skilli ani produktów i usług, których wartość opiera się głównie na nich.

---

## Dla autorów (wydawanie nowej wersji)

```bash
pip install pytest
python -m pytest -q tests          # testy bez Resolve
python tools/build.py              # aktualizuje w każdym SKILL.md wersję, SHA-256 i URL biblioteki
python tools/build.py --check      # to samo sprawdza CI
```

Wydanie jednego skilla:
1. Zmień `LIB_VERSION` w jego bibliotece, uruchom `python tools/build.py`, dopisz w `CHANGELOG.md` sekcję o nazwie tagu (np. `## narracja-v1.1`).
2. Commit, push do `main`.
3. Utwórz wydanie z tagiem `<tag_prefix><wersja>` (prefiksy w `tools/release.json`), np. w interfejsie GitHuba: Releases → Draft a new release. GitHub Actions sprawdzi testy, dopasuje tag do skilla, sprawdzi hash pliku pod adresem z SKILL.md, zbuduje ZIP i dołączy go do wydania razem z opisem z CHANGELOG.

Każda wersja biblioteki ma osobną nazwę pliku (`<biblioteka>_<wersja>.py`), więc stare instalacje skilla działają dalej, a nowa pobiera swoją wersję. Adres pobrania wskazuje tag, nie gałąź `main`, więc zmiany w repozytorium nie psują wydanych wersji.

Nowy skill: folder `skills/<nazwa>/` z `SKILL.md` (ze znacznikami `LIB:BEGIN`/`LIB:END`) i `scripts/<biblioteka>.py`, wpis w `tools/release.json` (biblioteka, prefiks tagu, folder instalacji, kod startowy) i testy w `tests/`.
