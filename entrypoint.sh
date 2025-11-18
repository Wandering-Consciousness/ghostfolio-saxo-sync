#!/bin/bash

# Entrypoint script for Saxo sync container

set -e

echo "Saxo Bank to Ghostfolio Sync Container"
echo "======================================"

# Disable interactive authentication in Docker (prevents port binding attempts)
export DISABLE_INTERACTIVE_AUTH=${DISABLE_INTERACTIVE_AUTH:-true}

# Check if CRON environment variable is set
if [ -z "$CRON" ]; then
  echo "CRON not set - running one-time sync now"
  python main.py
else
  echo "CRON schedule configured: $CRON"
  echo "Setting up cron job..."

  # Create cron job
  echo "$CRON /root/run.sh" > /etc/crontabs/root

  # Display cron schedule
  echo "Cron job installed:"
  cat /etc/crontabs/root

  # Run initial sync immediately
  echo ""
  echo "Running initial sync..."
  python main.py

  # Start cron daemon in foreground
  echo ""
  echo "Starting cron daemon..."
  echo "Container will run scheduled syncs at: $CRON"
  crond -f -d 8
fi
