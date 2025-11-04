#!/bin/bash

# Schoology OAuth 1.0a Verification Script
# Tests request_token endpoint with proper OAuth signature

# Your credentials (replace with actual values)
CONSUMER_KEY="111573b00469adf603471a59c8019a4b0690a5db3"
CONSUMER_SECRET="93dbd10afd358400043e168589deff7c"
API_BASE="https://api.schoology.com/v1"

# OAuth parameters
OAUTH_VERSION="1.0"
OAUTH_SIGNATURE_METHOD="HMAC-SHA1"
OAUTH_CALLBACK="oob"
OAUTH_NONCE=$(openssl rand -hex 16)
OAUTH_TIMESTAMP=$(date +%s)

echo "=== Schoology OAuth Request Token Verification ==="
echo "Consumer Key: ${CONSUMER_KEY:0:10}..."
echo "API Base: $API_BASE"
echo "Timestamp: $OAUTH_TIMESTAMP"
echo "Nonce: $OAUTH_NONCE"
echo ""

# Method 1: Using curl with OAuth (requires oauth plugin or manual signature)
echo "=== Test 1: Direct cURL to request_token endpoint ==="
echo "Endpoint: $API_BASE/oauth/request_token"
echo ""

# This will likely fail without proper OAuth signature, but shows the endpoint response
curl -X POST \
  -H "Accept: application/x-www-form-urlencoded" \
  -H "User-Agent: SchoologyAPIClient/1.0" \
  "$API_BASE/oauth/request_token" \
  -w "\n\nHTTP Status: %{http_code}\nContent-Type: %{content_type}\n" \
  -o response.txt

echo -e "\nResponse (first 500 chars):"
head -c 500 response.txt
echo -e "\n"

# Method 2: Python one-liner test (requires requests-oauthlib)
echo "=== Test 2: Python OAuth test ==="
cat > test_oauth.py << 'EOF'
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
EOF

python test_oauth.py "$CONSUMER_KEY" "$CONSUMER_SECRET"

echo -e "\n=== Verification Complete ==="
echo ""
echo "Expected successful response format:"
echo "  oauth_token=REQUEST_TOKEN_HERE&oauth_token_secret=REQUEST_SECRET_HERE&oauth_callback_confirmed=true"
echo ""
echo "If you see HTML or 404 errors, you need to:"
echo "1. Contact your Schoology/PowerSchool administrator"
echo "2. Request approval for 3-legged OAuth for your consumer key"
echo "3. Associate your app with the lynnschools.schoology.com tenant"
echo "4. Enable 'Access user data' permission for your app"