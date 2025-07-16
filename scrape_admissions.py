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
TIMEOUT = 20

# ─── LOGGING ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def safe_click(driver, element):
    """Try element.click(); if intercepted, scroll into view and JS-click."""
    try:
        element.click()
    except ElementClickInterceptedException:
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
    driver.get(entry["url"])
    logger.info(f"→ Visiting {entry['url']} (Admission)")

    # 1) switch to Admission tab
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "[class*='viewDetail_tabContainer']")
        )
    )
    tab3 = driver.find_element(By.CSS_SELECTOR, "#tab-3")
    safe_click(driver, tab3)
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "[class*='Admission_mainDiv']")
        )
    )

    # 2) load all cards
    while True:
        try:
            lm = driver.find_element(By.CSS_SELECTOR, "[class*='Admission_load_more']")
            logger.info("   Clicking “Load More”")
            safe_click(driver, lm)
            time.sleep(1.2)
        except NoSuchElementException:
            break

    result = {
        "id": entry["id"],
        "url": entry["url"],
        "name": entry.get("name"),
        "admissions": [],
    }
    cards = driver.find_elements(By.CSS_SELECTOR, "[class*='ExpandableCard_container']")
    for card in cards:
        title = card.find_element(
            By.CSS_SELECTOR, "[class*='ExpandableCard_titleText']"
        ).text.strip()
        safe_click(
            driver,
            card.find_element(By.CSS_SELECTOR, "[class*='ExpandableCard_titleDiv']"),
        )
        time.sleep(0.3)

        # skip if no admission tabs
        dd = card.find_elements(
            By.CSS_SELECTOR, "[class*='ExpandableCard_dropDownContainer']"
        )
        if not dd:
            logger.warning(f"No Admission tabs for “{title}” — skipping")
            continue
        dropdown = dd[0]

        data = {"title": title, "Eligibility": None, "Exam": None, "Intake": None}

        panels = {
            "eligibility": "[class*='Eligibility_container']",
            "exam": "[class*='ExamCourseTab_mainContainer']",
            "intake": "[class*='Intake_container']",
        }

        tabs = dropdown.find_elements(By.CSS_SELECTOR, "[class*='ChipTabs_tabTitle']")
        for tab in tabs:
            name = tab.text.strip().lower()
            if name not in panels:
                continue

            safe_click(driver, tab)
            panel_sel = panels[name]
            WebDriverWait(driver, TIMEOUT).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, panel_sel))
            )
            cont = dropdown.find_element(By.CSS_SELECTOR, panel_sel)

            if name == "eligibility":
                elig = {}
                # Category
                try:
                    elig["Category"] = cont.find_element(
                        By.CSS_SELECTOR,
                        "[class*='Common_categoryDiv'] [class*='Common_dropDownDiv'] > div",
                    ).text.strip()
                except NoSuchElementException:
                    elig["Category"] = None

                # Aggregate Marks
                agg = {}
                try:
                    blocks = cont.find_elements(
                        By.CSS_SELECTOR,
                        "[class*='Eligibility_aggregate_marks_children'] "
                        "[class*='Common_vertical_inner_container']",
                    )
                    for blk in blocks:
                        key = blk.find_element(
                            By.CSS_SELECTOR,
                            "[class*='Common_vertical_inner_container_heading'] [class*='Common_title']",
                        ).text.strip()
                        # *** FIXED: try both selectors ***
                        try:
                            # first try inner <div>
                            val = blk.find_element(
                                By.CSS_SELECTOR,
                                "[class*='Eligibility_value_class'] > div",
                            ).text.strip()
                        except NoSuchElementException:
                            try:
                                # fallback to container itself
                                val = blk.find_element(
                                    By.CSS_SELECTOR,
                                    "[class*='Eligibility_value_class']",
                                ).text.strip()
                            except NoSuchElementException:
                                val = None
                        agg[key] = val
                except NoSuchElementException:
                    agg = {}
                elig["Aggregate Marks"] = agg

                # Mandatory Subjects
                try:
                    grid = cont.find_element(
                        By.CSS_SELECTOR, "[class*='Common_eligibility_grid_container']"
                    )
                    headers = [
                        h.text.strip()
                        for h in grid.find_elements(
                            By.CSS_SELECTOR,
                            "[class*='Common_eligibility_grid_container_heading']",
                        )
                    ]
                    cells = [
                        c.text.strip()
                        for c in grid.find_elements(
                            By.CSS_SELECTOR,
                            "[class*='Common_eligibility_grid_container_cell']",
                        )
                    ]
                    rows = [
                        cells[i : i + len(headers)]
                        for i in range(0, len(cells), len(headers))
                    ]
                except NoSuchElementException:
                    headers, rows = [], []
                elig["Mandatory Subjects"] = {"headings": headers, "rows": rows}

                data["Eligibility"] = elig

            elif name == "exam":
                exam = {}
                try:
                    exam["Exam Name"] = cont.find_element(
                        By.CSS_SELECTOR, "[class*='ExamCourseTab_name']"
                    ).text.strip()
                    table = {}
                    for sec in cont.find_elements(
                        By.CSS_SELECTOR, "[class*='ExamCourseTab_subjectSubContainer']"
                    ):
                        subj = sec.find_element(
                            By.CSS_SELECTOR, "[class*='ExamCourseTab_subject']"
                        ).text.strip()
                        score = sec.find_element(
                            By.CSS_SELECTOR, "[class*='ExamCourseTab_score']"
                        ).text.strip()
                        table[subj] = score
                    exam["Cut Off Scores"] = table
                except NoSuchElementException:
                    pass
                data["Exam"] = exam

            elif name == "intake":
                intake = {}
                # Summary
                try:
                    summary = {}
                    for pair in cont.find_elements(
                        By.CSS_SELECTOR, "[class*='Intake_first'] > div"
                    ):
                        h = pair.find_element(
                            By.CSS_SELECTOR, "[class*='Intake_headtext']"
                        ).text.strip()
                        s = pair.find_element(
                            By.CSS_SELECTOR, "[class*='Intake_subText']"
                        ).text.strip()
                        summary[h] = s
                except NoSuchElementException:
                    summary = {}
                intake["Summary"] = summary

                # Category
                try:
                    intake["Category"] = cont.find_element(
                        By.CSS_SELECTOR, "[class*='Intake_dropDownDiv'] p"
                    ).text.strip()
                except NoSuchElementException:
                    intake["Category"] = None

                # Quota
                try:
                    intake["Quota"] = cont.find_element(
                        By.CSS_SELECTOR,
                        "[class*='Intake_fourth'] [class*='Intake_subText']",
                    ).text.strip()
                except NoSuchElementException:
                    intake["Quota"] = None

                data["Intake"] = intake

        result["admissions"].append(data)
        logger.info(f"   • Scraped admission for: {title}")

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
        all_results = []
        for e in entries:
            try:
                all_results.append(scrape_admission(driver, e))
            except Exception:
                logger.exception(f"Error scraping admission for ID {e['id']}")
        OUTPUT_FILE.write_text(
            json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"Wrote {len(all_results)} admission records to {OUTPUT_FILE}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
