"""Add partial unique index for active quiz sessions

Revision ID: 5ac362326f27
Revises: 10f5785b27d7
Create Date: 2025-08-28 17:46:38.700274

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ac362326f27'
down_revision: Union[str, Sequence[str], None] = '10f5785b27d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        'ix_one_active_quiz_per_user',
        'quiz_sessions',
        ['user_id'],
        unique=True,
        postgresql_where=sa.text('is_completed = FALSE')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_one_active_quiz_per_user', table_name='quiz_sessions')
