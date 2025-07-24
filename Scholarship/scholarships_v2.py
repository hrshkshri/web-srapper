import logging
import os
import tempfile
import time
import json
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException,
)
from webdriver_manager.chrome import ChromeDriverManager

# ─── Logging Setup ────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def save_to_json(data, filename="scholarship_details.json"):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"📄 Saved {len(data)} records to {filename}")
    except Exception as e:
        logger.error(f"Failed to save JSON: {e}")


def wait_for_page_load(driver, timeout=10):
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(2)
        logger.info("✅ Page fully loaded")
    except Exception as e:
        logger.warning(f"Page load wait failed: {e}")


def extract_detailed_scholarship_info(driver):
    """Extract detailed information from scholarship detail page based on the provided DOM"""
    details = {}

    try:
        # Extract title from the main image component
        title_element = driver.find_element(
            By.CSS_SELECTOR,
            ".content_MainImageCareerComponentHeadingWrapper__2UBDj span",
        )
        details["title"] = title_element.text.strip()
    except:
        try:
            title_element = driver.find_element(By.TAG_NAME, "h1")
            details["title"] = title_element.text.strip()
        except:
            details["title"] = ""
            logger.warning("Could not extract title")

    # Extract information from different sections
    sections = [
        "General Information",
        "Awards",
        "Eligibility",
        "Application Fees",
        "Application Procedure",
        "Selection Process",
        "Other Information",
        "Important Dates",
    ]

    for section in sections:
        try:
            section_element = driver.find_element(By.ID, section)
            content_wrapper = section_element.find_element(
                By.CSS_SELECTOR, ".content_careerFeedContentWrap__1td1l"
            )

            # Check if there's a "Read More" button and click it to expand content
            try:
                read_more = section_element.find_element(
                    By.CSS_SELECTOR, ".content_readMore__3Q5Ud"
                )
                if read_more.is_displayed():
                    driver.execute_script("arguments[0].click();", read_more)
                    time.sleep(1)
                    logger.info(f"Expanded {section} section")
            except:
                pass

            # Extract text content after potential expansion
            section_text = content_wrapper.text.strip()
            section_key = section.lower().replace(" ", "_")
            details[section_key] = section_text

            if section_text:
                logger.info(f"✅ Extracted {section}: {len(section_text)} characters")
            else:
                logger.warning(f"⚠️ No content found for {section}")

        except Exception as e:
            logger.warning(f"Could not extract {section}: {e}")
            section_key = section.lower().replace(" ", "_")
            details[section_key] = ""

    # Extract important dates table if present
    try:
        dates_table = driver.find_element(By.CSS_SELECTOR, ".table_table__voGg2")
        rows = dates_table.find_elements(By.CSS_SELECTOR, ".table_row__9zJE-")
        dates_info = {}

        for row in rows:
            cells = row.find_elements(By.CSS_SELECTOR, ".table_data__2vt7b")
            if len(cells) >= 2:
                key = cells[0].text.strip().replace(":", "")
                value = cells[1].text.strip()
                dates_info[key] = value

        details["important_dates_structured"] = dates_info
        logger.info(f"✅ Extracted structured dates: {dates_info}")
    except:
        details["important_dates_structured"] = {}
        logger.warning("Could not extract structured dates table")

    # Try to extract any additional metadata
    try:
        # Extract any visible deadlines or key dates from the page
        deadline_selectors = [
            "//td[contains(text(),'Last date to apply')]/following-sibling::td",
            "//td[contains(text(),'deadline') or contains(text(),'Deadline')]/following-sibling::td",
            "//*[contains(text(),'Last Date') or contains(text(),'Deadline')]",
        ]

        for selector in deadline_selectors:
            try:
                deadline_element = driver.find_element(By.XPATH, selector)
                details["deadline_extracted"] = deadline_element.text.strip()
                break
            except:
                continue
    except:
        details["deadline_extracted"] = ""

    # Extract any award/benefit information more specifically
    try:
        # Look for tables with benefit information
        benefit_tables = driver.find_elements(By.CSS_SELECTOR, "table")
        for table in benefit_tables:
            table_text = table.text.strip()
            if any(
                keyword in table_text.lower()
                for keyword in ["benefit", "award", "amount", "₹", "rs"]
            ):
                details["benefits_table"] = table_text
                logger.info("✅ Extracted benefits table")
                break
    except:
        details["benefits_table"] = ""

    return details


def scrape_scholarship_details(driver, timeout=10):
    """
    Load scholarship URLs from unique_scholarships.json and scrape each detail page.
    """
    INPUT_FILE = "unique_scholarships.json"
    OUTPUT_FILE = "scholarship_details.json"

    try:
        # Load the list of scholarship URLs
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)
        logger.info(f"📂 Loaded {len(entries)} scholarship URLs from {INPUT_FILE}")
    except FileNotFoundError:
        logger.error(f"❌ Input file {INPUT_FILE} not found!")
        logger.error(
            "Make sure you have the unique_scholarships.json file with scholarship URLs"
        )
        return []
    except Exception as e:
        logger.error(f"❌ Error loading input file: {e}")
        return []

    details = []
    successful_scrapes = 0
    failed_scrapes = 0

    for idx, entry in enumerate(entries, start=1):
        cid = entry.get("id", "")
        url = entry.get("url", "")
        entry_title = entry.get("title", "Unknown")

        if not url:
            logger.warning(f"⚠️ No URL found for entry {idx}")
            continue

        logger.info(f"🔍 ({idx}/{len(entries)}) Scraping: {entry_title[:50]}...")
        logger.info(f"🌐 URL: {url}")

        try:
            # Navigate to the scholarship detail page
            driver.get(url)
            wait_for_page_load(driver, timeout)
            time.sleep(2)  # Additional wait for dynamic content

            # Extract detailed information using the DOM-specific function
            detail_info = extract_detailed_scholarship_info(driver)

            # Add metadata
            detail_info.update(
                {
                    "scholarship_id": cid,
                    "url": url,
                    "original_title": entry_title,
                    "scrape_index": idx,
                    "scraped_at": datetime.now().isoformat(),
                    "scrape_status": "success",
                }
            )

            details.append(detail_info)
            successful_scrapes += 1

            # Log what we extracted
            extracted_title = detail_info.get("title", "No title")
            logger.info(f"✅ Successfully scraped: {extracted_title[:50]}...")

            # Save progress periodically (every 10 scholarships)
            if idx % 10 == 0:
                save_to_json(details, f"scholarship_details_progress_{idx}.json")
                logger.info(f"💾 Progress saved at {idx} scholarships")

        except Exception as e:
            logger.error(f"❌ Error scraping {url}: {e}")
            failed_scrapes += 1

            # Add error entry to keep track
            details.append(
                {
                    "scholarship_id": cid,
                    "url": url,
                    "original_title": entry_title,
                    "scrape_index": idx,
                    "error": str(e),
                    "scraped_at": datetime.now().isoformat(),
                    "scrape_status": "failed",
                }
            )

            # Take screenshot for debugging
            try:
                driver.save_screenshot(f"error_scholarship_{idx}_{cid}.png")
                logger.info(f"📸 Error screenshot saved for scholarship {idx}")
            except:
                pass

        # Small delay between requests to be respectful
        time.sleep(1)

    # Save final results
    save_to_json(details, OUTPUT_FILE)

    # Log summary
    logger.info("=" * 60)
    logger.info("📊 SCRAPING SUMMARY")
    logger.info("=" * 60)
    logger.info(f"✅ Successfully scraped: {successful_scrapes}")
    logger.info(f"❌ Failed scrapes: {failed_scrapes}")
    logger.info(f"📄 Total entries processed: {len(details)}")
    logger.info(f"💾 Results saved to: {OUTPUT_FILE}")
    logger.info("=" * 60)

    return details


def main():
    logger.info("▶️ Starting scholarship detail scraper")
    logger.info(
        "📝 This script reads URLs from unique_scholarships.json and scrapes each scholarship page"
    )

    BASE_URL = "https://assessment.jitinchawla.com"
    LOGIN_URL = BASE_URL + "/"
    TIMEOUT = 15

    EMAIL = os.environ.get("SCRAPER_EMAIL", "ribhu.chadha@gmail.com")
    PASSWORD = os.environ.get("SCRAPER_PASSWORD", "123456")

    # Browser Setup
    opts = Options()
    # opts.add_argument("--headless=new")  # uncomment for headless
    opts.add_argument("--start-maximized")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(f"--user-data-dir={tempfile.mkdtemp()}")

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()), options=opts
    )

    try:
        # ─── Log in ──────────────────────────────────────────────────────────
        logger.info("🔐 Logging into the website...")
        driver.get(LOGIN_URL)
        wait_for_page_load(driver)

        # Wait for login fields and perform login
        WebDriverWait(driver, TIMEOUT).until(
            EC.element_to_be_clickable((By.ID, "emailUid"))
        )

        email_field = driver.find_element(By.ID, "emailUid")
        password_field = driver.find_element(By.ID, "password")

        email_field.clear()
        password_field.clear()
        email_field.send_keys(EMAIL)
        time.sleep(0.5)
        password_field.send_keys(PASSWORD)
        time.sleep(0.5)

        login_btn = driver.find_element(By.CLASS_NAME, "SignIn_signUpBtnEnable__3VCty")
        login_btn.click()
        time.sleep(3)
        wait_for_page_load(driver)
        logger.info("✅ Successfully logged in")

        # ─── Start detailed scraping ──────────────────────────────────────────
        logger.info("🎓 Starting scholarship detail scraping...")

        # Check if input file exists
        if not os.path.exists("unique_scholarships.json"):
            logger.error("❌ unique_scholarships.json file not found!")
            logger.error("Please make sure you have this file with scholarship URLs")
            return

        # Scrape all scholarship details
        details = scrape_scholarship_details(driver, TIMEOUT)

        # Save a final screenshot
        driver.save_screenshot("final_scholarship_scraping.png")
        logger.info("📸 Final screenshot saved")

        logger.info("🎉 Scholarship scraping completed successfully!")

    except Exception as e:
        logger.error(f"❌ An error occurred: {e}")
        driver.save_screenshot("error_main.png")
        logger.info("📸 Error screenshot saved")

    finally:
        driver.quit()
        logger.info("✅ Browser closed")


if __name__ == "__main__":
    main()
