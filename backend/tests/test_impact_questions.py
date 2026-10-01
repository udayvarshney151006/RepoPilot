"""Ask impact uses explicit graph targets, refuses ambiguity, and preserves evidence budgets."""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import dependencies, ingestion
from app.config import settings
from app.db import Base
from app.models import CodeChunk, IndexingJob, Repository, RepositoryFile, utcnow
from app.providers import LocalEmbedding
from app.retrieval import answer_question


@pytest.fixture
def impact_demo(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(ingestion, "SessionLocal", factory)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "embedding_provider", "local")
    monkeypatch.setattr(settings, "llm_provider", "extractive")
    monkeypatch.setattr(settings, "redis_url", "")
    with factory() as session:
        repository = Repository(name="impact-demo", source_url="demo://shop")
        session.add(repository)
        session.flush()
        session.add(IndexingJob(repository_id=repository.id))
        session.commit()
        identity = repository.id
    ingestion.index_repository(identity)
    with factory() as session:
        assert session.get(Repository, identity).status == "ready"
    yield factory, identity, tmp_path
    engine.dispose()


def graph_repository(factory, directory, files):
    """Each tuple supplies a real source path, declaration, imports and optional padding."""
    with factory() as session:
        repository = Repository(name="graph-case", source_url="fixture://graph", root_path=str(directory),
                                status="ready", embedding_provider=LocalEmbedding.name, indexed_at=utcnow())
        session.add(repository)
        session.flush()
        for path, symbol, imports, padding in files:
            content = "".join(f"import {module}\n" for module in imports)
            content += f"def {symbol}():\n    return 1\n" + ("# " + padding + "\n" if padding else "")
            physical = directory / path
            physical.parent.mkdir(parents=True, exist_ok=True)
            physical.write_text(content, encoding="utf-8")
            source = RepositoryFile(repository_id=repository.id, path=path, language="python", content=content,
                                    imports=imports, symbols=[{"name": symbol, "type": "function", "start_line": 1,
                                                              "end_line": len(content.splitlines())}],
                                    line_count=len(content.splitlines()), size_bytes=len(content.encode()))
            session.add(source)
            session.flush()
            session.add(CodeChunk(repository_id=repository.id, file_id=source.id, file_path=path,
                                  symbol_name=symbol, symbol_type="function", language="python", start_line=1,
                                  end_line=len(content.splitlines()), content=content,
                                  embedding=LocalEmbedding().embed([content])[0]))
        session.commit()
        return repository.id


@pytest.mark.parametrize("question", [
    "Which files depend on shop/auth.py?",
    "Which files depend on auth.py?",
    "What will be affected if I modify validate_token?",
])
def test_explicit_path_unique_basename_and_symbol_resolve_real_demo_target(impact_demo, question):
    factory, identity, _ = impact_demo
    with factory() as session:
        impact = dependencies.dependency_question(session, identity, question)
        assert impact["status"] == "resolved"
        assert impact["path"] == "shop/auth.py"
        assert {"shop/routes.py", "tests/test_auth.py"}.issubset(impact["affected_files"])
        assert ["shop/routes.py", "shop/auth.py"] in impact["chains"]


def test_transitive_cycle_produces_finite_real_import_chains(impact_demo):
    factory, _, temporary = impact_demo
    identity = graph_repository(factory, temporary / "cyclic", [
        ("a.py", "action_a", ["b"], ""), ("b.py", "action_b", ["c"], ""),
        ("c.py", "action_c", ["a"], ""), ("facade.py", "facade", ["a"], ""),
    ])
    with factory() as session:
        result = dependencies.dependency_question(session, identity, "Which files depend on c.py?")
        assert result["status"] == "resolved"
        assert set(result["affected_files"]) == {"a.py", "b.py", "facade.py"}
        assert ["facade.py", "a.py", "b.py", "c.py"] in result["chains"]
        edges = {(edge["source"], edge["target"]) for edge in dependencies.graph(session, identity)["edges"]}
        for chain in result["chains"]:
            assert chain[0] in result["affected_files"]
            assert len(chain) == len(set(chain))
            assert chain[-1] == "c.py"
            assert all((source, target) in edges for source, target in zip(chain, chain[1:]))


@pytest.mark.parametrize("target", ["auth.py", "shared_action"])
def test_duplicate_basename_or_symbol_requires_clarification(impact_demo, target):
    factory, _, temporary = impact_demo
    identity = graph_repository(factory, temporary / "ambiguous", [
        ("left/auth.py", "shared_action", [], ""), ("right/auth.py", "shared_action", [], ""),
    ])
    with factory() as session:
        result = dependencies.dependency_question(session, identity, f"Which files depend on {target}?")
        assert result["status"] == "ambiguous"
        assert set(result["candidate_paths"]) == {"left/auth.py", "right/auth.py"}
        assert not result.get("affected_files")
        response = answer_question(session, identity, f"Which files depend on {target}?")
        assert response["impact"]["status"] == "ambiguous"
        assert not response["impact"].get("affected_files")
        assert "left/auth.py" in response["answer"] and "right/auth.py" in response["answer"]


def test_unknown_target_is_not_inferred_from_top_retrieved_authentication_evidence(impact_demo):
    factory, identity, _ = impact_demo
    question = "Which authentication files depend on MissingService?"
    with factory() as session:
        result = dependencies.dependency_question(session, identity, question)
        assert result["status"] == "unresolved"
        assert not result.get("affected_files")
        response = answer_question(session, identity, question)
        assert response["impact"]["status"] == "unresolved"
        assert not response["impact"].get("affected_files")
        assert not response["citations"]


def test_ambiguous_and_unresolved_questions_never_invoke_generation_provider(impact_demo, monkeypatch):
    import app.retrieval as retrieval_module
    factory, _, temporary = impact_demo
    identity = graph_repository(factory, temporary / "model-refusal", [
        ("left/auth.py", "shared_action", [], ""), ("right/auth.py", "shared_action", [], ""),
    ])
    class ProhibitedGeneration:
        def generate(self, question, evidence):
            raise AssertionError("Clarification must be deterministic and must not call a generation provider")
    monkeypatch.setattr(retrieval_module, "generation_provider", lambda: ProhibitedGeneration())
    with factory() as session:
        for target, status in [("auth.py", "ambiguous"), ("UnknownService", "unresolved")]:
            response = answer_question(session, identity, f"Which files depend on {target}?")
            assert response["impact"]["status"] == status
            assert response["metrics"]["model"] == "import-graph"
            assert response["citations"] == []


def test_ordinary_question_retains_existing_grounded_ask_response(impact_demo):
    factory, identity, _ = impact_demo
    with factory() as session:
        question = "Where is validate_token signature and expiration validation implemented?"
        assert dependencies.dependency_question(session, identity, question) is None
        response = answer_question(session, identity, question)
        assert response.get("impact") is None
        assert response["mode"] == "extractive"
        assert any(citation["symbol_name"] == "validate_token" for citation in response["citations"])


def test_graph_ask_summary_and_evidence_are_tied_to_actual_import_sources(impact_demo):
    factory, identity, _ = impact_demo
    with factory() as session:
        response = answer_question(session, identity, "What will be affected if I modify shop/auth.py?")
        assert response["impact"]["status"] == "resolved"
        first_line = response["answer"].splitlines()[0].casefold()
        assert "potential" in first_line and "import" in first_line
        assert "shop/routes.py" in response["answer"]
        retrieved = response["retrieval"]
        assert {"shop/auth.py", "shop/routes.py"}.issubset({row["file_path"] for row in retrieved})
        assert len(retrieved) <= 8
        assert sum(len(row["content"]) for row in retrieved) <= settings.max_context_chars
        assert {row["chunk_id"] for row in response["citations"]}.issubset({row["chunk_id"] for row in retrieved})
        for row in retrieved:
            source = session.scalar(select(RepositoryFile).where(RepositoryFile.repository_id == identity,
                                                                 RepositoryFile.path == row["file_path"]))
            assert row["content"].strip() == "\n".join(source.content.splitlines()[row["start_line"] - 1:row["end_line"]]).strip()


def test_graph_evidence_does_not_escape_existing_chunk_and_context_budgets(impact_demo, monkeypatch):
    factory, _, temporary = impact_demo
    files = [("target.py", "target_action", [], "")]
    files += [(f"consumer_{index}.py", f"consumer_{index}", ["target"], "padding " * 130) for index in range(20)]
    identity = graph_repository(factory, temporary / "many-imports", files)
    monkeypatch.setattr(settings, "max_context_chars", 1500)
    with factory() as session:
        response = answer_question(session, identity, "Which files depend on target.py?")
        assert len(response["impact"]["affected_files"]) == 20
        assert len(response["impact"]["chains"]) <= 8
        assert response["impact"]["chains_truncated"] is True
        assert len(response["retrieval"]) <= 8
        assert sum(len(row["content"]) for row in response["retrieval"]) <= 1500
        assert response["metrics"]["context_chars"] <= 1500
        assert any(row["file_path"] == "target.py" for row in response["retrieval"])
        assert all(row["file_path"] == "target.py" or row["file_path"] in response["impact"]["affected_files"]
                   for row in response["retrieval"])


def test_graph_summary_cites_the_target_and_import_chunks_when_model_has_no_citations(impact_demo, monkeypatch):
    from app import retrieval

    class UncitedProvider:
        def generate(self, question, evidence):
            return {"answer": "No generated explanation is available.", "citation_ids": [],
                    "model": "extractive-offline", "input_tokens": None, "output_tokens": None}

    monkeypatch.setattr(retrieval, "generation_provider", lambda: UncitedProvider())
    factory, identity, _ = impact_demo
    with factory() as session:
        response = answer_question(session, identity, "What will be affected if I modify validate_token?")
        target = next(row for row in response["citations"] if row["file_path"] == "shop/auth.py")
        importer = next(row for row in response["citations"] if row["file_path"] == "shop/routes.py")
        assert target["symbol_name"] == "validate_token"
        assert "from shop.auth import" in importer["content"]
        assert len(response["citations"]) == 3
