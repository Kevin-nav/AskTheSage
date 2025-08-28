"""Change Question.correct_answer to Integer

Revision ID: 92fa3315c14e
Revises: d5260d5f095b
Create Date: 2025-08-18 08:24:50.850514

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92fa3315c14e'
down_revision: Union[str, Sequence[str], None] = 'd5260d5f095b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("TRUNCATE TABLE questions CASCADE")
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.alter_column('correct_answer',
               existing_type=sa.String(),
               type_=sa.Integer(),
               postgresql_using='correct_answer::integer')


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("TRUNCATE TABLE questions CASCADE")
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.alter_column('correct_answer',
               existing_type=sa.Integer(),
               type_=sa.String(),
               postgresql_using='correct_answer::text')
