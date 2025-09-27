#!/usr/bin/env python3
import json, re, sys
from pathlib import Path
from bs4 import BeautifulSoup


def load_soup(p: Path) -> BeautifulSoup:
    return BeautifulSoup(p.read_text(encoding="utf-8", errors="ignore"), "lxml")


def text_search(pattern, text, cast=None):
    m = re.search(pattern, text, flags=re.I | re.S)
    if not m:
        return None
    val = m.group(1)
    if cast:
        try:
            return cast(val)
        except:
            return None
    return val


def parse_business_fields(soup: BeautifulSoup):
    txt = soup.get_text(" ", strip=False)
    city_state = text_search(r'"biz_city_state"\s*:\s*\[\s*\d+,\s*"([^"]+)"\s*\]', txt)
    overall = text_search(r'"rating"\s*:\s*\[\s*\d+,\s*([0-9.]+)\s*\]', txt, float)
    count = text_search(r'"biz_review_count"\s*:\s*\[\s*\d+,\s*"(\d+)"\s*\]', txt, int)

    name_tag = soup.find("h1")
    business_name = name_tag.get_text(strip=True) if name_tag else None

    cats = text_search(
        r'"second_level_categories"\s*:\s*\[\s*\d+,\s*"([^"]+)"\s*\]', txt
    )
    categories = [c.strip() for c in (cats or "").split(",") if c.strip()]

    return {
        "business_name": business_name,
        "city_state": city_state,
        "overall_rating": overall,
        "total_review_count": count,
        "categories": categories,
    }


def parse_reviews_jsonld(soup: BeautifulSoup):
    reviews = []
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = s.string or ""
        try:
            data = json.loads(raw)
        except Exception:
            continue
        # normalize
        items = data if isinstance(data, list) else [data]
        for it in items:
            if not isinstance(it, dict):
                continue
            # direct Review objects
            if it.get("@type") == "Review":
                reviews.append(
                    {
                        "reviewer_name": (
                            (it.get("author") or {}).get("name")
                            if isinstance(it.get("author"), dict)
                            else it.get("author")
                        ),
                        "review_stars": (
                            (it.get("reviewRating") or {}).get("ratingValue")
                            if isinstance(it.get("reviewRating"), dict)
                            else None
                        ),
                        "review_date": it.get("datePublished"),
                        "review_text": it.get("reviewBody"),
                    }
                )
            # ImageObject carrying a nested review
            if it.get("@type") == "ImageObject" and isinstance(it.get("review"), dict):
                r = it["review"]
                reviews.append(
                    {
                        "reviewer_name": (
                            (r.get("author") or {}).get("name")
                            if isinstance(r.get("author"), dict)
                            else r.get("author")
                        ),
                        "review_stars": (
                            (r.get("reviewRating") or {}).get("ratingValue")
                            if isinstance(r.get("reviewRating"), dict)
                            else None
                        ),
                        "review_date": r.get("datePublished"),
                        "review_text": r.get("reviewBody"),
                    }
                )
    # clean and cast rating
    for r in reviews:
        try:
            r["review_stars"] = (
                float(r["review_stars"]) if r["review_stars"] is not None else None
            )
        except:
            r["review_stars"] = None
    return [
        r
        for r in reviews
        if any(
            [
                r.get("reviewer_name"),
                r.get("review_stars"),
                r.get("review_date"),
                r.get("review_text"),
            ]
        )
    ]


def parse_reviews_dom(soup: BeautifulSoup):
    """
    Fallback for server-rendered review cards.
    Looks for aria-label="X star rating" near reviewer name/date/text.
    This will only work if reviews actually exist in the HTML snapshot.
    """
    results = []
    # common Yelp pattern: stars as a div/span with aria-label like "4.0 star rating"
    star_nodes = soup.find_all(
        attrs={"aria-label": re.compile(r"\bstar rating\b", re.I)}
    )
    for node in star_nodes:
        # climb to a likely review container
        card = node
        for _ in range(5):
            if card and card.name in ("section", "article", "li", "div"):
                # heuristic: look for name/date/text in this subtree
                text = card.get_text(" ", strip=True)
                # extract pieces with simple regex heuristics
                mstars = re.search(
                    r"([0-9](?:\.[05])?)\s+star rating",
                    node.get("aria-label", ""),
                    flags=re.I,
                )
                stars = float(mstars.group(1)) if mstars else None
                # try to pick a name: often an <a> or strong close to the star node
                name = None
                for a in card.find_all(["a", "span", "strong"], limit=6):
                    t = a.get_text(strip=True)
                    if (
                        t
                        and 2 <= len(t) <= 40
                        and "Elite" not in t
                        and "photo" not in t.lower()
                    ):
                        name = t
                        break
                # date often shows as time or span
                date = None
                ttag = card.find("time")
                if ttag and (ttag.get("datetime") or ttag.get_text(strip=True)):
                    date = ttag.get("datetime") or ttag.get_text(strip=True)
                # review text paragraphs
                body = None
                for p in card.find_all(["p", "span"], limit=10):
                    pt = p.get_text(" ", strip=True)
                    if pt and len(pt.split()) > 5:
                        body = pt
                        break

                if stars or body:
                    results.append(
                        {
                            "reviewer_name": name,
                            "review_stars": stars,
                            "review_date": date,
                            "review_text": body,
                        }
                    )
                    break
            card = card.parent
    # de-dup
    uniq = []
    seen = set()
    for r in results:
        key = (r.get("reviewer_name"), r.get("review_date"), r.get("review_text"))
        if key not in seen:
            uniq.append(r)
            seen.add(key)
    return uniq


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 parse_listing.py listing_tikkatangy.html")
        sys.exit(1)
    path = Path(sys.argv[1])
    soup = load_soup(path)

    biz = parse_business_fields(soup)
    jsonld_reviews = parse_reviews_jsonld(soup)
    dom_reviews = parse_reviews_dom(soup)

    reviews = jsonld_reviews or dom_reviews
    if not reviews:
        print(
            "Warning: 0 reviews found. Your HTML likely lacks server-rendered review cards."
        )
        print(
            "Try re-saving the page via Chrome DevTools → Network → Copy as cURL (bash)."
        )

    rows = []
    for r in reviews[:50]:
        rows.append(
            {
                **biz,
                "reviewer_name": r.get("reviewer_name"),
                "review_stars": r.get("review_stars"),
                "review_date": r.get("review_date"),
                "review_text": r.get("review_text"),
            }
        )

    out = path.with_name("parsed.json")
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"Business: {biz['business_name'] or '(unknown)'} | City: {biz['city_state']} | Rating: {biz['overall_rating']} | Count: {biz['total_review_count']}"
    )
    print(f"Wrote {len(rows)} reviews to {out}")


if __name__ == "__main__":
    main()
