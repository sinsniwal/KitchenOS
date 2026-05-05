import os
import sys
import json
import base64
import hashlib
import secrets
import urllib.parse
import urllib.request

# Configuration
SWIGGY_AUTH_URL = "https://mcp.swiggy.com/auth/authorize"
SWIGGY_TOKEN_URL = "https://mcp.swiggy.com/auth/token"
REDIRECT_URI = "http://localhost/callback"

def generate_pkce_pair():
    """Generate a PKCE verifier and challenge."""
    verifier = secrets.token_urlsafe(32)
    # S256 Challenge
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    challenge = base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')
    return verifier, challenge

def main():
    print("=== Swiggy MCP Local OAuth Flow ===")
    client_id = "localhost"  # Default for local testing

    verifier, challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(16)

    # 1. Build Authorization URL
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "scope": "mcp:tools" # Add mcp:resources mcp:prompts if needed
    }
    
    url = f"{SWIGGY_AUTH_URL}?{urllib.parse.urlencode(params)}"
    print("\n1. Open this URL in your browser to log in:")
    print("-" * 80)
    print(url)
    print("-" * 80)
    
    print("\n2. After logging in, your browser will redirect you to an empty page or error (http://localhost/callback?code=...).")
    print("3. Because the URL is extremely long, copying it into the terminal can fail.")
    print("   Please create a file named 'swiggy_url.txt' in this folder, paste the FULL URL into it, and save the file.")
    input("   Press Enter HERE only AFTER you have saved the URL to 'swiggy_url.txt'...")

    try:
        with open("swiggy_url.txt", "r") as f:
            redirected_url = f.read().strip()
    except FileNotFoundError:
        print("Error: Could not find 'swiggy_url.txt'. Please create it and paste the URL.")
        sys.exit(1)

    # Extract the 'code' from the URL
    parsed_url = urllib.parse.urlparse(redirected_url)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    if "code" not in query_params:
        print("Error: No 'code' found in the URL. Ensure you copied the exact redirect URL into the text file.")
        sys.exit(1)
        
    code = query_params["code"][0]
    returned_state = query_params.get("state", [""])[0]

    if returned_state != state:
        print("Error: State mismatch. Possible CSRF attack.")
        sys.exit(1)

    print("\n4. Exchanging code for access token...")
    
    # 2. Exchange Code for Token
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": verifier,
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI
    }).encode('ascii')
    
    req = urllib.request.Request(SWIGGY_TOKEN_URL, data=data)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            print("\n✅ Success! Here is your token information:")
            print("-" * 80)
            print(f"SWIGGY_ACCESS_TOKEN={result.get('access_token')}")
            print(f"Expires In: {result.get('expires_in')} seconds")
            print("-" * 80)
            print("\nCopy the SWIGGY_ACCESS_TOKEN and paste it into your .env file!")
    except urllib.error.HTTPError as e:
        error_info = e.read().decode('utf-8')
        print(f"\n❌ Failed to get token. HTTP {e.code}: {error_info}")

if __name__ == "__main__":
    main()
