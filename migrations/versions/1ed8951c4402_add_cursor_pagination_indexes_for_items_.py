"""Add cursor pagination indexes for items table

Revision ID: 1ed8951c4402
Revises: d5e84b9df44d
Create Date: 2025-08-13 16:33:33.418390

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1ed8951c4402'
down_revision = 'd5e84b9df44d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop existing indexes that will be replaced with cursor pagination optimized versions
    op.drop_index("idx_items_published_at", table_name="items")
    op.drop_index("idx_items_source_published", table_name="items")
    
    # Create new composite indexes for cursor pagination
    # Index for global pagination: (published_at DESC, id DESC)
    op.create_index(
        "idx_items_cursor_pagination",
        "items",
        [sa.literal_column("published_at DESC"), sa.literal_column("id DESC")],
        unique=False,
        postgresql_using="btree"
    )
    
    # Index for source-specific pagination: (source_id, published_at DESC, id DESC)
    op.create_index(
        "idx_items_source_cursor_pagination",
        "items",
        ["source_id", sa.literal_column("published_at DESC"), sa.literal_column("id DESC")],
        unique=False,
        postgresql_using="btree"
    )


def downgrade() -> None:
    # Drop the cursor pagination indexes
    op.drop_index("idx_items_source_cursor_pagination", table_name="items")
    op.drop_index("idx_items_cursor_pagination", table_name="items")
    
    # Recreate the original simple indexes
    op.create_index("idx_items_published_at", "items", ["published_at"], unique=False)
    op.create_index("idx_items_source_published", "items", ["source_id", "published_at"], unique=False)