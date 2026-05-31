import secrets
from urllib.parse import urlencode

import httpx

from admin_auth.core.config import settings

_GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO = "https://www.googleapis.com/oauth2/v3/userinfo"

_pending_states: dict[str, bool] = {}


def is_configured() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def build_login_url() -> str:
    state = secrets.token_urlsafe(24)
    _pending_states[state] = True
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{_GOOGLE_AUTH}?{urlencode(params)}"


def consume_state(state: str) -> bool:
    return _pending_states.pop(state, False)


async def exchange_code(code: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        token_res = await client.post(
            _GOOGLE_TOKEN,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        token_res.raise_for_status()
        tokens = token_res.json()
        user_res = await client.get(
            _GOOGLE_USERINFO,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        user_res.raise_for_status()
        return user_res.json()


def email_allowed(email: str) -> bool:
    domain = (settings.GOOGLE_ALLOWED_EMAIL_DOMAIN or "").strip().lower()
    if not domain:
        return True
    return email.lower().endswith("@" + domain)
