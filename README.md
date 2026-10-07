# YT Shorts Scraper

Dla każdego kanału z listy zbiera:
- datę założenia kanału, łączne wyświetlenia, subskrypcje, liczbę filmów, kraj
- liczbę shortów i sumę ich wyświetleń
- **najpopularniejszy** i **najstarszy** short: tytuł, link, datę dodania, wyświetlenia, lajki, komentarze, długość

Nic nie instaluje w systemie. Wszystko trafia do folderu `.venv` w projekcie.

## Wymagania

- **Python 3.9+**
  - macOS: zwykle już jest, sprawdzisz poleceniem `python3 --version`
  - Windows: pobierz z [python.org](https://www.python.org/downloads/) i przy instalacji zaznacz **„Add Python to PATH”**
- dostęp do internetu

## Pliki do skopiowania

Na nowy komputer przenieś cały folder, ale **bez** `.venv` i `output`:

```
scraper.py
requirements.txt
channels.txt
run.sh
```

> Nie kopiuj folderu `.venv`, bo nie zadziała na innym komputerze. Skrypt utworzy go od nowa sam.

## Lista kanałów

W pliku `channels.txt` wpisujesz jeden link na linię. Linie zaczynające się od `#` są pomijane.

```
https://www.youtube.com/@SERHITO_SH0TY/shorts
https://www.youtube.com/@InnyKanal/shorts
```

## Uruchomienie: macOS / Linux

W terminalu, w folderze projektu:

```bash
chmod +x run.sh      # tylko za pierwszym razem
./run.sh
```

Za pierwszym razem skrypt sam utworzy `.venv` i zainstaluje `yt-dlp`, co trwa kilkanaście sekund.

Inne warianty:

```bash
./run.sh -f moja_lista.txt                                  # inny plik z listą
./run.sh https://www.youtube.com/@SERHITO_SH0TY/shorts      # jeden kanał
```

## Uruchomienie: Windows

`run.sh` nie działa na Windows, więc za pierwszym razem robisz to ręcznie. W PowerShell albo CMD, w folderze projektu:

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Potem za każdym razem:

```bat
.venv\Scripts\python scraper.py
```

## Wyniki

Wszystko zapisuje się w folderze `output/`:

| Plik | Co zawiera |
|---|---|
| `output/<kanał>_<data>.json` | pełne dane jednego kanału |
| `output/results.csv` | tabela wszystkich kanałów: jeden wiersz na kanał, tworzona **od nowa** przy każdym uruchomieniu (stara wersja jest kasowana) |

`results.csv` ma dwa wiersze nagłówka: pierwszy po polsku, drugi po angielsku. Kolumny są rozdzielone średnikiem `;`, więc w Excelu (z polskimi ustawieniami) plik otwiera się od razu rozbity na kolumny. Jeśli któryś kanał się nie uda, i tak dostaje swój wiersz z opisem błędu w kolumnie „Błąd”.

## Problemy

- **„Sign in to confirm you're not a bot”**: YouTube blokuje pobieranie. Dodaj ciasteczka z przeglądarki, w której jesteś zalogowany na YouTube:
  ```bash
  ./run.sh --cookies-from-browser chrome     # albo firefox / safari / edge
  ```
- **Pusta data założenia lub wyświetlenia kanału**: YouTube zmienił stronę „About”. Reszta danych i tak się zapisze.
- **Nagle przestało działać**: zaktualizuj `yt-dlp`:
  ```bash
  .venv/bin/pip install -U yt-dlp            # macOS / Linux
  .venv\Scripts\pip install -U yt-dlp        # Windows
  ```
- **Chcesz wszystko wyczyścić**: usuń folder `.venv`. Przy następnym uruchomieniu utworzy się od nowa.
