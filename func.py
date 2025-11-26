import io
import json
import logging
import time
import hashlib
import jwt
import requests
from fdk import response

# Global token cache and app config
auth_cache = {}
oauth_apps = {}

# -----------------------------------------------------------------------------
# Initialization
# -----------------------------------------------------------------------------
def init_context(context):
    """Initialize context variables from OCI Function configuration."""
    if len(oauth_apps) < 1:
        try:
            logging.info("Initializing context...")
            oauth_apps['iam'] = {
                'TOKEN_URL': context['TOKEN_URL'],
                'SCOPE': context['SCOPE']
            }
        except Exception as ex:
            logging.error(f"Failed to initialize context: {ex}")
            raise

# -----------------------------------------------------------------------------
# Header extraction and cache helpers
# -----------------------------------------------------------------------------
def extract_auth_header(body):
    """Extract Authorization header value from the input payload."""
    auth_header = (
        body.get("token") or
        body.get("data", {}).get("Authorization") or
        body.get("Authorization")
    )
    if not auth_header or not auth_header.startswith("Basic "):
        raise ValueError("Missing or invalid Authorization header")

    logging.info(f"Auth Header: {auth_header}")
    return auth_header


def get_cache_key(auth_header: str) -> str:
    """Generate a unique cache key based on Authorization header."""
    cache_key = hashlib.sha256(auth_header.encode("utf-8")).hexdigest()

    logging.info(f"Cache Key: {cache_key}")
    return cache_key


def get_cached_token(cache_key: str):
    """Retrieve cached token if still valid."""
    token_data = auth_cache.get(cache_key)
    if not token_data:
        logging.error(f"Token data empty or None: {token_data}")
        return None

    token, exp = token_data.get("token"), token_data.get("exp")
    if exp and time.time() < exp:
        logging.info("Using cached valid token")
        return token
    else:
        logging.info("Cached token expired or invalid")
        return None

# -----------------------------------------------------------------------------
# Token handling
# -----------------------------------------------------------------------------
def decode_jwt_expiry(token):
    """Decode JWT token to get expiry (exp) timestamp."""
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        return decoded.get("exp")
    except Exception as ex:
        logging.warning(f"Failed to decode JWT expiry: {ex}")
        return None


def fetch_new_token(token_url, scope, auth_header):
    """Fetch new access token from OCI IAM token endpoint."""
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": auth_header
    }
    payload = {"grant_type": "client_credentials", "scope": scope}

    response_obj = requests.post(token_url, headers=headers, data=payload, timeout=10)
    if response_obj.status_code != 200:
        raise RuntimeError(f"Token request failed: {response_obj.text}")

    token_json = response_obj.json()
    access_token = token_json.get("access_token")
    if not access_token:
        raise ValueError("No access token returned from OCI IAM")
    return access_token


def cache_token(cache_key, token, exp):
    """Cache the token with expiry timestamp."""
    expiry = exp or (time.time() + 300)  # fallback 5 minutes
    auth_cache[cache_key] = {"token": token, "exp": expiry}
    logging.info("New token cached successfully")

# -----------------------------------------------------------------------------
# Response utility
# -----------------------------------------------------------------------------
def build_response(ctx, data, status=200):
    """Helper to standardize HTTP responses."""
    return response.Response(
        ctx,
        response_data=json.dumps(data),
        status_code=status,
        headers={"Content-Type": "application/json"}
    )

# -----------------------------------------------------------------------------
# Main handler
# -----------------------------------------------------------------------------
def handler(ctx, data: io.BytesIO = None):
    """OCI Function handler entry point."""
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger()

    try:
        init_context(dict(ctx.Config()))

        body = json.loads(data.getvalue())
        log.info(f"Function payload: {body}")

        # Step 1: Extract Authorization header
        auth_header = extract_auth_header(body)
        cache_key = get_cache_key(auth_header)
        log.info(f"Cache Key 2: {cache_key}")

        # Step 2: Check cache for valid token
        cached_token = get_cached_token(cache_key)
        scope = oauth_apps['iam']['SCOPE']
        log.info(f"Cached Token: {cached_token}")
        if cached_token:
            token_response = {
            "active": True,
            "scope": scope,
            "context": {
                "token_response": f"Bearer {cached_token}"
            }
            }
            log.info("Used Cached Token")
            return build_response(ctx, token_response)

        # Step 3: Fetch new token
        token_url = oauth_apps['iam']['TOKEN_URL']
        new_token = fetch_new_token(token_url, scope, auth_header)
        log.info(f"New Token: {new_token}")

        # Step 4: Decode expiry and cache
        exp = decode_jwt_expiry(new_token)
        log.info(f"Token Expiry: {exp}")
        cache_token(cache_key, new_token, exp)

        # Step 5: Build response
        token_response = {
            "active": True,
            "scope": scope,
            "context": {
                "token_response": f"Bearer {new_token}"
            }
        }
        log.info("Token generation successful")
        return build_response(ctx, token_response)

    except ValueError as ve:
        log.error(f"Validation error: {ve}")
        return build_response(ctx, {"error": str(ve)}, 400)

    except Exception as ex:
        log.error(f"Unhandled exception: {ex}")
        return build_response(ctx, {"error": str(ex)}, 500)
