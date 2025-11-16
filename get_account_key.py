#!/usr/bin/env python3
"""
Get Saxo account key from authenticated session
"""

import logging
import os
from dotenv import load_dotenv
from saxo_openapi import API
import saxo_openapi.endpoints.portfolio as pf
from saxo_oauth import perform_oauth_flow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment
load_dotenv()

print("=" * 60)
print("Saxo Bank Account Discovery")
print("=" * 60)
print()

try:
    # Authenticate
    print("Authenticating with Saxo Bank...")
    oauth = perform_oauth_flow()

    # Initialize API client
    use_production = os.getenv('SAXO_USE_PRODUCTION', 'false').lower() == 'true'
    if use_production:
        environment = 'live'
        print("Using PRODUCTION API")
    else:
        environment = 'simulation'
        print("Using SIMULATION API")

    print()

    client = API(access_token=oauth.access_token, environment=environment)

    # Get accounts
    print("Fetching your accounts...")
    r = pf.accounts.AccountsMe()
    response = client.request(r)

    accounts = response.get('Data', [])

    if not accounts:
        print("⚠ No accounts found")
        exit(1)

    print(f"\nFound {len(accounts)} account(s):\n")

    for i, account in enumerate(accounts, 1):
        account_id = account.get('AccountId', 'Unknown')
        account_key = account.get('AccountKey', 'Unknown')
        account_type = account.get('AccountType', 'Unknown')
        currency = account.get('Currency', 'Unknown')

        print(f"{i}. Account ID: {account_id}")
        print(f"   Account Key: {account_key}")
        print(f"   Type: {account_type}")
        print(f"   Currency: {currency}")

        # Get balance
        try:
            params = {'AccountKey': account_key}
            r_balance = pf.balances.AccountBalancesMe(params=params)
            balance_data = client.request(r_balance)

            if 'CashBalance' in balance_data:
                cash = balance_data['CashBalance']
                curr = balance_data.get('Currency', currency)
                print(f"   Cash Balance: {cash} {curr}")

            if 'TotalValue' in balance_data:
                total = balance_data['TotalValue']
                curr = balance_data.get('Currency', currency)
                print(f"   Total Value: {total} {curr}")

        except Exception as e:
            print(f"   (Could not fetch balance: {e})")

        print()

    # Show how to update .env
    if accounts:
        print("=" * 60)
        print("To use an account, add this to your .env file:")
        print("=" * 60)
        for i, account in enumerate(accounts, 1):
            account_key = account.get('AccountKey', 'Unknown')
            print(f"\nAccount {i}:")
            print(f"SAXO_ACCOUNT_KEY={account_key}")
        print()

except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
