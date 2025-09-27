import time
import json
import csv
import argparse
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

parser = argparse.ArgumentParser(
    description="Yelp multi-page review scraper (undetected-chromedriver)"
)
parser.add_argument(
    "--pages", type=int, default=3, help="Number of pages to scrape (default: 3)"
)
parser.add_argument(
    "--min_reviews",
    type=int,
    default=15,
    help="Minimum reviews to collect (default: 15)",
)
parser.add_argument(
    "--headless",
    action="store_true",
    help="Run Chrome headless (may be more detectable)",
)
args = parser.parse_args()

BASE_URL = "https://www.yelp.com/biz/tikka-tangy-saint-louis"
TARGET_PAGES = max(1, args.pages)
MIN_REVIEWS = max(1, args.min_reviews)
MAX_EXTRA_PAGES = 10


def scroll_to_bottom(driver, pause=0.8, steps=6):
    """Scroll down the page in steps to trigger lazy loading."""
    for i in range(steps):
        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight * arguments[0]);",
            (i + 1) / steps,
        )
        time.sleep(pause)


def parse_review_block(bs_block):
    """Extract reviewer name, rating, text, and date."""
    reviewer = None
    try:
        reviewer_tag = bs_block.select_one(
            "span[data-font-weight='bold'] a"
        ) or bs_block.select_one("a[href*='/user_details']")
        if reviewer_tag:
            reviewer = reviewer_tag.get_text(strip=True)
    except Exception:
        reviewer = None

    rating = None
    try:
        rating_div = bs_block.select_one("div[role='img'][aria-label]")
        if rating_div and rating_div.has_attr("aria-label"):
            rating = rating_div["aria-label"].strip()
    except Exception:
        rating = None

    date = None
    try:
        for sp in bs_block.find_all("span"):
            txt = sp.get_text(strip=True)
            if txt and (
                "," in txt
                and any(
                    month in txt
                    for month in [
                        "Jan",
                        "Feb",
                        "Mar",
                        "Apr",
                        "May",
                        "Jun",
                        "Jul",
                        "Aug",
                        "Sep",
                        "Oct",
                        "Nov",
                        "Dec",
                    ]
                )
            ):
                date = txt
                break
    except Exception:
        date = None

    text = None
    try:
        ttag = (
            bs_block.select_one("p.comment__09f24__D0cxf span.raw__09f24__T4Ezm")
            or bs_block.select_one("span.raw__09f24__T4Ezm")
            or bs_block.select_one("p")
        )
        if ttag:
            text = ttag.get_text(" ", strip=True)
    except Exception:
        text = None

    return {
        "reviewer": reviewer or "N/A",
        "rating": rating or "N/A",
        "date": date or "N/A",
        "text": text or "N/A",
    }


options = uc.ChromeOptions()
if args.headless:
    options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
options.add_argument("--disable-blink-features=AutomationControlled")

print("Launching browser (undetected-chromedriver). Please wait...")
driver = uc.Chrome(options=options)
driver.set_page_load_timeout(60)

collected = []
pages_scraped = 0
extra_pages_used = 0

try:
    driver.get(BASE_URL)
    time.sleep(2)

    while True:
        pages_scraped += 1
        print(f"\n--- Scraping page {pages_scraped} ---")
        scroll_to_bottom(driver, pause=1.0, steps=8)
        time.sleep(1)

        try:
            WebDriverWait(driver, 12).until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "ul[data-testid='reviews-list'], div[data-testid='reviews-list']",
                    )
                )
            )
        except Exception:
            pass

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "lxml")

        review_blocks = []
        try:
            review_list = soup.select_one("ul[data-testid='reviews-list']")
            if review_list:
                review_blocks = review_list.select("li")
        except Exception:
            review_blocks = []

        if not review_blocks:
            review_blocks = soup.select("div[data-testid='review']")

        if not review_blocks:
            review_blocks = soup.select("li:has(p)")

        print(
            f"Found {len(review_blocks)} candidate review blocks on page {pages_scraped}."
        )

        for block in review_blocks:
            rv = parse_review_block(block)
            if (
                rv["reviewer"] != "N/A"
                and rv["rating"] != "N/A"
                and rv["text"] != "N/A"
                and rv["date"] != "N/A"
            ):
                if not any(rv["text"] == e["text"] for e in collected):
                    collected.append(rv)

        print(f"Collected total reviews so far: {len(collected)}")

        if pages_scraped >= TARGET_PAGES and len(collected) >= MIN_REVIEWS:
            print("Reached target pages and minimum reviews.")
            break

        if pages_scraped >= TARGET_PAGES and len(collected) < MIN_REVIEWS:
            extra_pages_used += 1
            if extra_pages_used > MAX_EXTRA_PAGES:
                print("Reached safety cap for extra pages. Stopping.")
                break
            print(
                f"Not enough reviews yet ({len(collected)}). Will attempt extra page {extra_pages_used}..."
            )

        try:
            next_el = driver.find_element(
                By.XPATH,
                '//a[contains(@aria-label, "Next")] | //a[contains(@aria-label, "Next page")]',
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", next_el)
            time.sleep(0.6)
            next_el.click()
            time.sleep(2.5)
            continue
        except Exception:
            try:
                current = driver.current_url
                if "start=" in current:
                    import re

                    m = re.search(r"start=(\d+)", current)
                    if m:
                        start = int(m.group(1)) + 20
                        next_url = re.sub(r"start=\d+", f"start={start}", current)
                    else:
                        next_url = current + "&start=20"
                else:
                    next_url = current + (
                        "&start=20" if "?" in current else "?start=20"
                    )
                print("Trying pagination by URL:", next_url)
                driver.get(next_url)
                time.sleep(2.5)
                continue
            except Exception:
                print("No next page available. Ending.")
                break

finally:
    print("\nSaving results...")
    with open("adscrapperdata.json", "w", encoding="utf-8") as jf:
        json.dump(collected, jf, indent=2, ensure_ascii=False)

    fieldnames = ["reviewer", "rating", "date", "text"]
    with open("adscrapperdata.csv", "w", newline="", encoding="utf-8") as cf:
        writer = csv.DictWriter(cf, fieldnames=fieldnames)
        writer.writeheader()
        for item in collected:
            writer.writerow(item)

    try:
        driver.quit()
    except Exception:
        pass
print(f"Done. Pages scraped: {pages_scraped}. Reviews collected: {len(collected)}")
