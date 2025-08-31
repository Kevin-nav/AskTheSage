"""Merge branches to resolve multiple heads

Revision ID: 109ca0ff77c0
Revises: 46c04043db9e, a6bf4eeb6813
Create Date: 2025-08-31 14:03:44.945508

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '109ca0ff77c0'
down_revision: Union[str, Sequence[str], None] = ('46c04043db9e', 'a6bf4eeb6813')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
