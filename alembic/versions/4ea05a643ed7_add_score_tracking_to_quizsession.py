"""Add score tracking to QuizSession

Revision ID: 4ea05a643ed7
Revises: 4041aa968d62
Create Date: 2025-08-18 20:20:23.020631

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4ea05a643ed7'
down_revision: Union[str, Sequence[str], None] = '4041aa968d62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('quiz_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('questions_count', sa.Integer(), nullable=False, server_default='10'))
        batch_op.add_column(sa.Column('correct_answers', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('quiz_sessions', schema=None) as batch_op:
        batch_op.drop_column('correct_answers')
        batch_op.drop_column('questions_count')