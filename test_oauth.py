import sys
from requests_oauthlib import OAuth1Session

consumer_key = sys.argv[1]
consumer_secret = sys.argv[2]

oauth = OAuth1Session(
    consumer_key,
    client_secret=consumer_secret,
    callback_uri='oob'
)

url = 'https://api.schoology.com/v1/oauth/request_token'
print(f"Testing: {url}")

try:
    resp = oauth.post(url, headers={
        'Accept': 'application/x-www-form-urlencoded',
        'User-Agent': 'SchoologyAPIClient/1.0'
    })
    print(f"Status: {resp.status_code}")
    print(f"Headers: {dict(resp.headers)}")
    print(f"Body (first 200 chars): {resp.text[:200]}")

    if resp.status_code == 200 and 'oauth_token=' in resp.text:
        print("\n✓ SUCCESS: OAuth request_token endpoint is working!")
        print("Your consumer key is approved for 3-legged OAuth.")
    else:
        print("\n✗ FAILURE: Did not receive OAuth token.")
        if resp.status_code == 404:
            print("404 - Consumer key may not be approved for 3-legged OAuth")
        elif 'html' in resp.headers.get('content-type', '').lower():
            print("Received HTML instead of token - likely a configuration issue")
except Exception as e:
    print(f"\n✗ ERROR: {e}")
    if hasattr(e, 'response'):
        print(f"Response status: {e.response.status_code}")
        print(f"Response body preview: {e.response.text[:200]}")
