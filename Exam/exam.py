import json
import logging
import os
import tempfile
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ─── Logging Setup ────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def lazy_load_cards(driver, timeout=10):
    """Scrolls bottom until no new cards appear."""
    WebDriverWait(driver, timeout).until(
        EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "div[class*='ExamComponent_mainDiv']")
        )
    )
    last = 0
    while True:
        cards = driver.find_elements(
            By.CSS_SELECTOR, "div[class*='ExamComponent_mainDiv']"
        )
        count = len(cards)
        logger.info(f"  ▸ {count} cards loaded")
        if count == last:
            break
        last = count
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
    return cards


def main():
    logger.info("▶️ Starting front‑page only scraper")
    BASE_URL = "https://assessment.jitinchawla.com"
    LOGIN_URL = BASE_URL + "/"
    EXAMS_URL = BASE_URL + "/exams"
    OUTPUT = "exam_cards_front.jsonl"
    TIMEOUT = 10

    EMAIL = os.environ.get("SCRAPER_EMAIL", "ribhu.chadha@gmail.com")
    PASSWORD = os.environ.get("SCRAPER_PASSWORD", "123456")

    # ─── Browser Setup ─────────────────────────────────────────────────────
    opts = Options()
    # opts.add_argument("--headless=new")    # uncomment for headless
    opts.add_argument("--start-maximized")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(f"--user-data-dir={tempfile.mkdtemp()}")

    logger.info("🌐 Launching ChromeDriver")
    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()), options=opts
    )

    try:
        # ─── Log in ──────────────────────────────────────────────────────────
        logger.info("🔐 Opening login page")
        driver.get(LOGIN_URL)
        WebDriverWait(driver, TIMEOUT).until(
            EC.presence_of_element_located((By.ID, "emailUid"))
        )
        logger.info("✏️ Entering credentials")
        driver.find_element(By.ID, "emailUid").send_keys(EMAIL)
        driver.find_element(By.ID, "password").send_keys(PASSWORD)
        driver.find_element(By.CLASS_NAME, "SignIn_signUpBtnEnable__3VCty").click()
        time.sleep(2)
        logger.info("✅ Logged in")

        # ─── Load /exams & lazy‑load cards ──────────────────────────────────
        logger.info("📄 Navigating to exams listing")
        driver.get(EXAMS_URL)
        cards = lazy_load_cards(driver, TIMEOUT)
        total = len(cards)
        logger.info(f"✅ Total exam cards: {total}")

        # ─── Scrape each card ───────────────────────────────────────────────
        with open(OUTPUT, "w", encoding="utf-8") as out:
            for idx, card in enumerate(cards, start=1):
                logger.info(f"🔎 Scraping card {idx}/{total}")
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", card
                )
                time.sleep(0.2)

                # — Short Name
                try:
                    name = card.find_element(
                        By.CSS_SELECTOR, "div[class*='ExamComponent_mainText']"
                    ).text.strip()
                except:
                    name = ""
                logger.info(f"  • Short name: {name}")

                # — Full Name (description)
                try:
                    full_name = card.find_element(
                        By.CSS_SELECTOR, "div[class*='ExamComponent_locationText']"
                    ).text.strip()
                except:
                    full_name = ""
                logger.info(f"  • Full name: {full_name}")

                # — Exam Type
                try:
                    exam_type = card.find_element(
                        By.CSS_SELECTOR, "div[class*='ExamComponent_colTypeDiv']"
                    ).text.strip()
                except:
                    exam_type = ""

                # — Total Exams
                try:
                    total_exams = card.find_element(
                        By.CSS_SELECTOR, "div[class*='ExamComponent_noOfExamsDiv'] span"
                    ).text.strip()
                except:
                    total_exams = ""
                logger.info(f"  • Total exams: {total_exams}")

                # — Courses
                courses = [
                    c.text.strip()
                    for c in card.find_elements(
                        By.CSS_SELECTOR, "div[class*='ExamComponent_course']"
                    )
                ]
                logger.info(f"  • Courses: {courses}")

                # — Last Application & Exam Date sections
                last_app_name = last_app_date = last_app_status = ""
                exam_date = ""

                sections = card.find_elements(
                    By.CSS_SELECTOR, "div[class*='ExamComponent_approveDiv__']"
                )
                for sec in sections:
                    try:
                        head = sec.find_element(
                            By.CSS_SELECTOR, "div[class*='ExamComponent_headDiv']"
                        ).text.strip()
                    except:
                        continue

                    if "Last Application Date" in head:
                        try:
                            last_app_name = sec.find_element(
                                By.CSS_SELECTOR, "div[class*='ExamComponent_examName']"
                            ).text.strip()
                        except:
                            last_app_name = ""
                        try:
                            last_app_date = sec.find_element(
                                By.CSS_SELECTOR, "div[class*='ExamComponent_dateDiv']"
                            ).text.strip()
                        except:
                            last_app_date = ""
                        try:
                            last_app_status = sec.find_element(
                                By.CSS_SELECTOR, "div[class*='ExamComponent_statusDiv']"
                            ).text.strip()
                        except:
                            last_app_status = ""

                    elif "Exam Date" in head:
                        try:
                            exam_date = sec.find_element(
                                By.CSS_SELECTOR, "div[class*='ExamComponent_dateDiv']"
                            ).text.strip()
                        except:
                            exam_date = ""

                # — Write JSON line
                record = {
                    "short_name": name,
                    "full_name": full_name,
                    "exam_type": exam_type,
                    "total_exams": total_exams,
                    "courses": courses,
                    "last_application": {
                        "name": last_app_name,
                        "date": last_app_date,
                        "status": last_app_status,
                    },
                    "exam_date": exam_date,
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                logger.info("  ✓ Record written")

        logger.info(f"🏁 Done! Data saved to {OUTPUT}")

    finally:
        driver.quit()
        logger.info("✅ Browser closed")


if __name__ == "__main__":
    main()
