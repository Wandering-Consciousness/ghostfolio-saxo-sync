"""
Saxo Bank to Ghostfolio synchronization module
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
import yaml
from saxo_openapi import API
import saxo_openapi.endpoints.portfolio as pf
import saxo_openapi.endpoints.referencedata.instruments as rd_instruments

from saxo_oauth import SaxoOAuth

logger = logging.getLogger(__name__)


class SyncSaxo:
    """Synchronizes Saxo Bank account data with Ghostfolio"""

    def __init__(self, saxo_account_key, ghost_host, ghost_key, ghost_account_name, ghost_currency, ghost_saxo_platform=None):
        self.saxo_account_key = saxo_account_key
        self.ghost_host = ghost_host.rstrip('/')
        self.ghost_key = ghost_key
        self.ghost_account_name = ghost_account_name
        self.ghost_currency = ghost_currency
        self.ghost_saxo_platform = ghost_saxo_platform

        self.account_id = None
        self.saxo_client = None
        self.ghost_token = None
        self.symbol_mapping = self.load_symbol_mapping()
        self.instrument_cache = {}  # Cache for instrument lookups

    def load_symbol_mapping(self) -> Dict[str, str]:
        """Load symbol mapping from YAML file"""
        try:
            if os.path.exists('mapping.yaml'):
                with open('mapping.yaml', 'r') as f:
                    data = yaml.safe_load(f)
                    return data.get('symbol_mapping', {})
        except Exception as e:
            logger.warning(f"Failed to load symbol mapping: {e}")
        return {}

    def initialize_saxo_client(self, oauth: SaxoOAuth):
        """Initialize Saxo OpenAPI client with valid token"""
        try:
            access_token = oauth.get_valid_token()

            # Use production or simulation API based on environment
            use_production = os.getenv('SAXO_USE_PRODUCTION', 'false').lower() == 'true'
            if use_production:
                environment = 'live'
            else:
                environment = 'simulation'

            self.saxo_client = API(access_token=access_token, environment=environment)
            logger.info(f"Saxo API client initialized successfully ({'production' if use_production else 'simulation'} mode)")
        except Exception as e:
            logger.error(f"Failed to initialize Saxo client: {e}")
            raise

    def create_ghost_token(self):
        """Create Ghostfolio authentication token"""
        url = f"{self.ghost_host}/api/v1/auth/anonymous"
        payload = json.dumps({'accessToken': self.ghost_key})
        headers = {'Content-Type': 'application/json'}

        try:
            response = requests.post(url, headers=headers, data=payload, timeout=10)
            response.raise_for_status()

            if response.status_code == 201:
                self.ghost_token = response.json()["authToken"]
                logger.info("Ghostfolio bearer token fetched successfully")
                return self.ghost_token

        except Exception as e:
            logger.error(f"Failed to fetch Ghostfolio token: {e}")
            raise

        return None

    def get_saxo_account_info(self) -> Dict:
        """Retrieve Saxo account information"""
        try:
            logger.info(f"Fetching account info for account key: {self.saxo_account_key}")

            # Get account details
            r = pf.accounts.AccountDetails(AccountKey=self.saxo_account_key)
            account_data = self.saxo_client.request(r)

            logger.info(f"Account info retrieved: {account_data.get('AccountId', 'Unknown')}")
            return account_data

        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            raise

    def get_saxo_balances(self) -> Dict[str, float]:
        """Get cash balances from Saxo account"""
        try:
            logger.info("Fetching account balances...")

            # Get balances for the account
            r = pf.balances.AccountBalancesMe()
            balance_data = self.saxo_client.request(r)

            # Extract cash balances by currency
            balances = {}
            if 'CashBalance' in balance_data:
                cash = balance_data['CashBalance']
                currency = balance_data.get('Currency', self.ghost_currency)
                balances[currency] = float(cash)
                logger.info(f"Balance: {cash} {currency}")

            return balances

        except Exception as e:
            logger.error(f"Failed to get balances: {e}")
            return {}

    def get_instrument_details(self, uic: int, asset_type: str) -> Optional[Dict]:
        """
        Lookup instrument details by UIC and asset type
        Returns dict with Symbol, Isin, and other details
        """
        # Check cache first
        cache_key = f"{uic}_{asset_type}"
        if cache_key in self.instrument_cache:
            logger.debug(f"Using cached instrument details for UIC {uic}")
            return self.instrument_cache[cache_key]

        try:
            logger.info(f"Looking up instrument details for UIC {uic}, AssetType {asset_type}")

            # Use InstrumentsDetails endpoint with Uics parameter
            # Don't specify FieldGroups - get default fields which include Symbol and Isin
            params = {
                'Uics': str(uic),
                'AssetTypes': asset_type
            }

            r = rd_instruments.InstrumentsDetails(params=params)
            response = self.saxo_client.request(r)

            # Response should be a dict with 'Data' containing list of instruments
            instruments = response.get('Data', [])

            if instruments and len(instruments) > 0:
                instrument = instruments[0]

                # Extract key fields - Symbol and Isin should be in the root level
                raw_symbol = instrument.get('Symbol', '')
                isin = instrument.get('Isin', '')
                description = instrument.get('Description', '')

                # Strip exchange suffix from symbol (e.g., "QUBT:xnas" -> "QUBT")
                # Yahoo Finance doesn't use the :exchange format
                symbol = raw_symbol.split(':')[0] if raw_symbol else ''

                details = {
                    'Uic': uic,
                    'AssetType': asset_type,
                    'Symbol': symbol,
                    'Isin': isin,
                    'Description': description,
                    'Currency': instrument.get('CurrencyCode', ''),
                    'Exchange': instrument.get('ExchangeId', ''),
                    'RawSymbol': raw_symbol  # Keep original for reference
                }

                # Cache the result
                self.instrument_cache[cache_key] = details

                logger.info(f"Instrument {uic}: Symbol={symbol}, ISIN={isin}, Description={description}")
                return details
            else:
                logger.warning(f"No instrument data found for UIC {uic}")
                return None

        except Exception as e:
            logger.error(f"Failed to lookup instrument {uic}: {e}")
            return None

    def get_saxo_positions(self) -> List[Dict]:
        """Retrieve current open positions from Saxo"""
        try:
            logger.info("Fetching positions...")

            # Try closed positions first (if IntraDay netting)
            try:
                r = pf.closedpositions.ClosedPositionsMe()
                response = self.saxo_client.request(r)
                closed_positions = response.get('Data', [])
                logger.info(f"Found {len(closed_positions)} closed positions")
                return closed_positions
            except Exception as e:
                logger.info(f"Closed positions not available (EndOfDay netting): {e}")

            # Fall back to current open positions
            logger.info("Fetching current open positions instead...")
            r = pf.positions.PositionsMe()
            response = self.saxo_client.request(r)

            positions = response.get('Data', [])
            logger.info(f"Found {len(positions)} open positions")

            return positions

        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []

    def transform_saxo_position_to_activity(self, position: Dict) -> Dict:
        """
        Transform a Saxo position to Ghostfolio activity format
        Handles both open positions (PositionBase) and closed positions (DisplayAndFormat)
        """
        try:
            # Check if this is an open position or closed position
            position_base = position.get('PositionBase')
            if position_base:
                # Open position structure
                uic = position_base.get('Uic')
                asset_type = position_base.get('AssetType', 'Stock')
                position_id = position.get('PositionId', '')
                amount = abs(float(position_base.get('Amount', 0)))
                price = float(position_base.get('OpenPrice', 0))

                # Dates - use execution time
                exec_time = position_base.get('ExecutionTimeOpen')
                if exec_time:
                    date = datetime.fromisoformat(exec_time.replace('Z', '+00:00'))
                else:
                    date = datetime.now()

                # For open positions, Amount > 0 = BUY (long position)
                activity_type = 'BUY'

                # Calculate fees from costs
                price_with_costs = float(position_base.get('OpenPriceIncludingCosts', price))
                cost = abs((price_with_costs - price) * amount)

                # Lookup instrument details to get symbol and ISIN
                symbol = None
                isin = None
                currency = self.ghost_currency  # Default currency
                instrument_details = self.get_instrument_details(uic, asset_type)
                if instrument_details:
                    symbol = instrument_details.get('Symbol')
                    isin = instrument_details.get('Isin')
                    # Use instrument currency if available
                    instrument_currency = instrument_details.get('Currency')
                    if instrument_currency:
                        currency = instrument_currency

            else:
                # Closed position structure
                symbol = position.get('DisplayAndFormat', {}).get('Symbol', '')
                isin = position.get('DisplayAndFormat', {}).get('Isin', '')
                uic = position.get('Uic')

                # Determine buy/sell
                buy_sell = position.get('BuySell', 'Buy')
                activity_type = 'BUY' if buy_sell == 'Buy' else 'SELL'

                # Dates - use closing date
                close_time = position.get('CloseTime')
                if close_time:
                    date = datetime.fromisoformat(close_time.replace('Z', '+00:00'))
                else:
                    date = datetime.now()

                # Amounts
                amount = abs(float(position.get('Amount', 0)))
                price = float(position.get('ClosingPrice', 0))

                # Position ID for deduplication
                position_id = position.get('PositionId', '')

                # Cost/fees
                cost = abs(float(position.get('Cost', 0)))

                # Currency - use account currency as default
                currency = self.ghost_currency

            # Determine final symbol and data source
            # Priority: ISIN > mapped symbol > raw symbol > fallback to UIC
            final_symbol = None
            data_source = 'YAHOO'  # Default to YAHOO

            if isin:
                # ISINs work with YAHOO data source
                final_symbol = isin
                data_source = 'YAHOO'
            elif symbol:
                # Check if symbol has a mapping
                mapped_symbol = self.symbol_mapping.get(symbol, symbol)
                final_symbol = mapped_symbol
                data_source = 'YAHOO'
            else:
                # No symbol or ISIN - use UIC as fallback with MANUAL
                final_symbol = f"SAXO{uic}"
                data_source = 'MANUAL'
                logger.warning(f"No symbol/ISIN found for UIC {uic}, using placeholder: {final_symbol}")

            # Build comment with available info
            comment_parts = [f'saxoPositionId={position_id}', f'UIC={uic}']
            if symbol and symbol != final_symbol:
                comment_parts.append(f'SaxoSymbol={symbol}')

            activity = {
                'accountId': self.account_id,
                'symbol': final_symbol,
                'dataSource': data_source,
                'type': activity_type,
                'date': date.isoformat(),
                'quantity': amount,
                'unitPrice': price,
                'fee': cost,
                'currency': currency,
                'comment': ' | '.join(comment_parts),
            }

            logger.debug(f"Transformed position {position_id}: {activity_type} {amount} {final_symbol} @ {price}")

            return activity

        except Exception as e:
            logger.error(f"Failed to transform position: {e}")
            logger.error(f"Position data: {position}")
            return None

    def is_duplicate_activity(self, activity: Dict, existing_activities: List[Dict]) -> bool:
        """
        Check if activity already exists in Ghostfolio
        Uses position ID from comment for precise matching
        """
        # Extract Saxo position ID from new activity
        comment = activity.get('comment', '')
        match = re.search(r'saxoPositionId=([^,\s]+)', comment)
        if not match:
            logger.warning("Activity missing saxoPositionId in comment")
            return False

        new_position_id = match.group(1)

        # Check against existing activities
        for existing in existing_activities:
            existing_comment = existing.get('comment', '')
            existing_match = re.search(r'saxoPositionId=([^,\s]+)', existing_comment)

            if existing_match:
                existing_position_id = existing_match.group(1)
                if new_position_id == existing_position_id:
                    logger.debug(f"Duplicate found: position ID {new_position_id}")
                    return True

        return False

    def get_all_ghostfolio_activities(self) -> List[Dict]:
        """Retrieve all activities from Ghostfolio for the account"""
        if not self.account_id:
            logger.warning("No account ID available")
            return []

        try:
            url = f"{self.ghost_host}/api/v1/order"
            headers = {'Authorization': f'Bearer {self.ghost_token}'}
            params = {'accounts': self.account_id}

            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            activities = response.json().get('activities', [])
            logger.info(f"Retrieved {len(activities)} existing activities from Ghostfolio")
            return activities

        except Exception as e:
            logger.error(f"Failed to get Ghostfolio activities: {e}")
            return []

    def import_activities_to_ghostfolio(self, activities: List[Dict]) -> bool:
        """Import activities to Ghostfolio in chunks"""
        if not activities:
            logger.info("No activities to import")
            return True

        try:
            # Sort by date
            activities.sort(key=lambda x: x['date'])

            # Process in chunks of 10 (like IB sync)
            chunk_size = 10
            total_imported = 0

            for i in range(0, len(activities), chunk_size):
                chunk = activities[i:i + chunk_size]

                url = f"{self.ghost_host}/api/v1/import"
                headers = {
                    'Authorization': f'Bearer {self.ghost_token}',
                    'Content-Type': 'application/json'
                }
                payload = {'activities': chunk}

                response = requests.post(url, headers=headers, json=payload, timeout=30)
                response.raise_for_status()

                total_imported += len(chunk)
                logger.info(f"Imported chunk {i//chunk_size + 1}: {len(chunk)} activities (total: {total_imported}/{len(activities)})")

            logger.info(f"Successfully imported {total_imported} activities")
            return True

        except Exception as e:
            logger.error(f"Failed to import activities: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            return False

    def create_or_get_saxo_account(self) -> str:
        """Create Ghostfolio account or get existing one"""
        if self.account_id:
            return self.account_id

        try:
            # First, get existing accounts
            url = f"{self.ghost_host}/api/v1/account"
            headers = {'Authorization': f'Bearer {self.ghost_token}'}

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # Handle both dict with 'accounts' key and direct list response
            response_data = response.json()
            if isinstance(response_data, list):
                accounts = response_data
            else:
                accounts = response_data.get('accounts', [])

            # Look for existing Saxo account
            for account in accounts:
                if account.get('name') == self.ghost_account_name:
                    self.account_id = account['id']
                    logger.info(f"Found existing account: {self.ghost_account_name} (ID: {self.account_id})")
                    return self.account_id

            # Create new account if not found
            logger.info(f"Creating new account: {self.ghost_account_name}")

            # Get or create platform
            platform_id = self.get_or_create_platform()

            create_url = f"{self.ghost_host}/api/v1/account"
            account_data = {
                'balance': 0,
                'currency': self.ghost_currency,
                'isExcluded': False,
                'name': self.ghost_account_name,
                'platformId': platform_id
            }

            response = requests.post(create_url, headers=headers, json=account_data, timeout=10)
            response.raise_for_status()

            self.account_id = response.json()['id']
            logger.info(f"Created account: {self.ghost_account_name} (ID: {self.account_id})")

            return self.account_id

        except Exception as e:
            logger.error(f"Failed to create/get account: {e}")
            raise

    def get_or_create_platform(self) -> str:
        """Get or create Saxo Bank platform"""
        try:
            # If platform ID provided, use it
            if self.ghost_saxo_platform:
                return self.ghost_saxo_platform

            # Get existing platforms
            url = f"{self.ghost_host}/api/v1/platform"
            headers = {'Authorization': f'Bearer {self.ghost_token}'}

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # Handle both dict with 'platforms' key and direct list response
            response_data = response.json()
            if isinstance(response_data, list):
                platforms = response_data
            else:
                platforms = response_data.get('platforms', [])

            # Look for Saxo Bank platform
            for platform in platforms:
                if platform.get('name') == 'Saxo Bank':
                    logger.info(f"Found existing platform: Saxo Bank (ID: {platform['id']})")
                    return platform['id']

            # Create new platform
            logger.info("Creating new platform: Saxo Bank")

            create_url = f"{self.ghost_host}/api/v1/platform"
            platform_data = {
                'name': 'Saxo Bank',
                'url': 'https://www.home.saxo'
            }

            response = requests.post(create_url, headers=headers, json=platform_data, timeout=10)
            response.raise_for_status()

            platform_id = response.json()['id']
            logger.info(f"Created platform: Saxo Bank (ID: {platform_id})")

            return platform_id

        except Exception as e:
            logger.error(f"Failed to get/create platform: {e}")
            raise

    def update_account_balance(self, balances: Dict[str, float]) -> bool:
        """Update account balance in Ghostfolio"""
        if not self.account_id or not balances:
            return False

        try:
            # Use the primary currency balance
            balance = balances.get(self.ghost_currency, 0)

            url = f"{self.ghost_host}/api/v1/account/{self.account_id}"
            headers = {
                'Authorization': f'Bearer {self.ghost_token}',
                'Content-Type': 'application/json'
            }

            platform_id = self.get_or_create_platform()

            account_data = {
                'id': self.account_id,
                'balance': balance,
                'currency': self.ghost_currency,
                'name': self.ghost_account_name,
                'platformId': platform_id,
                'isExcluded': False
            }

            response = requests.put(url, headers=headers, json=account_data, timeout=10)
            response.raise_for_status()

            logger.info(f"Updated account balance: {balance} {self.ghost_currency}")
            return True

        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to update account balance: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Failed to update account balance: {e}")
            return False

    def delete_all_activities(self) -> bool:
        """Delete all activities for the account"""
        if not self.account_id:
            logger.error("No account ID available")
            return False

        try:
            url = f"{self.ghost_host}/api/v1/order"
            headers = {'Authorization': f'Bearer {self.ghost_token}'}
            params = {'accounts': self.account_id}

            response = requests.delete(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            logger.info("All activities deleted successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to delete activities: {e}")
            return False

    def sync(self, oauth: SaxoOAuth) -> bool:
        """
        Main synchronization method
        """
        try:
            logger.info("=" * 50)
            logger.info("Starting Saxo Bank sync")
            logger.info("=" * 50)

            # Initialize clients
            self.initialize_saxo_client(oauth)
            self.create_ghost_token()

            # Get or create Ghostfolio account
            self.create_or_get_saxo_account()

            # Get Saxo account info
            account_info = self.get_saxo_account_info()
            logger.info(f"Syncing account: {account_info.get('AccountId', 'Unknown')}")

            # Get positions from Saxo (open or closed depending on netting mode)
            positions = self.get_saxo_positions()

            if not positions:
                logger.info("No positions found")
            else:
                # Get existing Ghostfolio activities for deduplication
                existing_activities = self.get_all_ghostfolio_activities()

                # Transform to Ghostfolio format
                new_activities = []
                for position in positions:
                    activity = self.transform_saxo_position_to_activity(position)
                    if activity:
                        if not self.is_duplicate_activity(activity, existing_activities):
                            new_activities.append(activity)
                        else:
                            logger.debug(f"Skipping duplicate activity")

                logger.info(f"Found {len(new_activities)} new activities to import")

                # Import to Ghostfolio
                if new_activities:
                    self.import_activities_to_ghostfolio(new_activities)

            # Update account balance
            balances = self.get_saxo_balances()
            self.update_account_balance(balances)

            logger.info("=" * 50)
            logger.info("Saxo Bank sync completed successfully")
            logger.info("=" * 50)

            return True

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


if __name__ == "__main__":
    # Test sync
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    from dotenv import load_dotenv
    from saxo_oauth import perform_oauth_flow

    load_dotenv()

    # Get OAuth tokens
    oauth = perform_oauth_flow()

    # Initialize sync
    sync = SyncSaxo(
        saxo_account_key=os.getenv('SAXO_ACCOUNT_KEY'),
        ghost_host=os.getenv('GHOST_HOST'),
        ghost_key=os.getenv('GHOST_KEY'),
        ghost_account_name=os.getenv('GHOST_ACCOUNT_NAME', 'Saxo Bank'),
        ghost_currency=os.getenv('GHOST_CURRENCY', 'USD'),
        ghost_saxo_platform=os.getenv('GHOST_SAXO_PLATFORM')
    )

    # Run sync
    sync.sync(oauth)
