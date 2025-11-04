# ------------------------------------------------------------
#  PERSONAL AREA – EDIT ONLY THESE THREE LINES
# ------------------------------------------------------------
BASE_URL       = 'https://lynnschools.schoology.com'   # <-- your custom domain
CONSUMER_KEY   = '8efc66fd6fd8668d21dce0e5e3047e220690a1f22'                   # <-- fresh from Schoology API page
CONSUMER_SECRET = '9da622ccc709ba65e9e685ff9bc82746'               # <-- fresh from Schoology API page
HEADLESS       = False                                 # <-- Set to True once debugging is done
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

# Prompt for credentials securely (only if needed)
def get_credentials():
    print("Enter your Microsoft SSO credentials for Schoology:")
    username = input("Username (email): ")
    password = getpass.getpass("Password: ")
    return username, password

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
        print("Login page detected. Please log in manually in the browser window, then press Enter here.")
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
# 1. Get a request token (using logged-in session)
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
    
    # If SSO triggers again, prompt user to complete it
    if "login.microsoftonline.com" in driver.current_url or "auth" in driver.current_url:
        print("Additional authentication required. Please complete it in the browser, then press Enter here.")
        input("Press Enter after authenticating...")
    
    # Reset to default content if iframe was switched earlier
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
    user_id = r.json()['uid']
    print(f"\nYour Schoology user ID: {user_id}")
except requests.exceptions.RequestException as e:
    print(f"Failed to get user info: {e}")
    debug_response(r)
    exit(1)

# ------------------------------------------------------------------
# 6. List your sections (courses)
# ------------------------------------------------------------------
try:
    r = client.get(f'{BASE_URL}/v1/users/{user_id}/sections', timeout=15)
    r.raise_for_status()
    sections = r.json().get('section', [])
    if not sections:
        print("No sections found – are you teaching any courses?")
        exit(1)

    print("\nYour teaching sections:")
    for s in sections:
        print(f" • {s['course_title']} – Section ID: {s['id']} – Title: {s['section_title']}")
except requests.exceptions.RequestException as e:
    print(f"Failed to list sections: {e}")
    debug_response(r)
    exit(1)

# ------------------------------------------------------------------
# 7. Create a test folder in the **first** section
# ------------------------------------------------------------------
section_id = sections[0]['id']   # change index or hard-code if you prefer
folder_payload = {
    "title": "API Test Folder (Hello World)",
    "description": "Created automatically by a Python script."
}

try:
    r = client.post(
        f'{BASE_URL}/v1/sections/{section_id}/folders',
        json=folder_payload,
        timeout=15
    )
    r.raise_for_status()
    print(f"\nFolder created! ID: {r.json().get('id')}")
except requests.exceptions.RequestException as e:
    print(f"Failed to create folder: {e}")
    debug_response(r)
    exit(1)

print("\nAll done!")