"""Add created_at index and composite index for retention cleanup

Revision ID: b1c2d3e4f5a6
Revises: a566c8ed6709
Create Date: 2026-10-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'a566c8ed6709'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add indexes for retention cleanup performance."""
    # Add index on created_at for efficient retention queries
    op.create_index(
        op.f('ix_prediction_records_created_at'),
        'prediction_records',
        ['created_at'],
        unique=False
    )

    # Add composite index for efficient retention queries with customer_id
    op.create_index(
        op.f('ix_prediction_records_created_at_customer_id'),
        'prediction_records',
        ['created_at', 'customer_id'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema - remove added indexes."""
    op.drop_index(
        op.f('ix_prediction_records_created_at_customer_id'),
        table_name='prediction_records'
    )
    op.drop_index(
        op.f('ix_prediction_records_created_at'),
        table_name='prediction_records'
    )
