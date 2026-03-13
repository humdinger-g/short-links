"""Initial schema

Revision ID: 20260313_0001
Revises:
Create Date: 2026-03-13 13:45:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260313_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("short_code", sa.String(length=64), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "click_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_links_expires_at"), "links", ["expires_at"], unique=False)
    op.create_index(op.f("ix_links_original_url"), "links", ["original_url"], unique=False)
    op.create_index(op.f("ix_links_owner_id"), "links", ["owner_id"], unique=False)
    op.create_index(op.f("ix_links_short_code"), "links", ["short_code"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_links_short_code"), table_name="links")
    op.drop_index(op.f("ix_links_owner_id"), table_name="links")
    op.drop_index(op.f("ix_links_original_url"), table_name="links")
    op.drop_index(op.f("ix_links_expires_at"), table_name="links")
    op.drop_table("links")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
