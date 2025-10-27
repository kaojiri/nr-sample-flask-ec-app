"""Add is_admin field to users

Revision ID: 6cec384179da
Revises: add_bulk_user_indexes
Create Date: 2025-10-27 07:02:47.120849

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6cec384179da'
down_revision = 'add_bulk_user_indexes'
branch_labels = None
depends_on = None


def upgrade():
    # Add is_admin field to users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    # Remove is_admin field from users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_admin')
