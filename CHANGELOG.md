# Zmiany

Format tagów: `<skill>-v<wersja>`, np. `napisy-v3.1`. Sekcja o nazwie tagu trafia do opisu wydania na GitHubie.

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
