# ------------------------------------------------------------
#  PERSONAL AREA – EDIT ONLY THESE THREE LINES
# ------------------------------------------------------------
BASE_URL       = 'https://app.schoology.com'   # <-- main domain for login/OAuth
CONSUMER_KEY   = '111573b00469adf603471a59c8019a4b0690a5db3'       # <-- fresh from https://app.schoology.com/api
CONSUMER_SECRET = '93dbd10afd358400043e168589deff7c'   # <-- fresh from https://app.schoology.com/api
HEADLESS       = False                         # <-- Set to True once debugging is done
# ------------------------------------------------------------

import requests
from requests_oauthlib import OAuth1, OAuth1Session
import getpass  # For secure password input
from urllib.parse import parse_qsl
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
    print(resp.text)   # print full body for debug
    print("--- END DEBUG ---\n")

# Set up Chrome with options
options = Options()
if HEADLESS:
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
options.add_argument("--log-level=0")  # Verbose logging
driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

# ------------------------------------------------------------------
# Automate full Schoology login via SSO (ONLY for authorization step)
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
        print("Login page detected. Please log in manually in the browser window (search for your school, then SSO), then press Enter here.")
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

    # Get the instance domain (e.g., https://lynnschools.schoology.com)
    instance_domain = driver.current_url.rsplit('/home', 1)[0]
    print("Instance domain: " + instance_domain)

    # NOTE: We don't need cookies for OAuth API calls - OAuth uses signatures, not sessions
except Exception as e:
    print(f"Login automation failed: {e}")
    driver.quit()
    exit(1)

# API base is api.schoology.com
API_BASE = 'https://api.schoology.com/v1'

# ------------------------------------------------------------------
# 1. Request OAuth request token (NO COOKIES - pure OAuth 1.0a)
# ------------------------------------------------------------------
print("\n=== Step 1: Requesting OAuth request token ===")
request_token_url = f'{API_BASE}/oauth/request_token'

try:
    # Create OAuth1Session without any cookies - pure OAuth signature
    oauth_req = OAuth1Session(
        CONSUMER_KEY,
        client_secret=CONSUMER_SECRET,
        callback_uri='oob'  # Out-of-band for CLI apps
    )

    print(f"Requesting token from: {request_token_url}")
    print(f"Consumer Key: {CONSUMER_KEY[:10]}...")  # Show first 10 chars for verification

    # Attempt to fetch request token with proper headers
    try:
        token_dict = oauth_req.fetch_request_token(
            request_token_url,
            headers={
                'Accept': 'application/x-www-form-urlencoded',
                'User-Agent': 'SchoologyAPIClient/1.0'
            }
        )
        resource_owner_key = token_dict['oauth_token']
        resource_owner_secret = token_dict['oauth_token_secret']
        print("Request token obtained.")
        print(f"  oauth_token: {resource_owner_key[:20]}...")
    except Exception as api_error:
        # If API endpoint fails, it's likely a key approval issue
        print(f"\n*** API OAuth endpoint failed: {api_error}")

        if hasattr(api_error, 'response'):
            resp = api_error.response
            print(f"Response Status: {resp.status_code}")
            print(f"Response Headers: {dict(resp.headers)}")

            # Check if we got HTML (404 page or error page)
            if 'text/html' in resp.headers.get('Content-Type', ''):
                print("\nReceived HTML response - OAuth endpoint may not be accessible.")
                print("This typically means:")
                print("1. Your consumer key is not approved for 3-legged OAuth")
                print("2. The API endpoint requires app approval from PowerSchool/district")
                print("3. Your app needs to be associated with the tenant (lynnschools)")

                # Show first 500 chars of HTML for debugging
                print("\nFirst 500 chars of response:")
                print(resp.text[:500])

        print("\n=== ACTION REQUIRED ===")
        print("Contact your Schoology administrator to:")
        print("1. Verify the consumer key is approved for 3-legged OAuth")
        print("2. Associate the app with lynnschools.schoology.com tenant")
        print("3. Enable user data access permissions for the app")
        driver.quit()
        exit(1)

except Exception as e:
    print(f"Unexpected error fetching request token: {e}")
    driver.quit()
    exit(1)

# ------------------------------------------------------------------
# 2. Automate app authorization (using instance domain)
# ------------------------------------------------------------------
base_authorization_url = f'{instance_domain}/oauth/authorize'
oauth_auth = OAuth1Session(
    CONSUMER_KEY,
    client_secret=CONSUMER_SECRET,
    resource_owner_key=resource_owner_key,
    resource_owner_secret=resource_owner_secret
)
authorization_url = oauth_auth.authorization_url(base_authorization_url)
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
print("\n=== Step 3: Exchanging verifier for access token ===")
access_token_url = f'{API_BASE}/oauth/access_token'

try:
    oauth_acc = OAuth1Session(
        CONSUMER_KEY,
        client_secret=CONSUMER_SECRET,
        resource_owner_key=resource_owner_key,
        resource_owner_secret=resource_owner_secret,
        verifier=verifier
    )

    print(f"Exchanging at: {access_token_url}")
    token_dict = oauth_acc.fetch_access_token(
        access_token_url,
        headers={
            'Accept': 'application/x-www-form-urlencoded',
            'User-Agent': 'SchoologyAPIClient/1.0'
        }
    )
    access_key = token_dict['oauth_token']
    access_secret = token_dict['oauth_token_secret']
    print("Access token obtained.")
    print(f"  oauth_token: {access_key[:20]}...")
except Exception as e:
    print(f"Error fetching access token: {e}")
    if hasattr(e, 'response'):
        debug_response(e.response)
    driver.quit()
    exit(1)

driver.quit()  # Close browser

# ------------------------------------------------------------------
# 4. New OAuth session with the access token (NO COOKIES)
# ------------------------------------------------------------------
print("\n=== Step 4: Creating authenticated API client ===")
client = OAuth1Session(
    CONSUMER_KEY,
    client_secret=CONSUMER_SECRET,
    resource_owner_key=access_key,
    resource_owner_secret=access_secret
)
# NOTE: No cookies needed - OAuth signatures handle authentication

# ------------------------------------------------------------------
# 5. Get your user ID
# ------------------------------------------------------------------
try:
    r = client.get(f'{API_BASE}/users/me', timeout=15)
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
    r = client.get(f'{API_BASE}/users/{user_id}/sections', timeout=15)
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
        f'{API_BASE}/sections/{section_id}/folders',
        json=folder_data
    )
    r.raise_for_status()
    print(f"\nFolder created successfully in section {section_id}! Response: {r.json()}")
except requests.exceptions.RequestException as e:
    print(f"Error creating folder: {e}")