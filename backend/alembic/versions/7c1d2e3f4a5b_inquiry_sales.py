"""link inquiries to the sale they became

Revision ID: 7c1d2e3f4a5b
Revises: 42492ef288f2
Create Date: 2026-09-23 17:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7c1d2e3f4a5b"
down_revision: str | None = "42492ef288f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("inquiries", schema=None) as batch_op:
        batch_op.add_column(sa.Column("order_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_inquiries_order_id"), ["order_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_inquiries_order_id_orders",
            "orders",
            ["order_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("inquiries", schema=None) as batch_op:
        batch_op.drop_constraint("fk_inquiries_order_id_orders", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_inquiries_order_id"))
        batch_op.drop_column("order_id")
