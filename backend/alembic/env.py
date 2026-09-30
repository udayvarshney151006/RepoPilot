from alembic import context
from sqlalchemy import text

from app import models  # noqa: F401
from app.db import Base, engine

target_metadata = Base.metadata


def include_object(obj, name, kind, reflected, compare_to):
    return not (kind == "index" and name == "ix_chunk_embedding_hnsw" and engine.dialect.name == "sqlite")

if context.is_offline_mode():
    from app.config import settings
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        if connection.dialect.name == "sqlite":
            # Batch table recreation must preserve referencing rows; verify afterwards.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        if connection.dialect.name == "postgresql":
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True, include_object=include_object)
        with context.begin_transaction():
            context.run_migrations()
        if connection.dialect.name == "sqlite":
            connection.commit()
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchone():
                raise RuntimeError("Migration produced invalid foreign key relationships")
