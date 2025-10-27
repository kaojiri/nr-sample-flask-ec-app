"""Add indexes for bulk user management fields

Revision ID: add_bulk_user_indexes
Revises: 1571b224fa7b
Create Date: 2025-10-27 13:42:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_bulk_user_indexes'
down_revision = '1571b224fa7b'
branch_labels = None
depends_on = None


def upgrade():
    # Add indexes for better query performance (if they don't exist)
    connection = op.get_bind()
    
    # Check if indexes exist before creating them
    inspector = sa.inspect(connection)
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('users')]
    
    with op.batch_alter_table('users', schema=None) as batch_op:
        if 'idx_users_test_batch' not in existing_indexes:
            batch_op.create_index('idx_users_test_batch', ['test_batch_id'])
        if 'idx_users_is_test' not in existing_indexes:
            batch_op.create_index('idx_users_is_test', ['is_test_user'])


def downgrade():
    # Drop indexes (if they exist)
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('users')]
    
    with op.batch_alter_table('users', schema=None) as batch_op:
        if 'idx_users_is_test' in existing_indexes:
            batch_op.drop_index('idx_users_is_test')
        if 'idx_users_test_batch' in existing_indexes:
            batch_op.drop_index('idx_users_test_batch')