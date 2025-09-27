import requests
import pathlib

url = "https://www.yelp.com/biz/tikka-tangy-saint-louis"
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
resp = requests.get(url, headers=headers, timeout=20)

output_path = pathlib.Path("tikka_tangy.html")
output_path.write_text(resp.text, encoding=resp.encoding or "utf-8")

print(f"Saved HTML to: {output_path.resolve()}")
