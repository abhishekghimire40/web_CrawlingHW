from bs4 import BeautifulSoup
import json

with open("C:/Users/BIJAY/Desktop/Web Technologies HOmework 1/listing_ua.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

business = {}


name_tag = soup.find("h1")
business["name"] = name_tag.get_text(strip=True) if name_tag else "N/A"


address_tag = soup.find("address")
business["location"] = address_tag.get_text(" ", strip=True) if address_tag else "N/A"


rating_tag = soup.find("div", {"role": "img"})
business["overall_rating"] = rating_tag.get("aria-label") if rating_tag else "N/A"


review_count_tag = soup.find("span", string=lambda t: t and "review" in t.lower())
business["review_count"] = review_count_tag.get_text(strip=True) if review_count_tag else "N/A"


categories = []
category_section = soup.find_all("span")
for tag in category_section:
    text = tag.get_text(strip=True)
    
    if text.lower() in ["italian", "bars", "wine bars", "seafood", "cafe", "american"]:
        categories.append(text)
business["categories"] = list(set(categories)) if categories else ["N/A"]


price_tag = soup.find("span", string=lambda t: t and "$" in t and len(t) <= 4)
business["price_range"] = price_tag.get_text(strip=True) if price_tag else "N/A"


reviews = [] 

output = {
    "business": business,
    "reviews": reviews
}

with open("parsed.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"✅ Parsed business information into parsed.json")
