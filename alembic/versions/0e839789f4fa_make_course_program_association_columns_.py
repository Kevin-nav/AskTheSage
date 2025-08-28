"""Make course_program_association columns non-nullable and add pk

Revision ID: 0e839789f4fa
Revises: 636fda186aff
Create Date: 2025-08-18 08:16:09.310847

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0e839789f4fa'
down_revision: Union[str, Sequence[str], None] = 'c4e391ed18e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('course_program_association', schema=None) as batch_op:
        batch_op.alter_column('course_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.alter_column('program_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.create_primary_key(
            "pk_course_program_association",
            ["course_id", "program_id"]
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('course_program_association', schema=None) as batch_op:
        batch_op.drop_constraint("pk_course_program_association", type_="primary")
        batch_op.alter_column('program_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('course_id',
               existing_type=sa.INTEGER(),
               nullable=True)
