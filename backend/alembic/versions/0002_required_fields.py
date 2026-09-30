"""Enforce non-null required data for schemas created by the initial migration.

Revision ID: 0002
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

FIELDS = {
    "users": "name created_at",
    "repositories": "name source_url root_path status file_count chunk_count languages embedding_provider created_at",
    "repository_files": "path language content line_count size_bytes symbols imports created_at",
    "code_chunks": "file_path language symbol_name symbol_type start_line end_line content embedding created_at",
    "conversations": "title created_at",
    "messages": "role content citations metrics created_at",
    "indexing_jobs": "kind status stage progress created_at",
    "agent_runs": "task max_steps status summary test_results created_at",
    "agent_steps": "tool arguments result duration_ms success summary created_at",
    "evaluation_datasets": "name cases created_at",
    "evaluation_runs": "k cases status metrics results created_at",
}


def upgrade():
    for table, fields in FIELDS.items():
        with op.batch_alter_table(table) as batch:
            for name in fields.split():
                batch.alter_column(name, nullable=False)


def downgrade():
    for table, fields in reversed(list(FIELDS.items())):
        with op.batch_alter_table(table) as batch:
            for name in fields.split():
                batch.alter_column(name, nullable=True)
