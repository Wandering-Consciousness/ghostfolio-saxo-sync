#!/usr/bin/env python3
"""
Setup script for Saxo Bank OAuth authentication and account discovery
Run this before using the Docker container
"""

import logging
import os
import sys

from dotenv import load_dotenv
from saxo_openapi import API
import saxo_openapi.endpoints.portfolio as pf

from saxo_oauth import perform_oauth_flow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main setup function"""
    print("=" * 60)
    print("Saxo Bank to Ghostfolio Sync - Initial Setup")
    print("=" * 60)
    print()

    # Load environment
    load_dotenv()

    # Check required variables
    app_key = os.getenv('SAXO_APP_KEY')
    app_secret = os.getenv('SAXO_APP_SECRET')

    if not app_key or not app_secret:
        print("ERROR: SAXO_APP_KEY and SAXO_APP_SECRET must be set in .env file")
        print("Please edit your .env file with your Saxo Bank application credentials")
        sys.exit(1)

    print(f"App Key: {app_key}")
    print()

    # Step 1: OAuth Authentication
    print("Step 1: OAuth Authentication")
    print("-" * 60)
    print("A browser window will open for you to log in to Saxo Bank")
    print("and authorize this application.")
    print()
    input("Press Enter to continue...")
    print()

    try:
        oauth = perform_oauth_flow()
        print("✓ OAuth authentication successful!")
        print(f"  Access token: {oauth.access_token[:30]}...")
        print(f"  Refresh token: {oauth.refresh_token[:30]}...")
        print(f"  Expires at: {oauth.token_expiry}")
        print()
    except Exception as e:
        print(f"✗ OAuth authentication failed: {e}")
        sys.exit(1)

    # Step 2: Discover Accounts
    print("Step 2: Account Discovery")
    print("-" * 60)
    print("Fetching your Saxo Bank accounts...")
    print()

    try:
        client = API(access_token=oauth.access_token)

        # Get accounts
        r = pf.accounts.AccountsMe()
        response = client.request(r)

        accounts = response.get('Data', [])

        if not accounts:
            print("⚠ No accounts found")
            print("Please ensure you have an active Saxo Bank account")
            sys.exit(1)

        print(f"Found {len(accounts)} account(s):")
        print()

        for i, account in enumerate(accounts, 1):
            account_id = account.get('AccountId', 'Unknown')
            account_key = account.get('AccountKey', 'Unknown')
            account_type = account.get('AccountType', 'Unknown')
            currency = account.get('Currency', 'Unknown')

            print(f"  {i}. Account ID: {account_id}")
            print(f"     Account Key: {account_key}")
            print(f"     Type: {account_type}")
            print(f"     Currency: {currency}")
            print()

            # Get balance for this account
            try:
                params = {'AccountKey': account_key}
                r_balance = pf.balances.AccountBalancesMe(params=params)
                balance_data = client.request(r_balance)

                if 'CashBalance' in balance_data:
                    cash = balance_data['CashBalance']
                    curr = balance_data.get('Currency', currency)
                    print(f"     Balance: {cash} {curr}")

                if 'TotalValue' in balance_data:
                    total = balance_data['TotalValue']
                    curr = balance_data.get('Currency', currency)
                    print(f"     Total Value: {total} {curr}")

                print()

            except Exception as e:
                logger.debug(f"Could not fetch balance: {e}")

        # Step 3: Configure .env
        print("Step 3: Configuration")
        print("-" * 60)

        if len(accounts) == 1:
            selected_account = accounts[0]
            print(f"Using the only available account: {selected_account.get('AccountId')}")
        else:
            print("Which account would you like to sync?")
            try:
                choice = int(input(f"Enter number (1-{len(accounts)}): "))
                if 1 <= choice <= len(accounts):
                    selected_account = accounts[choice - 1]
                else:
                    print("Invalid choice")
                    sys.exit(1)
            except (ValueError, KeyboardInterrupt):
                print("\nSetup cancelled")
                sys.exit(1)

        account_key = selected_account.get('AccountKey')
        currency = selected_account.get('Currency', 'USD')

        print()
        print(f"Selected Account Key: {account_key}")
        print(f"Currency: {currency}")
        print()

        # Update .env file
        print("Updating .env file...")

        env_lines = []
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                env_lines = f.readlines()

        updated_lines = []
        updated_vars = set()
        updates = {
            'SAXO_ACCOUNT_KEY': account_key,
            'GHOST_CURRENCY': currency
        }

        for line in env_lines:
            if '=' in line:
                key = line.split('=')[0]
                if key in updates:
                    updated_lines.append(f"{key}={updates[key]}\n")
                    updated_vars.add(key)
                else:
                    updated_lines.append(line)
            else:
                updated_lines.append(line)

        # Add missing vars
        for key, value in updates.items():
            if key not in updated_vars:
                updated_lines.append(f"{key}={value}\n")

        with open('.env', 'w') as f:
            f.writelines(updated_lines)

        print("✓ .env file updated successfully!")
        print()

        # Step 4: Summary
        print("=" * 60)
        print("Setup Complete!")
        print("=" * 60)
        print()
        print("Your configuration:")
        print(f"  Saxo Account Key: {account_key}")
        print(f"  Ghostfolio Host: {os.getenv('GHOST_HOST')}")
        print(f"  Account Name: {os.getenv('GHOST_ACCOUNT_NAME')}")
        print(f"  Currency: {currency}")
        print()
        print("Next steps:")
        print("  1. Review your .env file")
        print("  2. Test sync: python main.py")
        print("  3. Build Docker: docker-compose build")
        print("  4. Run Docker: docker-compose up -d")
        print()
        print("To monitor: docker logs -f ghostfolio-saxo-sync")
        print()

    except Exception as e:
        print(f"✗ Account discovery failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user")
        sys.exit(130)
