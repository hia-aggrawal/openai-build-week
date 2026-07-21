"""add user auth and lecture ownership

Revision ID: 2f4c7b9a1d03
Revises: 8c963e1561d4
Create Date: 2026-07-19 18:00:00
"""

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "2f4c7b9a1d03"
down_revision: str | None = "8c963e1561d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.execute(
        sa.text(
            "INSERT INTO users (id, email, password_hash, created_at) "
            "VALUES (:id, :email, :password_hash, :created_at)"
        ).bindparams(
            id=LEGACY_USER_ID,
            email="legacy-migration@invalid.local",
            password_hash="disabled",
            created_at=datetime(2026, 7, 19, tzinfo=timezone.utc),
        )
    )

    op.add_column("lectures", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.execute(sa.text("UPDATE lectures SET user_id = :user_id").bindparams(user_id=LEGACY_USER_ID))
    with op.batch_alter_table("lectures") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.create_foreign_key("fk_lectures_user_id", "users", ["user_id"], ["id"])
        batch_op.create_index("ix_lectures_user_id", ["user_id"], unique=False)

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_user_sessions_token_hash"),
        "user_sessions",
        ["token_hash"],
        unique=True,
    )
    op.create_index(op.f("ix_user_sessions_user_id"), "user_sessions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_sessions_user_id"), table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_token_hash"), table_name="user_sessions")
    op.drop_table("user_sessions")
    with op.batch_alter_table("lectures") as batch_op:
        batch_op.drop_index("ix_lectures_user_id")
        batch_op.drop_constraint("fk_lectures_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
