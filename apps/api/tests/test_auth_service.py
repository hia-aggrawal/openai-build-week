from datetime import timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.time import utc_now
from app.db.session import Base
from app.models.user import UserSession
from app.repositories.users import session_token_hash
from app.services.auth import AuthService


def test_authentication_renews_and_persists_session_expiry() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    settings = Settings(_env_file=None, session_ttl_seconds=3600)

    with Session(engine) as session:
        _, token = AuthService(session, settings).signup(
            "sliding@example.com", "test-password"
        )

    with Session(engine) as session:
        stored_session = session.scalar(
            select(UserSession).where(UserSession.token_hash == session_token_hash(token))
        )
        assert stored_session is not None
        stored_session.expires_at = utc_now() + timedelta(seconds=5)
        session.commit()
        original_expiry = stored_session.expires_at

        renewed_at = utc_now()
        user = AuthService(session, settings).authenticate(token)
        session.refresh(stored_session)

        assert user.email == "sliding@example.com"
        assert stored_session.expires_at > original_expiry
        comparable_renewed_at = renewed_at.replace(tzinfo=stored_session.expires_at.tzinfo)
        renewed_lifetime = stored_session.expires_at - comparable_renewed_at
        assert timedelta(seconds=3599) <= renewed_lifetime <= timedelta(seconds=3601)

    with Session(engine) as session:
        persisted_expiry = session.scalar(
            select(UserSession.expires_at).where(
                UserSession.token_hash == session_token_hash(token)
            )
        )
        assert persisted_expiry is not None
        assert persisted_expiry > original_expiry
