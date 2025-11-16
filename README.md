# Saxo Bank to Ghostfolio Sync

Automated synchronization tool that imports trades, positions, and account data from Saxo Bank into [Ghostfolio](https://ghostfol.io), an open-source portfolio tracker.

## Features

- **Automatic instrument lookup** - Retrieves real stock symbols and ISINs from Saxo API
- Automated sync of open and closed positions from Saxo Bank
- OAuth2 authentication with token refresh
- Account balance synchronization
- Deduplication to prevent duplicate imports
- Symbol mapping for better data source matching
- Docker containerization with cron scheduling
- Support for multiple operation modes
- Production and simulation environment support

## Prerequisites

1. **Saxo Bank Developer Account**
   - Sign up at https://www.developer.saxo/
   - Request a simulation account (free for testing)

2. **Saxo Bank Application**
   - Create an app in Application Management
   - Configure OAuth2 Authorization Code flow
   - Note your App Key (client_id) and App Secret (client_secret)

3. **Ghostfolio Instance**
   - Running Ghostfolio instance (self-hosted or cloud)
   - API access token

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/spinsphere/ghostfolio-saxo-sync.git
cd ghostfolio-saxo-sync
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
nano .env
```

Required configuration:

```bash
# Saxo Bank Configuration
SAXO_APP_KEY=your_app_key_here
SAXO_APP_SECRET=your_app_secret_here
SAXO_REDIRECT_URI=http://localhost:5000/callback
SAXO_ACCOUNT_KEY=your_account_key_here

# Ghostfolio Configuration
GHOST_HOST=https://your-ghostfolio-instance.com
GHOST_KEY=your_ghostfolio_access_token
GHOST_ACCOUNT_NAME=Saxo Bank
GHOST_CURRENCY=USD

# Cron schedule (every 15 minutes)
CRON=*/15 * * * *
```

### 3. Initial Setup - Get OAuth Tokens

Before running the container, you need to complete the OAuth flow once to get your access and refresh tokens:

```bash
# Install dependencies
pip install -r requirements.txt

# Run OAuth authentication
python get_auth.py
```

This will:
1. Open your browser for Saxo Bank login
2. Prompt you to authorize the application
3. Save tokens to your `.env` file

**Note**: In Docker, the interactive OAuth flow won't work. You must obtain tokens locally first, then they'll be automatically refreshed by the container.

### 4. Get Your Saxo Account Key

You need to find your account key to sync the correct account:

```bash
# Run the account discovery script
python get_account_key.py
```

This will display all your Saxo accounts with their:
- Account ID
- Account Key
- Account Type
- Currency
- Cash Balance
- Total Value

Copy the `AccountKey` for your desired account and add it to your `.env` file as `SAXO_ACCOUNT_KEY`.

### 5. Run with Docker

Build and run the container:

```bash
# Build image
docker build -t ghostfolio-saxo-sync .

# Run container
docker run -d \
  --name saxo-sync \
  --env-file .env \
  --restart unless-stopped \
  ghostfolio-saxo-sync
```

Or use Docker Compose:

```yaml
# docker-compose.yml
version: '3.8'

services:
  saxo-sync:
    build: .
    container_name: saxo-sync
    env_file: .env
    restart: unless-stopped
```

```bash
docker-compose up -d
```

### 6. Monitor Logs

```bash
docker logs -f saxo-sync
```

## Configuration

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `SAXO_APP_KEY` | Yes | Saxo Bank application key (client_id) | - |
| `SAXO_APP_SECRET` | Yes | Saxo Bank application secret (client_secret) | - |
| `SAXO_REDIRECT_URI` | Yes | OAuth redirect URI | `http://localhost:5000/callback` |
| `SAXO_ACCOUNT_KEY` | Yes | Saxo account key to sync | - |
| `SAXO_USE_PRODUCTION` | No | Use production API (true/false) | `false` |
| `SAXO_ACCESS_TOKEN` | Auto | OAuth access token (auto-generated) | - |
| `SAXO_REFRESH_TOKEN` | Auto | OAuth refresh token (auto-generated) | - |
| `SAXO_TOKEN_EXPIRY` | Auto | Token expiration timestamp (auto-managed) | - |
| `GHOST_HOST` | Yes | Ghostfolio instance URL | `https://ghostfol.io` |
| `GHOST_KEY` | Yes | Ghostfolio access token | - |
| `GHOST_ACCOUNT_NAME` | No | Name for Saxo account in Ghostfolio | `Saxo Bank` |
| `GHOST_CURRENCY` | No | Account base currency | `USD` |
| `GHOST_SAXO_PLATFORM` | No | Platform ID (auto-created if not set) | - |
| `OPERATION` | No | Operation mode | `SYNCSAXO` |
| `CRON` | No | Cron schedule (leave empty for one-time run) | - |
| `LOG_LEVEL` | No | Logging level (DEBUG, INFO, WARN, ERROR) | `INFO` |

### Operation Modes

Set the `OPERATION` environment variable to control behavior:

- **SYNCSAXO** (default): Sync trades and balances from Saxo to Ghostfolio
- **DELETE_ALL_ACTS**: Delete all activities for the Saxo account in Ghostfolio
- **GET_ALL_ACTS**: List all activities for the Saxo account

### Cron Schedules

Examples for `CRON` variable:

```bash
*/15 * * * *   # Every 15 minutes
*/30 * * * *   # Every 30 minutes
0 */6 * * *    # Every 6 hours
0 0 * * *      # Daily at midnight
0 9 * * 1-5    # Weekdays at 9 AM
```

Leave empty for one-time execution.

## Instrument Lookup & Symbol Mapping

### Automatic Instrument Lookup

The sync tool automatically retrieves stock symbols and ISINs from Saxo Bank's API using the instrument's UIC (Universal Instrument Code). This happens transparently for all positions:

```
Position UIC 19756014 → API Lookup → QUBT (Quantum Computing Inc)
Position UIC 25225740 → API Lookup → IONQ (IonQ Inc.)
```

The lookup process:
1. Extracts UIC and AssetType from position data
2. Queries Saxo's `/ref/v1/instruments/details` endpoint
3. Retrieves Symbol, ISIN, Description, and Currency
4. Caches results to minimize API calls
5. Strips exchange suffixes (e.g., `QUBT:xnas` → `QUBT`) for Yahoo Finance compatibility

### Manual Symbol Mapping (Optional)

For instruments where automatic lookup fails or you need custom mappings, use `mapping.yaml`:

```yaml
symbol_mapping:
  VUAA: VUAA.L      # Vanguard S&P 500 (London)
  CSPX: CSPX.L      # iShares Core S&P 500 (London)
  V80A: VNGA80.MI   # Vanguard 80/20 (Milan)
```

Symbol priority: **ISIN** > **Manual Mapping** > **Auto-lookup Symbol** > **Fallback to SAXO{uic}**

## How It Works

### Authentication Flow

1. User authorizes application via OAuth2 (one-time setup)
2. Application receives authorization code
3. Code is exchanged for access token + refresh token
4. Tokens are saved and automatically refreshed before expiry

### Sync Process

1. **Initialize**: Authenticate with Saxo Bank and Ghostfolio
2. **Fetch Positions**: Retrieve open positions (or closed positions if available) from Saxo
3. **Lookup Instruments**: Query Saxo API for symbol/ISIN details for each position
4. **Transform**: Convert Saxo data to Ghostfolio format with proper symbols
5. **Deduplicate**: Check for existing activities using position IDs
6. **Import**: Send new activities to Ghostfolio in chunks
7. **Update Balance**: Sync cash balance to Ghostfolio account

### Data Mapping

Saxo Bank positions are transformed to Ghostfolio activities:

```python
{
  "accountId": "ghostfolio-account-uuid",
  "symbol": "AAPL",              # ISIN preferred, or mapped ticker
  "dataSource": "YAHOO",
  "type": "BUY" | "SELL",
  "date": "2024-01-15T00:00:00.000Z",
  "quantity": 10.0,
  "unitPrice": 185.50,
  "fee": 5.00,
  "currency": "USD",
  "comment": "saxoPositionId=12345",  # For deduplication
  "isin": "US0378331005"              # If available
}
```

### Deduplication

Activities are identified by `saxoPositionId` stored in the comment field. This ensures trades are never imported twice, even if sync runs multiple times.

## Troubleshooting

### OAuth Issues

**Problem**: Browser doesn't open or callback fails

**Solution**:
- Ensure `SAXO_REDIRECT_URI` matches your app configuration in Saxo portal
- For localhost, use `http://localhost:5000/callback`
- Check firewall isn't blocking port 5000

**Problem**: Token expired errors

**Solution**:
- The tool automatically refreshes tokens
- If refresh fails, delete tokens from `.env` and re-run `python saxo_oauth.py`

### Sync Issues

**Problem**: No trades imported

**Solution**:
- Verify `SAXO_ACCOUNT_KEY` is correct
- Check if you have closed positions (open positions aren't synced)
- Review logs with `LOG_LEVEL=DEBUG`

**Problem**: Symbol not found in Yahoo Finance

**Solution**:
- Add symbol mapping to `mapping.yaml`
- Use ISIN if available (more reliable than ticker)
- Consider using `MANUAL` data source for unsupported instruments

### Docker Issues

**Problem**: Container exits immediately

**Solution**:
- Check logs: `docker logs saxo-sync`
- Verify all required environment variables are set
- Ensure tokens are present in `.env` before building

**Problem**: Cron not running

**Solution**:
- Verify `CRON` variable is set in `.env`
- Check cron syntax is valid
- Monitor logs for execution messages

## Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit configuration
nano .env

# Run OAuth flow
python saxo_oauth.py

# Run sync
python main.py
```

### Testing

```bash
# List all activities
OPERATION=GET_ALL_ACTS python main.py

# Delete all activities (careful!)
OPERATION=DELETE_ALL_ACTS python main.py

# Run sync
OPERATION=SYNCSAXO python main.py
```

## Architecture

```
┌─────────────────┐
│   Saxo Bank     │
│   OpenAPI       │
│  (Simulation)   │
└────────┬────────┘
         │
         │ OAuth2 + REST API
         │
┌────────▼────────┐
│  Sync Service   │
│  (Python)       │
│  - OAuth Helper │
│  - SyncSaxo     │
│  - Transforms   │
└────────┬────────┘
         │
         │ POST /api/v1/import
         │ Bearer Token Auth
         │
┌────────▼────────┐
│   Ghostfolio    │
│   REST API      │
│   (Self-hosted) │
└─────────────────┘
```

## API Endpoints Used

### Saxo Bank OpenAPI

- `GET /port/v1/accounts` - Account details
- `GET /port/v1/balances` - Cash balances
- `GET /port/v1/positions/me` - Open positions
- `GET /port/v1/closedpositions/me` - Closed positions (if netting mode allows)
- `GET /ref/v1/instruments/details` - Instrument lookup by UIC
- `POST /token` - OAuth token endpoint

### Ghostfolio API

- `POST /api/v1/auth/anonymous` - Authentication
- `GET/POST /api/v1/account` - Account management
- `GET/POST /api/v1/platform` - Platform management
- `POST /api/v1/import` - Bulk import activities
- `GET/DELETE /api/v1/order` - Activity management

## Security Notes

- Store `.env` file securely - it contains sensitive credentials
- Never commit `.env` to version control
- Use environment-specific tokens (simulation vs production)
- Tokens are automatically refreshed - no need to store passwords
- OAuth2 provides secure, revocable access

## Limitations

- Syncs **open positions** from accounts with End of Day netting mode
- Closed positions synced when account uses Intraday netting mode
- Corporate actions may need manual adjustment
- Instrument lookup requires valid UIC and AssetType
- Some instruments may not have ISINs in Saxo's database
- Saxo simulation account has limited data

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Credits

- Inspired by [ghostfolio-sync](https://github.com/agusalex/ghostfolio-sync) (Interactive Brokers sync)
- Built with [saxo_openapi](https://github.com/hootnot/saxo_openapi) Python library
- Designed for [Ghostfolio](https://github.com/ghostfolio/ghostfolio) portfolio tracker

## Support

- Issues: https://github.com/spinsphere/ghostfolio-saxo-sync/issues
- Saxo Bank Developer Portal: https://www.developer.saxo/
- Ghostfolio Documentation: https://docs.ghostfol.io/

## Changelog

### v1.1.0 (2025-11-16)

- **NEW**: Automatic instrument lookup via Saxo API by UIC
- **NEW**: Support for open positions (End of Day netting accounts)
- **NEW**: Helper scripts: `get_auth.py` and `get_account_key.py`
- **NEW**: Production/simulation environment selection
- Fixed account balance update (added required `id` field)
- Fixed symbol validation (strip exchange suffixes for Yahoo Finance)
- Fixed mapping.yaml parsing issue
- Improved error logging with response details

### v1.0.0 (2024-XX-XX)

- Initial release
- OAuth2 authentication with auto-refresh
- Closed positions sync
- Account balance sync
- Docker support with cron scheduling
- Symbol mapping
- Deduplication support
