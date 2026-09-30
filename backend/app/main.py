import hmac
import json
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, RLock
from functools import wraps
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, engine, get_session
from app.dependencies import graph, impact
from app.ingestion import managed_root
from app.jobs import submit
from app.models import AgentRun, Conversation, EvaluationRun, IndexingJob, Message, Repository, RepositoryFile
from app.providers import embedding_provider
from app.retrieval import answer_question
from app.schemas import AgentRequest, EvaluationRequest, QueryRequest, RepositoryCreate
from app.security import redact_secrets, safe_path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("repopilot.http")


@asynccontextmanager
async def lifespan(_app):
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
    elif "repositories" not in inspect(engine).get_table_names():
        raise RuntimeError("Database schema missing. Run alembic upgrade head before starting the API.")
    yield


app = FastAPI(title="RepoPilot API", version="0.1.0", description="Grounded code intelligence with bounded tools and human-approved patches.", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","), allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Authorization"])
rate_windows: dict[str, deque] = defaultdict(deque)
rate_lock = Lock()
job_locks = [RLock() for _ in range(64)]


def serialized_job(function):
    """Serialize admission per repository locally and across PostgreSQL API processes."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        session = kwargs["session"]
        repository_id = kwargs.get("repository_id")
        if not repository_id:
            repository_id = entity(session, AgentRun, kwargs["run_id"]).repository_id
        with job_locks[hash(repository_id) % len(job_locks)]:
            session.scalar(select(Repository).where(Repository.id == repository_id).with_for_update().execution_options(populate_existing=True))
            return function(*args, **kwargs)
    return wrapped


@app.middleware("http")
async def request_boundary(request: Request, call_next):
    request_id = str(uuid4())
    started = time.perf_counter()
    if request.url.path.startswith("/api/") and request.url.path != "/api/health":
        if settings.api_auth_token:
            expected = "Bearer " + settings.api_auth_token
            if not hmac.compare_digest(request.headers.get("authorization", ""), expected):
                return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        if request.method == "POST":
            now = time.monotonic()
            peer = request.client.host if request.client else "unknown"
            with rate_lock:
                window = rate_windows[peer]
                while window and window[0] < now - 60:
                    window.popleft()
                if len(window) >= 60:
                    return JSONResponse(status_code=429, content={"detail": "Too many requests. Retry in a minute."}, headers={"Retry-After": "60"})
                window.append(now)
        if request.url.path == "/api/repositories/upload":
            try:
                declared_length = int(request.headers.get("content-length", ""))
            except ValueError:
                return JSONResponse(status_code=411, content={"detail": "Repository uploads require Content-Length"})
            if request.headers.get("transfer-encoding"):
                return JSONResponse(status_code=411, content={"detail": "Chunked repository uploads are not supported; use a bounded Content-Length request"})
            if declared_length < 0 or declared_length > settings.max_upload_bytes + 65536:
                return JSONResponse(status_code=413, content={"detail": "Upload request exceeds the configured size limit"})
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(json.dumps({"event": "http", "request_id": request_id, "method": request.method, "route": request.scope.get("route").path if request.scope.get("route") else "unmatched", "status": response.status_code, "duration_ms": round((time.perf_counter() - started) * 1000, 2)}))
    return response


def entity(session: Session, model, identity: str):
    row = session.get(model, identity)
    if row is None:
        raise HTTPException(404, "Resource not found")
    return row


def ready(session: Session, repository_id: str):
    repo = entity(session, Repository, repository_id)
    if repo.status != "ready":
        raise HTTPException(409, "Repository has not finished indexing")
    return repo


def repo_json(repo: Repository):
    return jsonable_encoder({key: getattr(repo, key) for key in ["id", "name", "source_url", "status", "error", "file_count", "chunk_count", "languages", "index_warnings", "created_at", "indexed_at", "embedding_provider"]}, custom_encoder={datetime: iso_utc})


def iso_utc(value: datetime):
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).isoformat()


def job_json(job: IndexingJob | None):
    return jsonable_encoder({key: getattr(job, key) for key in ["id", "repository_id", "kind", "status", "stage", "progress", "error", "created_at", "finished_at"]}, custom_encoder={datetime: iso_utc}) if job else None


def enqueue_index(session, repo):
    with job_locks[hash(repo.id) % len(job_locks)]:
        session.scalar(select(Repository).where(Repository.id == repo.id).with_for_update().execution_options(populate_existing=True))
        return _enqueue_index(session, repo)


def idle_investigations(session, repository_id):
    if session.scalar(select(AgentRun).where(AgentRun.repository_id == repository_id, AgentRun.status.in_(["queued", "running"]))) or session.scalar(select(EvaluationRun).where(EvaluationRun.repository_id == repository_id, EvaluationRun.status.in_(["queued", "running"]))):
        raise HTTPException(409, "Wait for running agents and evaluations to finish before changing the repository index")


def _enqueue_index(session, repo):
    idle_investigations(session, repo.id)
    active = session.scalar(select(IndexingJob).where(IndexingJob.repository_id == repo.id, IndexingJob.status.in_(["queued", "running"])))
    if active:
        raise HTTPException(409, "Indexing is already queued or running")
    job = IndexingJob(repository_id=repo.id)
    repo.status = "queued"
    repo.error = None
    session.add(job)
    session.commit()
    try:
        submit("index", repo.id)
    except Exception:
        job.status = "failed"
        job.error = "Background queue is unavailable. Check worker and Redis configuration, then retry indexing."
        repo.status = "failed"
        repo.error = job.error
        session.commit()
        raise HTTPException(503, job.error)
    return job


@app.get("/api/health")
def health(session: Session = Depends(get_session)):
    session.execute(text("SELECT 1"))
    from app.sandbox import DockerSandbox
    available = DockerSandbox().available()
    return {"status": "ok", "database": engine.dialect.name, "jobs": settings.job_backend,
            "providers": {"embedding": embedding_provider().name, "llm": settings.llm_provider}, "sandbox": available}


@app.get("/api/settings")
def public_settings():
    from app.sandbox import DockerSandbox
    return {"llm_provider": settings.llm_provider, "llm_model": settings.llm_model,
            "embedding_provider": settings.embedding_provider, "embedding_model": embedding_provider().name,
            "database": engine.dialect.name, "job_backend": settings.job_backend, "redis_enabled": bool(settings.redis_url),
            "sandbox": DockerSandbox().available(), "max_upload_mb": settings.max_upload_bytes // 1024**2,
            "max_files": settings.max_files, "agent_max_steps": settings.agent_max_steps, "mode": "single-user local workspace"}


@app.get("/api/repositories")
def repositories(session: Session = Depends(get_session)):
    return [repo_json(repo) for repo in session.scalars(select(Repository).order_by(Repository.created_at.desc()))]


@app.post("/api/repositories", status_code=202)
def create_repository(body: RepositoryCreate, session: Session = Depends(get_session)):
    repo = Repository(name="/".join(body.url.split("/")[-2:]), source_url=body.url)
    session.add(repo)
    session.commit()
    enqueue_index(session, repo)
    return repo_json(repo)


@app.post("/api/repositories/demo", status_code=202)
def create_demo(session: Session = Depends(get_session)):
    repo = Repository(name="acme / checkout-service", source_url="demo://shop")
    session.add(repo)
    session.commit()
    enqueue_index(session, repo)
    return repo_json(repo)


@app.post("/api/repositories/upload", status_code=202)
async def upload_repository(file: UploadFile, session: Session = Depends(get_session)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(422, "Upload a .zip repository archive")
    # The provided filename is a display label only, never a filesystem path.
    repo = Repository(name=Path(file.filename.replace("\\", "/")).stem[:150], source_url="upload://zip")
    session.add(repo)
    session.flush()
    archive = settings.data_dir / "uploads" / f"{repo.id}.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    try:
        size = 0
        with archive.open("wb") as output:
            while block := await file.read(65536):
                size += len(block)
                if size > settings.max_upload_bytes:
                    raise HTTPException(413, "ZIP exceeds the configured upload limit")
                output.write(block)
        import zipfile
        if not zipfile.is_zipfile(archive):
            raise HTTPException(422, "File is not a valid ZIP archive")
        session.commit()
    except Exception:
        session.rollback()
        archive.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    enqueue_index(session, repo)
    return repo_json(repo)


@app.get("/api/repositories/{repository_id}")
def repository(repository_id: str, session: Session = Depends(get_session)):
    return repo_json(entity(session, Repository, repository_id))


@app.post("/api/repositories/{repository_id}/index", status_code=202)
@serialized_job
def reindex(repository_id: str, session: Session = Depends(get_session)):
    return job_json(enqueue_index(session, entity(session, Repository, repository_id)))


@app.get("/api/repositories/{repository_id}/status")
def status(repository_id: str, session: Session = Depends(get_session)):
    repo = entity(session, Repository, repository_id)
    job = session.scalar(select(IndexingJob).where(IndexingJob.repository_id == repository_id).order_by(IndexingJob.created_at.desc()))
    return {"repository": repo_json(repo), "job": job_json(job)}


@app.get("/api/repositories/{repository_id}/files")
def files(repository_id: str, session: Session = Depends(get_session)):
    entity(session, Repository, repository_id)
    rows = session.scalars(select(RepositoryFile).where(RepositoryFile.repository_id == repository_id).order_by(RepositoryFile.path))
    return [{"path": row.path, "language": row.language, "line_count": row.line_count, "size_bytes": row.size_bytes} for row in rows]


@app.get("/api/repositories/{repository_id}/files/{path:path}")
def read_file(repository_id: str, path: str, session: Session = Depends(get_session)):
    entity(session, Repository, repository_id)
    try:
        safe_path(managed_root(repository_id), path)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    row = session.scalar(select(RepositoryFile).where(RepositoryFile.repository_id == repository_id, RepositoryFile.path == path))
    if not row:
        raise HTTPException(404, "File is not indexed")
    return {"path": row.path, "language": row.language, "content": row.content, "line_count": row.line_count, "symbols": row.symbols}


@app.post("/api/repositories/{repository_id}/query")
def query(repository_id: str, body: QueryRequest, session: Session = Depends(get_session)):
    ready(session, repository_id)
    try:
        return answer_question(session, repository_id, body.question, body.strategy, body.conversation_id)
    except ValueError as exc:
        session.rollback()
        raise HTTPException(422, redact_secrets(str(exc)))
    except Exception as exc:
        session.rollback()
        logger.warning(json.dumps({"event": "query_failed", "repository_id": repository_id, "error_type": type(exc).__name__}))
        raise HTTPException(502, "The provider could not complete this request. Check configuration and retry.")


@app.get("/api/repositories/{repository_id}/conversations")
def conversations(repository_id: str, session: Session = Depends(get_session)):
    entity(session, Repository, repository_id)
    result = []
    for row in session.scalars(select(Conversation).where(Conversation.repository_id == repository_id).order_by(Conversation.created_at.desc()).limit(30)):
        messages = session.scalars(select(Message).where(Message.conversation_id == row.id).order_by(Message.created_at))
        result.append({"id": row.id, "title": row.title, "created_at": iso_utc(row.created_at), "messages": [{"role": m.role, "content": m.content, "citations": m.citations, "metrics": m.metrics} for m in messages]})
    return result


@app.get("/api/repositories/{repository_id}/dependencies")
def dependencies(repository_id: str, session: Session = Depends(get_session)):
    ready(session, repository_id)
    return graph(session, repository_id)


@app.get("/api/repositories/{repository_id}/impact")
def impact_analysis(repository_id: str, path: str, session: Session = Depends(get_session)):
    ready(session, repository_id)
    try:
        return impact(session, repository_id, path)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.post("/api/repositories/{repository_id}/agent-runs", status_code=202)
@serialized_job
def create_agent_run(repository_id: str, body: AgentRequest, session: Session = Depends(get_session)):
    ready(session, repository_id)
    if session.scalar(select(AgentRun).where(AgentRun.repository_id == repository_id, AgentRun.status.in_(["queued", "running"]))):
        raise HTTPException(409, "An agent is already running for this repository")
    run = AgentRun(repository_id=repository_id, task=body.task, max_steps=min(body.max_steps, settings.agent_max_steps))
    session.add(run)
    session.commit()
    try:
        submit("agent", run.id)
    except Exception:
        run.status = "failed"
        run.error = "Background queue unavailable"
        session.commit()
        raise HTTPException(503, run.error)
    from app.agents import serialize_run
    return serialize_run(session, run)


@app.get("/api/repositories/{repository_id}/agent-runs")
def agent_runs(repository_id: str, session: Session = Depends(get_session)):
    entity(session, Repository, repository_id)
    from app.agents import serialize_run
    return [serialize_run(session, run) for run in session.scalars(select(AgentRun).where(AgentRun.repository_id == repository_id).order_by(AgentRun.created_at.desc()).limit(20))]


@app.get("/api/agent-runs/{run_id}")
def agent_run(run_id: str, session: Session = Depends(get_session)):
    from app.agents import serialize_run
    return serialize_run(session, entity(session, AgentRun, run_id))


@app.post("/api/agent-runs/{run_id}/{decision}")
@serialized_job
def decide_patch(run_id: str, decision: str, session: Session = Depends(get_session)):
    from app.agents import approve_run, reject_run
    run = entity(session, AgentRun, run_id)
    repo = entity(session, Repository, run.repository_id)
    if decision not in {"approve", "reject"}:
        raise HTTPException(404, "Unknown decision")
    if decision == "approve" and repo.status != "ready":
        raise HTTPException(409, "Wait for indexing to finish before applying a patch")
    if decision == "approve":
        idle_investigations(session, repo.id)
    try:
        result = approve_run(session, run) if decision == "approve" else reject_run(session, run)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    if decision == "approve":
        enqueue_index(session, repo)
    return result


@app.get("/api/repositories/{repository_id}/evaluation-dataset")
def evaluation_dataset(repository_id: str, session: Session = Depends(get_session)):
    ready(session, repository_id)
    from app.evaluations import ensure_dataset
    dataset = ensure_dataset(session, repository_id)
    return {"id": dataset.id, "name": dataset.name, "cases": dataset.cases}


@app.post("/api/repositories/{repository_id}/evaluations", status_code=202)
@serialized_job
def create_evaluation(repository_id: str, body: EvaluationRequest = EvaluationRequest(), session: Session = Depends(get_session)):
    ready(session, repository_id)
    from app.evaluations import ensure_dataset, serialize_evaluation
    if session.scalar(select(EvaluationRun).where(EvaluationRun.repository_id == repository_id, EvaluationRun.status.in_(["queued", "running"]))):
        raise HTTPException(409, "An evaluation is already running")
    dataset = ensure_dataset(session, repository_id)
    cases = [case.model_dump() for case in body.cases] if body.cases is not None else dataset.cases
    if not cases:
        raise HTTPException(422, "Provide at least one evaluation case")
    run = EvaluationRun(repository_id=repository_id, dataset_id=dataset.id, k=body.k, cases=cases)
    session.add(run)
    session.commit()
    try:
        submit("evaluation", run.id)
    except Exception:
        run.status = "failed"
        run.error = "Background queue unavailable"
        session.commit()
        raise HTTPException(503, run.error)
    return serialize_evaluation(run)


@app.get("/api/repositories/{repository_id}/evaluations")
def evaluations(repository_id: str, session: Session = Depends(get_session)):
    entity(session, Repository, repository_id)
    from app.evaluations import serialize_evaluation
    return [serialize_evaluation(run) for run in session.scalars(select(EvaluationRun).where(EvaluationRun.repository_id == repository_id).order_by(EvaluationRun.created_at.desc()).limit(20))]


@app.get("/api/evaluations/{run_id}")
def evaluation(run_id: str, session: Session = Depends(get_session)):
    from app.evaluations import serialize_evaluation
    return serialize_evaluation(entity(session, EvaluationRun, run_id))
