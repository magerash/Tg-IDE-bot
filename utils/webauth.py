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
