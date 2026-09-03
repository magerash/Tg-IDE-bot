"""Auth helpers for the web dashboard: token + Telegram Mini App initData."""
import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qsl

logger = logging.getLogger("bot.webauth")

INIT_DATA_MAX_AGE = 86400  # reject initData older than 24h


def validate_init_data(init_data: str, bot_token: str) -> int | None:
    """Verify Telegram WebApp initData HMAC signature.

    Returns the Telegram user id on success, None on any failure.
    Spec: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash", "")
        if not received_hash:
            return None
        check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, received_hash):
            logger.debug("initData hash mismatch")
            return None
        if time.time() - int(pairs.get("auth_date", 0)) > INIT_DATA_MAX_AGE:
            logger.debug("initData expired")
            return None
        user = json.loads(pairs.get("user", "{}"))
        uid = user.get("id")
        return int(uid) if uid else None
    except Exception as e:
        logger.debug("initData validation error: %s", e)
        return None


def check_token(request_bearer: str, request_query_token: str, web_token: str) -> bool:
    """Timing-safe token comparison. Empty configured token never matches."""
    if not web_token:
        return False
    return (
        hmac.compare_digest(request_bearer, web_token)
        or hmac.compare_digest(request_query_token, web_token)
    )


# --- Scoped tokens -----------------------------------------------------------
# The refine view runs on one of these instead of the full credential, so the
# server (not the page) is what refuses /api/sh and friends. Format:
#     <scope>.<expiry-unix>.<hex mac>
# Read from the Authorization header ONLY — never the ?token= query form, which
# would put the token in every proxy and tunnel access log.

SCOPE_TTL = 12 * 3600      # < INIT_DATA_MAX_AGE, so a scope can't outlive its minter
_SCOPE_INFO = b"tgide-scope-v1"


def _scope_key(secret: str) -> bytes | None:
    """Derive a subkey so scope tokens never share key material with initData,
    which HMACs the same bot token under a different construction."""
    if not secret:
        return None            # same rule as check_token: no secret, no validation
    return hmac.new(_SCOPE_INFO, secret.encode(), hashlib.sha256).digest()


def make_scoped_token(secret: str, scope: str, ttl: int = SCOPE_TTL) -> str:
    """Mint a scope-limited bearer. Returns "" when no secret is configured."""
    key = _scope_key(secret)
    if not key or not scope:
        return ""
    exp = int(time.time()) + int(ttl)
    mac = hmac.new(key, f"{scope}.{exp}".encode(), hashlib.sha256).hexdigest()
    return f"{scope}.{exp}.{mac}"


def verify_scoped_token(token: str, secret: str, scope: str) -> bool:
    """True only for an unexpired token minted for exactly this scope.

    The scope is inside the MAC: signing the expiry alone would let anyone
    rewrite the prefix and promote a refine token to something else.
    """
    key = _scope_key(secret)
    if not key or not token or not scope:
        return False
    try:
        got_scope, exp_s, mac = token.split(".", 2)
    except ValueError:
        return False           # wrong arity — not one of ours
    if not hmac.compare_digest(got_scope, scope):
        return False
    try:
        exp = int(exp_s)
    except ValueError:
        return False
    if exp < time.time():
        logger.debug("scoped token expired")
        return False
    expected = hmac.new(key, f"{got_scope}.{exp}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, mac)
