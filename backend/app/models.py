from datetime import datetime, timezone
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.db import Base


def new_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def index_generation(value: datetime | None) -> str:
    if value is None:
        return "unversioned"
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).isoformat()


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Identity, Base):
    __tablename__ = "users"
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(254), unique=True)


class Repository(Identity, Base):
    __tablename__ = "repositories"
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str] = mapped_column(Text)
    root_path: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    error: Mapped[str | None] = mapped_column(Text)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    languages: Mapped[dict] = mapped_column(JSON, default=dict)
    index_warnings: Mapped[list] = mapped_column(JSON, default=list)
    embedding_provider: Mapped[str] = mapped_column(String(150), default="")
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RepositoryFile(Identity, Base):
    __tablename__ = "repository_files"
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    line_count: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(Integer)
    symbols: Mapped[list] = mapped_column(JSON, default=list)
    imports: Mapped[list] = mapped_column(JSON, default=list)
    __table_args__ = (Index("ix_repo_file_path", "repository_id", "path", unique=True),)


class CodeChunk(Identity, Base):
    __tablename__ = "code_chunks"
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[str] = mapped_column(ForeignKey("repository_files.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(32))
    symbol_name: Mapped[str] = mapped_column(String(300))
    symbol_type: Mapped[str] = mapped_column(String(32))
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(Vector(settings.embedding_dimensions).with_variant(JSON(), "sqlite"))
    __table_args__ = (
        Index("ix_repo_chunk_symbol", "repository_id", "symbol_name"),
        Index("ix_chunk_embedding_hnsw", "embedding", postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"}).ddl_if(dialect="postgresql"),
    )


class Conversation(Identity, Base):
    __tablename__ = "conversations"
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))


class Message(Identity, Base):
    __tablename__ = "messages"
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)


class IndexingJob(Identity, Base):
    __tablename__ = "indexing_jobs"
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32), default="index")
    status: Mapped[str] = mapped_column(String(32), default="queued")
    stage: Mapped[str] = mapped_column(String(32), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRun(Identity, Base):
    __tablename__ = "agent_runs"
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    task: Mapped[str] = mapped_column(Text)
    max_steps: Mapped[int] = mapped_column(Integer, default=12)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text)
    patch: Mapped[dict | None] = mapped_column(JSON)
    test_results: Mapped[list] = mapped_column(JSON, default=list)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentStep(Identity, Base):
    __tablename__ = "agent_steps"
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    tool: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    duration_ms: Mapped[float] = mapped_column(Float, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    summary: Mapped[str] = mapped_column(Text, default="")


class EvaluationDataset(Identity, Base):
    __tablename__ = "evaluation_datasets"
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    cases: Mapped[list] = mapped_column(JSON, default=list)


class EvaluationRun(Identity, Base):
    __tablename__ = "evaluation_runs"
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey("evaluation_datasets.id", ondelete="CASCADE"))
    k: Mapped[int] = mapped_column(Integer, default=5)
    cases: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    error: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[list] = mapped_column(JSON, default=list)
    results: Mapped[list] = mapped_column(JSON, default=list)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
