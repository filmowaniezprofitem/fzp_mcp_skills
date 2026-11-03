# fzp_mcp_skills

Zestaw skilli do pracy z MCP DaVinci Resolve z użyciem Claude. Przygotowane przez [Filmowanie z Profitem](https://filmowaniezprofitem.pl).

| Skill | Co robi | Wersja |
|---|---|---|
| [fzp-napisy-z-timeline](skills/fzp-napisy-z-timeline/SKILL.md) | Polskie napisy SRT z dialogów bieżącego timeline'u: transkrypcja w Resolve, czasy z pojedynczych słów, polskie zasady łamania wierszy, korekty do akceptacji, wstawienie po timecodzie | 3.1 |

## fzp-napisy-z-timeline

Claude renderuje ścieżki dialogowe do WAV, uruchamia transkrypcję w Resolve, poprawia tekst (o niepewne poprawki pyta), dzieli go na napisy zgodnie z polskimi zasadami i cięciami montażowymi, a gotowy SRT importuje do Media Poola. Ty robisz jeden klik, żeby wstawić napisy na timeline. Na koniec projekt wraca do stanu sprzed pracy skilla: ustawienia renderu, ścieżki, folder, strona.

### Wymagania

- **DaVinci Resolve Studio 21.1 lub nowszy** (wersja darmowa nie ma potrzebnego API).
- Włączone MCP w Resolve: **File > Setup AI Assistants**.
- Claude z dostępem do Resolve przez MCP (aplikacja Claude na komputerze, na którym działa Resolve) i z obsługą skilli.
- Internet na komputerze z Resolve przy pierwszym uruchomieniu (pobranie biblioteki, ok. 40 kB).

### Instalacja

1. Pobierz `fzp-napisy-z-timeline.zip` z najnowszego wydania: [Releases](../../releases/latest).
2. Wgraj ZIP jako skill w ustawieniach Claude (sekcja skilli).
3. Gotowe. Przy pierwszym użyciu skill sam pobierze bibliotekę do `~/.napisy-z-timeline/` i sprawdzi jej sumę SHA-256.

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

### Instalacja biblioteki bez internetu

Jeśli komputer z Resolve nie ma dostępu do sieci, skopiuj [`napisy_lib.py`](skills/fzp-napisy-z-timeline/scripts/napisy_lib.py) z wydania jako `~/.napisy-z-timeline/napisy_lib_3.1.py` (na Windows: `C:\Users\<nazwa>\.napisy-z-timeline\napisy_lib_3.1.py`). Plik musi być identyczny bajt w bajt, nie otwieraj go w edytorze, który zmienia końce linii.

### Zgłaszanie problemów

[Issues](../../issues). Podaj wersję Resolve, system, FPS i timecode startu timeline'u oraz komunikat błędu. Folder roboczy (`state.json`, `timeline.json`) bardzo pomaga.

## Licencja

[MIT + Commons Clause](LICENSE).

- Możesz używać skilli za darmo, także w płatnej pracy dla klientów. Napisy, które zrobisz, są twoje.
- Możesz kopiować i modyfikować kod, zachowując informację o autorze i licencji.
- **Nie możesz sprzedawać** skilli ani produktów i usług, których wartość opiera się głównie na nich.

---

## Dla autorów (wydawanie nowej wersji)

```bash
pip install pytest
python -m pytest -q tests          # testy bez Resolve
python tools/build.py              # aktualizuje w SKILL.md wersję, SHA-256 i URL biblioteki
python tools/build.py --check      # to samo sprawdza CI
```

Wydanie:
1. Zmień `LIB_VERSION` w `scripts/napisy_lib.py`, uruchom `python tools/build.py`, dopisz sekcję w `CHANGELOG.md`.
2. Commit, push do `main`.
3. `git tag napisy-v<wersja> && git push origin napisy-v<wersja>`. GitHub Actions sprawdzi testy, zgodność tagu z wersją i hash pliku pod adresem z SKILL.md, a potem zbuduje ZIP i utworzy wydanie.

Każda wersja biblioteki ma osobną nazwę pliku (`napisy_lib_<wersja>.py`), więc stare instalacje skilla działają dalej, a nowa pobiera swoją wersję. Adres pobrania wskazuje tag, nie gałąź `main`, więc zmiany w repozytorium nie psują wydanych wersji.

Nowy skill: folder `skills/<nazwa>/` z `SKILL.md` (i ewentualnie `scripts/`), wpis w `tools/release.json`, osobny `tag_prefix` i wpis w `.github/workflows/release.yml`.
