from fastapi import Response

from app.core.config import Settings


SESSION_COOKIE_NAME = "studyflow_session"


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        domain=settings.session_cookie_domain,
        path="/",
    )
