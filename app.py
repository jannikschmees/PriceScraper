from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import io
import time # Added for potential waits
import traceback # Keep for debugging

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException

app = Flask(__name__)
app.secret_key = 'super secret key' # Replace with a real secret key in production

data = [] # In-memory storage for CSV data and results
# Placeholder for credentials - REPLACE WITH ACTUAL CREDENTIALS
PHARMACY_EMAIL = "jannik.schmees@sanvivo.eu" # <<< --- REPLACE THIS
PHARMACY_PASSWORD = "qKBm7t5!Mmup3eh"       # <<< --- REPLACE THIS

@app.route('/', methods=['GET', 'POST'])
def index():
    global data
    if request.method == 'POST':
        # --- Step 1: CSV Upload ---
        if 'csv_file' not in request.files:
            return redirect(request.url)
        file = request.files['csv_file']
        if file.filename == '':
            return redirect(request.url)
        if file and file.filename.endswith('.csv'):
            try:
                # Read CSV directly into pandas DataFrame
                # Use UTF-8-sig to handle potential BOM (Byte Order Mark)
                # Ensure quotechar is set if pandas doesn't detect it automatically
                stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
                # Adjusted read_csv: specified separator and quote character explicitly if needed,
                # but pandas usually auto-detects common formats well. Let's rely on auto-detection first.
                df = pd.read_csv(stream, sep=',', quotechar='"', skipinitialspace=True) # Added sep, quotechar explicitly

                # --- Step 2: Global Margin Input ---
                margin_percent = request.form.get('margin', type=float, default=0.0)
                # margin_decimal = margin_percent / 100.0 # Calculation moved to where it's used

                # Validate required columns - UPDATED column names
                required_cols = ["productName", "EK"]
                missing_cols = [col for col in required_cols if col not in df.columns]
                if missing_cols:
                     # TODO: Add user feedback about missing columns
                    error_msg = f"CSV must contain the following columns: {', '.join(required_cols)}. Missing: {', '.join(missing_cols)}."
                    return render_template('index.html', table_data=data, error=error_msg)


                # Process data
                processed_data = []
                for index, row in df.iterrows():
                    # UPDATED column names for extraction
                    product_name = row['productName']
                    purchase_price_str = row['EK'] # Read as string first

                    # Basic validation
                    if pd.isna(product_name) or pd.isna(purchase_price_str):
                        # Skip rows with missing essential data
                        # TODO: Consider logging or providing feedback about skipped rows
                        continue

                    # Attempt to convert purchase price to float, handle potential formatting issues (e.g., comma as decimal)
                    try:
                        # Replace comma decimal separator with period if necessary
                        purchase_price = float(str(purchase_price_str).replace(',', '.'))
                    except (ValueError, TypeError):
                        # Handle cases where purchase price is not a valid number after potential comma replacement
                        # TODO: Provide specific feedback or log the problematic row/value
                        print(f"Warning: Could not convert purchase price '{purchase_price_str}' to float for product '{product_name}'. Skipping row.")
                        continue

                    processed_data.append({
                        'product_name': product_name,
                        'purchase_price': purchase_price,
                        'margin_percent': margin_percent,
                        # Initialize other fields needed later
                        'prices_found': [], # Store individual prices found during scraping
                        'average_market_price': None,
                        'minimum_market_price': None,
                        'recommended_price': None
                    })
                data = processed_data # Update global data store
                # Clear previous results if new file is uploaded
                for item in data:
                    item['prices_found'] = []
                    item['average_market_price'] = None
                    item['minimum_market_price'] = None
                    item['recommended_price'] = None

                return redirect(url_for('index')) # Redirect to GET to show table
            except Exception as e:
                # TODO: Log the error e
                print(traceback.format_exc()) # Print full traceback for debugging
                return render_template('index.html', table_data=data, error=f"Error processing CSV: {e}")

    # --- Step 3: Initial Table Display (on GET request or after POST redirect) ---
    return render_template('index.html', table_data=data)

# Function to setup WebDriver
def setup_driver():
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless") # Run in background without opening a window
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.85 Safari/537.36") # Set a common user agent
    # Add more options as needed (e.g., proxy settings)
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.implicitly_wait(5) # Implicit wait for elements (adjust as needed)
        return driver
    except Exception as e:
        print(f"Error setting up WebDriver: {e}")
        print(traceback.format_exc())
        return None


@app.route('/scrape', methods=['POST'])
def trigger_scraping():
    global data
    if not data:
        return redirect(url_for('index'))

    print("Scraping process initiated...")
    driver = setup_driver()

    if not driver:
        print("Failed to initialize WebDriver. Scraping aborted.")
        return redirect(url_for('index'))

    partner_links = set()

    try:
        print("Navigating to cannaleo.de...")
        driver.get("https://cannaleo.de")

        # --- Find Partner Links --- 
        references_heading_selector = "h3#referenzen"
        carousel_container_selector = "//h3[@id='referenzen']/ancestor::section[1]"
        link_selector_in_container = "a.MuiLink-root[href]"
        next_button_selector = "button[aria-label='next']"
        wait_time = 15

        try:
            print(f"Waiting for references heading: {references_heading_selector}")
            references_heading = WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, references_heading_selector))
            )
            print("References heading found.")

            # Scroll heading into view
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", references_heading)
            time.sleep(0.5) # Short pause - REDUCED

            # Find the main carousel container
            print(f"Waiting for carousel container: {carousel_container_selector}")
            carousel_container = WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((By.XPATH, carousel_container_selector))
            )
            print("Carousel container found.")

            # Wait for the next button to be present somewhere on the page
            print(f"Waiting for next button presence: {next_button_selector}")
            WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, next_button_selector))
            )
            print("Carousel 'next' button present.")

            max_clicks = 5 # UPDATED: Limit clicks to 5
            clicks = 0

            # --- UPDATED LOOP LOGIC --- 
            while clicks < max_clicks:
                print(f"Processing carousel view (after {clicks} clicks)...")
                # Find all links matching the selector *within the container* at current state
                try:
                    current_links_in_container = carousel_container.find_elements(By.CSS_SELECTOR, link_selector_in_container)
                    print(f"  Found {len(current_links_in_container)} potential link elements in container.")
                    found_new = False
                    for link_element in current_links_in_container:
                        try:
                            href = link_element.get_attribute('href')
                            # Check if href is valid and new
                            if href and href.startswith(("http://", "https://")) and href not in partner_links:
                                print(f"    Found new partner link: {href}")
                                partner_links.add(href)
                                found_new = True
                            # else: 
                                # Optional: print ignored links
                                # print(f"    Ignoring link: {href} (duplicate or invalid schema)")
                        except Exception as link_err:
                            # Handle potential stale element reference if DOM changes during loop
                            print(f"    Error getting href from a link element: {link_err}")
                    if not found_new and len(current_links_in_container) > 0:
                        print("  No *new* links found in this view.")

                except Exception as find_err:
                    print(f"  Error finding links within carousel container: {find_err}")

                # --- Click next button --- 
                # Check if we've already reached max clicks before trying to click again
                if clicks >= max_clicks:
                    print("Reached max clicks limit.")
                    break 

                try:
                    # Wait for the button to be clickable before clicking
                    current_next_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, next_button_selector))
                    )
                    is_disabled_attr = current_next_button.get_attribute("disabled")
                    if not is_disabled_attr:
                        print(f"Clicking 'next' (Attempt {clicks + 1}/{max_clicks})...")
                        driver.execute_script("arguments[0].click();", current_next_button)
                        time.sleep(1.5) # Wait for transition - REDUCED
                        clicks += 1
                    else:
                        print("Next button has 'disabled' attribute. Assuming end of carousel.")
                        break
                except Exception as e:
                    print(f"Next button not clickable or not found. Assuming end of carousel: {e}")
                    break # Exit loop if button fails

            # This warning might be less relevant now with a fixed lower click limit
            # if clicks == max_clicks:
            #     print("Warning: Reached maximum carousel clicks.")

        except Exception as e:
            print(f"Error during partner link scraping process on cannaleo.de: {e}")
            print(traceback.format_exc())

        print(f"\nFound {len(partner_links)} unique partner links: {list(partner_links)}")

        # --- Step 6, 7, 8: Loop through partners, login, search, collect data ---
        all_product_prices = {item['product_name']: [] for item in data}
        # --- DEBUG: Print keys --- 
        print(f"DEBUG: Initialized all_product_prices with keys: {list(all_product_prices.keys())}")
        
        # Define selectors (assuming common structure)
        initial_login_button_xpath = "//button[normalize-space()='Anmelden' and @type='button']"
        email_input_selector = "input[name='email']"
        password_input_selector = "input[name='password']"
        submit_login_button_selector = "button[type='submit']"
        login_confirm_link_selector = "a[href='/product']"
        search_input_selector = "#global-search-desktop"
        price_element_selector = "span.mui-117w3h3"
        first_search_result_link_selector = "a.mui-1obnvjb"

        successful_logins = 0
        failed_logins = 0

        for link in partner_links:
            print(f"\nProcessing partner site: {link}")
            login_successful = False
            try:
                driver.get(link)
                time.sleep(1)

                # --- Optional: Handle Cookies/Consent Banner if necessary --- 
                # try:
                #    consent_button = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.accept-cookies")))
                #    consent_button.click()
                #    time.sleep(0.5)
                # except Exception: 
                #    pass # No banner found or clickable

                # --- Step 1: Click initial "Anmelden" button (if it exists/needed) ---
                try:
                    print("  Looking for initial login button...")
                    initial_login_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, initial_login_button_xpath))
                    )
                    print("  Clicking initial login button...")
                    driver.execute_script("arguments[0].click();", initial_login_button)
                    time.sleep(1)
                except Exception:
                    print("  Initial login button not found or not needed. Proceeding...")
                    pass

                # --- Step 2: Find form fields --- 
                print("  Looking for login form fields...")
                email_field = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, email_input_selector))
                )
                password_field = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, password_input_selector))
                )
                submit_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, submit_login_button_selector))
                )
                print("  Login form fields found.")

                # --- Step 3: Fill and submit --- 
                print(f"  Attempting login with {PHARMACY_EMAIL}...")
                email_field.clear()
                email_field.send_keys(PHARMACY_EMAIL)
                password_field.clear()
                password_field.send_keys(PHARMACY_PASSWORD)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", submit_button)
                print("  Login submitted. Waiting for confirmation...")

                # --- Step 4: Wait for confirmation (navigate to product page) --- 
                confirmation_link = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, login_confirm_link_selector))
                )
                print("  Login confirmation link found.")
                login_successful = True
                successful_logins += 1
                print("  Login appears successful.")

            except Exception as login_err:
                failed_logins += 1
                print(f"  Login failed for {link}. Error: {login_err}")
                # driver.save_screenshot(f"error_login_{link.split('//')[1].split('/')[0]}.png")
                continue # Skip to next site if login fails

            # --- If login successful, proceed to search --- 
            if login_successful:
                print(f"  Starting product search workflow...")
                for product_data in data:
                    product_name = product_data['product_name']
                    print(f"      Searching for: {product_name}")
                    product_found_and_processed = False
                    try:
                        # --- Find and clear search input --- 
                        print("        Looking for search input...")
                        search_input = WebDriverWait(driver, 10).until(
                           EC.element_to_be_clickable((By.CSS_SELECTOR, search_input_selector))
                        )
                        # Clear using JavaScript to avoid element not interactable issues
                        driver.execute_script("arguments[0].value = '';", search_input)
                        time.sleep(0.5)  # Short pause after clearing
                        
                        # --- Type search term --- 
                        search_input.send_keys(product_name)
                        print(f"        Search term '{product_name}' entered.")
                        # Submit search immediately
                        search_input.send_keys(Keys.RETURN)
                        print("        Pressed Enter to submit search.")
                        time.sleep(1)  # Wait for dropdown to appear
                        
                        # First try: Look for exact match in dropdown
                        try:
                            dropdown_item_selector = "li.MuiAutocomplete-option"
                            dropdown_items = WebDriverWait(driver, 5).until(
                                EC.presence_of_all_elements_located((By.CSS_SELECTOR, dropdown_item_selector))
                            )
                            
                            exact_match_found = False
                            for item in dropdown_items:
                                item_text = item.text.strip()
                                print(f"        Checking dropdown item: '{item_text}'")
                                if item_text.lower() == product_name.lower().strip():
                                    print("        Found exact match in dropdown. Clicking...")
                                    driver.execute_script("arguments[0].click();", item)
                                    exact_match_found = True
                                    time.sleep(2)  # Wait for product page to load
                                    break
                            
                            if not exact_match_found:
                                print("        No exact match in dropdown. Proceeding with search...")
                                # Get fresh reference to search input
                                search_input = WebDriverWait(driver, 10).until(
                                    EC.element_to_be_clickable((By.CSS_SELECTOR, search_input_selector))
                                )
                                search_input.send_keys(Keys.RETURN)
                                print("        Pressed Enter to submit search.")
                                time.sleep(2)  # Increased wait for search results
                                
                                # Try to find and click first result
                                try:
                                    print(f"        Looking for first result...")
                                    first_result = WebDriverWait(driver, 12).until(
                                        EC.element_to_be_clickable((By.CSS_SELECTOR, first_search_result_link_selector))
                                    )
                                    result_text = first_result.text.strip()
                                    print(f"        First result text: '{result_text}'")
                                    
                                    # Click the first result regardless of exact match
                                    print("        Clicking first result...")
                                    driver.execute_script("arguments[0].click();", first_result)
                                    time.sleep(2)  # Wait for product page to load
                                    
                                    # --- Price Extraction (Now on Product Page) --- 
                                    print(f"        Extracting prices from product page ({driver.current_url})...")
                                    try:
                                        price_element = WebDriverWait(driver, 10).until(
                                            EC.presence_of_element_located((By.CSS_SELECTOR, price_element_selector))
                                        )
                                        price_text = price_element.text.strip()
                                        print(f"        Found price text: '{price_text}'")
                                        
                                        if '€' in price_text:
                                            price_part = price_text.split('€')[0].strip()
                                            cleaned_price = price_part.replace('.', '').replace(',', '.')
                                            if cleaned_price:
                                                price_float = float(cleaned_price)
                                                if price_float > 0:
                                                    print(f"        Successfully extracted price: {price_float}")
                                                    all_product_prices[product_name].append(price_float)
                                                    product_found_and_processed = True
                                    except Exception as price_err:
                                        print(f"        Error extracting price: {price_err}")
                                
                                except TimeoutException:
                                    print(f"        No search results found for '{product_name}'")
                                    
                            # --- Handle exact match price extraction ---
                            if exact_match_found:
                                print("        Extracting price for exact match...")
                                try:
                                    price_element = WebDriverWait(driver, 10).until(
                                        EC.presence_of_element_located((By.CSS_SELECTOR, price_element_selector))
                                    )
                                    price_text = price_element.text.strip()
                                    print(f"        Found price text: '{price_text}'")
                                    
                                    if '€' in price_text:
                                        price_part = price_text.split('€')[0].strip()
                                        cleaned_price = price_part.replace('.', '').replace(',', '.')
                                        if cleaned_price:
                                            price_float = float(cleaned_price)
                                            if price_float > 0:
                                                print(f"        Successfully extracted price: {price_float}")
                                                all_product_prices[product_name].append(price_float)
                                                product_found_and_processed = True
                                except Exception as price_err:
                                    print(f"        Error extracting price: {price_err}")
                            
                        except Exception as dropdown_err:
                            print(f"        Error handling dropdown: {dropdown_err}")
                            
                        if not product_found_and_processed:
                            print(f"      Product '{product_name}' was not successfully processed on this site.")
                            
                    except Exception as search_err:
                        print(f"      MAJOR ERROR during search workflow for {product_name}: {search_err}")
                        print(traceback.format_exc())
                        continue
                            
        print(f"\nFinished processing sites. Successful logins: {successful_logins}, Failed logins: {failed_logins}")

        # --- Step 8 & 9: Aggregate prices and calculate recommendation ---
        print("\nAggregating results...")
        for item in data:
            product_name = item['product_name']
            collected_prices = all_product_prices.get(product_name, [])
            item['prices_found'] = collected_prices
            if collected_prices:
                item['minimum_market_price'] = min(collected_prices)
                item['average_market_price'] = sum(collected_prices) / len(collected_prices)
                print(f"  Product: {product_name} | Min: {item['minimum_market_price']:.2f}, Avg: {item['average_market_price']:.2f}")
                margin_price = item['purchase_price'] * (1 + item['margin_percent'] / 100.0)
                competitor_price_minus_penny = item['minimum_market_price'] - 0.01
                item['recommended_price'] = max(margin_price, competitor_price_minus_penny)
                print(f"    Margin Price: {margin_price:.2f}, Comp Price (-0.01): {competitor_price_minus_penny:.2f} -> Rec Price: {item['recommended_price']:.2f}")
            else:
                print(f"  Product: {product_name} | No market prices found.")
                item['recommended_price'] = item['purchase_price'] * (1 + item['margin_percent'] / 100.0)
                print(f"    No competitor prices found. Setting recommended price based on margin: {item['recommended_price']:.2f}")
        print("Scraping process finished.")

    except Exception as e:
        print(f"An error occurred during the overall scraping process: {e}")
        print(traceback.format_exc())
    finally:
        if driver:
            print("Closing WebDriver.")
            driver.quit()

    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True) 