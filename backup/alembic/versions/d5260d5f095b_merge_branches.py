"""Merge branches

Revision ID: d5260d5f095b
Revises: 0e839789f4fa, 636fda186aff
Create Date: 2025-08-18 08:17:26.792334

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5260d5f095b'
down_revision: Union[str, Sequence[str], None] = ('0e839789f4fa', '636fda186aff')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
