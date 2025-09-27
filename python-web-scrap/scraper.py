from requests_html import HTMLSession
import json
import argparse

import sys

pages = 3
if len(sys.argv) > 1:
    pages = int(sys.argv[1])

url = "https://www.yelp.com/biz/tikka-tangy-saint-louis"
session = HTMLSession()
reviews = []

for page in range(pages):
    page_url = f"{url}?start={page*20}"  # 20 reviews per page
    r = session.get(page_url)
    r.html.render(wait=3)

    review_texts = r.html.find("p.comment__09f24__gu0rG")  # update selector if needed
    for rev in review_texts:
        reviews.append({"review": rev.text})

    if not review_texts:
        break

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(reviews, f, indent=4, ensure_ascii=False)

print(f" scraped {len(reviews)} reviews")
