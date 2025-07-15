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

    # ─── LOAD CHECKPOINT ──────────────────────────────────────────────────
    overviews = []
    counter = 0
    START_ID = 1

    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            overviews = data.get("colleges", [])
            counter = data.get("count", 0)
            if overviews:
                START_ID = overviews[-1]["id"] + 1
                logger.info(f"🔁 Resuming from ID {START_ID}")

    END_ID = 10000

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

            # ─── only proceed if the detail container actually loads ────────────
            try:
                WebDriverWait(driver, TIMEOUT).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div[class^='viewDetail_container']")
                    )
                )
            except TimeoutException:
                logger.warning(f"→ ID {cid} failed to load detail container, skipping")
                continue

            # ─── scrape fields now that we know it’s valid ─────────────────────
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

            # ─── count, append, and periodically save ──────────────────────────
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

            # ✅ PERIODIC SAVE EVERY 100 ITEMS
            if counter % 100 == 0:
                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    json.dump(
                        {"count": counter, "colleges": overviews},
                        f,
                        indent=2,
                        ensure_ascii=False,
                    )
                    logger.info(f"💾 Saved checkpoint at {counter} entries")

    except Exception:
        logger.error("❌ An error occurred:\n" + traceback.format_exc())

    finally:
        # ✅ FINAL SAVE
        output = {"count": counter, "colleges": overviews}
        logger.info(f"✅ Writing final {output['count']} overviews to {OUTPUT_FILE}")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        driver.quit()


if __name__ == "__main__":
    main()
