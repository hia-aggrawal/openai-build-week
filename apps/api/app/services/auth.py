import secrets

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApplicationError
from app.core.passwords import hash_password, verify_password
from app.models.user import User, UserSession
from app.repositories.users import UserRepository, UserSessionRepository, session_token_hash


class AuthService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)
        self.sessions = UserSessionRepository(session)

    def signup(self, email: str, password: str) -> tuple[User, str]:
        if self.users.get_by_email(email) is not None:
            raise ApplicationError(
                "EMAIL_ALREADY_REGISTERED", "That email is already registered.", 409
            )
        try:
            user = self.users.add(User(email=email, password_hash=hash_password(password)))
            token = self._create_session(user.id)
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise ApplicationError(
                "EMAIL_ALREADY_REGISTERED", "That email is already registered.", 409
            ) from None
        return user, token

    def login(self, email: str, password: str) -> tuple[User, str]:
        user = self.users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise ApplicationError("INVALID_CREDENTIALS", "Email or password is incorrect.", 401)
        token = self._create_session(user.id)
        self.session.commit()
        return user, token

    def authenticate(self, token: str | None) -> User:
        if not token:
            raise ApplicationError("AUTHENTICATION_REQUIRED", "Sign in to continue.", 401)
        user_session = self.sessions.get_active(token)
        if user_session is None:
            raise ApplicationError("AUTHENTICATION_REQUIRED", "Sign in to continue.", 401)
        user_session.expires_at = UserSession.expires_in(self.settings.session_ttl_seconds)
        self.session.commit()
        return user_session.user

    def logout(self, token: str | None) -> None:
        if token:
            self.sessions.delete(token)
            self.session.commit()

    def _create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        self.sessions.add(
            UserSession(
                user_id=user_id,
                token_hash=session_token_hash(token),
                expires_at=UserSession.expires_in(self.settings.session_ttl_seconds),
            )
        )
        return token
