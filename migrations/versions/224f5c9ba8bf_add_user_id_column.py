"""Add user_id column

Revision ID: 224f5c9ba8bf
Revises: 
Create Date: 2025-01-30 16:24:04.576085

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '224f5c9ba8bf'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column('atm_events', sa.Column('user_id', sa.String(), nullable=True))

def downgrade():
    op.drop_column('atm_events', 'user_id')