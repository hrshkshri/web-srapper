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

# ─── NEW: webdriver-manager import ────────────────────────────────────
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
    COLLEGES_URL = "https://assessment.jitinchawla.com/colleges"
    EMAIL = os.environ.get("SCRAPER_EMAIL", "ribhu.chadha@gmail.com")
    PASSWORD = os.environ.get("SCRAPER_PASSWORD", "123456")
    TIMEOUT = 20
    OUTPUT_FILE = "college_overviews.json"

    # ─── START DRIVER ────────────────────────────────────────────────────
    options = Options()
    options.add_argument("--headless")  # run in headless mode
    options.add_argument("--no-sandbox")  # required on many CI systems
    options.add_argument("--disable-dev-shm-usage")  # overcome limited /dev/shm
    options.add_argument("--disable-gpu")  # disable GPU (may help stability)
    options.add_argument("--user-data-dir=/tmp/chrome")  # unique profile dir

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()), options=options
    )

    overviews = []

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
        time.sleep(2)  # allow login to complete
        logger.info("✅ Logged in")

        # ─── 2) NAVIGATE TO COLLEGES LIST ───────────────────────────────────
        logger.info("Navigating to colleges page…")
        driver.get(COLLEGES_URL)
        WebDriverWait(driver, TIMEOUT).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div[class*='CollegeComponent_mainDiv']")
            )
        )

        # ─── 3) REMOVE FILTER IF PRESENT ────────────────────────────────────
        try:
            driver.find_element(
                By.CSS_SELECTOR, "img.FilterValues_closeIcon__2TZTb"
            ).click()
            logger.info("Removed 'After 12th Degree' filter")
            time.sleep(2)
        except NoSuchElementException:
            logger.info("No filter to remove")

        # ─── 4) SCROLL TO LOAD ALL CARDS ────────────────────────────────────
        logger.info("Scrolling to load all college cards…")
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        logger.info("All cards loaded")

        # ─── 5) SCRAPE ALL CARDS ─────────────────────────────────────────────
        cards = driver.find_elements(
            By.CSS_SELECTOR, "div[class*='CollegeComponent_mainDiv']"
        )
        logger.info(f"Found {len(cards)} cards; scraping overviews…")
        main_handle = driver.current_window_handle

        for idx, card in enumerate(cards, start=1):
            logger.info(f" → [{idx}/{len(cards)}] scraping card…")
            driver.execute_script("arguments[0].scrollIntoView(true);", card)
            time.sleep(0.3)

            # open detail in new tab
            try:
                card.find_element(
                    By.CSS_SELECTOR, "div.CollegeComponent_blueButtonDiv__1imVp"
                ).click()
            except NoSuchElementException:
                logger.error("   • View Details button not found, skipping")
                continue

            WebDriverWait(driver, TIMEOUT).until(EC.number_of_windows_to_be(2))
            detail_handle = [h for h in driver.window_handles if h != main_handle][0]
            driver.switch_to.window(detail_handle)

            # wait for detail to load
            try:
                WebDriverWait(driver, TIMEOUT).until(
                    lambda d: d.execute_script("return document.readyState")
                    == "complete"
                )
                WebDriverWait(driver, TIMEOUT).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div[class^='viewDetail_container']")
                    )
                )
            except TimeoutException:
                logger.error("   • Detail page load timed out")
                driver.close()
                driver.switch_to.window(main_handle)
                continue

            # scrape URL, name, location
            url = driver.current_url
            name, location = "", ""
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

            # scrape overview blocks
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

            overviews.append(
                {
                    "url": url,
                    "name": name,
                    "location": location,
                    "overview": overview,
                }
            )
            logger.info(f"   • Scraped '{name}'")

            driver.close()
            driver.switch_to.window(main_handle)

    except Exception:
        logger.error("❌ An error occurred during scraping:\n" + traceback.format_exc())

    finally:
        logger.info(f"Writing {len(overviews)} overviews to {OUTPUT_FILE}")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(overviews, f, indent=2, ensure_ascii=False)
        driver.quit()


if __name__ == "__main__":
    main()
