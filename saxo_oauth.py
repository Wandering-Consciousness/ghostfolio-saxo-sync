"""
OAuth2 authentication helper for Saxo Bank OpenAPI
"""

import base64
import json
import logging
import os
import time
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests

logger = logging.getLogger(__name__)


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback"""

    authorization_code = None

    def do_GET(self):
        """Handle GET request with authorization code"""
        query = urlparse(self.path).query
        params = parse_qs(query)

        if 'code' in params:
            OAuthCallbackHandler.authorization_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <head><title>Authorization Successful</title></head>
                <body>
                    <h1>Authorization Successful!</h1>
                    <p>You can close this window and return to the application.</p>
                </body>
                </html>
            """)
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            error = params.get('error', ['Unknown error'])[0]
            self.wfile.write(f"""
                <html>
                <head><title>Authorization Failed</title></head>
                <body>
                    <h1>Authorization Failed</h1>
                    <p>Error: {error}</p>
                </body>
                </html>
            """.encode())

    def log_message(self, format, *args):
        """Suppress request logging"""
        pass


class SaxoOAuth:
    """Handles OAuth2 authentication for Saxo Bank OpenAPI"""

    def __init__(self, app_key, app_secret, redirect_uri, auth_endpoint, token_endpoint):
        self.app_key = app_key
        self.app_secret = app_secret
        self.redirect_uri = redirect_uri
        self.auth_endpoint = auth_endpoint
        self.token_endpoint = token_endpoint

        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None

    def get_authorization_url(self, state="random_state"):
        """Generate authorization URL for user to visit"""
        params = {
            'response_type': 'code',
            'client_id': self.app_key,
            'redirect_uri': self.redirect_uri,
            'state': state
        }
        return f"{self.auth_endpoint}?{urlencode(params)}"

    def get_authorization_code_interactive(self, port=5000):
        """
        Open browser for user authorization and capture the code
        Returns the authorization code
        """
        logger.info("Starting OAuth authorization flow...")

        # Start local server to receive callback
        server_address = ('', port)
        httpd = HTTPServer(server_address, OAuthCallbackHandler)

        # Open browser for authorization
        auth_url = self.get_authorization_url()
        logger.info(f"Opening browser for authorization: {auth_url}")
        webbrowser.open(auth_url)

        logger.info(f"Waiting for callback on http://localhost:{port}/callback")

        # Wait for one request (the callback)
        httpd.handle_request()

        if OAuthCallbackHandler.authorization_code:
            logger.info("Authorization code received successfully")
            return OAuthCallbackHandler.authorization_code
        else:
            raise Exception("Failed to receive authorization code")

    def exchange_code_for_token(self, authorization_code):
        """
        Exchange authorization code for access token and refresh token
        """
        logger.info("Exchanging authorization code for tokens...")

        # Create Basic Auth header
        credentials = f"{self.app_key}:{self.app_secret}"
        b64_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            'Authorization': f'Basic {b64_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'grant_type': 'authorization_code',
            'code': authorization_code,
            'redirect_uri': self.redirect_uri
        }

        try:
            response = requests.post(self.token_endpoint, headers=headers, data=data)
            response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data['access_token']
            self.refresh_token = token_data['refresh_token']

            # Calculate expiry time
            expires_in = token_data.get('expires_in', 1200)  # Default 20 minutes
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in)

            logger.info("Tokens obtained successfully")
            logger.info(f"Access token expires at: {self.token_expiry}")

            return {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'token_expiry': self.token_expiry.isoformat()
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to exchange code for token: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            raise

    def refresh_access_token(self):
        """
        Refresh the access token using the refresh token
        """
        if not self.refresh_token:
            raise Exception("No refresh token available")

        logger.info("Refreshing access token...")

        # Create Basic Auth header
        credentials = f"{self.app_key}:{self.app_secret}"
        b64_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            'Authorization': f'Basic {b64_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
        }

        try:
            response = requests.post(self.token_endpoint, headers=headers, data=data)
            response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data['access_token']
            self.refresh_token = token_data.get('refresh_token', self.refresh_token)

            # Calculate expiry time
            expires_in = token_data.get('expires_in', 1200)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in)

            logger.info("Access token refreshed successfully")
            logger.info(f"New token expires at: {self.token_expiry}")

            return {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'token_expiry': self.token_expiry.isoformat()
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to refresh token: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            raise

    def is_token_expired(self):
        """Check if the access token is expired or about to expire"""
        if not self.token_expiry:
            return True

        # Consider token expired if less than 5 minutes remaining
        return datetime.now() >= (self.token_expiry - timedelta(minutes=5))

    def get_valid_token(self):
        """
        Get a valid access token, refreshing if necessary
        """
        if not self.access_token:
            raise Exception("No access token available. Please authorize first.")

        if self.is_token_expired():
            logger.info("Token expired or expiring soon, refreshing...")
            self.refresh_access_token()

        return self.access_token

    def load_tokens_from_env(self):
        """Load tokens from environment variables"""
        self.access_token = os.getenv('SAXO_ACCESS_TOKEN')
        self.refresh_token = os.getenv('SAXO_REFRESH_TOKEN')

        expiry_str = os.getenv('SAXO_TOKEN_EXPIRY')
        if expiry_str:
            try:
                self.token_expiry = datetime.fromisoformat(expiry_str)
            except ValueError:
                logger.warning("Invalid token expiry format in environment")
                self.token_expiry = None

        if self.access_token:
            logger.info("Loaded tokens from environment variables")
            return True
        return False

    def save_tokens_to_file(self, filepath='.env'):
        """
        Save tokens to .env file (updates existing file)
        """
        try:
            # Read existing .env file
            env_lines = []
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    env_lines = f.readlines()

            # Update token values
            token_vars = {
                'SAXO_ACCESS_TOKEN': self.access_token,
                'SAXO_REFRESH_TOKEN': self.refresh_token,
                'SAXO_TOKEN_EXPIRY': self.token_expiry.isoformat() if self.token_expiry else ''
            }

            updated_lines = []
            updated_keys = set()

            for line in env_lines:
                key = line.split('=')[0] if '=' in line else None
                if key in token_vars:
                    updated_lines.append(f"{key}={token_vars[key]}\n")
                    updated_keys.add(key)
                else:
                    updated_lines.append(line)

            # Add missing keys
            for key, value in token_vars.items():
                if key not in updated_keys:
                    updated_lines.append(f"{key}={value}\n")

            # Write back to file
            with open(filepath, 'w') as f:
                f.writelines(updated_lines)

            logger.info(f"Tokens saved to {filepath}")

        except Exception as e:
            logger.error(f"Failed to save tokens to file: {e}")


def perform_oauth_flow():
    """
    Perform complete OAuth flow and save tokens
    """
    app_key = os.getenv('SAXO_APP_KEY')
    app_secret = os.getenv('SAXO_APP_SECRET')
    redirect_uri = os.getenv('SAXO_REDIRECT_URI', 'http://localhost:5000/callback')

    auth_endpoint = 'https://sim.logonvalidation.net/authorize'
    token_endpoint = 'https://sim.logonvalidation.net/token'

    if not app_key or not app_secret:
        raise ValueError("SAXO_APP_KEY and SAXO_APP_SECRET must be set in environment")

    oauth = SaxoOAuth(app_key, app_secret, redirect_uri, auth_endpoint, token_endpoint)

    # Try to load existing tokens
    if oauth.load_tokens_from_env():
        try:
            # Try to refresh if expired
            if oauth.is_token_expired():
                oauth.refresh_access_token()
            return oauth
        except Exception as e:
            logger.warning(f"Failed to use existing tokens: {e}")
            logger.info("Will perform new authorization flow")

    # Perform new authorization
    port = int(urlparse(redirect_uri).port or 5000)
    code = oauth.get_authorization_code_interactive(port)
    oauth.exchange_code_for_token(code)
    oauth.save_tokens_to_file()

    return oauth


if __name__ == "__main__":
    # Test OAuth flow
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    from dotenv import load_dotenv
    load_dotenv()

    oauth = perform_oauth_flow()
    print(f"Access token: {oauth.access_token[:20]}...")
    print(f"Refresh token: {oauth.refresh_token[:20]}...")
    print(f"Token expiry: {oauth.token_expiry}")
