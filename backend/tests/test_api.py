"""Exercise real API handlers and workers with a fresh, isolated SQLite database."""
import io
import json
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import agents, db, evaluations, ingestion, main
from app.config import settings
from app.jobs import dispatch
from app.models import AgentRun, CodeChunk, EvaluationRun, Repository
from app.sandbox import DockerSandbox


@pytest.fixture
def api(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "embedding_provider", "local")
    monkeypatch.setattr(settings, "llm_provider", "extractive")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "api_auth_token", "")
    monkeypatch.setattr(main, "engine", engine)
    for module in (ingestion, agents, evaluations):
        monkeypatch.setattr(module, "SessionLocal", factory)
    monkeypatch.setattr(main, "submit", dispatch)
    monkeypatch.setattr(DockerSandbox, "available", lambda self: False)
    def sessions():
        with factory() as session:
            yield session
    main.app.dependency_overrides[db.get_session] = sessions
    main.rate_windows.clear()
    with TestClient(main.app) as client:
        yield SimpleNamespace(client=client, sessions=factory, data_dir=settings.data_dir)
    main.app.dependency_overrides.pop(db.get_session, None)
    main.rate_windows.clear()
    engine.dispose()


def demo(api):
    created = api.client.post("/api/repositories/demo")
    assert created.status_code == 202, created.text
    identity = created.json()["id"]
    current = api.client.get(f"/api/repositories/{identity}")
    assert current.json()["status"] == "ready", current.text
    return identity


def zip_bytes(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return stream.getvalue()


def upload(api, files, filename="repository.zip"):
    return api.client.post("/api/repositories/upload", files={"file": (filename, zip_bytes(files), "application/zip")})


def agent(api, identity):
    submitted = api.client.post(f"/api/repositories/{identity}/agent-runs", json={
        "task": "Fix POST /checkout returning 500 when an item omits quantity", "max_steps": 12})
    assert submitted.status_code == 202, submitted.text
    run_id = submitted.json()["id"]
    run = api.client.get(f"/api/agent-runs/{run_id}").json()
    assert run["status"] == "awaiting_approval", run
    return run


def test_demo_health_files_query_citations_conversations_and_import_impact(api):
    health = api.client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["database"] == "sqlite"
    assert health.json()["sandbox"] is False
    identity = demo(api)
    state = api.client.get(f"/api/repositories/{identity}/status").json()
    assert state["job"]["status"] == "completed"
    assert state["job"]["progress"] == 100
    assert state["repository"]["chunk_count"] > 0
    listing = api.client.get(f"/api/repositories/{identity}/files").json()
    assert {item["path"] for item in listing} >= {"shop/auth.py", "shop/checkout.py", "web/api.ts", "web/cart.js"}
    source = api.client.get(f"/api/repositories/{identity}/files/shop/auth.py").json()
    assert any(symbol["name"] == "validate_token" for symbol in source["symbols"])
    response = api.client.post(f"/api/repositories/{identity}/query", json={
        "question": "Where does validate_token check JWT signature and expiration?", "strategy": "hybrid_rerank"})
    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["mode"] == "extractive"
    assert answer["citations"]
    assert any(cite["file_path"] == "shop/auth.py" and cite["symbol_name"] == "validate_token" for cite in answer["citations"])
    assert all(cite["file_path"] != "evaluation.json" for cite in answer["retrieval"])
    for citation in answer["citations"]:
        file = api.client.get(f"/api/repositories/{identity}/files/{citation['file_path']}").json()
        lines = file["content"].splitlines()
        assert citation["content"].strip() == "\n".join(lines[citation["start_line"] - 1:citation["end_line"]]).strip()
    conversations = api.client.get(f"/api/repositories/{identity}/conversations").json()
    assert conversations[0]["id"] == answer["conversation_id"]
    assert [message["role"] for message in conversations[0]["messages"]] == ["user", "assistant"]
    dependency = api.client.get(f"/api/repositories/{identity}/dependencies").json()
    assert {"source": "shop/routes.py", "target": "shop/checkout.py", "kind": "imports"} in dependency["edges"]
    affected = api.client.get(f"/api/repositories/{identity}/impact", params={"path": "shop/checkout.py"}).json()
    assert "shop/routes.py" in affected["affected_files"]
    assert "potential impact" in affected["explanation"]


def test_query_request_id_correlates_http_and_query_logs(api, caplog):
    identity = demo(api)
    caplog.set_level("INFO")
    request_id = "DB6F6F57-B8D4-4584-80E5-F29C5E1B1B55"
    response = api.client.post(f"/api/repositories/{identity}/query", headers={"X-Request-ID": request_id},
                               json={"question": "Where is validate_token defined?"})
    assert response.status_code == 200, response.text
    assert response.headers["X-Request-ID"] == request_id.lower()
    logs = [json.loads(record.message) for record in caplog.records
            if record.name in {"repopilot.http", "repopilot.requests"}]
    assert {row["event"] for row in logs} >= {"http", "query"}
    assert all(row["request_id"] == request_id.lower() for row in logs)


@pytest.mark.parametrize("client_id", ["not-a-uuid-sensitive-value", "x" * 1000,
                                     "00000000-0000-0000-0000-00000000000z"])
def test_invalid_request_ids_are_replaced_without_echoing_or_logging_input(api, caplog, client_id):
    caplog.set_level("INFO", logger="repopilot.http")
    response = api.client.get("/api/health", headers={"X-Request-ID": client_id})
    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]
    assert str(UUID(request_id)) == request_id
    assert request_id != client_id
    assert client_id not in caplog.text
    logs = [json.loads(record.message) for record in caplog.records if record.name == "repopilot.http"]
    assert logs[-1]["request_id"] == request_id


@pytest.mark.parametrize("rejection", ["authentication", "rate_limit", "invalid_length", "oversized_upload"])
def test_boundary_rejections_keep_request_id_and_structured_http_log(api, monkeypatch, caplog, rejection):
    caplog.set_level("INFO", logger="repopilot.http")
    request_id = "a42c507c-6a85-4b4a-baf1-c5d432d90111"
    headers = {"X-Request-ID": request_id}
    path = "/api/repositories/demo"
    method = "POST"
    if rejection == "authentication":
        monkeypatch.setattr(settings, "api_auth_token", "private-test-token")
        path, method, expected = "/api/settings", "GET", 401
    elif rejection == "rate_limit":
        main.rate_windows["testclient"].extend([time.monotonic()] * 60)
        expected = 429
    elif rejection == "invalid_length":
        path, expected = "/api/repositories/upload", 411
        headers["Content-Length"] = "invalid"
    else:
        path, expected = "/api/repositories/upload", 413
        headers["Content-Length"] = str(settings.max_upload_bytes + 65537)
    response = api.client.request(method, path, headers=headers)
    assert response.status_code == expected
    assert response.headers["X-Request-ID"] == request_id
    logs = [json.loads(record.message) for record in caplog.records if record.name == "repopilot.http"]
    assert logs[-1]["request_id"] == request_id
    assert logs[-1]["status"] == expected
    assert "private-test-token" not in caplog.text


def test_agent_rejection_preserves_managed_source_and_demonstrates_unavailable_tests(api):
    identity = demo(api)
    before = api.client.get(f"/api/repositories/{identity}/files/shop/checkout.py").json()["content"]
    run = agent(api, identity)
    assert "item.get('quantity', 1)" in run["patch"]["diff"]
    assert len(run["test_results"]) == 2
    assert all(result["status"] == "unavailable" and not result["executed"] for result in run["test_results"])
    with api.sessions() as session:
        working_copy = Path(session.get(Repository, identity).root_path) / "shop/checkout.py"
        assert working_copy.read_text() == before
    rejected = api.client.post(f"/api/agent-runs/{run['id']}/reject")
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert working_copy.read_text() == before
    assert api.client.post(f"/api/agent-runs/{run['id']}/approve").status_code == 409
    assert api.client.get(f"/api/repositories/{identity}/agent-runs").json()[0]["id"] == run["id"]


def test_agent_approval_applies_managed_patch_and_rebuilds_real_code_chunks(api):
    identity = demo(api)
    run = agent(api, identity)
    approved = api.client.post(f"/api/agent-runs/{run['id']}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    state = api.client.get(f"/api/repositories/{identity}/status").json()
    assert state["repository"]["status"] == "ready"
    assert state["job"]["status"] == "completed"
    updated = api.client.get(f"/api/repositories/{identity}/files/shop/checkout.py").json()
    assert "item.get('quantity', 1)" in updated["content"]
    with api.sessions() as session:
        chunks = session.scalars(select(CodeChunk).where(CodeChunk.repository_id == identity,
                                                         CodeChunk.symbol_name == "calculate_total")).all()
        assert chunks and all("item.get('quantity', 1)" in chunk.content for chunk in chunks)
    bundled = ingestion.PROJECT_ROOT / "demo-repository/shop/checkout.py"
    assert "item['quantity']" in bundled.read_text()
    assert api.client.post(f"/api/agent-runs/{run['id']}/approve").status_code == 409


def test_approval_conflict_is_exposed_as_409_and_never_overwrites_new_source(api):
    identity = demo(api)
    run = agent(api, identity)
    with api.sessions() as session:
        path = Path(session.get(Repository, identity).root_path) / "shop/checkout.py"
    path.write_text("# external change after staging\n")
    response = api.client.post(f"/api/agent-runs/{run['id']}/approve")
    assert response.status_code == 409
    assert "Patch conflict" in response.json()["detail"]
    assert path.read_text() == "# external change after staging\n"


def test_evaluation_executes_demo_cases_for_all_strategies_without_polluting_chat(api):
    identity = demo(api)
    dataset = api.client.get(f"/api/repositories/{identity}/evaluation-dataset").json()
    assert len(dataset["cases"]) == 6
    created = api.client.post(f"/api/repositories/{identity}/evaluations", json={"k": 5})
    assert created.status_code == 202, created.text
    run = api.client.get(f"/api/evaluations/{created.json()['id']}").json()
    assert run["status"] == "completed", run
    assert len(run["results"]) == 24
    assert {row["strategy"] for row in run["metrics"]} == {"vector", "bm25", "hybrid", "hybrid_rerank"}
    for metric in run["metrics"]:
        assert 0 <= metric["recall_at_k"] <= 1
        assert 0 <= metric["mrr"] <= 1
        assert metric["avg_latency_ms"] > 0
        assert metric["input_tokens"] is None and metric["estimated_cost"] is None
        assert "proxy" in metric["answer_assessment"]
    assert all(row["retrieved_chunk_ids"] for row in run["results"])
    assert api.client.get(f"/api/repositories/{identity}/conversations").json() == []
    assert api.client.get(f"/api/repositories/{identity}/evaluations").json()[0]["id"] == run["id"]


def test_zip_import_normalizes_folder_and_indexes_actual_python_without_secrets(api):
    response = upload(api, {"project/service.py": "def ping():\n    return 'pong'\n",
                            "project/.env": "API_KEY=should-not-be-indexed",
                            "project/credentials.json": '{"password":"not-for-indexing"}'})
    assert response.status_code == 202, response.text
    identity = response.json()["id"]
    repository = api.client.get(f"/api/repositories/{identity}").json()
    assert repository["status"] == "ready", repository
    assert repository["source_url"] == "upload://zip"
    files = api.client.get(f"/api/repositories/{identity}/files").json()
    assert [file["path"] for file in files] == ["service.py"]
    result = api.client.post(f"/api/repositories/{identity}/query", json={"question": "Where is ping defined?"})
    assert result.status_code == 200
    assert result.json()["citations"][0]["symbol_name"] == "ping"


@pytest.mark.parametrize("url", ["https://evil.example/owner/repo", "http://github.com/owner/repo",
                                 "https://github.com/owner/repo/tree/main", "https://user:secret@github.com/owner/repo"])
def test_invalid_repository_urls_are_rejected_before_jobs_or_records(api, url):
    response = api.client.post("/api/repositories", json={"url": url})
    assert response.status_code == 422
    assert api.client.get("/api/repositories").json() == []


@pytest.mark.parametrize("filename,payload", [("plain.txt", b"not a zip"), ("broken.zip", b"not a zip")])
def test_invalid_zip_upload_is_rejected_and_transaction_is_rolled_back(api, filename, payload):
    response = api.client.post("/api/repositories/upload", files={"file": (filename, payload, "application/zip")})
    assert response.status_code == 422
    assert api.client.get("/api/repositories").json() == []
    assert not list(api.data_dir.glob("uploads/*.zip"))


def test_zip_traversal_fails_the_index_job_without_writing_outside_managed_storage(api):
    response = upload(api, {"../escape.py": "raise RuntimeError('untrusted')\n", "valid.py": "def ping(): return 1\n"})
    assert response.status_code == 202
    identity = response.json()["id"]
    state = api.client.get(f"/api/repositories/{identity}/status").json()
    assert state["repository"]["status"] == "failed"
    assert "traverse" in state["repository"]["error"]
    assert state["job"]["status"] == "failed"
    assert not (api.data_dir / "repositories/escape.py").exists()
    assert not (api.data_dir / "escape.py").exists()


@pytest.mark.parametrize("path", ["..%2Fsecret.py", "C%3A%2Fsecret.py", "shop%5Ccheckout.py", "%2Fetc%2Fpasswd"])
def test_file_endpoint_rejects_unsafe_paths(api, path):
    identity = demo(api)
    response = api.client.get(f"/api/repositories/{identity}/files/{path}")
    assert response.status_code == 422


def test_upload_size_limit_cleans_staged_archive_and_repository_record(api, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 32)
    response = upload(api, {"service.py": "def ping(): return 1\n"})
    assert response.status_code == 413
    assert api.client.get("/api/repositories").json() == []
    assert not list(api.data_dir.glob("uploads/*.zip"))


def test_expanded_zip_size_limit_fails_job_and_prevents_queries(api, monkeypatch):
    monkeypatch.setattr(settings, "max_repository_bytes", 20)
    response = upload(api, {"service.py": "def ping():\n    return 'more than twenty bytes'\n"})
    assert response.status_code == 202
    identity = response.json()["id"]
    state = api.client.get(f"/api/repositories/{identity}/status").json()
    assert state["repository"]["status"] == "failed"
    assert "size limit" in state["repository"]["error"]
    query = api.client.post(f"/api/repositories/{identity}/query", json={"question": "Where is ping?"})
    assert query.status_code == 409


def test_queue_failure_is_a_persisted_actionable_failure(api, monkeypatch):
    def unavailable(*_):
        raise ConnectionError("queue unavailable")
    monkeypatch.setattr(main, "submit", unavailable)
    response = api.client.post("/api/repositories/demo")
    assert response.status_code == 503
    repositories = api.client.get("/api/repositories").json()
    assert len(repositories) == 1
    assert repositories[0]["status"] == "failed"
    state = api.client.get(f"/api/repositories/{repositories[0]['id']}/status").json()
    assert state["job"]["status"] == "failed"
    assert "queue" in state["job"]["error"].lower()


def test_optional_api_auth_hides_settings_and_rate_limit_remains_bounded(api, monkeypatch):
    monkeypatch.setattr(settings, "api_auth_token", "integration-test-token")
    assert api.client.get("/api/health").status_code == 200
    assert api.client.get("/api/settings").status_code == 401
    settings_response = api.client.get("/api/settings", headers={"Authorization": "Bearer integration-test-token"})
    assert settings_response.status_code == 200
    assert "integration-test-token" not in settings_response.text
    monkeypatch.setattr(settings, "api_auth_token", "")
    main.rate_windows["testclient"].extend([time.monotonic()] * 60)
    throttled = api.client.post("/api/repositories/demo")
    assert throttled.status_code == 429
    assert throttled.headers["Retry-After"] == "60"


@pytest.mark.parametrize("model", [AgentRun, EvaluationRun])
def test_index_and_patch_approval_wait_for_active_investigations(api, model):
    identity = demo(api)
    staged = agent(api, identity)
    with api.sessions() as session:
        values = {"repository_id": identity, "status": "running"}
        if model is AgentRun:
            values["task"] = "Existing investigation"
        session.add(model(**values))
        session.commit()
    indexed = api.client.post(f"/api/repositories/{identity}/index")
    assert indexed.status_code == 409
    approved = api.client.post(f"/api/agent-runs/{staged['id']}/approve")
    assert approved.status_code == 409
    with api.sessions() as session:
        source = Path(session.get(Repository, identity).root_path) / "shop/checkout.py"
        assert "item['quantity']" in source.read_text()


def test_duplicate_queued_agent_is_rejected_before_second_job(api, monkeypatch):
    identity = demo(api)
    monkeypatch.setattr(main, "submit", lambda *_: None)
    first = api.client.post(f"/api/repositories/{identity}/agent-runs", json={"task": "Investigate checkout"})
    second = api.client.post(f"/api/repositories/{identity}/agent-runs", json={"task": "Investigate checkout"})
    assert first.status_code == 202
    assert second.status_code == 409
    assert len(api.client.get(f"/api/repositories/{identity}/agent-runs").json()) == 1


def test_oversized_single_line_is_skipped_and_reported_without_losing_other_files(api):
    uploaded = upload(api, {"project/normal.py": "def ping(): return 1\n", "project/generated.py": "#" + "x" * 7000})
    assert uploaded.status_code == 202
    current = api.client.get(f"/api/repositories/{uploaded.json()['id']}").json()
    assert current["status"] == "ready"
    assert current["file_count"] == 1
    assert any("generated.py" in warning and "budget" in warning for warning in current["index_warnings"])
