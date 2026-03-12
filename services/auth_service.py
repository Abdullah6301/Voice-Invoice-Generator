"""
Invoice Generator Auth Service
JWT token creation and verification for cookie-based auth.
"""

import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from backend.config import settings

SECRET = settings.SECRET_KEY
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30
COOKIE_NAME = "bv_token"


def create_token(contractor_id: int, email: str) -> str:
    """Create a JWT token for a contractor."""
    payload = {
        "sub": str(contractor_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def verify_token(token: str) -> dict | None:
    """Verify and decode a JWT token. Returns payload or None."""
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def get_current_user(request: Request) -> dict | None:
    """Extract user info from the request cookie."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    payload = verify_token(token)
    if payload and "sub" in payload:
        payload["sub"] = int(payload["sub"])
    return payload


def require_auth(request: Request) -> dict:
    """Get current user or raise 401."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def set_auth_cookie(response, contractor_id: int, email: str):
    """Set the auth JWT cookie on a response."""
    token = create_token(contractor_id, email)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=TOKEN_EXPIRE_DAYS * 86400,
    )
    return response


def clear_auth_cookie(response):
    """Remove the auth cookie."""
    response.delete_cookie(key=COOKIE_NAME)
    return response
