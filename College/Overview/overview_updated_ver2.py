import re
import time
import json
import logging
import traceback
import os
import tempfile
import requests

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager


# ─── SETUP LOGGING ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    # ─── CONFIG ──────────────────────────────────────────────────────────
    LOGIN_URL = "https://assessment.jitinchawla.com/"
    BASE_URL = "https://assessment.jitinchawla.com/colleges"
    EMAIL = os.environ.get("SCRAPER_EMAIL", "ribhu.chadha@gmail.com")
    PASSWORD = os.environ.get("SCRAPER_PASSWORD", "123456")
    TIMEOUT = 5
    OUTPUT_FILE = "college_overviews_1001_1200.json"

    # ─── RESUME FROM LAST LINE ───────────────────────────────────────────
    START_ID = 519
    counter = 0
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            counter = len(lines)
            if lines:
                last_entry = json.loads(lines[-1])
                START_ID = last_entry["id"] + 1
                logger.info(f"🔁 Resuming from ID {START_ID}")

    END_ID = 1000

    # ─── START DRIVER ────────────────────────────────────────────────────
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--log-level=3")  # Suppress ChromeDriver logs
    options.add_argument(f"--user-data-dir={tempfile.mkdtemp()}")

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()), options=options
    )

    try:
        # ─── 1) LOGIN ────────────────────────────────────────────────────────
        logger.info("Logging in…")
        driver.get(LOGIN_URL)
        WebDriverWait(driver, TIMEOUT).until(
            EC.presence_of_element_located((By.ID, "emailUid"))
        )
        driver.find_element(By.ID, "emailUid").send_keys(EMAIL)
        driver.find_element(By.ID, "password").send_keys(PASSWORD)
        driver.find_element(By.CLASS_NAME, "SignIn_signUpBtnEnable__3VCty").click()
        time.sleep(2)
        logger.info("✅ Logged in")

        # ─── 2) BRUTE‐FORCE EACH ID ──────────────────────────────────────────
        for cid in range(START_ID, END_ID + 1):
            url = f"{BASE_URL}/{cid}/overview"

            # ✅ FAST PRE-CHECK
            try:
                response = requests.get(url, stream=True, timeout=(2, 4))
                if response.status_code == 404:
                    logger.warning(f"→ ID {cid} returned 404, skipping")
                    continue
                elif response.status_code >= 500:
                    logger.warning(
                        f"→ ID {cid} server error {response.status_code}, skipping"
                    )
                    continue
            except requests.RequestException as e:
                logger.warning(f"⚠️ ID {cid} request failed ({e}), skipping")
                continue

            # ✅ Load Page in Selenium
            try:
                driver.get(url)
                # time.sleep(1)  # Minimal wait

                # ✅ Detect soft-404 using known image
                if driver.find_elements(
                    By.XPATH, "//img[contains(@src, 'page_not_found.png')]"
                ):
                    # logger.warning(f"→ ID {cid} is a soft-404 (404 image found), skipping")
                    continue

                # ✅ Wait for actual content to appear
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div[class^='viewDetail_container']")
                    )
                )

            except TimeoutException:
                # logger.warning(f"→ ID {cid} failed to load detail container, skipping")
                continue

            # ─── SCRAPE FIELDS ────────────────────────────────────────────────
            name = location = ""
            try:
                name = driver.find_element(
                    By.CSS_SELECTOR, "div[class^='viewDetail_headingSection'] p"
                ).text
            except NoSuchElementException:
                pass

            try:
                location = driver.find_element(
                    By.CSS_SELECTOR, "div[class^='viewDetail_subHeading'] p"
                ).text
            except NoSuchElementException:
                pass

            overview = {}
            blocks = driver.find_elements(
                By.CSS_SELECTOR, "div[class^='OverviewDetails_container']"
            )
            for blk in blocks:
                try:
                    key = blk.find_element(By.TAG_NAME, "h5").text
                    vals = [
                        p.text.strip()
                        for p in blk.find_elements(By.TAG_NAME, "p")
                        if p.text.strip()
                    ]
                    if vals:
                        overview[key] = vals[0] if len(vals) == 1 else vals
                except NoSuchElementException:
                    continue

            # ─── APPEND TO FILE ──────────────────────────────────────────────
            counter += 1
            college_data = {
                "counter": counter,
                "id": cid,
                "url": url,
                "name": name,
                "location": location,
                "overview": overview,
            }

            with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(college_data, ensure_ascii=False) + "\n")
            if counter % 50 == 0:
                # logger.info(f"→ [{counter}] Scraped ID {cid}: {name or '[no name]'}")
                logger.info(f"✅ Processed {counter} entries so far.")

    except Exception:
        logger.error("❌ An error occurred:\n" + traceback.format_exc())

    finally:
        driver.quit()
        logger.info(f"✅ Finished scraping. Total records: {counter}")


if __name__ == "__main__":
    main()
