"""Add explanation column to questions table

Revision ID: 4041aa968d62
Revises: 92fa3315c14e
Create Date: 2025-08-18 13:23:26.379937

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4041aa968d62'
down_revision: Union[str, Sequence[str], None] = 'd5260d5f095b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('questions', sa.Column('explanation', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('questions', 'explanation')
