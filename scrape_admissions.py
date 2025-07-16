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
OUTPUT_FILE = Path("admissions.json")
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
    """
    Try a normal .click(); if intercepted, scroll into view and JS-click.
    """
    try:
        element.click()
    except ElementClickInterceptedException:
        logger.debug("Click intercepted, retrying with JS click")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        time.sleep(0.2)
        driver.execute_script("arguments[0].click();", element)


def login(driver):
    logger.info("Opening login page")
    driver.get(LOGIN_URL)
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located((By.ID, "emailUid"))
    )
    driver.find_element(By.ID, "emailUid").send_keys(EMAIL)
    driver.find_element(By.ID, "password").send_keys(PASSWORD)
    driver.find_element(By.CLASS_NAME, "SignIn_signUpBtnEnable__3VCty").click()
    WebDriverWait(driver, TIMEOUT).until(lambda d: "dashboard" in d.current_url.lower())
    logger.info("Logged in successfully")


def scrape_admission(driver, entry):
    detail_url = entry["url"]
    logger.info(f"→ Visiting {detail_url} (Admission)")
    driver.get(detail_url)

    # wait for the tab container
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "[class*='viewDetail_tabContainer']")
        )
    )

    # click the "Admission" tab (#tab-3)
    tab3 = driver.find_element(By.CSS_SELECTOR, "#tab-3")
    safe_click(driver, tab3)
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div[class*='Admission_mainDiv']")
        )
    )

    # load all admission cards
    while True:
        try:
            lm = driver.find_element(
                By.CSS_SELECTOR, "div[class*='Admission_load_more']"
            )
            logger.info("   Clicking “Load More”")
            safe_click(driver, lm)
            time.sleep(1.2)
        except NoSuchElementException:
            break

    # collect admission entries
    admissions = []
    cards = driver.find_elements(
        By.CSS_SELECTOR, "div[class*='ExpandableCard_container']"
    )
    for card in cards:
        title = card.find_element(
            By.CSS_SELECTOR, "div[class*='ExpandableCard_titleText']"
        ).text.strip()

        # expand the card
        toggle = card.find_element(
            By.CSS_SELECTOR, "div[class*='ExpandableCard_titleDiv']"
        )
        safe_click(driver, toggle)
        time.sleep(0.5)

        # skip cards without any Admission tabs
        dropdowns = card.find_elements(
            By.CSS_SELECTOR, "div[class*='ExpandableCard_dropDownContainer']"
        )
        if not dropdowns:
            logger.warning(f"No Admission tabs for “{title}” — skipping")
            continue
        dropdown = dropdowns[0]

        data = {"title": title, "admission": {}}

        # iterate each tab (Eligibility, Exam, Intake)
        tabs = dropdown.find_elements(
            By.CSS_SELECTOR, "div[class*='ChipTabs_tabTitle']"
        )
        for tab in tabs:
            tab_name = tab.text.strip()
            safe_click(driver, tab)
            time.sleep(0.3)

            # ─ Eligibility ───────────────────────────────────────────────
            if tab_name.lower() == "eligibility":
                try:
                    cont = card.find_element(
                        By.CSS_SELECTOR, "div[class*='Eligibility_container']"
                    )
                    elig = {}

                    # Category
                    try:
                        cat = cont.find_element(
                            By.CSS_SELECTOR,
                            "div[class*='Common_categoryDiv'] div[class*='Common_dropDownDiv'] > div",
                        ).text.strip()
                    except NoSuchElementException:
                        cat = None
                    elig["Category"] = cat

                    # Aggregate Marks
                    agg = {}
                    blocks = cont.find_elements(
                        By.CSS_SELECTOR,
                        "div[class*='Eligibility_aggregate_marks_children'] "
                        "div[class*='Common_vertical_inner_container']",
                    )
                    for block in blocks:
                        key = block.find_element(
                            By.CSS_SELECTOR,
                            "div[class*='Common_vertical_inner_container_heading'] "
                            "div[class*='Common_title']",
                        ).text.strip()
                        val = block.find_element(
                            By.CSS_SELECTOR, "div[class*='Eligibility_value_class']"
                        ).text.strip()
                        agg[key] = val
                    elig["Aggregate Marks"] = agg

                    # Mandatory Subjects grid
                    grid = cont.find_element(
                        By.CSS_SELECTOR,
                        "div[class*='Common_eligibility_grid_container']",
                    )
                    headings = [
                        h.text.strip()
                        for h in grid.find_elements(
                            By.CSS_SELECTOR,
                            "div[class*='Common_eligibility_grid_container_heading']",
                        )
                    ]
                    cells = [
                        c.text.strip()
                        for c in grid.find_elements(
                            By.CSS_SELECTOR,
                            "div[class*='Common_eligibility_grid_container_cell']",
                        )
                    ]
                    rows = [
                        cells[i : i + len(headings)]
                        for i in range(0, len(cells), len(headings))
                    ]
                    elig["Mandatory Subjects"] = {"headings": headings, "rows": rows}

                    data["admission"]["Eligibility"] = elig
                except NoSuchElementException:
                    logger.warning(f"No Eligibility section for “{title}”")
                    data["admission"]["Eligibility"] = None

            # ─ Exam ────────────────────────────────────────────────────
            elif tab_name.lower() == "exam":
                try:
                    cont = card.find_element(
                        By.CSS_SELECTOR, "div[class*='ExamCourseTab_mainContainer']"
                    )
                    exam = {
                        "Exam Name": cont.find_element(
                            By.CSS_SELECTOR, "span[class*='ExamCourseTab_name']"
                        ).text.strip()
                    }
                    table = {}
                    secs = cont.find_elements(
                        By.CSS_SELECTOR,
                        "div[class*='ExamCourseTab_subjectSubContainer']",
                    )
                    for sec in secs:
                        subj = sec.find_element(
                            By.CSS_SELECTOR, "p[class*='ExamCourseTab_subject']"
                        ).text.strip()
                        score = sec.find_element(
                            By.CSS_SELECTOR, "p[class*='ExamCourseTab_score']"
                        ).text.strip()
                        table[subj] = score
                    exam["Cut Off Scores"] = table

                    data["admission"]["Exam"] = exam
                except NoSuchElementException:
                    logger.warning(f"No Exam section for “{title}”")
                    data["admission"]["Exam"] = None

            # ─ Intake ──────────────────────────────────────────────────
            elif tab_name.lower() == "intake":
                try:
                    cont = card.find_element(
                        By.CSS_SELECTOR, "div[class*='Intake_container']"
                    )
                    intake = {}

                    # Summary
                    top = {}
                    for pair in cont.find_elements(
                        By.CSS_SELECTOR, "div[class*='Intake_first'] > div"
                    ):
                        head = pair.find_element(
                            By.CSS_SELECTOR, "p[class*='Intake_headtext']"
                        ).text.strip()
                        sub = pair.find_element(
                            By.CSS_SELECTOR, "p[class*='Intake_subText']"
                        ).text.strip()
                        top[head] = sub
                    intake["Summary"] = top

                    # Category
                    try:
                        cat = cont.find_element(
                            By.CSS_SELECTOR, "div[class*='Intake_dropDownDiv'] p"
                        ).text.strip()
                    except NoSuchElementException:
                        cat = None
                    intake["Category"] = cat

                    # Quota
                    try:
                        quota = cont.find_element(
                            By.CSS_SELECTOR,
                            "div[class*='Intake_fourth'] p[class*='Intake_subText']",
                        ).text.strip()
                    except NoSuchElementException:
                        quota = None
                    intake["Quota"] = quota

                    data["admission"]["Intake"] = intake
                except NoSuchElementException:
                    logger.warning(f"No Intake section for “{title}”")
                    data["admission"]["Intake"] = None

            else:
                logger.debug(f"Skipping unknown tab “{tab_name}”")

        admissions.append(data)
        logger.info(f"   • Scraped admission for: {title}")

    return {
        "id": entry["id"],
        "url": detail_url,
        "name": entry.get("name"),
        "admissions": admissions,
    }


def main():
    if not URL_FILE.exists():
        logger.error(f"{URL_FILE} not found—run extract_urls.py first.")
        return

    with open(URL_FILE, encoding="utf-8") as f:
        url_list = json.load(f)

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
        results = []
        for entry in url_list:
            try:
                results.append(scrape_admission(driver, entry))
            except Exception:
                logger.exception(f"Error scraping admission for ID {entry['id']}")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
            json.dump(results, out, indent=2, ensure_ascii=False)
        logger.info(f"Wrote {len(results)} admission records to {OUTPUT_FILE}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
