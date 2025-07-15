import re
import time
import json
import logging
import traceback
import os

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
    TIMEOUT = 20
    OUTPUT_FILE = "college_overviews.json"

    # ─── RANGE TO TRY ─────────────────────────────────────────────────────
    START_ID = 20000
    END_ID = 20005

    # ─── START DRIVER ────────────────────────────────────────────────────
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--user-data-dir=/tmp/chrome")

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()), options=options
    )

    overviews = []
    counter = 0

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
            driver.get(url)
            time.sleep(1)

            # skip 404 or React “page not found”
            if driver.title.lower().startswith("404") or driver.find_elements(
                By.CSS_SELECTOR, "div.pageNotFound_container__1Wxjd"
            ):
                logger.warning(f"⚠️ 404 for ID {cid} at {url}")
                continue

            # scrape fields
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

            # overview blocks
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

            # increment our scraped‐items counter
            counter += 1

            overviews.append(
                {
                    "counter": counter,
                    "id": cid,
                    "url": url,
                    "name": name,
                    "location": location,
                    "overview": overview,
                }
            )
            logger.info(f"→ [{counter}] Scraped ID {cid}: {name or '[no name]'}")

    except Exception:
        logger.error("❌ An error occurred:\n" + traceback.format_exc())

    finally:
        # ─── DUMP WITH COUNTER ──────────────────────────────────────────────
        output = {"count": counter, "colleges": overviews}
        logger.info(f"Writing {output['count']} overviews to {OUTPUT_FILE}")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        driver.quit()


if __name__ == "__main__":
    main()
