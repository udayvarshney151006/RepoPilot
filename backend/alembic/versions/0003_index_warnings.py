"""Persist bounded indexing warnings for skipped oversized/generated files."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("repositories", sa.Column("index_warnings", sa.JSON, nullable=False, server_default="[]"))
    with op.batch_alter_table("repositories") as batch:
        batch.alter_column("index_warnings", server_default=None)


def downgrade():
    op.drop_column("repositories", "index_warnings")
