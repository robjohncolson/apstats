# ------------------------------------------------------------
#  PERSONAL AREA – EDIT ONLY THESE THREE LINES
# ------------------------------------------------------------
BASE_URL       = 'https://app.schoology.com'   # <-- main domain for API/OAuth
CONSUMER_KEY   = '8efc66fd6fd8668d21dce0e5e3047e220690a1f22'           # <-- fresh from https://app.schoology.com/api
CONSUMER_SECRET = '9da622ccc709ba65e9e685ff9bc82746'       # <-- fresh from https://app.schoology.com/api
HEADLESS       = False                         # <-- Set to True once debugging is done
# ------------------------------------------------------------

import requests
from requests_oauthlib import OAuth1Session
import getpass  # For secure password input
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import logging

# Set up Selenium logging
logging.basicConfig(level=logging.INFO)

# ------------------------------------------------------------------
# Helper: print raw response when something goes wrong (debug)
# ------------------------------------------------------------------
def debug_response(resp):
    print("\n--- DEBUG RESPONSE ---")
    print(f"Status: {resp.status_code}")
    print("Headers:")
    for k, v in resp.headers.items():
        print(f"  {k}: {v}")
    print("Body:")
    print(resp.text[:1000])   # first 1000 chars – enough to see HTML/JSON
    print("--- END DEBUG ---\n")

# Set up Chrome with options
options = Options()
if HEADLESS:
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
options.add_argument("--log-level=0")  # Verbose logging
driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

# ------------------------------------------------------------------
# Automate full Schoology login via SSO (to get session cookies)
# ------------------------------------------------------------------
print("\nAutomating Schoology login via SSO...")
try:
    driver.get(f"{BASE_URL}/login")
    
    wait = WebDriverWait(driver, 30)
    
    # Check if already logged in (redirected to dashboard)
    time.sleep(2)  # Brief wait for redirect
    if "/home" in driver.current_url:
        print("Already logged in (redirected to dashboard). Skipping SSO steps.")
        print("Current URL: " + driver.current_url)
    else:
        print("Login page detected. Please log in manually in the browser window (select school if needed, then SSO), then press Enter here.")
        input("Press Enter after logging in...")
        # Wait for dashboard
        try:
            wait.until(EC.url_contains("/home"))
            print("Login successful. Current URL: " + driver.current_url)
        except TimeoutException as e:
            print(f"Timeout waiting for dashboard URL. Current URL: {driver.current_url}")
            print("Page source for debug:")
            print(driver.page_source[:2000])
            raise e
except Exception as e:
    print(f"Login automation failed: {e}")
    driver.quit()
    exit(1)

# Extract cookies from Selenium and create requests session
requests_session = requests.Session()
for cookie in driver.get_cookies():
    requests_session.cookies.set(cookie['name'], cookie['value'])

# ------------------------------------------------------------------
# 1. Get a request token (using logged-in session cookies)
# ------------------------------------------------------------------
oauth = OAuth1Session(CONSUMER_KEY, client_secret=CONSUMER_SECRET)
oauth.cookies.update(requests_session.cookies)

request_token_url = f'{BASE_URL}/oauth/request_token'
try:
    resp = oauth.fetch_request_token(request_token_url, timeout=15)
except Exception as e:
    print(f"Error fetching request token: {e}")
    raw = requests_session.post(request_token_url, timeout=15, allow_redirects=False)
    debug_response(raw)
    driver.quit()
    exit(1)

resource_owner_key = resp.get('oauth_token')
resource_owner_secret = resp.get('oauth_token_secret')
print("Request token obtained.")

# ------------------------------------------------------------------
# 2. Automate app authorization (using same logged-in driver)
# ------------------------------------------------------------------
base_authorization_url = f'{BASE_URL}/oauth/authorize'
authorization_url = oauth.authorization_url(base_authorization_url, callback_uri='oob')  # oob for verifier display
print(f"\nAutomating app authorization at: {authorization_url}")

try:
    driver.get(authorization_url)
    
    # If SSO triggers again, prompt manual
    if "login.microsoftonline.com" in driver.current_url or "auth" in driver.current_url:
        print("Additional authentication required. Please complete it in the browser, then press Enter here.")
        input("Press Enter after authenticating...")
    
    # Reset to default content
    driver.switch_to.default_content()
    
    # Click Allow
    allow_button = wait.until(EC.element_to_be_clickable((By.NAME, "oauth_authorize_submit")))
    driver.execute_script("arguments[0].click();", allow_button)
    
    # Wait for verifier page and extract code
    verifier_element = wait.until(EC.presence_of_element_located((By.TAG_NAME, "pre")))
    verifier = verifier_element.text.strip()
    print(f"Verifier extracted: {verifier}")
except Exception as e:
    print(f"Authorization automation failed: {e}. Current URL: {driver.current_url}")
    print("Page source for debug: " + driver.page_source[:2000])
    driver.quit()
    exit(1)

# ------------------------------------------------------------------
# 3. Exchange for access token using verifier
# ------------------------------------------------------------------
access_token_url = f'{BASE_URL}/oauth/access_token'
try:
    oauth_tokens = oauth.fetch_access_token(access_token_url, verifier=verifier, timeout=15)
except Exception as e:
    print(f"Error fetching access token: {e}")
    raw = requests_session.post(access_token_url, timeout=15, allow_redirects=False)
    debug_response(raw)
    driver.quit()
    exit(1)

access_key = oauth_tokens['oauth_token']
access_secret = oauth_tokens['oauth_token_secret']
print("Access token obtained.")

driver.quit()  # Close browser

# ------------------------------------------------------------------
# 4. New session with the access token
# ------------------------------------------------------------------
client = OAuth1Session(
    CONSUMER_KEY,
    client_secret=CONSUMER_SECRET,
    resource_owner_key=access_key,
    resource_owner_secret=access_secret
)
client.cookies.update(requests_session.cookies)

# ------------------------------------------------------------------
# 5. Get your user ID
# ------------------------------------------------------------------
try:
    r = client.get(f'{BASE_URL}/v1/users/me', timeout=15)
    r.raise_for_status()
    user = r.json()
    user_id = user['uid']
    print(f"Your user ID: {user_id}")
except requests.exceptions.RequestException as e:
    print(f"Error getting user info: {e}")
    exit(1)

# ------------------------------------------------------------------
# 6. List your sections (courses)
# ------------------------------------------------------------------
try:
    r = client.get(f'{BASE_URL}/v1/users/{user_id}/sections', timeout=15)
    r.raise_for_status()
    sections_data = r.json()
    sections = sections_data.get('section', [])
    if not sections:
        print("No sections found. Are you enrolled/teaching any?")
        exit(1)
    print("\nYour sections:")
    for sec in sections:
        print(f"- {sec['course_title']} (Section ID: {sec['id']}, Code: {sec['section_title']})")
except requests.exceptions.RequestException as e:
    print(f"Error listing sections: {e}")
    exit(1)

# ------------------------------------------------------------------
# 7. Create a folder in the first section (change index if needed)
# ------------------------------------------------------------------
section_id = sections[0]['id']  # Use the first section; replace with a specific ID if desired
folder_data = {
    "title": "API Test Folder",
    "description": "This folder was created via a Python script using the Schoology API."
    # Optional: "files_allowed": 1, "allow_comments": 1, etc.
}

try:
    r = client.post(
        f'{BASE_URL}/v1/sections/{section_id}/folders',
        json=folder_data
    )
    r.raise_for_status()
    print(f"\nFolder created successfully in section {section_id}! Response: {r.json()}")
except requests.exceptions.RequestException as e:
    print(f"Error creating folder: {e}")