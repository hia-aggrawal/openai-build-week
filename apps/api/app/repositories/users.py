from hashlib import sha256

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.core.time import utc_now
from app.models.user import User, UserSession


def session_token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))


class UserSessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, user_session: UserSession) -> UserSession:
        self.session.add(user_session)
        self.session.flush()
        return user_session

    def get_active(self, token: str) -> UserSession | None:
        statement = (
            select(UserSession)
            .options(joinedload(UserSession.user))
            .where(
                UserSession.token_hash == session_token_hash(token),
                UserSession.expires_at > utc_now(),
            )
        )
        return self.session.scalar(statement)

    def get_user(self, token: str) -> User | None:
        user_session = self.get_active(token)
        return user_session.user if user_session is not None else None

    def delete(self, token: str) -> None:
        self.session.execute(
            delete(UserSession).where(UserSession.token_hash == session_token_hash(token))
        )
