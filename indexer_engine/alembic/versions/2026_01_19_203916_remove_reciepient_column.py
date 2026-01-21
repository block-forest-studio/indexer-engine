"""remove_reciepient_column

Revision ID: 2026_01_19_203916
Revises: 2026_01_16_212529
Create Date: 2026-01-19 20:39:20.733342

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2026_01_19_203916'
down_revision: Union[str, Sequence[str], None] = '2026_01_16_212529'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('uniswap_v4_wallet_swaps', 'recipient', schema='domain')

def downgrade() -> None:
    op.add_column(
        'uniswap_v4_wallet_swaps',
        sa.Column('recipient', postgresql.BYTEA(), nullable=True),
        schema='domain',
    )
