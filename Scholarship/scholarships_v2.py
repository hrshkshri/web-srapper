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


def parse_table_to_structured_data(table_element):
    """Parse HTML table into structured JSON format"""
    try:
        table_data = {}
        rows = table_element.find_elements(By.TAG_NAME, "tr")

        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 2:
                key = cells[0].text.strip()
                value = cells[1].text.strip()
                if key and value:
                    table_data[key] = value

        return table_data
    except Exception as e:
        logger.warning(f"Error parsing table: {e}")
        return {}


def extract_section_content(section_element, section_name, driver):
    """Extract content from a section, handling tables and text separately"""
    content_data = {"raw_text": "", "structured_data": {}, "tables": [], "lists": []}

    try:
        content_wrapper = section_element.find_element(
            By.CSS_SELECTOR, ".content_careerFeedContentWrap__1td1l"
        )

        # Enhanced Read More button handling
        max_attempts = 5
        expansion_successful = False

        for attempt in range(max_attempts):
            try:
                # Look for Read More button in footer wrap
                read_more = section_element.find_element(
                    By.CSS_SELECTOR,
                    ".content_careerFeedFooterWrap__b4oB8 .content_readMore__3Q5Ud",
                )

                # Check if the content is still truncated (has blur effect)
                blur_element = section_element.find_elements(
                    By.CSS_SELECTOR, ".content_contentBottomBlur__3a0h7"
                )

                if read_more.is_displayed() and read_more.is_enabled() and blur_element:
                    # Scroll to the button first
                    driver.execute_script(
                        "arguments[0].scrollIntoView(true);", read_more
                    )
                    time.sleep(0.5)

                    # Click using JavaScript to avoid any interception issues
                    driver.execute_script("arguments[0].click();", read_more)
                    time.sleep(2)  # Wait for content to expand

                    logger.info(
                        f"✅ Expanded {section_name} section (attempt {attempt + 1})"
                    )
                    expansion_successful = True

                    # Check if there's still more content to expand
                    try:
                        # Re-find the read more button after DOM update
                        updated_read_more = section_element.find_element(
                            By.CSS_SELECTOR,
                            ".content_careerFeedFooterWrap__b4oB8 .content_readMore__3Q5Ud",
                        )
                        if not updated_read_more.is_displayed():
                            break  # No more content to expand
                    except:
                        break  # Button disappeared, content fully expanded

                else:
                    # No read more button or content already expanded
                    break

            except NoSuchElementException:
                # No Read More button found, content might be fully expanded
                logger.info(f"No Read More button found for {section_name}")
                break
            except Exception as e:
                logger.warning(
                    f"Error clicking Read More for {section_name} (attempt {attempt + 1}): {e}"
                )
                time.sleep(1)
                continue

        # Wait additional time for content to fully load after all expansions
        if expansion_successful:
            time.sleep(2)
            # Check if content wrapper height changed
            try:
                content_height = content_wrapper.get_attribute("style")
                logger.info(f"Content wrapper style after expansion: {content_height}")
            except:
                pass

        # Extract raw text after expansion
        content_data["raw_text"] = content_wrapper.text.strip()

        # Extract tables specifically
        tables = content_wrapper.find_elements(By.TAG_NAME, "table")
        for i, table in enumerate(tables):
            structured_table = parse_table_to_structured_data(table)
            if structured_table:
                content_data["tables"].append(
                    {"table_index": i, "data": structured_table}
                )
                logger.info(
                    f"✅ Parsed table {i} in {section_name} with {len(structured_table)} rows"
                )

        # Extract lists (ul, ol)
        lists = content_wrapper.find_elements(By.CSS_SELECTOR, "ul, ol")
        for i, list_element in enumerate(lists):
            list_items = list_element.find_elements(By.TAG_NAME, "li")
            list_data = [item.text.strip() for item in list_items if item.text.strip()]
            if list_data:
                content_data["lists"].append(
                    {"list_index": i, "type": list_element.tag_name, "items": list_data}
                )

        # For specific sections, try to extract more structured data
        if section_name.lower() == "awards":
            content_data["structured_data"] = extract_awards_structured_data(
                content_wrapper
            )
        elif section_name.lower() == "eligibility":
            content_data["structured_data"] = extract_eligibility_structured_data(
                content_wrapper
            )
        elif section_name.lower() == "important dates":
            content_data["structured_data"] = extract_dates_structured_data(
                content_wrapper
            )

    except Exception as e:
        logger.warning(f"Error extracting content from {section_name}: {e}")
        content_data["raw_text"] = ""

    return content_data


def extract_awards_structured_data(content_wrapper):
    """Extract structured award information"""
    awards_data = {"description": "", "amounts": {}, "benefits": []}

    try:
        # Extract main description
        paragraphs = content_wrapper.find_elements(By.TAG_NAME, "p")
        if paragraphs:
            awards_data["description"] = paragraphs[0].text.strip()

        # Extract amount information from tables or structured text
        tables = content_wrapper.find_elements(By.TAG_NAME, "table")
        for table in tables:
            table_data = parse_table_to_structured_data(table)
            awards_data["amounts"].update(table_data)

        # If no table, try to parse from text
        if not awards_data["amounts"]:
            text_content = content_wrapper.text
            # Look for patterns like "Program: Rs. X,XXX per annum"
            import re

            amount_patterns = re.findall(
                r"([^:]+):\s*Rs\.?\s*([\d,]+)\s*per\s*annum",
                text_content,
                re.IGNORECASE,
            )
            for program, amount in amount_patterns:
                awards_data["amounts"][program.strip()] = f"Rs. {amount} per annum"

    except Exception as e:
        logger.warning(f"Error parsing awards structure: {e}")

    return awards_data


def extract_eligibility_structured_data(content_wrapper):
    """Extract structured eligibility information"""
    eligibility_data = {
        "requirements": [],
        "categories": [],
        "academic_criteria": {},
        "institutes": [],
    }

    try:
        # Extract list items
        list_items = content_wrapper.find_elements(By.CSS_SELECTOR, "li")
        for item in list_items:
            text = item.text.strip()
            if text:
                eligibility_data["requirements"].append(text)

        # Extract institute information from tables or text
        tables = content_wrapper.find_elements(By.TAG_NAME, "table")
        for table in tables:
            rows = table.find_elements(By.TAG_NAME, "tr")
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 2:
                    institute_text = cells[1].text.strip()
                    if institute_text:
                        eligibility_data["institutes"].append(institute_text)

        # Extract category information
        text_content = content_wrapper.text.lower()
        categories = ["general", "st", "sc", "obc", "sebc", "ebc", "pwd"]
        for category in categories:
            if category in text_content:
                eligibility_data["categories"].append(category.upper())

        # Extract ranking criteria
        import re

        ranking_match = re.search(
            r"top (\d+) students", content_wrapper.text, re.IGNORECASE
        )
        if ranking_match:
            eligibility_data["academic_criteria"]["top_students"] = ranking_match.group(
                1
            )

    except Exception as e:
        logger.warning(f"Error parsing eligibility structure: {e}")

    return eligibility_data


def extract_dates_structured_data(content_wrapper):
    """Extract structured date information"""
    dates_data = {}

    try:
        # First try to get from table
        table = content_wrapper.find_element(By.TAG_NAME, "table")
        dates_data = parse_table_to_structured_data(table)
    except:
        # If no table, try to extract from text
        try:
            import re

            text_content = content_wrapper.text
            date_patterns = re.findall(r"([^:]+):\s*([^\n]+)", text_content)
            for key, value in date_patterns:
                if any(
                    word in key.lower()
                    for word in ["date", "deadline", "start", "end", "last"]
                ):
                    dates_data[key.strip()] = value.strip()
        except:
            pass

    return dates_data


def extract_detailed_scholarship_info(driver):
    """Extract detailed information from scholarship detail page with structured parsing"""
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

    # Extract information from different sections with structured parsing
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
            # Pass driver to the function for Read More handling
            section_content = extract_section_content(section_element, section, driver)
            section_key = section.lower().replace(" ", "_")
            details[section_key] = section_content

            # Log what we extracted
            if section_content["raw_text"]:
                logger.info(
                    f"✅ Extracted {section}: {len(section_content['raw_text'])} chars, "
                    f"{len(section_content['tables'])} tables, {len(section_content['lists'])} lists"
                )
            else:
                logger.warning(f"⚠️ No content found for {section}")

        except Exception as e:
            logger.warning(f"Could not extract {section}: {e}")
            section_key = section.lower().replace(" ", "_")
            details[section_key] = {
                "raw_text": "",
                "structured_data": {},
                "tables": [],
                "lists": [],
            }

    # Extract comprehensive important dates information
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

        # If we already have important_dates section, add this structured data to it
        if "important_dates" in details:
            details["important_dates"]["main_dates_table"] = dates_info
        else:
            details["important_dates_table"] = dates_info

        logger.info(f"✅ Extracted main dates table: {dates_info}")
    except:
        logger.warning("Could not extract main dates table")

    # Extract any additional comprehensive information
    try:
        # Look for any other tables on the page that might contain useful info
        all_tables = driver.find_elements(By.TAG_NAME, "table")
        additional_tables = []

        for i, table in enumerate(all_tables):
            try:
                # Skip if it's the main dates table we already processed
                if "table_table__voGg2" in table.get_attribute("class"):
                    continue

                table_data = parse_table_to_structured_data(table)
                if table_data:
                    additional_tables.append(
                        {"table_index": i, "data": table_data, "location": "page_level"}
                    )
            except:
                continue

        if additional_tables:
            details["additional_tables"] = additional_tables
            logger.info(f"✅ Found {len(additional_tables)} additional tables")

    except Exception as e:
        logger.warning(f"Error extracting additional tables: {e}")

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
