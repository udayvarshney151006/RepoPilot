"""Initial application schema with PostgreSQL vector extension.

Revision ID: 0001
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def identity():
    return [sa.Column("id", sa.String(36), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True))]


def fk(name, target, nullable=False):
    return sa.Column(name, sa.String(36), sa.ForeignKey(target, ondelete="CASCADE"), nullable=nullable)


def upgrade():
    bind = op.get_bind()
    postgres = bind.dialect.name == "postgresql"
    if postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table("users", *identity(), sa.Column("name", sa.String(120)), sa.Column("email", sa.String(254), unique=True))
    op.create_table("repositories", *identity(), fk("owner_id", "users.id", True),
        sa.Column("name", sa.String(200)), sa.Column("source_url", sa.Text), sa.Column("root_path", sa.Text),
        sa.Column("status", sa.String(32)), sa.Column("error", sa.Text), sa.Column("file_count", sa.Integer),
        sa.Column("chunk_count", sa.Integer), sa.Column("languages", sa.JSON),
        sa.Column("embedding_provider", sa.String(150)), sa.Column("indexed_at", sa.DateTime(timezone=True)))
    op.create_index("ix_repositories_status", "repositories", ["status"])
    op.create_table("repository_files", *identity(), fk("repository_id", "repositories.id"),
        sa.Column("path", sa.Text), sa.Column("language", sa.String(32)), sa.Column("content", sa.Text),
        sa.Column("line_count", sa.Integer), sa.Column("size_bytes", sa.Integer),
        sa.Column("symbols", sa.JSON), sa.Column("imports", sa.JSON))
    op.create_index("ix_repo_file_path", "repository_files", ["repository_id", "path"], unique=True)
    op.create_table("code_chunks", *identity(), fk("repository_id", "repositories.id"), fk("file_id", "repository_files.id"),
        sa.Column("file_path", sa.Text), sa.Column("language", sa.String(32)), sa.Column("symbol_name", sa.String(300)),
        sa.Column("symbol_type", sa.String(32)), sa.Column("start_line", sa.Integer), sa.Column("end_line", sa.Integer),
        sa.Column("content", sa.Text), sa.Column("embedding", Vector(384) if postgres else sa.JSON))
    op.create_index("ix_repo_chunk_symbol", "code_chunks", ["repository_id", "symbol_name"])
    if postgres:
        op.create_index("ix_chunk_embedding_hnsw", "code_chunks", ["embedding"], postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"})
    op.create_table("conversations", *identity(), fk("repository_id", "repositories.id"), sa.Column("title", sa.String(200)))
    op.create_table("messages", *identity(), fk("conversation_id", "conversations.id"),
        sa.Column("role", sa.String(20)), sa.Column("content", sa.Text), sa.Column("citations", sa.JSON), sa.Column("metrics", sa.JSON))
    op.create_table("indexing_jobs", *identity(), fk("repository_id", "repositories.id"), sa.Column("kind", sa.String(32)),
        sa.Column("status", sa.String(32)), sa.Column("stage", sa.String(32)), sa.Column("progress", sa.Integer),
        sa.Column("error", sa.Text), sa.Column("finished_at", sa.DateTime(timezone=True)))
    op.create_table("agent_runs", *identity(), fk("repository_id", "repositories.id"), sa.Column("task", sa.Text),
        sa.Column("max_steps", sa.Integer), sa.Column("status", sa.String(32)), sa.Column("summary", sa.Text),
        sa.Column("error", sa.Text), sa.Column("patch", sa.JSON), sa.Column("test_results", sa.JSON),
        sa.Column("finished_at", sa.DateTime(timezone=True)))
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])
    op.create_table("agent_steps", *identity(), fk("run_id", "agent_runs.id"), sa.Column("tool", sa.String(64)),
        sa.Column("arguments", sa.JSON), sa.Column("result", sa.JSON), sa.Column("duration_ms", sa.Float),
        sa.Column("success", sa.Boolean), sa.Column("summary", sa.Text))
    op.create_table("evaluation_datasets", *identity(), fk("repository_id", "repositories.id"),
        sa.Column("name", sa.String(200)), sa.Column("cases", sa.JSON))
    op.create_table("evaluation_runs", *identity(), fk("repository_id", "repositories.id"), fk("dataset_id", "evaluation_datasets.id", True),
        sa.Column("k", sa.Integer), sa.Column("cases", sa.JSON), sa.Column("status", sa.String(32)), sa.Column("error", sa.Text),
        sa.Column("metrics", sa.JSON), sa.Column("results", sa.JSON), sa.Column("finished_at", sa.DateTime(timezone=True)))
    for table, column in [("repositories", "owner_id"), ("repository_files", "repository_id"),
        ("code_chunks", "repository_id"), ("code_chunks", "file_id"), ("conversations", "repository_id"),
        ("messages", "conversation_id"), ("indexing_jobs", "repository_id"), ("agent_runs", "repository_id"),
        ("agent_steps", "run_id"), ("evaluation_datasets", "repository_id"), ("evaluation_runs", "repository_id")]:
        op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    for table in ["evaluation_runs", "evaluation_datasets", "agent_steps", "agent_runs", "indexing_jobs",
        "messages", "conversations", "code_chunks", "repository_files", "repositories", "users"]:
        op.drop_table(table)
