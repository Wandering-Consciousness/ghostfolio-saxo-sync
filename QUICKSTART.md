# Quick Start Guide

Get up and running with Saxo Bank sync in 5 minutes!

## Prerequisites

- Docker installed on your system
- Python 3.9+ (for initial setup)
- Saxo Bank developer account with app credentials
- Ghostfolio instance running

## Step-by-Step Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Credentials

Edit your `.env` file with your credentials:
- Saxo App Key: (from Saxo Bank Developer Portal)
- Saxo App Secret: (from Saxo Bank Developer Portal)
- Ghostfolio Host: `https://ghostfol.io/en`
- Ghostfolio Key: (from your Ghostfolio instance)

### 3. Run Initial Setup

This script will:
- Perform OAuth authentication (opens browser)
- Discover your Saxo accounts
- Save tokens and account key to `.env`

```bash
python setup_auth.py
```

Follow the prompts:
1. Browser opens → Log in to Saxo Bank
2. Authorize the application
3. Select which account to sync
4. Done!

### 4. Test the Sync Locally

```bash
python main.py
```

This will:
- Connect to Saxo Bank
- Fetch closed positions
- Import to Ghostfolio
- Update account balance

### 5. Deploy with Docker

#### Option A: Docker Compose (Recommended)

```bash
# Build and start
docker-compose up -d

# View logs
docker logs -f ghostfolio-saxo-sync

# Stop
docker-compose down
```

#### Option B: Docker CLI

```bash
# Build
docker build -t ghostfolio-saxo-sync .

# Run
docker run -d \
  --name saxo-sync \
  --env-file .env \
  -v $(pwd)/.env:/root/.env \
  --restart unless-stopped \
  ghostfolio-saxo-sync

# View logs
docker logs -f saxo-sync

# Stop
docker stop saxo-sync && docker rm saxo-sync
```

## Verify It's Working

Check the logs for:

```
[2024-XX-XX XX:XX:XX] Starting Saxo Bank sync
[2024-XX-XX XX:XX:XX] Saxo API client initialized successfully
[2024-XX-XX XX:XX:XX] Ghostfolio bearer token fetched successfully
[2024-XX-XX XX:XX:XX] Found X closed positions
[2024-XX-XX XX:XX:XX] Found Y new activities to import
[2024-XX-XX XX:XX:XX] Imported chunk 1: Y activities
[2024-XX-XX XX:XX:XX] Updated account balance: XXXX.XX USD
[2024-XX-XX XX:XX:XX] Saxo Bank sync completed successfully
```

Then check Ghostfolio:
1. Go to your Ghostfolio instance
2. Navigate to Accounts
3. You should see "Saxo Bank" account
4. Check Activities for imported trades

## Scheduled Syncs

The container is configured to run every 15 minutes automatically.

To change the schedule, edit `.env`:

```bash
# Every 30 minutes
CRON=*/30 * * * *

# Every hour
CRON=0 * * * *

# Every 6 hours
CRON=0 */6 * * *

# Daily at 9 AM
CRON=0 9 * * *
```

Then restart the container:

```bash
docker-compose restart
```

## Troubleshooting

### No Trades Showing Up?

1. **Check if you have closed positions**:
   - Only completed trades are synced
   - Open positions are not imported

2. **Verify account key**:
   ```bash
   grep SAXO_ACCOUNT_KEY .env
   ```

3. **Check logs for errors**:
   ```bash
   docker logs ghostfolio-saxo-sync | grep ERROR
   ```

### Token Expired?

The container automatically refreshes tokens. If it fails:

```bash
# Re-run setup
python setup_auth.py

# Rebuild container
docker-compose down
docker-compose up -d --build
```

### Symbol Not Found?

Add to `mapping.yaml`:

```yaml
symbol_mapping:
  SAXO_SYMBOL: YAHOO_TICKER
```

Example:
```yaml
symbol_mapping:
  VUAA: VUAA.L
  CSPX: CSPX.L
```

## Useful Commands

```bash
# View all activities in Ghostfolio
OPERATION=GET_ALL_ACTS python main.py

# Delete all activities (careful!)
OPERATION=DELETE_ALL_ACTS python main.py

# Run sync once
OPERATION=SYNCSAXO python main.py

# Rebuild container after changes
docker-compose up -d --build

# View live logs
docker logs -f ghostfolio-saxo-sync

# Check container status
docker ps | grep saxo

# Enter container for debugging
docker exec -it ghostfolio-saxo-sync sh
```

## Next Steps

1. **Monitor the first few syncs** - Check logs to ensure everything works
2. **Add symbol mappings** - Map any unmapped instruments in `mapping.yaml`
3. **Adjust cron schedule** - Fine-tune sync frequency in `.env`
4. **Set up monitoring** - Consider log aggregation or alerts
5. **Review Ghostfolio** - Check portfolio accuracy and performance

## Need Help?

- Check README.md for detailed documentation
- Review logs with `LOG_LEVEL=DEBUG` in `.env`
- Open an issue on GitHub
- Consult Saxo Bank OpenAPI docs: https://www.developer.saxo/

---

**That's it! Your Saxo Bank account is now syncing automatically with Ghostfolio.** 🎉
