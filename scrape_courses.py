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
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from webdriver_manager.chrome import ChromeDriverManager

# ─── CONFIG ─────────────────────────────────────────────────────────────
LOGIN_URL = "https://assessment.jitinchawla.com/"
URL_FILE = Path("url.json")
OUTPUT_FILE = Path("courses.json")
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


def login(driver):
    logger.info("1) Opening login page")
    driver.get(LOGIN_URL)
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located((By.ID, "emailUid"))
    )

    logger.info("2) Filling credentials")
    driver.find_element(By.ID, "emailUid").send_keys(EMAIL)
    driver.find_element(By.ID, "password").send_keys(PASSWORD)
    driver.find_element(By.CLASS_NAME, "SignIn_signUpBtnEnable__3VCty").click()

    logger.info("3) Waiting for dashboard")
    WebDriverWait(driver, TIMEOUT).until(lambda d: "dashboard" in d.current_url.lower())
    logger.info("✅ Logged in")


def scrape_one(driver, entry):
    detail_url = entry["url"]
    logger.info(f"→ Visiting {detail_url}")
    driver.get(detail_url)

    # wait for the overview container (matches viewDetail_container__hash)
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div[class*='viewDetail_container']")
        )
    )

    # grab name + location
    name_el = driver.find_element(
        By.CSS_SELECTOR, "[class*='viewDetail_headingSection'] p"
    )
    loc_el = driver.find_element(By.CSS_SELECTOR, "[class*='viewDetail_subHeading'] p")
    name = name_el.text.strip()
    location = loc_el.text.strip()

    # switch to Courses tab
    driver.find_element(By.CSS_SELECTOR, "#tab-2").click()
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div[class*='Course_mainDiv']")
        )
    )

    # load everything
    while True:
        try:
            lm = driver.find_element(By.CSS_SELECTOR, "div[class*='Course_load_more']")
            logger.info("   Clicking “Load More”")
            lm.click()
            time.sleep(1.2)
        except:
            break

    # collect courses
    courses = []
    cards = driver.find_elements(
        By.CSS_SELECTOR, "div[class*='ExpandableCard_container']"
    )
    for card in cards:
        title = card.find_element(
            By.CSS_SELECTOR, "div[class*='ExpandableCard_titleText']"
        ).text.strip()

        # expand
        toggle = card.find_element(
            By.CSS_SELECTOR, "div[class*='ExpandableCard_titleDiv']"
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", toggle)
        time.sleep(0.2)
        toggle.click()
        time.sleep(0.5)

        # program & fees
        prog, fees = {}, {}
        panels = card.find_elements(
            By.CSS_SELECTOR, "div[class*='ProgramDetails_program_details']"
        )
        if panels:
            panel = panels[0]
            # program chips
            for chip in panel.find_elements(
                By.CSS_SELECTOR, "div[class*='Common_data_chip']"
            ):
                k, v = [t.strip() for t in chip.text.split(":", 1)]
                prog[k] = v
            # fees sections
            for sec in panel.find_elements(
                By.CSS_SELECTOR, "div[class*='Common_vertical_inner_container']"
            ):
                head = sec.find_element(
                    By.CSS_SELECTOR,
                    "div[class*='Common_vertical_inner_container_heading'] div[class*='Common_title']",
                ).text
                if "Fee Total" in head:
                    fees["Fee Total"] = sec.find_element(
                        By.CSS_SELECTOR, "div[class*='ProgramDetails_fees_wrap']"
                    ).text
                else:
                    cat = sec.find_element(
                        By.CSS_SELECTOR,
                        "div[class*='Common_categoryDiv'] div[class*='Common_dropDownDiv'] > div",
                    ).text.strip()
                    fees[head] = cat

        # extras tabs
        extras = {}
        for tab_el in card.find_elements(
            By.CSS_SELECTOR, "div[class*='ChipTabs_tabTitle']"
        ):
            tab_name = tab_el.text.strip()
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", tab_el
            )
            tab_el.click()
            time.sleep(0.4)

            cont = card.find_elements(
                By.CSS_SELECTOR, f"div[class*='{tab_name}_container']"
            )
            texts = []
            if cont:
                texts = [
                    p.text.strip()
                    for p in cont[0].find_elements(By.TAG_NAME, "p")
                    if p.text.strip()
                ]
            extras[tab_name] = texts or None

        courses.append(
            {"title": title, "program": prog, "fees": fees, "extras": extras}
        )
        logger.info(f"   • Scraped course: {title}")

    return {
        "id": entry["id"],
        "url": detail_url,
        "name": name,
        "location": location,
        "courses": courses,
    }


def main():
    # 1) load URL list
    if not URL_FILE.exists():
        logger.error(f"{URL_FILE} not found—run extract_urls.py first.")
        return

    with open(URL_FILE, encoding="utf-8") as f:
        url_list = json.load(f)

    # 2) start driver & login
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

        # 3) iterate all URLs
        results = []
        for idx, entry in enumerate(url_list, start=1):
            try:
                item = scrape_one(driver, entry)
                results.append(item)
            except Exception:
                logger.exception(f"⚠️ Error on ID {entry['id']}")

        # 4) write out
        logger.info(f"Writing {len(results)} records to {OUTPUT_FILE}")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
            json.dump(results, out, indent=2, ensure_ascii=False)

        logger.info("✅ All done")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
