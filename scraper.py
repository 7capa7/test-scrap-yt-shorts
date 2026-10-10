#!/usr/bin/env python3
"""
Scraper YouTube – sam rozpoznaje rodzaj linku i dobiera sposób zbierania danych.

Rodzaj ustala PIERWSZY link z listy, linki innego rodzaju są pomijane.

  kanał         https://www.youtube.com/@SERHITO_SH0TY/shorts
                → data założenia, wyświetlenia kanału, najlepszy i najstarszy short
  wyszukiwanie  https://www.youtube.com/results?search_query=Familienkonfikte&sp=EgQIBBAJ
                → statystyki filmików/shortów z wyników (filtry z `sp` są zachowane)
  hashtag       https://www.youtube.com/hashtag/fight/shorts
                → statystyki shortów z hashtagu

Użycie:
    python scraper.py                          # czyta linki z links.txt
    python scraper.py -f moja_lista.txt        # inny plik z listą
    python scraper.py <link> [<link> ...]
    python scraper.py --limit 50               # ile filmików na wyszukiwanie/hashtag (domyślnie 20)
    python scraper.py --fast                   # bez wchodzenia w każdy filmik (szybciej, mniej danych)
    python scraper.py --cookies-from-browser chrome   # gdy YouTube każe się "zalogować"

Każde uruchomienie tworzy nowe pliki:  output/RRRR-MM-DD_GG-MM-SS.csv  oraz  .json
"""
import argparse
import csv
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

import yt_dlp

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "en-US,en;q=0.9",
    # pomija stronę zgody na cookies (EU)
    "Cookie": "SOCS=CAI; CONSENT=YES+cb",
}
BASE_DIR = Path(__file__).parent
OUT_DIR = BASE_DIR / "output"
DEFAULT_LIST = BASE_DIR / "links.txt"
VIDEO_ID_RE = re.compile(r"[\w-]{11}")

KIND_NAMES = {"channel": "kanały", "search": "wyszukiwania", "hashtag": "hashtagi"}

# (klucz, nagłówek PL, nagłówek EN) – kolejność = kolejność kolumn w CSV
CHANNEL_COLUMNS = [
    ("scraped_at",          "Data pobrania",                 "Scraped at"),
    ("channel_url",         "Link do kanału",                "Channel URL"),
    ("channel_name",        "Nazwa kanału",                  "Channel name"),
    ("channel_id",          "ID kanału",                     "Channel ID"),
    ("joined_date",         "Data założenia kanału",         "Channel created"),
    ("total_views",         "Wyświetlenia kanału",           "Channel total views"),
    ("subscribers",         "Subskrypcje",                   "Subscribers"),
    ("video_count",         "Liczba filmów",                 "Video count"),
    ("shorts_count",        "Liczba shortów",                "Shorts count"),
    ("shorts_views_sum",    "Suma wyświetleń shortów",       "Shorts total views"),
    ("country",             "Kraj",                          "Country"),
    ("best_title",          "Najlepszy short – tytuł",       "Best short – title"),
    ("best_url",            "Najlepszy short – link",        "Best short – URL"),
    ("best_upload_date",    "Najlepszy short – data",        "Best short – upload date"),
    ("best_views",          "Najlepszy short – wyświetlenia","Best short – views"),
    ("best_likes",          "Najlepszy short – lajki",       "Best short – likes"),
    ("best_comments",       "Najlepszy short – komentarze",  "Best short – comments"),
    ("best_duration_s",     "Najlepszy short – długość (s)", "Best short – duration (s)"),
    ("oldest_title",        "Najstarszy short – tytuł",      "Oldest short – title"),
    ("oldest_url",          "Najstarszy short – link",       "Oldest short – URL"),
    ("oldest_upload_date",  "Najstarszy short – data",       "Oldest short – upload date"),
    ("oldest_views",        "Najstarszy short – wyświetlenia","Oldest short – views"),
    ("oldest_likes",        "Najstarszy short – lajki",      "Oldest short – likes"),
    ("oldest_comments",     "Najstarszy short – komentarze", "Oldest short – comments"),
    ("oldest_duration_s",   "Najstarszy short – długość (s)","Oldest short – duration (s)"),
    ("error",               "Błąd",                          "Error"),
]

# kolumny dla wyszukiwania i hashtagów
VIDEO_COLUMNS = [
    ("position",            "Nr",                            "No."),
    ("title",               "Tytuł",                         "Title"),
    ("url",                 "Link",                          "URL"),
    ("type",                "Typ",                           "Type"),
    ("author",              "Autor",                         "Author"),
    ("author_url",          "Link do autora",                "Author URL"),
    ("author_subscribers",  "Subskrypcje autora",            "Author subscribers"),
    ("upload_date",         "Data publikacji",               "Upload date"),
    ("days_since_upload",   "Dni od publikacji",             "Days since upload"),
    ("views",               "Wyświetlenia",                  "Views"),
    ("views_per_day",       "Wyświetlenia na dzień",         "Views per day"),
    ("likes",               "Lajki",                         "Likes"),
    ("comments",            "Komentarze",                    "Comments"),
    ("duration_s",          "Długość (s)",                   "Duration (s)"),
    ("thumbnail",           "Miniaturka",                    "Thumbnail URL"),
    ("tags",                "Tagi",                          "Tags"),
    ("description",         "Opis",                          "Description"),
    ("id",                  "ID filmu",                      "Video ID"),
    ("error",               "Błąd",                          "Error"),
]


# ---------------------------------------------------------------- zapis

def csv_cell(v):
    if v is None:
        return ""
    if isinstance(v, list):
        v = ", ".join(map(str, v))
    if isinstance(v, str):
        v = re.sub(r"\s*[\r\n]+\s*", " ", v).strip()
        if len(v) > 1000:
            v = v[:1000] + "…"
        if v[:1] in ("=", "+", "-", "@"):
            v = " " + v  # żeby Excel nie potraktował tekstu jako formuły
    return v


def write_csv(path: Path, columns, rows):
    """Zapisuje CSV od zera: 2 wiersze nagłówka (PL, EN) + dane.
    Wiersz-słownik = dane w kolumnach, wiersz-lista = wpisany tak jak jest (np. nagłówek sekcji).
    Średnik + BOM UTF-8, żeby Excel (polskie ustawienia) sam rozdzielił kolumny
    i poprawnie pokazał polskie znaki."""
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([pl for _, pl, _ in columns])
        w.writerow([en for _, _, en in columns])
        for row in rows:
            if isinstance(row, dict):
                w.writerow([csv_cell(row.get(k)) for k, _, _ in columns])
            else:
                w.writerow([csv_cell(x) for x in row])


def write_json(path: Path, kind: str, items):
    payload = {"kind": kind, "scraped_at": datetime.now().isoformat(timespec="seconds"), "items": items}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------- helpers

def normalize_url(url: str) -> str:
    url = url.strip()
    if not re.match(r"https?://", url):
        url = "https://" + url
    u = urllib.parse.urlparse(url)
    if re.fullmatch(r"(?:www\.|m\.)?youtube\.com", u.netloc):
        u = u._replace(scheme="https", netloc="www.youtube.com")
    return urllib.parse.urlunparse(u)


def detect_kind(url: str):
    """'channel' / 'search' / 'hashtag' albo None, gdy link nieobsługiwany."""
    u = urllib.parse.urlparse(url)
    if u.netloc != "www.youtube.com":
        return None
    qs = urllib.parse.parse_qs(u.query)
    if u.path in ("/results", "/search") and (qs.get("search_query") or qs.get("q")):
        return "search"
    if re.match(r"/hashtag/[^/]+", u.path):
        return "hashtag"
    if re.match(r"/(@[^/]+|channel/[^/]+|c/[^/]+|user/[^/]+)", u.path):
        return "channel"
    return None


def listing_label(url: str, kind: str) -> str:
    """Nagłówek sekcji w CSV: fraza wyszukiwania albo #hashtag."""
    u = urllib.parse.urlparse(url)
    if kind == "search":
        qs = urllib.parse.parse_qs(u.query)
        return (qs.get("search_query") or qs.get("q"))[0]
    return "#" + urllib.parse.unquote(u.path.split("/")[2])


def channel_base_url(url: str) -> str:
    """https://www.youtube.com/@X/shorts -> https://www.youtube.com/@X"""
    url = url.strip().split("?")[0].rstrip("/")
    return re.sub(r"/(shorts|videos|streams|about|featured|playlists|community)$", "", url)


def err_text(e) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", str(e)).replace("ERROR: ", "").strip()


def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def http_post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={**HEADERS, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def initial_data(html: str) -> dict:
    m = re.search(r"var ytInitialData\s*=\s*(\{.*?\});\s*</script>", html, re.S)
    if not m:
        raise RuntimeError("Nie znalazłem ytInitialData na stronie")
    return json.loads(m.group(1))


def find_key(obj, key):
    """Rekurencyjnie szuka pierwszego wystąpienia klucza w JSON-ie."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = find_key(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = find_key(v, key)
            if found is not None:
                return found
    return None


def text_of(x):
    if x is None:
        return None
    if isinstance(x, str):
        return x
    if "content" in x:
        return x["content"]
    if "simpleText" in x:
        return x["simpleText"]
    if "runs" in x:
        return "".join(r.get("text", "") for r in x["runs"])
    return None


def parse_int(s):
    if s is None:
        return None
    digits = re.sub(r"[^\d]", "", str(s))
    return int(digits) if digits else None


def parse_joined(s):
    """'Joined Mar 5, 2020' -> '2020-03-05'"""
    if not s:
        return None
    s = s.replace("Joined", "").strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return s


def fmt_date(yyyymmdd):
    if not yyyymmdd:
        return None
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"


# ---------------------------------------------------------------- yt-dlp

def ydl_opts(args, flat, limit=None):
    o = {"quiet": True, "no_warnings": True, "skip_download": True,
         "extractor_args": {"youtube": {"lang": ["en"]}}}
    if flat:
        o["extract_flat"] = "in_playlist"
    if limit:
        o["playlistend"] = limit
    if args.cookies_from_browser:
        o["cookiesfrombrowser"] = (args.cookies_from_browser,)
    return o


def video_details(ydl, url: str) -> dict:
    """Pełne dane jednego filmiku (wchodzi na jego stronę)."""
    v = ydl.extract_info(url, download=False)
    return {
        "id": v.get("id"),
        "url": url,
        "title": v.get("title"),
        "author": v.get("channel") or v.get("uploader"),
        "author_url": v.get("channel_url") or v.get("uploader_url"),
        "author_subscribers": v.get("channel_follower_count"),
        "upload_date": fmt_date(v.get("upload_date")),
        "views": v.get("view_count"),
        "likes": v.get("like_count"),
        "comments": v.get("comment_count"),
        "duration_s": v.get("duration"),
        "thumbnail": v.get("thumbnail"),
        "tags": v.get("tags") or None,
        "description": v.get("description"),
    }


# ---------------------------------------------------------------- tryb: kanał

def scrape_about(base_url: str) -> dict:
    html = http_get(base_url + "/about")
    data = initial_data(html)

    about = find_key(data, "aboutChannelViewModel")
    if about is None:
        # sekcja "About" bywa doładowywana przez continuation -> dociągamy ją
        token = None
        panel = find_key(data, "engagementPanelSectionListRenderer") or data
        cont = find_key(panel, "continuationCommand")
        if cont:
            token = cont.get("token")
        api_key = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html)
        client_ver = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', html)
        if token and api_key:
            resp = http_post_json(
                f"https://www.youtube.com/youtubei/v1/browse?key={api_key.group(1)}",
                {
                    "context": {"client": {
                        "clientName": "WEB",
                        "clientVersion": client_ver.group(1) if client_ver else "2.20241001.00.00",
                        "hl": "en", "gl": "US",
                    }},
                    "continuation": token,
                },
            )
            about = find_key(resp, "aboutChannelViewModel")
    if about is None:
        raise RuntimeError("Nie udało się pobrać sekcji About kanału")

    return {
        "channel_id": about.get("channelId"),
        "joined_raw": text_of(about.get("joinedDateText")),
        "joined_date": parse_joined(text_of(about.get("joinedDateText"))),
        "total_views": parse_int(text_of(about.get("viewCountText"))),
        "subscribers_text": text_of(about.get("subscriberCountText")),
        "video_count": parse_int(text_of(about.get("videoCountText"))),
        "country": text_of(about.get("country")),
        "description": text_of(about.get("description")),
    }


def list_shorts(base_url: str, args) -> tuple[dict, list]:
    with yt_dlp.YoutubeDL(ydl_opts(args, flat=True)) as ydl:
        info = ydl.extract_info(base_url + "/shorts", download=False)
    entries = [e for e in (info.get("entries") or []) if e and e.get("id")]
    return info, entries


def scrape_channel(url: str, args, ydl) -> tuple[dict, dict]:
    base = channel_base_url(url)
    print(f"Kanał: {base}")

    print("→ Pobieram informacje o kanale (About)...")
    try:
        about = scrape_about(base)
    except Exception as e:  # noqa: BLE001
        print(f"  ! About nie wyszło: {e}")
        about = {}

    print("→ Pobieram listę shortów...")
    ch_info, shorts = list_shorts(base, args)
    print(f"  znaleziono {len(shorts)} shortów")
    if not shorts:
        raise RuntimeError("Brak shortów na kanale.")

    # lista jest od najnowszego -> ostatni = najstarszy
    oldest_id = shorts[-1]["id"]
    best_id = max(shorts, key=lambda e: e.get("view_count") or 0)["id"]

    print("→ Szczegóły najpopularniejszego shorta...")
    best = video_details(ydl, f"https://www.youtube.com/shorts/{best_id}")
    print("→ Szczegóły najstarszego shorta...")
    oldest = best if oldest_id == best_id else video_details(ydl, f"https://www.youtube.com/shorts/{oldest_id}")

    result = {
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
        "channel_url": base,
        "channel_name": ch_info.get("channel") or ch_info.get("uploader") or ch_info.get("title"),
        "channel_id": about.get("channel_id") or ch_info.get("channel_id"),
        "joined_date": about.get("joined_date"),
        "total_views": about.get("total_views"),
        "subscribers": ch_info.get("channel_follower_count") or about.get("subscribers_text"),
        "video_count": about.get("video_count"),
        "shorts_count": len(shorts),
        "shorts_views_sum": sum(e.get("view_count") or 0 for e in shorts),
        "country": about.get("country"),
        "best_short": best,
        "oldest_short": oldest,
    }

    row = {k: v for k, v in result.items() if not isinstance(v, dict)}
    for prefix, vid in (("best", best), ("oldest", oldest)):
        for k, v in vid.items():
            row[f"{prefix}_{k}"] = v

    print("\n=========== WYNIK ===========")
    print(f"Kanał:            {result['channel_name']}")
    print(f"Założony:         {result['joined_date']}")
    print(f"Wyświetlenia:     {result['total_views']}")
    print(f"Subskrypcje:      {result['subscribers']}")
    print(f"Shortów:          {result['shorts_count']}")
    print(f"\nNajlepszy short:  {best['title']}")
    print(f"  {best['url']}  | {best['upload_date']} | {best['views']} wyśw. | {best['likes']} lajków")
    print(f"Najstarszy short: {oldest['title']}")
    print(f"  {oldest['url']}  | {oldest['upload_date']} | {oldest['views']} wyśw. | {oldest['likes']} lajków")
    return result, row


def run_channels(urls, args, ydl, csv_path, json_path) -> list:
    rows, results, failed = [], [], []
    for i, url in enumerate(urls, 1):
        print(f"\n######## [{i}/{len(urls)}] {url}")
        try:
            result, row = scrape_channel(url, args, ydl)
        except Exception as e:  # noqa: BLE001 – jeden zły kanał nie zatrzymuje reszty
            print(f"  !!! BŁĄD: {err_text(e)}")
            failed.append(url)
            result = row = {"scraped_at": datetime.now().isoformat(timespec="seconds"),
                            "channel_url": url, "error": err_text(e)}
        results.append(result)
        rows.append(row)
        # zapis po każdym kanale – przerwanie nie gubi wyników
        write_csv(csv_path, CHANNEL_COLUMNS, rows)
        write_json(json_path, "channel", results)
    return failed


# ---------------------------------------------------------------- tryb: wyszukiwanie / hashtag

def entries_from_page(url: str) -> list:
    """Zapasowo: wyciąga ID filmików prosto z HTML-a strony (tylko pierwsza porcja wyników)."""
    data = initial_data(http_get(url))
    out, seen = [], set()

    def add(vid, is_short):
        if vid and vid not in seen:
            seen.add(vid)
            out.append({"id": vid, "url": (f"https://www.youtube.com/shorts/{vid}" if is_short
                                           else f"https://www.youtube.com/watch?v={vid}")})

    def walk(o):
        if isinstance(o, dict):
            vr = o.get("videoRenderer")
            if isinstance(vr, dict):
                add(vr.get("videoId"), find_key(vr.get("navigationEndpoint") or {}, "reelWatchEndpoint") is not None)
            rw = o.get("reelWatchEndpoint")
            if isinstance(rw, dict):
                add(rw.get("videoId"), True)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    return out


def list_entries(url: str, args) -> list:
    entries = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts(args, flat=True, limit=args.limit)) as ydl:
            info = ydl.extract_info(url, download=False)
        entries = [e for e in (info.get("entries") or [])
                   if e and VIDEO_ID_RE.fullmatch(e.get("id") or "")]
    except Exception as e:  # noqa: BLE001
        print(f"  ! yt-dlp nie dał rady ({err_text(e)})")
    if not entries:
        print("  → próbuję odczytać wyniki prosto ze strony...")
        entries = entries_from_page(url)
    return entries[: args.limit]


def row_from_flat(e: dict) -> dict:
    vid = e["id"]
    url = e.get("url") or ""
    if not url.startswith("http"):
        url = f"https://www.youtube.com/watch?v={vid}"
    thumbs = [t for t in (e.get("thumbnails") or []) if t.get("url")]
    return {
        "id": vid,
        "url": url,
        "type": "Short" if "/shorts/" in url else "Film",
        "title": e.get("title"),
        "author": e.get("channel") or e.get("uploader"),
        "author_url": e.get("channel_url") or e.get("uploader_url"),
        "views": e.get("view_count"),
        "duration_s": e.get("duration"),
        "thumbnail": thumbs[-1]["url"] if thumbs else f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        "description": e.get("description"),
    }


def add_derived(row: dict):
    if row.get("upload_date") and row.get("views") is not None:
        try:
            days = (date.today() - date.fromisoformat(row["upload_date"])).days
        except ValueError:
            return
        row["days_since_upload"] = days
        row["views_per_day"] = round(row["views"] / max(days, 1))


def scrape_listing(url: str, args, ydl) -> list:
    print("→ Pobieram listę wyników...")
    entries = list_entries(url, args)
    print(f"  znaleziono {len(entries)}")
    videos = []
    for n, e in enumerate(entries, 1):
        row = {"position": n, **row_from_flat(e)}
        if not args.fast:
            print(f"  [{n}/{len(entries)}] {row['title'] or row['id']}")
            try:
                for k, v in video_details(ydl, row["url"]).items():
                    if v is not None:
                        row[k] = v
            except Exception as ex:  # noqa: BLE001
                row["error"] = f"szczegóły: {err_text(ex)}"
        add_derived(row)
        videos.append(row)
    return videos


def run_listings(kind, urls, args, ydl, csv_path, json_path) -> list:
    rows, groups, failed = [], [], []
    for i, url in enumerate(urls, 1):
        label = listing_label(url, kind)
        print(f"\n######## [{i}/{len(urls)}] {label}")
        try:
            videos = scrape_listing(url, args, ydl)
            error = None if videos else "Brak wyników"
        except Exception as e:  # noqa: BLE001 – jedna zła fraza nie zatrzymuje reszty
            videos, error = [], err_text(e)
        if error:
            print(f"  !!! BŁĄD: {error}")
            failed.append(url)

        if rows:
            rows.append([])          # pusta linia między sekcjami
        rows.append([label, url])    # nagłówek sekcji: fraza / #hashtag
        rows.extend(videos)
        if error:
            rows.append({"error": error})
        groups.append({"label": label, "url": url, "error": error, "videos": videos})
        # zapis po każdej frazie – przerwanie nie gubi wyników
        write_csv(csv_path, VIDEO_COLUMNS, rows)
        write_json(json_path, kind, groups)
    return failed


# ---------------------------------------------------------------- main

def read_link_list(path: Path) -> list[str]:
    """Jeden URL na linię; puste linie i linie z # na początku są pomijane."""
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def main():
    p = argparse.ArgumentParser(description="Scraper YouTube: kanały / wyszukiwanie / hashtagi")
    p.add_argument("urls", nargs="*", help="linki (kanał, wyszukiwanie albo hashtag)")
    p.add_argument("-f", "--file", type=Path,
                   help="plik .txt z listą linków (jeden na linię); "
                        "domyślnie links.txt, gdy nie podano linków")
    p.add_argument("--limit", type=int, default=20,
                   help="ile filmików brać z każdego wyszukiwania/hashtagu (domyślnie 20)")
    p.add_argument("--fast", action="store_true",
                   help="nie wchodź w każdy filmik – szybciej, ale bez lajków, dat, komentarzy")
    p.add_argument("--cookies-from-browser", metavar="BROWSER",
                   help="chrome / firefox / safari – gdy YouTube blokuje jako bota")
    args = p.parse_args()

    urls = list(args.urls)
    list_file = args.file or (None if urls else DEFAULT_LIST)
    if list_file:
        if not list_file.exists():
            sys.exit(f"Nie ma pliku {list_file}")
        urls += read_link_list(list_file)
    if not urls:
        sys.exit("Brak linków do sprawdzenia.")

    urls = [normalize_url(u) for u in urls]
    kind = detect_kind(urls[0])
    if kind is None:
        sys.exit(f"Nie rozpoznaję linku: {urls[0]}\n"
                 "Obsługiwane: kanał (youtube.com/@nazwa), "
                 "wyszukiwanie (youtube.com/results?search_query=...), "
                 "hashtag (youtube.com/hashtag/...)")
    selected = [u for u in urls if detect_kind(u) == kind]
    skipped = [u for u in urls if detect_kind(u) != kind]
    print(f"Rodzaj linków: {KIND_NAMES[kind]} ({len(selected)} do sprawdzenia)")
    if skipped:
        print("Pomijam linki innego rodzaju niż pierwszy:")
        for u in skipped:
            print(f"  - {u}")

    OUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    csv_path = OUT_DIR / f"{stamp}.csv"
    json_path = OUT_DIR / f"{stamp}.json"

    with yt_dlp.YoutubeDL(ydl_opts(args, flat=False)) as ydl:
        if kind == "channel":
            failed = run_channels(selected, args, ydl, csv_path, json_path)
        else:
            failed = run_listings(kind, selected, args, ydl, csv_path, json_path)

    print(f"\nGotowe: {len(selected) - len(failed)}/{len(selected)} OK.")
    if failed:
        print("Nie udało się:")
        for u in failed:
            print(f"  - {u}")
    print(f"Zapisano: {csv_path}\n          {json_path}")


if __name__ == "__main__":
    main()
