import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup


def load_html(path: Path) -> BeautifulSoup:
    html_text = path.read_text(encoding="utf-8", errors="ignore")
    return BeautifulSoup(html_text, "lxml")


def get_business_name(soup: BeautifulSoup) -> Optional[str]:
    # Yelp usually has a single <h1> for the business name.
    # In your file it renders as: <h1 class="...">Tikka Tangy</h1>
    # (class names are hashed, so we just grab the first h1)
    header = soup.find("h1")
    return header.get_text(strip=True) if header else None


def get_city_state_ga(soup: BeautifulSoup) -> Optional[str]:
    """
    Inlined JSON blob contains: "biz_city_state": ["...", "Saint Louis, MO"]
    We'll extract the string value via regex from the whole document text.
    """
    doc = soup.get_text(" ", strip=False)
    m = re.search(r'"biz_city_state"\s*:\s*\[\s*\d+,\s*"([^"]+)"\s*\]', doc)
    if not m:
        # Some snapshots show without the index on the left; try a simpler pattern
        m = re.search(r'"biz_city_state"\s*:\s*\[\s*"?\d*"?\s*,\s*"([^"]+)"\s*\]', doc)
    return m.group(1) if m else None  # e.g., "Saint Louis, MO"


def get_overall_rating_and_count(soup: BeautifulSoup) -> Dict[str, Optional[float]]:
    """
    Pull rating (float) and review_count (int) from the same GA dimensions block.
    Examples in your file:
      "rating":[114,4.5]
      "biz_review_count":[10,"40"]
    """
    text = soup.get_text(" ", strip=False)

    rating = None
    # Look for rating:number (either with or without the GA index)
    m_rating = re.search(r'"rating"\s*:\s*\[\s*\d+\s*,\s*([0-9.]+)\s*\]', text)
    if not m_rating:
        m_rating = re.search(r'"rating"\s*:\s*([0-9.]+)\b', text)
    if m_rating:
        try:
            rating = float(m_rating.group(1))
        except ValueError:
            rating = None

    review_count = None
    m_count = re.search(r'"biz_review_count"\s*:\s*\[\s*\d+\s*,\s*"(\d+)"\s*\]', text)
    if not m_count:
        m_count = re.search(r'"biz_review_count"\s*:\s*"(\d+)"', text)
    if m_count:
        try:
            review_count = int(m_count.group(1))
        except ValueError:
            review_count = None

    return {"overall_rating": rating, "total_review_count": review_count}


def get_categories(soup: BeautifulSoup) -> List[str]:
    """
    Categories also appear in GA JSON as:
      "second_level_categories":[110,"indpak, pizza, mediterranean"]
    We'll split on comma.
    """
    text = soup.get_text(" ", strip=False)
    m = re.search(
        r'"second_level_categories"\s*:\s*\[\s*\d+\s*,\s*"([^"]+)"\s*\]', text
    )
    if not m:
        m = re.search(r'"second_level_categories"\s*:\s*"([^"]+)"', text)
    if m:
        raw = m.group(1)
        return [c.strip() for c in raw.split(",") if c.strip()]
    return []


def iter_jsonld_blocks(soup: BeautifulSoup):
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        # Some Yelp JSON-LD has multiple objects per tag (array) and some a single object.
        try:
            data = json.loads(tag.string or "null")
        except json.JSONDecodeError:
            # Some tags include HTML comments or minor issues; try to sanitize lightly.
            content = (tag.string or "").strip()
            content = content.strip("<!--").strip("-->")
            try:
                data = json.loads(content)
            except Exception:
                continue
        yield data


def collect_review_items_from_jsonld(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    The saved page includes many ImageObject entries that embed a "review" object:
    {
      "@type": "ImageObject",
      "author": {"@type": "Person", "name": "..."},
      "review": {
         "@type": "Review",
         "author": {"@type": "Person", "name": "Robert B."},
         "itemReviewed": {"@type": "Thing", "name": "Tikka Tangy"},
         "reviewRating": {"@type": "Rating", "ratingValue": 4},
         "datePublished": "2025-07-17T04:38:26Z",
         "reviewBody": "...?" (not always present)
      }
    }
    We’ll use these as our review rows if the HTML doesn’t render the standard list.
    """
    reviews: List[Dict[str, Any]] = []
    for data in iter_jsonld_blocks(soup):
        # Normalize to a list
        objs = data if isinstance(data, list) else [data]
        for obj in objs:
            if not isinstance(obj, dict):
                continue
            if obj.get("@type") == "ImageObject" and isinstance(
                obj.get("review"), dict
            ):
                r = obj["review"]
                author = None
                if isinstance(r.get("author"), dict):
                    author = r["author"].get("name")
                rating_value = None
                if isinstance(r.get("reviewRating"), dict):
                    rating_value = r["reviewRating"].get("ratingValue")
                    try:
                        rating_value = (
                            float(rating_value) if rating_value is not None else None
                        )
                    except ValueError:
                        rating_value = None
                date_published = r.get("datePublished")
                text = r.get("reviewBody")  # often missing in Yelp’s JSON-LD for photos
                reviews.append(
                    {
                        "reviewer_name": author,
                        "review_stars": rating_value,
                        "review_date": date_published,
                        "review_text": text,  # may be None
                    }
                )
    return reviews


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 parse_listing.py listing_tikkatangy.html")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"File not found: {input_path}")
        sys.exit(1)

    soup = load_html(input_path)

    business_name = get_business_name(soup)
    city_state = get_city_state_ga(soup)  # e.g., "Saint Louis, MO"
    rating_info = get_overall_rating_and_count(soup)
    categories = get_categories(soup)

    # Try to harvest review rows from JSON-LD (since the visible DOM is skeleton in this snapshot).
    review_rows = collect_review_items_from_jsonld(soup)

    # Filter to at least 5 distinct reviews (drop null names if needed)
    clean_rows: List[Dict[str, Any]] = []
    for row in review_rows:
        # we accept rows with at least a name and rating or date
        if (
            row.get("reviewer_name")
            or row.get("review_stars")
            or row.get("review_date")
        ):
            clean_rows.append(row)
    # If there are many, keep the first 20 (or adjust as you like)
    clean_rows = clean_rows[:20]

    # Attach business-level fields to every review row to satisfy the ≥6 fields requirement
    output_rows = []
    for r in clean_rows:
        output_rows.append(
            {
                "business_name": business_name,
                "city_state": city_state,
                "categories": categories,
                "overall_rating": rating_info["overall_rating"],
                "total_review_count": rating_info["total_review_count"],
                "reviewer_name": r.get("reviewer_name"),
                "review_stars": r.get("review_stars"),
                "review_date": r.get("review_date"),
                "review_text": r.get("review_text"),
            }
        )

    # Save as parsed.json (one object per review)
    out_path = input_path.with_name("parsed.json")
    out_path.write_text(
        json.dumps(output_rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote {len(output_rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
