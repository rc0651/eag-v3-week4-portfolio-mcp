import os
import webbrowser
from dotenv import load_dotenv, set_key
from kiteconnect import KiteConnect

load_dotenv(override=True)

api_key    = os.getenv("KITE_API_KEY")
api_secret = os.getenv("KITE_API_SECRET")

if not api_key or not api_secret:
    print("ERROR: KITE_API_KEY and KITE_API_SECRET must be set in .env")
    exit(1)

if api_secret == "your_api_secret_here":
    print("ERROR: Please set your actual KITE_API_SECRET in .env first")
    exit(1)

kite = KiteConnect(api_key=api_key)

login_url = f"https://kite.zerodha.com/connect/login?api_key={api_key}&v=3"
print(f"\nOpening Kite login in browser...\n{login_url}\n")
webbrowser.open(login_url)

print("After logging in, you will be redirected to a URL like:")
print("  https://your-redirect-url?request_token=XXXXXXXX&action=login&status=success\n")

import sys
if len(sys.argv) > 1:
    request_token = sys.argv[1].strip()
    print(f"Using request_token: {request_token}")
else:
    request_token = input("Paste the request_token from the redirect URL: ").strip()

try:
    session = kite.generate_session(request_token, api_secret=api_secret)
    access_token = session["access_token"]

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    set_key(env_path, "KITE_ACCESS_TOKEN", access_token, quote_mode="never")

    print(f"\nAccess token saved to .env successfully.")
    print(f"KITE_ACCESS_TOKEN={access_token}")
except Exception as e:
    print(f"\nERROR generating session: {e}")
    exit(1)
