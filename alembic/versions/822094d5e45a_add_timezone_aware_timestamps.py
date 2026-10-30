"""add_timezone_aware_timestamps

Revision ID: 822094d5e45a
Revises: b1c2d3e4f5a6
Create Date: 2026-10-14 12:32:04.326894

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '822094d5e45a'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add timezone-aware timestamps."""
    # For PostgreSQL: alter column to use timezone-aware timestamp
    # For SQLite: this is a no-op since SQLite doesn't have native timezone support
    # but the ORM will handle timezone-aware datetimes correctly

    # Check if we're using PostgreSQL
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # PostgreSQL: alter column type to TIMESTAMP WITH TIME ZONE
        op.alter_column('prediction_records', 'created_at',
                       type_=sa.DateTime(timezone=True),
                       existing_type=sa.DateTime(timezone=False),
                       existing_nullable=True)
        op.alter_column('retention_recommendations', 'created_at',
                       type_=sa.DateTime(timezone=True),
                       existing_type=sa.DateTime(timezone=False),
                       existing_nullable=True)
    else:
        # SQLite: just ensure the columns exist (they already do)
        # The ORM will handle timezone-aware datetimes correctly
        pass


def downgrade() -> None:
    """Downgrade schema - remove timezone awareness."""
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.alter_column('prediction_records', 'created_at',
                       type_=sa.DateTime(timezone=False),
                       existing_type=sa.DateTime(timezone=True),
                       existing_nullable=True)
        op.alter_column('retention_recommendations', 'created_at',
                       type_=sa.DateTime(timezone=False),
                       existing_type=sa.DateTime(timezone=True),
                       existing_nullable=True)
    else:
        # SQLite: no-op
        pass
