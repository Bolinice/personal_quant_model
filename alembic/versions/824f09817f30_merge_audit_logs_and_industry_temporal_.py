"""merge audit logs and industry temporal fields

Revision ID: 824f09817f30
Revises: b49f9755a8a8, d5e6f7a8b9c0
Create Date: 2026-05-04 08:06:41.236280

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '824f09817f30'
down_revision: Union[str, Sequence[str], None] = ('b49f9755a8a8', 'd5e6f7a8b9c0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
