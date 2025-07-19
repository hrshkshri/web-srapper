#!/usr/bin/env python3
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

from webdriver_manager.chrome import ChromeDriverManager

# ─── CONFIG ─────────────────────────────────────────────────────────────
LOGIN_URL = "https://assessment.jitinchawla.com/"
URL_FILE = Path("url.json")
OUTPUT_FILE = Path("courses.jsonl")  # now JSON-Lines
EMAIL = os.getenv("SCRAPER_EMAIL", "ribhu.chadha@gmail.com")
PASSWORD = os.getenv("SCRAPER_PASSWORD", "123456")
TIMEOUT = 20  # seconds
# ────────────────────────────────────────────────────────────────────────

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

    # Switch to Courses tab
    driver.find_element(By.CSS_SELECTOR, "#tab-2").click()
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div[class*='Course_mainDiv']")
        )
    )

    # Load all courses
    while True:
        try:
            lm = driver.find_element(By.CSS_SELECTOR, "div[class*='Course_load_more']")
            lm.click()
            time.sleep(1.2)
        except:
            break

    courses = []
    cards = driver.find_elements(
        By.CSS_SELECTOR, "div[class*='ExpandableCard_container']"
    )
    for card in cards:
        title = card.find_element(
            By.CSS_SELECTOR, "div[class*='ExpandableCard_titleText']"
        ).text.strip()
        toggle = card.find_element(
            By.CSS_SELECTOR, "div[class*='ExpandableCard_leftDiv']"
        )

        # Wait for toggle to be clickable (fixes blank first course)
        WebDriverWait(driver, TIMEOUT).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "div[class*='ExpandableCard_leftDiv']")
            )
        )

        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", toggle)
        time.sleep(0.2)

        for attempt in range(2):
            try:
                logger.info(f"Attempt {attempt+1}: Clicking toggle for: {title}")
                driver.execute_script("arguments[0].click();", toggle)
                WebDriverWait(card, 5).until(
                    EC.presence_of_element_located(
                        (
                            By.CSS_SELECTOR,
                            "div[class*='ProgramDetails_program_details']",
                        )
                    )
                )
                break
            except Exception as e:
                if attempt == 0:
                    logger.info("🔁 Retrying after short wait...")
                    time.sleep(1.5)
                else:
                    logger.error(f"❌ Failed to open panel for: {title}")

        try:
            WebDriverWait(card, TIMEOUT).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div[class*='ProgramDetails_program_details']")
                )
            )
        except:
            logger.warning(f"Program/fees panel may be missing for course: {title}")

        prog, fees = {}, {}
        try:
            panel = card.find_element(
                By.CSS_SELECTOR, "div[class*='ProgramDetails_program_details']"
            )

            # --- Extract Program Info ---
            for chip in panel.find_elements(
                By.CSS_SELECTOR, "div[class*='Common_data_chip']"
            ):
                try:
                    full_text = chip.text.strip()
                    value = chip.find_element(By.TAG_NAME, "span").text.strip()
                    key = full_text.replace(value, "").strip().rstrip(":").strip()
                    prog[key] = value
                except Exception as e:
                    logger.warning(f"Skipping program chip: {e}")

            # --- Extract Fees Info ---
            for sec in panel.find_elements(
                By.CSS_SELECTOR, "div[class*='Common_vertical_inner_container']"
            ):
                try:
                    head_el = sec.find_element(
                        By.CSS_SELECTOR,
                        "div[class*='Common_vertical_inner_container_heading'] div[class*='Common_title']",
                    )
                    head = head_el.text.strip()

                    if "Fee Total" in head:
                        divs = sec.find_elements(
                            By.CSS_SELECTOR,
                            "div[class*='Common_vertical_inner_container_heading'] > div",
                        )
                        fees["Fee Total"] = (
                            divs[1].text.strip() if len(divs) > 1 else None
                        )
                    else:
                        dropdowns = sec.find_elements(
                            By.CSS_SELECTOR,
                            "div[class*='Common_categoryDiv'] div[class*='Common_dropDownDiv'] > div",
                        )
                        fees[head] = dropdowns[0].text.strip() if dropdowns else None
                except Exception as e:
                    logger.warning(f"Error in fees section: {e}")

        except Exception as e:
            logger.warning(f"Could not find program/fees panel: {e}")

        if not prog:
            logger.info(f"Program info missing for: {title}")
        if not fees:
            logger.info(f"Fees info missing for: {title}")
        logger.info(f"[CHECK] Program keys for '{title}': {list(prog.keys())}")

        # Extract extras
        extras = {}
        for tab_el in card.find_elements(
            By.CSS_SELECTOR, "div[class*='ChipTabs_tabTitle']"
        ):
            tab_name = tab_el.text.strip()
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", tab_el
            )
            try:
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
            except Exception:
                extras[tab_name] = None

        courses.append(
            {"title": title, "program": prog, "fees": fees, "extras": extras}
        )

    logger.info(f"[SUMMARY] Parsed {len(courses)} courses for: {name}")
    return {
        "id": entry["id"],
        "url": detail_url,
        "name": name,
        "location": location,
        "courses": courses,
    }


def main():
    if not URL_FILE.exists():
        logger.error(f"{URL_FILE} not found—run extract_urls.py first.")
        return

    with open(URL_FILE, encoding="utf-8") as f:
        url_list = json.load(f)

    # Prepare (truncate) output file
    OUTPUT_FILE.unlink(missing_ok=True)
    OUTPUT_FILE.touch()

    opts = Options()
    # opts.add_argument("--headless=new")  # uncomment for headless runs
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
        for entry in url_list:
            try:
                item = scrape_one(driver, entry)
                with open(OUTPUT_FILE, "a", encoding="utf-8") as out:
                    json.dump(item, out, ensure_ascii=False)
                    out.write("\n")
                logger.info(f"✅ Saved ID {entry['id']}")
            except Exception:
                logger.exception(f"⚠️ Error on ID {entry['id']}")
    finally:
        driver.quit()
        logger.info("Browser closed")


if __name__ == "__main__":
    main()
