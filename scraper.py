#!/usr/bin/env python3
"""
Prosty scraper kanału YouTube (Shorts).

Użycie:
    python scraper.py                          # czyta kanały z channels.txt
    python scraper.py -f moja_lista.txt        # inny plik z listą
    python scraper.py https://www.youtube.com/@SERHITO_SH0TY/shorts
    python scraper.py --cookies-from-browser chrome   # gdy YouTube każe się "zalogować"

Zbiera:
  - datę założenia kanału, łączne wyświetlenia, subskrypcje, liczbę filmów, kraj
  - najpopularniejszy short (najwięcej wyświetleń)
  - najstarszy short
Zapisuje do:  output/<kanał>_<data>.json  oraz  output/results.csv (tworzony od nowa przy każdym uruchomieniu)
"""
import argparse
import csv
import json
import re
import sys
import urllib.request
from datetime import datetime
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
OUT_DIR = Path(__file__).parent / "output"
CSV_PATH = OUT_DIR / "results.csv"

# (klucz, nagłówek PL, nagłówek EN) – kolejność = kolejność kolumn w CSV
CSV_COLUMNS = [
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


def write_csv(rows: list[dict]):
    """Nadpisuje CSV od zera: 2 wiersze nagłówka (PL, EN) + dane.
    Średnik + BOM UTF-8, żeby Excel (polskie ustawienia) sam rozdzielił kolumny
    i poprawnie pokazał polskie znaki."""
    OUT_DIR.mkdir(exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([pl for _, pl, _ in CSV_COLUMNS])
        w.writerow([en for _, _, en in CSV_COLUMNS])
        for row in rows:
            w.writerow(["" if row.get(k) is None else row.get(k) for k, _, _ in CSV_COLUMNS])


# ---------------------------------------------------------------- helpers

def channel_base_url(url: str) -> str:
    """https://www.youtube.com/@X/shorts -> https://www.youtube.com/@X"""
    url = url.strip().split("?")[0].rstrip("/")
    return re.sub(r"/(shorts|videos|streams|about|featured|playlists|community)$", "", url)


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


# ---------------------------------------------------------------- channel about

def scrape_about(base_url: str) -> dict:
    html = http_get(base_url + "/about")
    m = re.search(r"var ytInitialData\s*=\s*(\{.*?\});\s*</script>", html, re.S)
    if not m:
        raise RuntimeError("Nie znalazłem ytInitialData na stronie /about")
    data = json.loads(m.group(1))

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


# ---------------------------------------------------------------- shorts

def ydl_opts(args, flat):
    o = {"quiet": True, "no_warnings": True, "skip_download": True,
         "extractor_args": {"youtube": {"lang": ["en"]}}}
    if flat:
        o["extract_flat"] = "in_playlist"
    if args.cookies_from_browser:
        o["cookiesfrombrowser"] = (args.cookies_from_browser,)
    return o


def list_shorts(base_url: str, args) -> tuple[dict, list]:
    with yt_dlp.YoutubeDL(ydl_opts(args, flat=True)) as ydl:
        info = ydl.extract_info(base_url + "/shorts", download=False)
    entries = [e for e in (info.get("entries") or []) if e and e.get("id")]
    return info, entries


def video_details(video_id: str, args) -> dict:
    url = f"https://www.youtube.com/shorts/{video_id}"
    with yt_dlp.YoutubeDL(ydl_opts(args, flat=False)) as ydl:
        v = ydl.extract_info(url, download=False)
    return {
        "id": video_id,
        "url": url,
        "title": v.get("title"),
        "upload_date": fmt_date(v.get("upload_date")),
        "views": v.get("view_count"),
        "likes": v.get("like_count"),
        "comments": v.get("comment_count"),
        "duration_s": v.get("duration"),
    }


# ---------------------------------------------------------------- main

def read_channel_list(path: Path) -> list[str]:
    """Jeden URL na linię; puste linie i linie z # są pomijane."""
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def main():
    p = argparse.ArgumentParser(description="Scraper kanałów YouTube Shorts")
    p.add_argument("urls", nargs="*",
                   help="URL-e kanałów, np. https://www.youtube.com/@SERHITO_SH0TY/shorts")
    p.add_argument("-f", "--file", type=Path,
                   help="plik .txt z listą kanałów (jeden URL na linię); "
                        "domyślnie channels.txt, gdy nie podano URL-i")
    p.add_argument("--cookies-from-browser", metavar="BROWSER",
                   help="chrome / firefox / safari – gdy YouTube blokuje jako bota")
    args = p.parse_args()

    urls = list(args.urls)
    list_file = args.file or (None if urls else Path(__file__).parent / "channels.txt")
    if list_file:
        if not list_file.exists():
            sys.exit(f"Nie ma pliku {list_file}")
        urls += read_channel_list(list_file)
    if not urls:
        sys.exit("Brak kanałów do sprawdzenia.")

    failed = []
    rows = []
    write_csv(rows)  # stary CSV kasujemy od razu – zostają same nagłówki
    for i, url in enumerate(urls, 1):
        print(f"\n######## [{i}/{len(urls)}] {url}")
        try:
            rows.append(scrape_channel(url, args))
        except Exception as e:  # noqa: BLE001 – jeden zły kanał nie zatrzymuje reszty
            print(f"  !!! BŁĄD: {e}")
            failed.append(url)
            rows.append({"scraped_at": datetime.now().isoformat(timespec="seconds"),
                         "channel_url": url, "error": str(e)})
        write_csv(rows)  # zapis po każdym kanale – przerwanie nie gubi wyników

    print(f"\nGotowe: {len(urls) - len(failed)}/{len(urls)} kanałów OK.")
    print(f"CSV: {CSV_PATH}")
    if failed:
        print("Nie udało się:")
        for u in failed:
            print(f"  - {u}")


def scrape_channel(url: str, args):
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
    best = video_details(best_id, args)
    print("→ Szczegóły najstarszego shorta...")
    oldest = best if oldest_id == best_id else video_details(oldest_id, args)

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

    # ---- zapis
    OUT_DIR.mkdir(exist_ok=True)
    handle = re.sub(r"[^\w\-]", "", base.rsplit("/", 1)[-1]) or "channel"
    json_path = OUT_DIR / f"{handle}_{datetime.now():%Y%m%d_%H%M%S}.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    row = {k: v for k, v in result.items() if not isinstance(v, dict)}
    for prefix, vid in (("best", best), ("oldest", oldest)):
        for k, v in vid.items():
            row[f"{prefix}_{k}"] = v

    # ---- podsumowanie
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
    print(f"\nZapisano: {json_path}")
    return row


if __name__ == "__main__":
    main()
