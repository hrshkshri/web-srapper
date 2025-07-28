#!/usr/bin/env python3
import json
import time
import logging
import os
from pathlib import Path

from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
)

from webdriver_manager.chrome import ChromeDriverManager

# ─── CONFIG ─────────────────────────────────────────────────────────────
LOGIN_URL = "https://assessment.jitinchawla.com/"
URL_FILE = Path("url.json")
OUTPUT_FILE = Path("scholarships.jsonl")  # now JSON-Lines
EMAIL = os.getenv("SCRAPER_EMAIL", "ribhu.chadha@gmail.com")
PASSWORD = os.getenv("SCRAPER_PASSWORD", "123456")
TIMEOUT = 20  # seconds
# ────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def safe_click(driver, element):
    """Try normal click; on interception scroll into view and JS-click."""
    try:
        element.click()
    except (ElementClickInterceptedException, Exception):
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        time.sleep(0.3)
        try:
            element.click()
        except Exception:
            driver.execute_script("arguments[0].click();", element)


def login(driver):
    logger.info("1) Opening login page")
    driver.get(LOGIN_URL)
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located((By.ID, "emailUid"))
    )

    logger.info("2) Filling credentials")
    driver.find_element(By.ID, "emailUid").send_keys(EMAIL)
    driver.find_element(By.ID, "password").send_keys(PASSWORD)

    signin_btn = driver.find_element(By.CLASS_NAME, "SignIn_signUpBtnEnable__3VCty")
    signin_btn.click()

    logger.info("3) Waiting for login form to go away…")
    WebDriverWait(driver, TIMEOUT).until(EC.staleness_of(signin_btn))
    WebDriverWait(driver, TIMEOUT).until(
        EC.invisibility_of_element_located((By.ID, "emailUid"))
    )
    logger.info("✅ Logged in (login form gone).")


def scrape_scholarships(driver, entry):
    url = entry["url"]
    logger.info(f"→ Visiting {url}")
    driver.get(url)

    # 1) wait for overview
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div[class*='viewDetail_container']")
        )
    )
    name = driver.find_element(
        By.CSS_SELECTOR, "[class*='viewDetail_headingSection'] p"
    ).text.strip()
    location = driver.find_element(
        By.CSS_SELECTOR, "[class*='viewDetail_subHeading'] p"
    ).text.strip()

    # 2) switch to Scholarships tab
    WebDriverWait(driver, TIMEOUT).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#tab-4"))
    )
    safe_click(driver, driver.find_element(By.CSS_SELECTOR, "#tab-4"))
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div[class*='Scholarships_mainDiv']")
        )
    )

    # 3) load all scholarships
    while True:
        try:
            more = driver.find_element(
                By.CSS_SELECTOR, "div[class*='Scholarships_load_more']"
            )
            logger.info("   Clicking “Load More Courses”")
            safe_click(driver, more)
            time.sleep(1)
        except NoSuchElementException:
            break

    result = {
        "id": entry["id"],
        "url": url,
        "name": name,
        "location": location,
        "scholarships": [],
    }

    # 4) for each course card:
    cards = driver.find_elements(
        By.CSS_SELECTOR, "div[class*='ExpandableCard_container']"
    )
    for card in cards:
        title_div = card.find_element(
            By.CSS_SELECTOR, "div[class*='ExpandableCard_titleDiv']"
        )
        course = title_div.find_element(
            By.CSS_SELECTOR, "div[class*='ExpandableCard_titleText']"
        ).text.strip()
        logger.info(f"🔽 Opening course: {course}")

        # ensure visibility + click
        WebDriverWait(driver, TIMEOUT).until(
            lambda d: title_div.is_displayed() and title_div.is_enabled()
        )

        # Try normal click, retry with JS if needed
        for attempt in range(2):
            try:
                logger.info(
                    f"Attempt {attempt+1}: Clicking scholarship toggle for: {course}"
                )
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", title_div
                )
                time.sleep(0.3)
                driver.execute_script("arguments[0].click();", title_div)

                # Wait for scholarship panel to appear inside this card
                WebDriverWait(card, 5).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div[class*='Common_scholarship_container']")
                    )
                )
                break
            except Exception as e:
                if attempt == 0:
                    logger.info(
                        "🔁 Retrying scholarship toggle click after short wait…"
                    )
                    time.sleep(1.5)
                else:
                    logger.warning(
                        f"❌ Failed to open scholarship panel for {course}: {e}"
                    )
                    continue  # will result in no scholarships collected

        # wait for scholarship container
        try:
            cont = WebDriverWait(driver, TIMEOUT).until(
                lambda d: card.find_element(
                    By.CSS_SELECTOR, "div[class*='Common_scholarship_container']"
                )
            )
        except TimeoutException:
            logger.info(f"No scholarships for {course}")
            continue

        # “Load more” inside this card
        while True:
            try:
                vm = cont.find_element(
                    By.CSS_SELECTOR, "div[class*='Common_view_more']"
                )
                if not vm.text.strip().lower().startswith("load"):
                    break
                logger.info(f"      Clicking “{vm.text.strip()}” for {course}")
                safe_click(driver, vm)
                time.sleep(0.7)
            except NoSuchElementException:
                break

        # collect scholarships
        items = []
        for a in cont.find_elements(
            By.CSS_SELECTOR, "a[class*='Common_scholarship_body_container']"
        ):
            try:
                title = a.find_element(
                    By.CSS_SELECTOR, "div[class*='Common_heading']"
                ).text.strip()
                href = a.get_attribute("href")
                items.append({"name": title, "url": href})
            except Exception as e:
                logger.warning(f"⚠️ Skipping bad scholarship in {course}: {e}")

        logger.info(f"   • {len(items)} scholarships for {course}")
        result["scholarships"].append({"course": course, "scholarships": items})

        # collapse the card
        safe_click(driver, title_div)
        time.sleep(0.3)

    return result


def main():
    if not URL_FILE.exists():
        logger.error(f"{URL_FILE} not found—run extract_urls.py first.")
        return

    entries = json.loads(URL_FILE.read_text(encoding="utf-8"))

    # truncate the output JSON-Lines file
    OUTPUT_FILE.unlink(missing_ok=True)
    OUTPUT_FILE.touch()

    opts = Options()
    opts.add_argument("--headless=new")
    # opts.add_argument("--start-maximized")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-setuid-sandbox")

    service = ChromeService(
        ChromeDriverManager().install(), log_path="chromedriver.log"
    )
    driver = webdriver.Chrome(service=service, options=opts)

    try:
        login(driver)
        for entry in entries:
            try:
                record = scrape_scholarships(driver, entry)
                # append each record immediately
                with open(OUTPUT_FILE, "a", encoding="utf-8") as out:
                    json.dump(record, out, ensure_ascii=False)
                    out.write("\n")
                logger.info(f"✅ Saved scholarships for ID {entry['id']}")
            except Exception:
                logger.exception(f"⚠️ Error scraping scholarships for ID {entry['id']}")
    finally:
        driver.quit()
        logger.info("Browser closed")


if __name__ == "__main__":
    main()
