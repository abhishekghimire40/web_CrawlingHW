import json
import csv
from bs4 import BeautifulSoup

# Load the saved Yelp HTML file
with open("listing_tikkatangy.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "lxml")

# --- Business Info ---
business = {}
business["name"] = soup.find("h1").get_text(strip=True) if soup.find("h1") else None

rating_tag = soup.find("div", {"role": "img"})
business["rating"] = rating_tag["aria-label"] if rating_tag else None

business["address"] = "390 N Euclid Ave, Saint Louis, MO 63108"
business["categories"] = ["Indian", "Mediterranean"]
business["price_range"] = "$18.99 - $23.99"

review_count_tag = soup.find("span", class_="y-css-1pxa9xg")
business["total_reviews"] = (
    review_count_tag.get_text(strip=True) if review_count_tag else None
)

# --- Extract Reviews ---
reviews = []
review_divs = soup.find_all("div", class_="y-css-1cbn7je")  # review container

for rc in review_divs:
    reviewer_tag = rc.find("span", class_="y-css-1m051bw")
    reviewer = reviewer_tag.get_text(strip=True) if reviewer_tag else None

    rating_tag = rc.find("div", role="img")
    rating = rating_tag["aria-label"] if rating_tag else None

    date_tag = rc.find("span", class_="y-css-chan6m")
    date = date_tag.get_text(strip=True) if date_tag else None

    text_tag = rc.find("span", class_="y-css-1p0srr7")
    text = text_tag.get_text(" ", strip=True) if text_tag else None

    reviews.append({"reviewer": reviewer, "rating": rating, "date": date, "text": text})

# save json
output = {"business": business, "reviews": reviews}

with open("parsed.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=4)

# save csv
with open("parsed.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["reviewer", "rating", "date", "text"])
    writer.writeheader()
    for r in reviews:
        writer.writerow(r)

print(f" Extracted {len(reviews)} reviews. Saved to parsed.json and parsed.csv")
