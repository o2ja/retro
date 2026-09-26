"""background-free watch image per product

Revision ID: 8d2e3f4a5b6c
Revises: 7c1d2e3f4a5b
Create Date: 2026-09-23 18:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8d2e3f4a5b6c"
down_revision: str | None = "7c1d2e3f4a5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(sa.Column("cutout_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_column("cutout_url")
