"""remove customer_id plaintext column

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-25 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - remove plaintext customer_id column."""
    # Drop composite index first (depends on customer_id column)
    op.drop_index(op.f('ix_prediction_records_created_at_customer_id'), table_name='prediction_records')
    # Drop index on customer_id column
    op.drop_index(op.f('ix_prediction_records_customer_id'), table_name='prediction_records')
    # Drop customer_id column
    op.drop_column('prediction_records', 'customer_id')


def downgrade() -> None:
    """Downgrade schema - restore plaintext customer_id column."""
    # Add customer_id column back
    op.add_column('prediction_records',
        sa.Column('customer_id', sa.String(), nullable=False, server_default='')
    )
    # Recreate index on customer_id
    op.create_index(op.f('ix_prediction_records_customer_id'), 'prediction_records', ['customer_id'], unique=False)
    # Recreate composite index
    op.create_index(op.f('ix_prediction_records_created_at_customer_id'), 'prediction_records', ['created_at', 'customer_id'], unique=False)
