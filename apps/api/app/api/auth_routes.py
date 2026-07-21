import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies import build_auth_service, get_current_user
from app.core.auth import SESSION_COOKIE_NAME, set_session_cookie
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import CredentialsRequest, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/signup", response_model=UserResponse, status_code=201)
def signup(
    credentials: CredentialsRequest,
    response: Response,
    request: Request,
    session: Session = Depends(get_db),
) -> UserResponse:
    user, token = build_auth_service(session).signup(credentials.email, credentials.password)
    set_session_cookie(response, token, settings)
    logger.info(
        "user signed up",
        extra={"request_id": request.state.request_id, "user_id": user.id},
    )
    return UserResponse(id=user.id, email=user.email)


@router.post("/login", response_model=UserResponse)
def login(
    credentials: CredentialsRequest,
    response: Response,
    request: Request,
    session: Session = Depends(get_db),
) -> UserResponse:
    user, token = build_auth_service(session).login(credentials.email, credentials.password)
    set_session_cookie(response, token, settings)
    logger.info(
        "user logged in",
        extra={"request_id": request.state.request_id, "user_id": user.id},
    )
    return UserResponse(id=user.id, email=user.email)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    request: Request,
    session: Session = Depends(get_db),
) -> None:
    build_auth_service(session).logout(request.cookies.get(SESSION_COOKIE_NAME))
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        domain=settings.session_cookie_domain,
        path="/",
    )


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=user.id, email=user.email)
