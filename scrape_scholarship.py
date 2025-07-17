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
EMAIL = os.getenv("SCRAPER_EMAIL", "ribhu.chadha@gmail.com")
PASSWORD = os.getenv("SCRAPER_PASSWORD", "123456")
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

    # click and wait for the form to disappear
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

    # 1) overview
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

    # 2) Scholarships tab
    WebDriverWait(driver, TIMEOUT).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#tab-4"))
    )
    safe_click(driver, driver.find_element(By.CSS_SELECTOR, "#tab-4"))
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div[class*='Scholarships_mainDiv']")
        )
    )

    # 3) load all courses
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

    # 4) for each course tile:
    tiles = driver.find_elements(
        By.CSS_SELECTOR, "div[class*='ExpandableCard_titleDiv']"
    )
    for tile in tiles:
        course = tile.find_element(
            By.CSS_SELECTOR, "div[class*='ExpandableCard_titleText']"
        ).text.strip()
        logger.info(f"🔽 Opening course: {course}")

        # open
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", tile)
        safe_click(driver, tile)

        # wait for scholarship container
        try:
            cont = WebDriverWait(driver, TIMEOUT).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div[class*='Common_scholarship_container']")
                )
            )
        except TimeoutException:
            logger.info(f"No scholarships for {course}")
            continue

        # load-only-while-text-is-“Load”
        while True:
            try:
                vm = cont.find_element(
                    By.CSS_SELECTOR, "div[class*='Common_view_more']"
                )
                txt = vm.text.strip().lower()
                if not txt.startswith("load"):
                    break
                logger.info(f"      Clicking “{vm.text.strip()}” for {course}")
                safe_click(driver, vm)
                time.sleep(0.7)
            except NoSuchElementException:
                break

        # scrape links
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

        # collapse before next
        logger.info(f"🔒 Collapsing {course}")
        safe_click(driver, tile)
        time.sleep(0.3)

    return result


def main():
    if not URL_FILE.exists():
        logger.error(f"{URL_FILE} not found—run extract_urls.py first.")
        return

    entries = json.loads(URL_FILE.read_text(encoding="utf-8"))

    opts = Options()
    # opts.add_argument("--headless=new")  # watch live until rock-solid
    opts.add_argument("--start-maximized")
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
        for entry in entries:
            try:
                all_sch.append(scrape_scholarships(driver, entry))
            except Exception:
                logger.exception(f"⚠️ Error scraping scholarships for ID {entry['id']}")
        OUTPUT_FILE.write_text(
            json.dumps(all_sch, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"Wrote {len(all_sch)} records to {OUTPUT_FILE}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
