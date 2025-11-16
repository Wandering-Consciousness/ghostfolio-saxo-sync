"""
Main entry point for Saxo Bank to Ghostfolio synchronization
"""

import logging
import os
import sys

from dotenv import load_dotenv

from SyncSaxo import SyncSaxo
from saxo_oauth import perform_oauth_flow

# Configure logging
template = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(level=getattr(logging, log_level), format=template)

logger = logging.getLogger(__name__)


def main():
    """Main execution function"""
    # Load environment variables
    load_dotenv()

    # Get configuration
    operation = os.getenv('OPERATION', 'SYNCSAXO').upper()
    saxo_account_key = os.getenv('SAXO_ACCOUNT_KEY')
    ghost_host = os.getenv('GHOST_HOST', 'https://ghostfol.io')
    ghost_key = os.getenv('GHOST_KEY')
    ghost_account_name = os.getenv('GHOST_ACCOUNT_NAME', 'Saxo Bank')
    ghost_currency = os.getenv('GHOST_CURRENCY', 'USD')
    ghost_saxo_platform = os.getenv('GHOST_SAXO_PLATFORM')

    # Validate required configuration
    if not saxo_account_key:
        logger.error("SAXO_ACCOUNT_KEY is required")
        sys.exit(1)

    if not ghost_key:
        logger.error("GHOST_KEY is required")
        sys.exit(1)

    try:
        # Perform OAuth flow (will use cached tokens if available)
        logger.info("Authenticating with Saxo Bank...")
        oauth = perform_oauth_flow()

        # Initialize sync object
        sync = SyncSaxo(
            saxo_account_key=saxo_account_key,
            ghost_host=ghost_host,
            ghost_key=ghost_key,
            ghost_account_name=ghost_account_name,
            ghost_currency=ghost_currency,
            ghost_saxo_platform=ghost_saxo_platform
        )

        # Initialize Ghostfolio authentication
        sync.create_ghost_token()

        # Execute operation
        if operation == 'SYNCSAXO':
            logger.info("Operation: SYNC SAXO")
            success = sync.sync(oauth)

        elif operation == 'DELETE_ALL_ACTS':
            logger.info("Operation: DELETE ALL ACTIVITIES")
            # Ensure account exists
            sync.create_or_get_saxo_account()
            success = sync.delete_all_activities()

        elif operation == 'GET_ALL_ACTS':
            logger.info("Operation: GET ALL ACTIVITIES")
            # Ensure account exists
            sync.create_or_get_saxo_account()
            activities = sync.get_all_ghostfolio_activities()

            logger.info(f"\n{'='*50}")
            logger.info(f"Found {len(activities)} activities:")
            logger.info(f"{'='*50}\n")

            for i, activity in enumerate(activities, 1):
                logger.info(f"{i}. {activity.get('type')} {activity.get('quantity')} {activity.get('symbol')} "
                          f"@ {activity.get('unitPrice')} {activity.get('currency')} "
                          f"on {activity.get('date', '')[:10]}")

            success = True

        else:
            logger.error(f"Unknown operation: {operation}")
            logger.error("Valid operations: SYNCSAXO, DELETE_ALL_ACTS, GET_ALL_ACTS")
            sys.exit(1)

        if success:
            logger.info("Operation completed successfully")
            sys.exit(0)
        else:
            logger.error("Operation failed")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        sys.exit(130)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
