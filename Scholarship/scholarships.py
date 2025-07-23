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
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# ─── Logging Setup ────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def extract_card_info_safe(card_element, driver, base_url):
    """
    Extract information from a single scholarship card with stale element handling.
    Returns a dictionary with card details.
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            card_data = {
                "id": None,
                "name": None,
                "type": None,
                "categories": [],
                "url": None,
                "scraped_at": datetime.now().isoformat(),
            }

            # Check if element is still valid
            try:
                card_element.is_displayed()
            except:
                logger.warning(f"Card element stale on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue
                else:
                    return None

            # Extract all text content at once to minimize DOM queries
            try:
                card_html = card_element.get_attribute("outerHTML")
                card_text = card_element.text
            except:
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue
                else:
                    return None

            # Extract scholarship name
            try:
                name_selectors = [
                    ".ListItem_name__OI6v5 span",
                    "[class*='name'] span",
                    "[class*='title']",
                ]
                for selector in name_selectors:
                    try:
                        name_elem = card_element.find_element(By.CSS_SELECTOR, selector)
                        if name_elem and name_elem.text.strip():
                            card_data["name"] = name_elem.text.strip()
                            break
                    except:
                        continue
            except:
                # Fallback: extract from HTML using text patterns
                if "ListItem_name" in card_html:
                    import re

                    name_match = re.search(r"<span[^>]*>([^<]+)</span>", card_html)
                    if name_match:
                        card_data["name"] = name_match.group(1).strip()

            # Extract type (Scholarship, Fellowship, etc.)
            try:
                type_selectors = [".ListItem_type__2d7Hq span", "[class*='type'] span"]
                for selector in type_selectors:
                    try:
                        type_elem = card_element.find_element(By.CSS_SELECTOR, selector)
                        if type_elem and type_elem.text.strip():
                            type_text = type_elem.text.strip().replace("●", "").strip()
                            card_data["type"] = type_text
                            break
                    except:
                        continue
            except:
                # Fallback: look for type indicators in text
                if "Scholarship" in card_text:
                    card_data["type"] = "Scholarship"
                elif "Fellowship" in card_text:
                    card_data["type"] = "Fellowship"

            # Extract categories/chips (UG, PG, PhD, etc.)
            try:
                chip_selectors = [".ListItem_chip__FW9Kz span", "[class*='chip'] span"]
                for selector in chip_selectors:
                    try:
                        chip_elements = card_element.find_elements(
                            By.CSS_SELECTOR, selector
                        )
                        for chip in chip_elements:
                            if chip and chip.text.strip():
                                card_data["categories"].append(chip.text.strip())
                    except:
                        continue
            except:
                # Fallback: extract common categories from text
                import re

                categories = re.findall(
                    r"\b(UG|PG|PhD|Post Doc|Fellowship Prog|School)\b", card_text
                )
                card_data["categories"] = list(set(categories))

            # Extract URL - simplified approach to avoid navigation issues
            try:
                # Look for direct href first
                href_elements = card_element.find_elements(By.CSS_SELECTOR, "a[href]")
                if href_elements:
                    href = href_elements[0].get_attribute("href")
                    if href:
                        card_data["url"] = (
                            href if href.startswith("http") else base_url + href
                        )

                # If no direct href, construct potential URL from card data
                if not card_data["url"] and card_data["name"]:
                    # Create a potential URL based on name pattern
                    name_slug = (
                        card_data["name"].lower().replace(" ", "-").replace("–", "-")
                    )
                    card_data["url"] = f"{base_url}/scholarship/{name_slug}"

            except Exception as url_error:
                logger.warning(f"URL extraction failed: {url_error}")

            # Generate a fallback ID if none exists
            if not card_data["id"] and card_data["name"]:
                card_data["id"] = (
                    card_data["name"]
                    .lower()
                    .replace(" ", "_")
                    .replace("-", "_")
                    .replace("–", "_")
                )

            # Validate that we got essential data
            if card_data["name"]:
                return card_data
            else:
                logger.warning("No essential data extracted from card")
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue
                else:
                    return None

        except Exception as e:
            logger.warning(f"Extract attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            else:
                logger.error(f"All extraction attempts failed: {e}")
                return None

    return None


def save_to_json(data, filename="scholarships.json"):
    """Save data to JSON file with pretty formatting."""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"📄 Saved {len(data)} scholarships to {filename}")
    except Exception as e:
        logger.error(f"Failed to save JSON: {e}")


def scroll_and_extract_cards_optimized(driver, base_url, timeout=10):
    """
    Optimized scrolling and card extraction with better error handling.
    Updates JSON file incrementally.
    Returns (scroll_count, scholarships_data).
    """
    # Wait for initial batch of cards
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "div[class*='ListItem_wrapper__']")
            )
        )
        logger.info("✅ Initial cards loaded")
    except Exception as e:
        logger.warning(f"Initial card wait failed: {e}")

    scrolls = 0
    last_count = 0
    no_change_count = 0
    max_no_change = 4  # Increased tolerance
    scroll_attempts = 0
    max_scroll_attempts = 3

    # Dictionary to store unique scholarships (using name as key to avoid duplicates)
    scholarships_data = {}
    processed_names = set()  # Track processed scholarship names

    while True:
        # Get fresh card elements on each iteration to avoid stale references
        cards = []
        card_selectors = [
            "div[class*='ListItem_wrapper__']",
            "div[class*='ListItem_wrapper']",
            "div[class*='listitem']",
        ]

        for selector in card_selectors:
            try:
                cards = driver.find_elements(By.CSS_SELECTOR, selector)
                if cards:
                    logger.info(f"Found {len(cards)} cards using selector: {selector}")
                    break
            except Exception as e:
                logger.warning(f"Selector {selector} failed: {e}")
                continue

        if not cards:
            logger.warning("No cards found with any selector")
            break

        count = len(cards)
        logger.info(f"  ▸ {count} scholarship cards found (after {scrolls} scrolls)")

        # Process cards in smaller batches to handle stale elements better
        batch_size = 5
        new_cards_processed = 0

        for batch_start in range(0, count, batch_size):
            batch_end = min(batch_start + batch_size, count)
            logger.info(f"  📋 Processing batch {batch_start+1}-{batch_end} of {count}")

            # Re-fetch cards for this batch to avoid stale references
            try:
                fresh_cards = driver.find_elements(By.CSS_SELECTOR, card_selectors[0])
                batch_cards = fresh_cards[batch_start:batch_end]
            except Exception as e:
                logger.warning(f"Failed to re-fetch cards: {e}")
                continue

            for i, card in enumerate(batch_cards):
                try:
                    actual_index = batch_start + i
                    logger.info(f"    📄 Processing card {actual_index+1}/{count}")

                    # Quick validation check
                    try:
                        card.is_displayed()
                    except:
                        logger.warning(
                            f"    ⚠️ Card {actual_index+1} is stale, skipping"
                        )
                        continue

                    card_info = extract_card_info_safe(card, driver, base_url)

                    if card_info and card_info.get("name"):
                        card_name = card_info["name"]

                        # Check for duplicates
                        if card_name not in processed_names:
                            scholarships_data[card_name] = card_info
                            processed_names.add(card_name)
                            new_cards_processed += 1
                            logger.info(f"    ✅ Added: {card_name}")
                        else:
                            logger.info(f"    🔄 Skipped duplicate: {card_name}")
                    else:
                        logger.warning(
                            f"    ❌ Failed to extract info from card {actual_index+1}"
                        )

                except Exception as e:
                    logger.warning(
                        f"    ❌ Error processing card {actual_index+1}: {e}"
                    )
                    continue

            # Small delay between batches
            time.sleep(0.5)

        # Save updated data to JSON after processing all cards
        if new_cards_processed > 0:
            try:
                save_to_json(list(scholarships_data.values()))
                logger.info(
                    f"  💾 Added {new_cards_processed} new scholarships (total: {len(scholarships_data)})"
                )
            except Exception as e:
                logger.error(f"Failed to save JSON: {e}")

        # Check if no new cards appeared
        if count <= last_count:
            no_change_count += 1
            logger.info(
                f"No new cards or same count ({no_change_count}/{max_no_change})"
            )
            if no_change_count >= max_no_change:
                logger.info("No new content after multiple attempts; stopping.")
                break
        else:
            no_change_count = 0
            scroll_attempts = 0

        last_count = count

        # Perform scroll with multiple strategies
        scroll_success = perform_scroll_strategies(driver)

        if scroll_success:
            scrolls += 1
            scroll_attempts = 0
            logger.info(f"✅ Scroll #{scrolls} successful")
            # Wait for new content to load
            time.sleep(2)
        else:
            scroll_attempts += 1
            logger.warning(
                f"❌ Scroll failed ({scroll_attempts}/{max_scroll_attempts})"
            )
            if scroll_attempts >= max_scroll_attempts:
                logger.info("🛑 Max scroll attempts reached; stopping.")
                break

        if scrolls > 50:  # Reasonable limit
            logger.warning("Reached max scroll limit (50); stopping.")
            break

    logger.info("📊 Scroll and extraction complete")
    logger.info(f"  • Successful scrolls: {scrolls}")
    logger.info(f"  • Total unique scholarships: {len(scholarships_data)}")

    return scrolls, list(scholarships_data.values())


def perform_scroll_strategies(driver):
    """
    Try different scroll strategies and return True if any succeeds.
    """
    strategies = [
        (
            "window.scrollTo bottom",
            lambda: driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            ),
        ),
        (
            "window.scrollBy viewport",
            lambda: driver.execute_script("window.scrollBy(0, window.innerHeight);"),
        ),
        (
            "window.scrollBy half viewport",
            lambda: driver.execute_script("window.scrollBy(0, window.innerHeight/2);"),
        ),
        (
            "PAGE_DOWN key",
            lambda: driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN),
        ),
        ("scroll container", lambda: scroll_containers(driver)),
    ]

    for strategy_name, strategy_func in strategies:
        try:
            logger.info(f"  ⏬ Trying: {strategy_name}")

            # Record position before scroll
            before = driver.execute_script("return window.pageYOffset;")

            # Execute strategy
            strategy_func()
            time.sleep(1)

            # Check if position changed
            after = driver.execute_script("return window.pageYOffset;")

            if after > before:
                logger.info(
                    f"  ✅ {strategy_name} succeeded (moved {after - before}px)"
                )
                return True

        except Exception as e:
            logger.warning(f"  ❌ {strategy_name} failed: {e}")
            continue

    return False


def scroll_containers(driver):
    """Helper function to scroll specific containers."""
    containers = driver.find_elements(
        By.CSS_SELECTOR,
        "div[class*='scroll'], div[class*='list'], div[class*='container'], main, .content",
    )

    for container in containers:
        try:
            before = driver.execute_script("return arguments[0].scrollTop;", container)
            driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollHeight;", container
            )
            after = driver.execute_script("return arguments[0].scrollTop;", container)
            if after > before:
                return True
        except:
            continue
    return False


def wait_for_page_load(driver, timeout=10):
    """Wait until document.readyState == 'complete', plus small buffer."""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(2)
        logger.info("✅ Page fully loaded")
    except Exception as e:
        logger.warning(f"Page load wait failed: {e}")


def main():
    logger.info("▶️ Starting enhanced scholarship scraper with JSON export")

    BASE_URL = "https://assessment.jitinchawla.com"
    LOGIN_URL = BASE_URL + "/"
    SCHOLARSHIPS_URL = BASE_URL + "/scholarships"
    TIMEOUT = 15

    EMAIL = os.environ.get("SCRAPER_EMAIL", "ribhu.chadha@gmail.com")
    PASSWORD = os.environ.get("SCRAPER_PASSWORD", "123456")

    # ─── Browser Setup ─────────────────────────────────────────────────────
    opts = Options()
    # opts.add_argument("--headless=new")  # uncomment for headless
    opts.add_argument("--start-maximized")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-gpu")
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
        wait_for_page_load(driver)

        WebDriverWait(driver, TIMEOUT).until(
            EC.element_to_be_clickable((By.ID, "emailUid"))
        )
        logger.info("✏️ Entering credentials")
        email_field = driver.find_element(By.ID, "emailUid")
        password_field = driver.find_element(By.ID, "password")
        email_field.clear()
        password_field.clear()
        email_field.send_keys(EMAIL)
        time.sleep(0.5)
        password_field.send_keys(PASSWORD)
        time.sleep(0.5)
        login_btn = WebDriverWait(driver, TIMEOUT).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "SignIn_signUpBtnEnable__3VCty"))
        )
        login_btn.click()
        time.sleep(3)
        wait_for_page_load(driver)
        logger.info("✅ Logged in")

        # ─── Navigate to scholarships ─────────────────────────────────────────
        logger.info("🎓 Navigating to scholarships page")
        driver.get(SCHOLARSHIPS_URL)
        wait_for_page_load(driver)
        logger.info(f"Current URL: {driver.current_url}")
        logger.info(f"Page title: {driver.title}")

        # ─── Scholarships scroll and extraction ─────────────────────────────────
        scrolls, scholarships_data = scroll_and_extract_cards_optimized(
            driver, BASE_URL, TIMEOUT
        )

        # Final save with metadata
        final_data = {
            "scrape_info": {
                "timestamp": datetime.now().isoformat(),
                "total_scrolls": scrolls,
                "total_scholarships": len(scholarships_data),
                "source_url": SCHOLARSHIPS_URL,
            },
            "scholarships": scholarships_data,
        }

        # Save final comprehensive data
        save_to_json(final_data, "scholarships_final.json")
        save_to_json(scholarships_data, "scholarships.json")  # Keep simple format too

        logger.info("✅ Finished scraping scholarships")
        logger.info(f"  • Total scrolls: {scrolls}")
        logger.info(f"  • Total scholarships: {len(scholarships_data)}")
        logger.info(f"  • Data saved to scholarships.json and scholarships_final.json")

        # Save screenshots for debugging
        driver.save_screenshot("final_scholarships_page.png")
        logger.info("📸 Saved final_scholarships_page.png")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        driver.save_screenshot("error_scholarships.png")
        logger.info("📸 Saved error_scholarships.png")

    finally:
        driver.quit()
        logger.info("✅ Browser closed")


if __name__ == "__main__":
    main()
