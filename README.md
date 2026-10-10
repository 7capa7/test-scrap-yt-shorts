# YT Shorts Scraper

Wklejasz linki do `links.txt`, a skrypt **sam rozpoznaje, co to za linki**, i zbiera odpowiednie dane:

| Rodzaj linku | Przykład | Co zbiera |
|---|---|---|
| **Kanał** | `https://www.youtube.com/@SERHITO_SH0TY/shorts` | datę założenia kanału, łączne wyświetlenia, subskrypcje, liczbę filmów, kraj, liczbę shortów i sumę ich wyświetleń, a do tego **najpopularniejszy** i **najstarszy** short |
| **Wyszukiwanie** | `https://www.youtube.com/results?search_query=Familienkonfikte&sp=EgQIBBAJ` | filmiki i shorty z wyników wyszukiwania; filtry ustawione na YouTube (np. „Shorts”, „ten miesiąc”) są zachowane |
| **Hashtag** | `https://www.youtube.com/hashtag/fight/shorts` | shorty z hashtagu |

Dla wyszukiwania i hashtagów każdy filmik dostaje: tytuł, link, typ (Short/Film), autora, link do autora, subskrypcje autora, datę publikacji, liczbę dni od publikacji, wyświetlenia, **wyświetlenia na dzień**, lajki, komentarze, długość, **link do miniaturki**, tagi i opis.

> **Rodzaj ustala pierwszy link z listy.** Linki innego rodzaju są pomijane (skrypt wypisze, które). Na jedno uruchomienie bierzesz więc same kanały, same wyszukiwania albo same hashtagi.

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
links.txt
run.sh
```

> Nie kopiuj folderu `.venv`, bo nie zadziała na innym komputerze. Skrypt utworzy go od nowa sam.

## Lista linków

W pliku `links.txt` wpisujesz jeden link na linię. Linie zaczynające się od `#` są pomijane.

```
https://www.youtube.com/hashtag/fight/shorts
https://www.youtube.com/hashtag/boxing/shorts
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
./run.sh https://www.youtube.com/@SERHITO_SH0TY/shorts      # jeden link
./run.sh --limit 50                                         # 50 filmików na wyszukiwanie/hashtag (domyślnie 20)
./run.sh --fast                                             # szybciej, ale bez lajków, dat, komentarzy i autora
```

Przy wyszukiwaniu i hashtagach skrypt wchodzi w każdy filmik po pełne dane, więc 20 filmików to mniej więcej minuta. `--fast` pomija ten krok i zapisuje tylko to, co widać na liście wyników (tytuł, wyświetlenia, miniaturka).

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
| `output/RRRR-MM-DD_GG-MM-SS.csv` | tabela do Excela, np. `2026-10-10_14-32-05.csv` |
| `output/RRRR-MM-DD_GG-MM-SS.json` | te same dane w pełnej postaci (np. całe opisy filmików) |

**Każde uruchomienie tworzy nowe pliki** z datą i godziną w nazwie, więc stare wyniki zostają.

CSV ma dwa wiersze nagłówka: pierwszy po polsku, drugi po angielsku. Kolumny są rozdzielone średnikiem `;`, więc w Excelu (z polskimi ustawieniami) plik otwiera się od razu rozbity na kolumny.

- **Kanały:** jeden wiersz na kanał.
- **Wyszukiwanie / hashtagi:** wyniki są pogrupowane. Najpierw wiersz z frazą albo hashtagiem, pod nim jego filmiki, potem pusta linia i następna grupa:

```
#fight
1  tytuł…  link…  wyświetlenia…
2  …
(pusta linia)
#boxing
1  …
```

Jeśli coś się nie uda (kanał, fraza albo pojedynczy filmik), i tak dostaje swój wiersz z opisem w kolumnie „Błąd”.

**Miniaturki:** shorty też mają miniaturki. Zwykle to klatka z filmiku wybrana przez autora albo automatycznie przez YouTube. Link prowadzi do obrazka na `i.ytimg.com`.

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
