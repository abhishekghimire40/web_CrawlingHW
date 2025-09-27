import pathlib
import sys
import time
import requests


def fetch_html(url, out_path="page.html", cookie_header=None, tries=2, pause=2):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }
    if cookie_header:
        headers["Cookie"] = cookie_header.strip()

    last_exc = None
    for i in range(tries):
        try:
            resp = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
            print(f"status {resp.status_code}")
            # Save whatever we got to inspect blocks/challenges
            path = pathlib.Path(out_path)
            path.write_text(resp.text, encoding=resp.encoding or "utf-8")
            # Raise on 4xx/5xx after saving, so you can still open the file
            resp.raise_for_status()
            return str(path.resolve())
        except requests.RequestException as e:
            last_exc = e
            if i < tries - 1:
                time.sleep(pause)
    raise last_exc


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_html.py <url> [output_file]")
        sys.exit(1)

    url = sys.argv[1]
    out_file = sys.argv[2] if len(sys.argv) > 2 else "page.html"

    # Optionally paste your Cookie header from Chrome DevTools here
    COOKIE = ""  # example: "__cf_bm=...; datadome=...; optanonConsent=..."

    try:
        saved_path = fetch_html(url, out_file, cookie_header=COOKIE)
        print(f"Saved HTML to: {saved_path}")
    except Exception as e:
        print(f"Request failed: {e}")
        print(
            "If this is Yelp, that likely means a bot block. Use your saved listing.html for parsing."
        )
