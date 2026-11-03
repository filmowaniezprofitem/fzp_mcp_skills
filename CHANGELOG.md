# Zmiany

Format tagów: `<prefiks>-v<wersja>`, np. `napisy-v3.1` albo `narracja-v1.0` (prefiksy w `tools/release.json`). Sekcja o nazwie tagu trafia do opisu wydania na GitHubie.

## narracja-v1.0

Pierwsze wydanie skilla **fzp-szybka-narracja**: gotowa narracja z wypowiedzi (A-roll) według briefu.

- Brief i założenia na wejściu; pytania tylko o brakujące rzeczy (bin, długość, cel).
- Transkrypcja brakujących klipów z czekaniem na status Resolve; plik współdzielony przez subclipy transkrybowany raz, jednostki przycinane do In/Out klipu.
- Narracja tekstowa do akceptacji: sekcje, cytaty z mówcą, klipem, timecode'em i czasem, suma liczona z klatek, braki względem briefu.
- Po akceptacji nowy timeline o nazwie podanej przez użytkownika: cięcia na granicach słów, zapasy 0,3/0,4 s bez wchodzenia na sąsiednie słowa, łączenie kolejnych fragmentów jednego klipu, markery sekcji, kontrola dziur, nakładek i długości.
- Poprawki zawsze jako nowa wersja timeline'u.

Przetestowane w Resolve 21.1.2 na subclipach z jednego nagrania (4 osoby, 25 fps): 6 fragmentów, 41,6 s, bez dziur i nakładek.

## napisy-v3.1.1

Poprawki po pierwszym teście na materiale produkcyjnym.

- Ostrzeżenia o szybkości 15–17 zn/s (normalne tempo mowy) trafiają do osobnej listy `warnings_soft` i w raporcie pojawiają się tylko jako liczba. Indywidualnie pokazywane są napisy powyżej 17 zn/s i pozostałe problemy (łamanie, cięcia, czasy). Liczby w raporcie pochodzą z wyniku `build`, a nie z liczenia przez model.
- Instalacja biblioteki, sprawdzenie środowiska i inwentarz timeline'u w jednym skrypcie: o jedno wywołanie mniej na starcie.

## napisy-v3.1

Pierwsze publiczne wydanie skilla **fzp-napisy-z-timeline**.

- Biblioteka instalowana z GitHuba z weryfikacją SHA-256. Model nie przepisuje już kodu z pamięci; jest to tylko awaryjny tryb dla komputerów bez internetu, też sprawdzany hashem.
- Wykrywanie porzuconego przebiegu (preset `_napisy_backup` i niezamknięty `state.json`) i propozycja przywrócenia. Wcześniej nowy przebieg kasował kopię oryginalnych ustawień renderu.
- `wait_transcription()` czeka do 50 s w jednym wywołaniu zamiast odpytywania co 30 s przez model.
- `build()` zapisuje `plan.json` i `params.json`, a nowe `rebuild()` przebudowuje napisy z innymi parametrami lub dodatkowymi korektami bez ponownego renderu i transkrypcji.
- Timecode drop-frame (29,97 / 59,94 DF) poprawnie wyświetlany w jednostkach, podglądzie i ostrzeżeniach.
- `check_env()` sprawdza wersję Resolve Studio przed startem.
- Pulpit na Windows wykrywany także przy przekierowaniu przez OneDrive. Bezpieczne nazwy folderów roboczych.
- Cięcia liczone bez tytułów, Text+, generatorów i klipów dopasowujących.
- Krok startowy mieści się w jednym oknie pytań (maks. 4 pytania). Domyślny tryb szybki przeglądu korekt: oczywiste poprawki bez pytania, do decyzji tylko niepewne.
- Poprawka w `verify()` (kolejność warunków przy wyszukiwaniu ścieżki napisów).
- Jawne kodowanie UTF-8 przy wszystkich plikach roboczych (Windows).

Do sprawdzenia w Resolve przed szerszym udostępnieniem: pomijanie tytułów przy cięciach (`GetMediaPoolItem()`), Windows z OneDrive, timeline 29,97 DF.

## napisy-v3.0

Wersja wewnętrzna (biblioteka osadzona w SKILL.md).
