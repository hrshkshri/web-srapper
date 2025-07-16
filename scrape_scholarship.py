import json
import time
import logging
import os
from pathlib import Path

from selenium import webdriver
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
OUTPUT_FILE = Path("scholarships.json")
EMAIL = os.getenv("SCRAPER_EMAIL", "your.email@domain.com")
PASSWORD = os.getenv("SCRAPER_PASSWORD", "yourpassword")
TIMEOUT = 20  # seconds

# ─── LOGGING ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def safe_click(driver, element):
    """Try normal click; on interception, scroll into view and JS-click."""
    try:
        element.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        time.sleep(0.2)
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

    # click the known Sign-In button
    driver.find_element(By.CLASS_NAME, "SignIn_signUpBtnEnable__3VCty").click()

    logger.info("3) Waiting for login to complete (URL change)...")
    try:
        WebDriverWait(driver, TIMEOUT).until(lambda d: d.current_url != LOGIN_URL)
    except TimeoutException:
        logger.error("Login never redirected—still at %s", driver.current_url)
        logger.error("Page source snippet:\n%s", driver.page_source[:500])
        raise

    logger.info("✅ Logged in, now at %s", driver.current_url)


def scrape_scholarships(driver, entry):
    url = entry["url"]
    logger.info(f"→ Visiting {url}")
    driver.get(url)

    # 1) wait for the overview container
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
    safe_click(driver, driver.find_element(By.CSS_SELECTOR, "#tab-4"))
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div[class*='Scholarships_mainDiv']")
        )
    )

    # 3) load all course‐cards
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

    cards = driver.find_elements(
        By.CSS_SELECTOR, "div[class*='ExpandableCard_container']"
    )
    for card in cards:
        course = card.find_element(
            By.CSS_SELECTOR, "div[class*='ExpandableCard_titleText']"
        ).text.strip()

        # expand the card
        safe_click(
            driver,
            card.find_element(By.CSS_SELECTOR, "div[class*='ExpandableCard_titleDiv']"),
        )
        time.sleep(0.5)

        # locate the dropdown
        try:
            dropdown = card.find_element(
                By.CSS_SELECTOR, "div[class*='ExpandableCard_dropDownContainer']"
            )
        except NoSuchElementException:
            logger.warning(f"No scholarships for “{course}” – skipping")
            continue

        # load all scholarships within this card
        while True:
            try:
                vm = dropdown.find_element(
                    By.CSS_SELECTOR, "div[class*='Common_view_more']"
                )
                logger.info(f"      Loading more scholarships for {course}")
                safe_click(driver, vm)
                time.sleep(0.7)
            except NoSuchElementException:
                break

        # scrape each scholarship link
        items = []
        for a in dropdown.find_elements(
            By.CSS_SELECTOR, "a[class*='Common_scholarship_body_container']"
        ):
            title = a.find_element(
                By.CSS_SELECTOR, "div[class*='Common_heading']"
            ).text.strip()
            href = a.get_attribute("href")
            items.append({"name": title, "url": href})

        result["scholarships"].append({"course": course, "scholarships": items})
        logger.info(f"   • {len(items)} scholarships for: {course}")

    return result


def main():
    if not URL_FILE.exists():
        logger.error(f"{URL_FILE} not found—run extract_urls.py first.")
        return

    entries = json.loads(URL_FILE.read_text(encoding="utf-8"))

    opts = Options()
    opts.add_argument("--headless=new")
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
        all_sch = []
        for e in entries:
            try:
                all_sch.append(scrape_scholarships(driver, e))
            except Exception:
                logger.exception(f"⚠️ Error scraping scholarships for ID {e['id']}")
        OUTPUT_FILE.write_text(
            json.dumps(all_sch, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"Wrote {len(all_sch)} records to {OUTPUT_FILE}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
