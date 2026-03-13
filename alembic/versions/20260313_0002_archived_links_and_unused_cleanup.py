"""Add archived links history

Revision ID: 20260313_0002
Revises: 20260313_0001
Create Date: 2026-03-13 15:10:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260313_0002"
down_revision: Union[str, None] = "20260313_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "archived_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("short_code", sa.String(length=64), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "click_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("deletion_reason", sa.String(length=32), nullable=False),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_archived_links_deleted_at"),
        "archived_links",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_archived_links_deletion_reason"),
        "archived_links",
        ["deletion_reason"],
        unique=False,
    )
    op.create_index(
        op.f("ix_archived_links_owner_id"),
        "archived_links",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_archived_links_short_code"),
        "archived_links",
        ["short_code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_archived_links_short_code"), table_name="archived_links")
    op.drop_index(op.f("ix_archived_links_owner_id"), table_name="archived_links")
    op.drop_index(op.f("ix_archived_links_deletion_reason"), table_name="archived_links")
    op.drop_index(op.f("ix_archived_links_deleted_at"), table_name="archived_links")
    op.drop_table("archived_links")
