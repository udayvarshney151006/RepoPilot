"""Behavioral coverage of tool boundaries, approval, sandbox constraints and actual metrics."""
from pathlib import Path
from datetime import datetime, timedelta
from types import SimpleNamespace
import json

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import agents, evaluations
from app.config import Settings, settings
from app.db import Base
from app.models import AgentRun, AgentStep, CodeChunk, EvaluationRun, Repository, RepositoryFile
from app.providers import LocalEmbedding
from app.sandbox import CommandRejected, DockerSandbox, copy_repository, validate_command


@pytest.fixture
def indexed_repository(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path / "index-data")
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    content = "def calculate_total(items):\n    return sum(item['price'] * item['quantity'] for item in items)\n"
    (tmp_path / "shop").mkdir()
    (tmp_path / "shop" / "checkout.py").write_text(content, encoding="utf-8")
    repository = Repository(name="approval-test", source_url="demo", root_path=str(tmp_path), status="ready",
                            embedding_provider=LocalEmbedding.name)
    session.add(repository)
    session.flush()
    source = RepositoryFile(repository_id=repository.id, path="shop/checkout.py", content=content,
                            language="python", line_count=2, size_bytes=len(content), symbols=[], imports=[])
    session.add(source)
    session.flush()
    chunk = CodeChunk(repository_id=repository.id, file_id=source.id, file_path=source.path, language="python",
                      symbol_name="calculate_total", symbol_type="function", start_line=1, end_line=2,
                      content=content, embedding=LocalEmbedding().embed([content])[0])
    session.add(chunk)
    run = AgentRun(repository_id=repository.id, task="Fix checkout bug when quantity is omitted", status="running", max_steps=12)
    session.add(run)
    session.commit()
    yield session, factory, repository, run, source, chunk
    session.close()
    engine.dispose()


def stage(tools):
    result = tools.call("create_patch", {"changes": [{"path": "shop/checkout.py", "old_text": "item['quantity']",
                                                    "new_text": "item.get('quantity', 1)"}],
                                         "explanation": "Missing quantity defaults to one.", "risks": []})
    assert result["success"]
    tools.run.status = "awaiting_approval"
    tools.session.commit()
    return result


@pytest.mark.parametrize("command", [
    "python -c print(1)", "pytest; whoami", "pytest && curl example.org", "pytest $(env)",
    ["pytest", "--override-ini=addopts=-p evil"], ["pytest", "/etc/passwd"],
    ["pytest", "../../secret"], ["pytest", "C:/secret"], "npm install", ["npm", "test", "--", "--eval=evil"],
])
def test_test_command_allowlist_rejects_arbitrary_execution(command):
    with pytest.raises(CommandRejected):
        validate_command(command)


@pytest.mark.parametrize("command,expected", [
    ("pytest -q tests/test_checkout.py", ["pytest", "-q", "tests/test_checkout.py"]),
    ("python -m pytest -q", ["python", "-m", "pytest", "-q"]),
    ("pytest tests/test_checkout.py::test_total --tb=short", ["pytest", "tests/test_checkout.py::test_total", "--tb=short"]),
    ("npm test -- --runInBand", ["npm", "test", "--", "--runInBand"]),
])
def test_permitted_commands_are_argv(command, expected):
    assert validate_command(command) == expected


def test_unavailable_docker_reports_no_execution(monkeypatch, tmp_path):
    monkeypatch.setattr(DockerSandbox, "available", lambda self: False)
    result = DockerSandbox().run(tmp_path, "pytest -q")
    assert result["status"] == "unavailable"
    assert result["executed"] is False
    assert result["exit_code"] is None


def test_sandbox_constrains_container_and_passes_command_as_argv(monkeypatch, tmp_path):
    import app.sandbox as sandbox_module
    (tmp_path / "test_ok.py").write_text("def test_ok(): assert True\n")
    calls = []
    class Process:
        returncode = 0
        def __init__(self, argv, stdout, stderr, shell):
            calls.append(argv)
            assert shell is False
            stdout.write(b"1 passed\n")
        def poll(self):
            return 0
        def wait(self, timeout):
            return 0
    monkeypatch.setattr(DockerSandbox, "available", lambda self: True)
    monkeypatch.setattr(sandbox_module.subprocess, "Popen", Process)
    monkeypatch.setattr(sandbox_module.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0))
    result = DockerSandbox().run(tmp_path, "python -m pytest -q")
    command = calls[0]
    for flag in ("--rm", "--read-only", "--cap-drop", "--security-opt", "--user", "--memory", "--cpus", "--pids-limit"):
        assert flag in command
    assert command[command.index("--network") + 1] == "none"
    assert command[command.index("--user") + 1] == "65534:65534"
    assert command[-4:] == ["python", "-m", "pytest", "-q"]
    assert result["status"] == "passed"


def test_configured_prebuilt_node_image_runs_only_allowlisted_npm_tests_without_network(monkeypatch, tmp_path):
    import app.sandbox as sandbox_module
    configured_image = "registry.example:5000/acme/repository-tests:local"
    monkeypatch.setenv("SANDBOX_NODE_IMAGE", configured_image)
    configured = Settings(_env_file=None, data_dir=tmp_path)
    assert configured.sandbox_node_image == configured_image
    monkeypatch.setattr(sandbox_module, "settings", configured)
    calls = []
    class Process:
        returncode = 0
        def __init__(self, argv, stdout, stderr, shell):
            calls.append(argv)
            assert shell is False
            stdout.write(b"test runner completed\n")
        def poll(self):
            return 0
        def wait(self, timeout):
            return 0
    monkeypatch.setattr(DockerSandbox, "available", lambda self: True)
    monkeypatch.setattr(sandbox_module.subprocess, "Popen", Process)
    monkeypatch.setattr(sandbox_module.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0))
    result = DockerSandbox().run(tmp_path, "npm test -- --runInBand")
    command = calls[0]
    assert command[command.index(configured_image) + 1] == "sh"
    assert command[command.index("--network") + 1] == "none"
    assert "--pull=never" in command
    assert command[-4:] == ["npm", "test", "--", "--runInBand"]
    assert "install" not in command
    assert result["status"] == "passed"
    rejected = DockerSandbox().run(tmp_path, "npm install")
    assert rejected["status"] == "rejected" and rejected["executed"] is False
    assert len(calls) == 1


@pytest.mark.parametrize("image", ["", "--privileged", "node:22 --network host", "node:22;env", "node\n:22"])
def test_sandbox_image_configuration_rejects_flags_whitespace_and_shell_syntax(tmp_path, image):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, data_dir=tmp_path, sandbox_node_image=image)


def test_snapshot_excludes_credentials_and_symlinks(tmp_path):
    original, copied = tmp_path / "original", tmp_path / "copy"
    original.mkdir()
    copied.mkdir()
    (original / "source.py").write_text("print('safe')")
    (original / ".env").write_text("SECRET=untrusted")
    (original / "private.key").write_text("private")
    (original / ".git").mkdir()
    (original / ".git" / "config").write_text("credentials")
    copy_repository(original, copied)
    assert {path.name for path in copied.iterdir()} == {"source.py"}


@pytest.mark.parametrize("path", ["../secret.py", "/etc/passwd", "C:/secret.py", "shop\\checkout.py", ".git/config", ".env",
                                  "shop/./checkout.py", "shop//checkout.py"])
def test_agent_blocks_unsafe_paths(indexed_repository, path):
    session, _, repository, run, _, _ = indexed_repository
    result = agents.AgentTools(session, run, repository).call("read_file", {"path": path})
    assert not result["success"]


def test_tools_reject_extra_arguments_and_unindexed_files(indexed_repository):
    session, _, repository, run, _, _ = indexed_repository
    tools = agents.AgentTools(session, run, repository)
    assert not tools.call("read_file", {"path": "shop/checkout.py", "system_command": "env"})["success"]
    assert not tools.call("read_file", {"path": "secret.py"})["success"]
    assert not tools.call("unrestricted_shell", {"command": "whoami"})["success"]


def test_staging_preserves_source_and_approval_applies_diff(indexed_repository):
    session, _, repository, run, source, _ = indexed_repository
    tools = agents.AgentTools(session, run, repository)
    patch = stage(tools)["patch"]
    path = Path(repository.root_path) / source.path
    assert "item['quantity']" in path.read_text()
    assert "-" in patch["diff"] and "+" in patch["diff"]
    response = agents.approve_run(session, run)
    assert response["status"] == "approved"
    assert "item.get('quantity', 1)" in path.read_text()
    assert repository.status == "queued"
    with pytest.raises(ValueError):
        agents.approve_run(session, run)


def test_rejection_preserves_source(indexed_repository):
    session, _, repository, run, source, _ = indexed_repository
    stage(agents.AgentTools(session, run, repository))
    response = agents.reject_run(session, run)
    assert response["status"] == "rejected"
    assert "item['quantity']" in (Path(repository.root_path) / source.path).read_text()
    with pytest.raises(ValueError):
        agents.approve_run(session, run)


def test_approval_detects_source_change_and_never_overwrites_it(indexed_repository):
    session, _, repository, run, source, _ = indexed_repository
    stage(agents.AgentTools(session, run, repository))
    path = Path(repository.root_path) / source.path
    path.write_text("# user changed this file\n")
    with pytest.raises(ValueError, match="Patch conflict"):
        agents.approve_run(session, run)
    assert path.read_text() == "# user changed this file\n"
    assert run.status == "awaiting_approval"


def test_ambiguous_patch_is_rejected(indexed_repository):
    session, _, repository, run, _, _ = indexed_repository
    result = agents.AgentTools(session, run, repository).call("create_patch", {
        "changes": [{"path": "shop/checkout.py", "old_text": "item", "new_text": "entry"}],
        "explanation": "Ambiguous change"})
    assert not result["success"]
    assert run.patch is None


def test_all_original_hashes_are_validated_before_any_file_is_changed(indexed_repository):
    session, _, repository, run, source, _ = indexed_repository
    tools = agents.AgentTools(session, run, repository)
    stage(tools)
    second = Path(repository.root_path) / "tests/test_new.py"
    run.patch = {**run.patch, "files": [*run.patch["files"],
        {"path": "tests/test_new.py", "before": None, "after": "def test_new(): assert True\n", "original_hash": None}]}
    session.commit()
    second.parent.mkdir()
    second.write_text("# Created after staging\n")
    with pytest.raises(ValueError, match="Patch conflict"):
        agents.approve_run(session, run)
    assert (Path(repository.root_path) / source.path).read_text() == source.content
    assert second.read_text() == "# Created after staging\n"


def test_agent_can_stage_new_tests_but_not_new_application_files(indexed_repository):
    session, _, repository, run, _, _ = indexed_repository
    tools = agents.AgentTools(session, run, repository)
    denied = tools.call("create_patch", {"changes": [{"path": "shop/new.py", "old_text": "", "new_text": "x = 1\n"}],
                                         "explanation": "Unsupported new application file"})
    assert denied["success"] is False
    accepted = tools.call("create_patch", {"changes": [{"path": "tests/test_total.py", "old_text": "",
                                                       "new_text": "def test_total():\n    assert 2 + 2 == 4\n"}],
                                           "explanation": "Stage a new test"})
    assert accepted["success"] is True
    assert not (Path(repository.root_path) / "tests/test_total.py").exists()
    run.status = "awaiting_approval"
    session.commit()
    agents.approve_run(session, run)
    assert (Path(repository.root_path) / "tests/test_total.py").is_file()


def test_symlink_tool_access_is_blocked(indexed_repository, tmp_path):
    session, _, repository, run, _, _ = indexed_repository
    target = tmp_path.parent / "outside-file.py"
    target.write_text("PRIVATE = True\n")
    link = Path(repository.root_path) / "linked.py"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Windows does not grant symlink creation in this environment")
    try:
        with pytest.raises(ValueError, match="Symbolic links"):
            agents.safe_path(repository.root_path, "linked.py")
    finally:
        target.unlink(missing_ok=True)


def test_configured_agent_tools_enforce_command_boundaries_and_keep_source_untrusted(indexed_repository, monkeypatch):
    session, factory, _, run, _, _ = indexed_repository
    run.status = "queued"
    session.commit()
    requests = []
    messages = [
        {"tool_calls": [{"id": "first", "type": "function", "function": {"name": "run_command",
            "arguments": json.dumps({"command": "python -c print('secret')"})}}]},
        {"tool_calls": [{"id": "second", "type": "function", "function": {"name": "read_file",
            "arguments": json.dumps({"path": "shop/checkout.py"})}}]},
        {"content": "Inspected shop/checkout.py. No changes applied."},
    ]
    class Client:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, headers, json):
            requests.append(json)
            return SimpleNamespace(is_error=False, json=lambda: {"choices": [{"message": messages.pop(0)}]})
    monkeypatch.setattr(agents, "SessionLocal", factory)
    monkeypatch.setattr(agents.httpx, "Client", Client)
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    agents.execute_agent(run.id)
    session.expire_all()
    completed = session.get(AgentRun, run.id)
    assert completed.status == "completed"
    steps = session.scalars(select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.created_at)).all()
    assert len(steps) == 2
    assert steps[0].result["status"] == "rejected"
    assert steps[0].result["executed"] is False
    assert steps[1].result["path"] == "shop/checkout.py"
    assert "UNTRUSTED DATA" in requests[0]["messages"][0]["content"]
    tool_messages = [message for message in requests[-1]["messages"] if message["role"] == "tool"]
    assert "untrusted_repository_tool_result" in tool_messages[-1]["content"]


def test_offline_agent_stages_real_source_with_unavailable_test_results(indexed_repository, monkeypatch):
    session, factory, repository, run, source, _ = indexed_repository
    run.status = "queued"
    session.commit()
    monkeypatch.setattr(agents, "SessionLocal", factory)
    monkeypatch.setattr(settings, "llm_provider", "extractive")
    monkeypatch.setattr(DockerSandbox, "available", lambda self: False)
    agents.execute_agent(run.id)
    session.expire_all()
    completed = session.get(AgentRun, run.id)
    assert completed.status == "awaiting_approval"
    assert completed.patch["files"][0]["path"] == "shop/checkout.py"
    assert len(completed.test_results) == 2
    assert all(result["executed"] is False for result in completed.test_results)
    assert "item['quantity']" in (Path(repository.root_path) / source.path).read_text()
    steps = session.scalars(select(AgentStep).where(AgentStep.run_id == run.id)).all()
    assert len(steps) <= 12
    assert {step.tool for step in steps} >= {"search_code", "read_file", "create_patch", "show_git_diff", "run_tests"}


def test_agent_respects_user_step_limit(indexed_repository, monkeypatch):
    session, factory, _, run, _, _ = indexed_repository
    run.status, run.max_steps = "queued", 2
    session.commit()
    monkeypatch.setattr(agents, "SessionLocal", factory)
    monkeypatch.setattr(settings, "llm_provider", "extractive")
    agents.execute_agent(run.id)
    session.expire_all()
    assert len(session.scalars(select(AgentStep).where(AgentStep.run_id == run.id)).all()) == 2
    assert session.get(AgentRun, run.id).patch is None


def test_metric_arithmetic_and_invalid_citations(indexed_repository):
    _, _, _, _, _, chunk = indexed_repository
    case = {"expected_file": chunk.file_path, "expected_symbol": chunk.symbol_name,
            "expected_answer_keywords": ["price", "quantity"]}
    hit = {"chunk_id": chunk.id, "file_path": chunk.file_path, "symbol_name": chunk.symbol_name,
           "start_line": chunk.start_line, "end_line": chunk.end_line, "content": chunk.content}
    wrong = {**hit, "chunk_id": "wrong", "symbol_name": "other"}
    score = evaluations.score_case(case, [wrong, hit], "The price is summed.", [chunk.id, "invented"], {chunk.id: chunk}, 5)
    assert score["recall_at_k"] == 1
    assert score["reciprocal_rank"] == 0.5
    assert score["answer_keyword_coverage"] == 0.5
    assert score["citation_validity"] == 0.5
    cutoff = evaluations.score_case(case, [wrong, hit], "", [], {chunk.id: chunk}, 1)
    assert cutoff["recall_at_k"] == 0
    assert cutoff["reciprocal_rank"] == 0


def test_evaluation_executes_all_four_strategies_and_persists_real_results(indexed_repository, monkeypatch):
    session, factory, repository, _, _, chunk = indexed_repository
    dataset = evaluations.ensure_dataset(session, repository.id)
    assert dataset.cases[0]["expected_symbol"] == chunk.symbol_name
    run = EvaluationRun(repository_id=repository.id, cases=dataset.cases, k=5, status="queued")
    session.add(run)
    session.commit()
    monkeypatch.setattr(evaluations, "SessionLocal", factory)
    monkeypatch.setattr(settings, "llm_provider", "extractive")
    evaluations.execute_evaluation(run.id)
    session.expire_all()
    completed = session.get(EvaluationRun, run.id)
    assert completed.status == "completed", completed.error
    assert {metric["strategy"] for metric in completed.metrics} == set(evaluations.STRATEGIES)
    assert len(completed.results) == 4
    assert all(metric["recall_at_k"] == 1 for metric in completed.metrics)
    assert all(metric["avg_latency_ms"] >= 0 for metric in completed.metrics)
    assert all(metric["input_tokens"] is None for metric in completed.metrics)
    assert all(metric["estimated_cost"] is None for metric in completed.metrics)


def test_agent_and_evaluation_sqlite_timestamps_are_explicitly_utc(indexed_repository):
    session, _, repository, run, _, _ = indexed_repository
    evaluation = EvaluationRun(repository_id=repository.id, cases=[], k=5, status="queued")
    session.add(evaluation)
    session.commit()
    run_id, evaluation_id = run.id, evaluation.id
    session.expire_all()
    loaded_run, loaded_eval = session.get(AgentRun, run_id), session.get(EvaluationRun, evaluation_id)
    assert loaded_run.created_at.tzinfo is None
    assert loaded_eval.created_at.tzinfo is None
    serialized = [agents.serialize_run(session, loaded_run), evaluations.serialize_evaluation(loaded_eval)]
    for item in serialized:
        parsed = datetime.fromisoformat(item["created_at"])
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timedelta(0)
