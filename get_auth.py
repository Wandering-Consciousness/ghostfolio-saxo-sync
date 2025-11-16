#!/usr/bin/env python3
"""
Quick OAuth authentication script
Automatically opens browser and completes OAuth flow
"""

import logging
import os
from dotenv import load_dotenv
from saxo_oauth import perform_oauth_flow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment
load_dotenv()

print("=" * 60)
print("Saxo Bank OAuth Authentication")
print("=" * 60)
print()
print("Opening browser for Saxo Bank login...")
print("Please log in and authorize the application.")
print()

try:
    oauth = perform_oauth_flow()
    print()
    print("✓ OAuth authentication successful!")
    print()
    print(f"Access token: {oauth.access_token[:50]}...")
    print(f"Refresh token: {oauth.refresh_token[:50]}...")
    print(f"Expires at: {oauth.token_expiry}")
    print()
    print("Tokens have been saved to .env file")
    print()
except Exception as e:
    print(f"✗ OAuth authentication failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
