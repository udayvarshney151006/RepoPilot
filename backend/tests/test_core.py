import zipfile

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import ingestion
from app.config import settings
from app.db import Base
from app.dependencies import impact, resolve_import
from app.models import CodeChunk, IndexingJob, Repository, RepositoryFile
from app.parsing import parse_code
from app.providers import IdentifierReranker, LocalEmbedding
from app.retrieval import bm25_scores, reciprocal_rank_fusion, retrieve
from app.security import allowed_file, redact_secrets, safe_path, validate_github_url


@pytest.mark.parametrize("url", ["http://github.com/a/b", "https://github.com.evil.org/a/b", "https://u:p@github.com/a/b", "https://github.com/a/b/tree/main", "file:///tmp/a", "https://github.com/a/../b", "https://github.com/a/b?token=secret", "https://127.0.0.1/a/b"])
def test_github_url_rejects_non_repository_sources(url):
    with pytest.raises(ValueError):
        validate_github_url(url)


def test_github_url_normalizes():
    assert validate_github_url("https://github.com/acme/shop.git/") == "https://github.com/acme/shop"


@pytest.mark.parametrize("path", ["../x", "/etc/passwd", "C:/x", "a\\b.py", "a/../../x", "a:stream", "NUL.py", "foo./secret", "CON/x.py"])
def test_path_escape_and_windows_aliases_rejected(tmp_path, path):
    with pytest.raises(ValueError):
        safe_path(tmp_path, path)


def test_filter_and_redaction_preserve_source_locations():
    assert not allowed_file("node_modules/foo.js")
    assert not allowed_file(".env.local")
    assert allowed_file("src/auth.ts")
    source = "jwt_secret = 'sensitive-literal-value'\n-----BEGIN PRIVATE KEY-----\nxyz\n-----END PRIVATE KEY-----\ndef next(): pass\n"
    clean = redact_secrets(source)
    assert "sensitive-literal-value" not in clean
    assert "xyz" not in clean
    assert len(clean.splitlines()) == len(source.splitlines())


@pytest.mark.parametrize("language,path,code,name", [
    ("python", "auth.py", "import jwt\n\nclass Auth:\n    def login(self, user):\n        return user\n", "Auth.login"),
    ("javascript", "auth.js", "import x from './x';\nexport const login = (user) => user;\n", "login"),
    ("typescript", "auth.ts", "import { x } from './x';\nexport function login(user: string): string { return user; }\n", "login"),
])
def test_semantic_chunks_and_line_boundaries(language, path, code, name):
    parsed = parse_code(code, language, path)
    match = next(row for row in parsed.chunks if row["symbol_name"] == name)
    assert match["content"] == "\n".join(code.splitlines()[match["start_line"]-1:match["end_line"]])
    assert parsed.imports
    assert any(row["symbol_type"] == "module" for row in parsed.chunks)


def test_oversized_symbol_keeps_identity_and_complete_lines(monkeypatch):
    monkeypatch.setattr(settings, "max_chunk_lines", 4)
    source = "def large():\n" + "    value = 1\n" * 10
    parsed = parse_code(source, "python", "large.py")
    chunks = [chunk for chunk in parsed.chunks if chunk["symbol_name"] == "large"]
    assert [(c["start_line"], c["end_line"]) for c in chunks] == [(1, 4), (5, 8), (9, 11)]
    assert "\n".join(c["content"] for c in chunks) == source.rstrip("\n")


def test_bm25_exact_identifier_and_rank_fusion():
    scores = bm25_scores("PaymentService", ["PaymentService checkout", "auth password", "PaymentService " + "noise " * 100])
    assert scores[0] > scores[2] > scores[1]
    fused = reciprocal_rank_fusion([["both", "lexical"], ["dense", "both"]])
    assert max(fused, key=fused.get) == "both"
    assert fused["both"] == pytest.approx(1/61 + 1/62)


def test_reranker_prefers_symbol_evidence():
    rows = [dict(chunk_id="a", file_path="README.md", symbol_name="README.md", symbol_type="module", start_line=1, content="login handler", fusion_score=.02),
            dict(chunk_id="b", file_path="auth.py", symbol_name="login_handler", symbol_type="function", start_line=1, content="def login_handler(): pass", fusion_score=.02)]
    assert IdentifierReranker().rank("login handler", rows)[0]["chunk_id"] == "b"


def test_zip_traversal_link_and_limits(tmp_path, monkeypatch):
    archive = tmp_path / "upload.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../escape.py", "print('x')")
    with pytest.raises(ValueError):
        ingestion.extract_zip(archive, tmp_path / "target")
    assert not (tmp_path / "escape.py").exists()
    with zipfile.ZipFile(archive, "w") as output:
        link = zipfile.ZipInfo("link.py")
        link.external_attr = (0o120777 << 16)
        output.writestr(link, "/etc/passwd")
    with pytest.raises(ValueError, match="Symbolic"):
        ingestion.extract_zip(archive, tmp_path / "target")
    monkeypatch.setattr(settings, "max_repository_bytes", 10)
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("main.py", "x" * 20)
    with pytest.raises(ValueError, match="size limit"):
        ingestion.extract_zip(archive, tmp_path / "target")


@pytest.fixture
def indexed_demo(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(ingestion, "SessionLocal", factory)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "embedding_provider", "local")
    with factory() as session:
        repo = Repository(name="demo", source_url="demo://shop")
        session.add(repo)
        session.flush()
        session.add(IndexingJob(repository_id=repo.id))
        session.commit()
        rid = repo.id
    ingestion.index_repository(rid)
    yield factory, rid
    engine.dispose()


def test_real_index_retrieval_dependencies_and_no_evaluation_leakage(indexed_demo):
    factory, rid = indexed_demo
    with factory() as session:
        repo = session.get(Repository, rid)
        assert repo.status == "ready", repo.error
        assert repo.file_count >= 8
        assert repo.embedding_provider == LocalEmbedding.name
        chunks = session.scalars(select(CodeChunk).where(CodeChunk.repository_id == rid)).all()
        assert not any(chunk.file_path == "evaluation.json" for chunk in chunks)
        for strategy in ["bm25", "vector", "hybrid", "hybrid_rerank"]:
            evidence, timing = retrieve(session, rid, "Where is validate_token signature expiration validation?", strategy, k=5)
            assert any(row["symbol_name"] == "validate_token" for row in evidence)
            assert timing["retrieval_ms"] >= 0
            for row in evidence:
                source = session.scalar(select(RepositoryFile).where(RepositoryFile.repository_id == rid, RepositoryFile.path == row["file_path"]))
                assert row["content"] == "\n".join(source.content.splitlines()[row["start_line"]-1:row["end_line"]])
        affected = impact(session, rid, "shop/auth.py")
        assert "shop/routes.py" in affected["affected_files"]
        assert "tests/test_auth.py" in affected["affected_files"]


def test_embedding_provider_mismatch_requires_reindex(indexed_demo):
    factory, rid = indexed_demo
    with factory() as session:
        repo = session.get(Repository, rid)
        repo.embedding_provider = "other-model"
        session.commit()
        with pytest.raises(ValueError, match="reindex"):
            retrieve(session, rid, "auth")


def test_relative_import_resolution():
    assert resolve_import("src/routes/auth.ts", "../services/auth", {"src/services/auth.ts"}, "typescript") == "src/services/auth.ts"
    assert resolve_import("shop/routes.py", ".auth", {"shop/auth.py"}, "python") == "shop/auth.py"
    assert resolve_import("shop/routes.py", "requests", {"shop/auth.py"}, "python") is None
