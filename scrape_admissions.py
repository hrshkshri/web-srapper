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
    Try element.click(); if it's intercepted, scroll into view and JS-click.
    """
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
    detail_url = entry["url"]
    logger.info(f"→ Visiting {detail_url} (Admission)")
    driver.get(detail_url)

    # 1) Click the Admission tab
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "[class*='viewDetail_tabContainer']")
        )
    )
    tab3 = driver.find_element(By.CSS_SELECTOR, "#tab-3")
    safe_click(driver, tab3)
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div[class*='Admission_mainDiv']")
        )
    )

    # 2) Load more
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

    # 3) Scrape each card
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

        # find the dropdown container
        dropdowns = card.find_elements(
            By.CSS_SELECTOR, "div[class*='ExpandableCard_dropDownContainer']"
        )
        if not dropdowns:
            logger.warning(f"No Admission tabs for “{title}” — skipping")
            continue
        dropdown = dropdowns[0]

        data = {"title": title, "admission": {}}

        # map tab-names → the CSS-selector for that panel
        tab_to_panel = {
            "eligibility": "div[class*='Eligibility_container']",
            "exam": "div[class*='ExamCourseTab_mainContainer']",
            "intake": "div[class*='Intake_container']",
        }

        tabs = dropdown.find_elements(
            By.CSS_SELECTOR, "div[class*='ChipTabs_tabTitle']"
        )
        for tab in tabs:
            name = tab.text.strip().lower()
            if name not in tab_to_panel:
                continue

            # click + wait for panel
            safe_click(driver, tab)
            panel_sel = tab_to_panel[name]
            WebDriverWait(driver, TIMEOUT).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, panel_sel))
            )
            cont = dropdown.find_element(By.CSS_SELECTOR, panel_sel)

            # ─ Eligibility ─────────────────────────────────────────
            if name == "eligibility":
                elig = {}
                # Category
                try:
                    elig["Category"] = cont.find_element(
                        By.CSS_SELECTOR,
                        "div[class*='Common_categoryDiv'] div[class*='Common_dropDownDiv'] > div",
                    ).text.strip()
                except NoSuchElementException:
                    elig["Category"] = None

                # Aggregate Marks
                agg = {}
                for blk in cont.find_elements(
                    By.CSS_SELECTOR,
                    "div[class*='Eligibility_aggregate_marks_children'] "
                    "div[class*='Common_vertical_inner_container']",
                ):
                    k = blk.find_element(
                        By.CSS_SELECTOR,
                        "div[class*='Common_vertical_inner_container_heading'] div[class*='Common_title']",
                    ).text.strip()
                    v = blk.find_element(
                        By.CSS_SELECTOR, "div[class*='Eligibility_value_class']"
                    ).text.strip()
                    agg[k] = v
                elig["Aggregate Marks"] = agg

                # Mandatory Subjects
                grid = cont.find_element(
                    By.CSS_SELECTOR, "div[class*='Common_eligibility_grid_container']"
                )
                heads = [
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
                    cells[i : i + len(heads)] for i in range(0, len(cells), len(heads))
                ]
                elig["Mandatory Subjects"] = {"headings": heads, "rows": rows}

                data["admission"]["Eligibility"] = elig

            # ─ Exam ────────────────────────────────────────────────
            elif name == "exam":
                exam = {}
                exam["Exam Name"] = cont.find_element(
                    By.CSS_SELECTOR, "span[class*='ExamCourseTab_name']"
                ).text.strip()
                table = {}
                for sec in cont.find_elements(
                    By.CSS_SELECTOR, "div[class*='ExamCourseTab_subjectSubContainer']"
                ):
                    subj = sec.find_element(
                        By.CSS_SELECTOR, "p[class*='ExamCourseTab_subject']"
                    ).text.strip()
                    score = sec.find_element(
                        By.CSS_SELECTOR, "p[class*='ExamCourseTab_score']"
                    ).text.strip()
                    table[subj] = score
                exam["Cut Off Scores"] = table

                data["admission"]["Exam"] = exam

            # ─ Intake ──────────────────────────────────────────────
            elif name == "intake":
                intake = {}
                # Summary
                summary = {}
                for pair in cont.find_elements(
                    By.CSS_SELECTOR, "div[class*='Intake_first'] > div"
                ):
                    h = pair.find_element(
                        By.CSS_SELECTOR, "p[class*='Intake_headtext']"
                    ).text.strip()
                    s = pair.find_element(
                        By.CSS_SELECTOR, "p[class*='Intake_subText']"
                    ).text.strip()
                    summary[h] = s
                intake["Summary"] = summary

                # Category
                try:
                    intake["Category"] = cont.find_element(
                        By.CSS_SELECTOR, "div[class*='Intake_dropDownDiv'] p"
                    ).text.strip()
                except NoSuchElementException:
                    intake["Category"] = None

                # Quota
                try:
                    intake["Quota"] = cont.find_element(
                        By.CSS_SELECTOR,
                        "div[class*='Intake_fourth'] p[class*='Intake_subText']",
                    ).text.strip()
                except NoSuchElementException:
                    intake["Quota"] = None

                data["admission"]["Intake"] = intake

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

    url_list = json.loads(URL_FILE.read_text(encoding="utf-8"))

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
        OUTPUT_FILE.write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"Wrote {len(results)} admission records to {OUTPUT_FILE}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
