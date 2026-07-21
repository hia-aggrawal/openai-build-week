"""add lecture media hash

Revision ID: 7ad9d3f61b42
Revises: 2f4c7b9a1d03
Create Date: 2026-07-21 14:00:00
"""

from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "7ad9d3f61b42"
down_revision: str | None = "2f4c7b9a1d03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _legacy_media_hash(lecture_id: str, media_path: str) -> str:
    digest = sha256()
    try:
        with Path(media_path).open("rb") as media:
            while chunk := media.read(1024 * 1024):
                digest.update(chunk)
    except OSError:
        digest.update(f"missing-legacy-media:{lecture_id}".encode())
    return digest.hexdigest()


def upgrade() -> None:
    op.add_column("lectures", sa.Column("media_hash", sa.String(length=64), nullable=True))
    connection = op.get_bind()
    lectures = connection.execute(sa.text("SELECT id, media_path FROM lectures")).mappings()
    for lecture in lectures:
        connection.execute(
            sa.text("UPDATE lectures SET media_hash = :media_hash WHERE id = :lecture_id"),
            {
                "media_hash": _legacy_media_hash(lecture["id"], lecture["media_path"]),
                "lecture_id": lecture["id"],
            },
        )
    with op.batch_alter_table("lectures") as batch_op:
        batch_op.alter_column("media_hash", existing_type=sa.String(length=64), nullable=False)
        batch_op.create_index(
            "ix_lectures_user_media_hash", ["user_id", "media_hash"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("lectures") as batch_op:
        batch_op.drop_index("ix_lectures_user_media_hash")
        batch_op.drop_column("media_hash")
