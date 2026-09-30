import json
import logging
import shutil
import stat
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import quote

import httpx
from sqlalchemy import delete, select

from app.config import PROJECT_ROOT, settings
from app.db import SessionLocal
from app.models import CodeChunk, EvaluationDataset, IndexingJob, Repository, RepositoryFile, index_generation, utcnow
from app.lexical import build_index
from app.parsing import ParsedFile, parse_code
from app.providers import embedding_provider
from app.security import EXTENSIONS, allowed_file, redact_secrets, safe_path, validate_github_url

logger = logging.getLogger("repopilot.jobs")


def extract_zip(archive: Path, destination: Path):
    total = 0
    count = 0
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        if len(entries) > settings.max_files * 5:
            raise ValueError("Archive contains too many entries")
        for entry in entries:
            # Validate EVERY member before filtering; even ignored entries cannot escape.
            safe_path(destination, entry.filename.rstrip("/"))
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError("Symbolic links are not accepted in repository archives")
            if entry.flag_bits & 1:
                raise ValueError("Encrypted ZIP archives are not supported")
            total += entry.file_size
            if total > settings.max_repository_bytes:
                raise ValueError("Expanded repository exceeds the configured size limit")
            if entry.is_dir() or not allowed_file(entry.filename):
                continue
            if entry.file_size > settings.max_file_bytes:
                continue
            count += 1
            if count > settings.max_files:
                raise ValueError("Repository contains too many supported files")
            target = safe_path(destination, entry.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            # Per-file streaming cap also defends against incorrect archive metadata.
            with zipped.open(entry) as source, target.open("wb") as output:
                copied = 0
                while block := source.read(65536):
                    copied += len(block)
                    if copied > settings.max_file_bytes:
                        raise ValueError("Archive file exceeded declared size")
                    output.write(block)


def download_github(url: str, archive: Path):
    url = validate_github_url(url)
    owner, name = url.rsplit("/", 2)[-2:]
    with httpx.Client(timeout=40, follow_redirects=False, headers={"User-Agent": "RepoPilot/0.1", "Accept": "application/vnd.github+json"}) as client:
        info = client.get(f"https://api.github.com/repos/{owner}/{name}")
        if info.status_code != 200:
            raise ValueError(f"Public GitHub repository could not be read (HTTP {info.status_code})")
        branch = info.json().get("default_branch")
        if not isinstance(branch, str) or not branch or len(branch) > 250:
            raise ValueError("GitHub did not return a valid default branch")
        endpoint = f"https://codeload.github.com/{owner}/{name}/zip/refs/heads/{quote(branch, safe='')}"
        with client.stream("GET", endpoint) as response:
            if response.status_code != 200:
                raise ValueError(f"GitHub archive download failed (HTTP {response.status_code})")
            size = 0
            with archive.open("wb") as output:
                for block in response.iter_bytes(65536):
                    size += len(block)
                    if size > settings.max_upload_bytes:
                        raise ValueError("GitHub archive exceeds download limit")
                    output.write(block)


def managed_root(repository_id: str) -> Path:
    return settings.data_dir / "repositories" / repository_id


def index_repository(repository_id: str):
    with SessionLocal() as session:
        repo = session.get(Repository, repository_id)
        if not repo:
            return
        job = session.scalar(select(IndexingJob).where(IndexingJob.repository_id == repository_id, IndexingJob.status == "queued").order_by(IndexingJob.created_at.desc()))
        if not job:
            job = IndexingJob(repository_id=repository_id)
            session.add(job)
        def stage(name: str, progress: int):
            repo.status = name
            repo.error = None
            job.status = "running"
            job.stage = name
            job.progress = progress
            session.commit()
            logger.info(json.dumps({"event": "index_stage", "repository_id": repository_id, "stage": name, "progress": progress}))
        try:
            stage("cloning", 8)
            root = managed_root(repository_id)
            root.mkdir(parents=True, exist_ok=True)
            if not repo.root_path:
                if repo.source_url == "demo://shop":
                    shutil.copytree(PROJECT_ROOT / "demo-repository", root, dirs_exist_ok=True)
                else:
                    archive = settings.data_dir / "uploads" / f"{repository_id}.zip"
                    archive.parent.mkdir(parents=True, exist_ok=True)
                    if repo.source_url.startswith("https://github.com/"):
                        download_github(repo.source_url, archive)
                    extract_zip(archive, root)
                    children = list(root.iterdir())
                    # GitHub/ZIP root folder normalization without moving/deleting paths.
                    if len(children) == 1 and children[0].is_dir():
                        root = children[0]
                repo.root_path = str(root.resolve())
            else:
                root = Path(repo.root_path)
                if not root.resolve().is_relative_to(managed_root(repository_id).resolve()):
                    raise ValueError("Repository root is outside managed storage")
            stage("parsing", 25)
            parsed_files = []
            warnings = []
            total = 0
            for source in sorted(root.rglob("*")):
                if not source.is_file() or source.is_symlink():
                    continue
                path = source.relative_to(root).as_posix()
                if not allowed_file(path):
                    continue
                safe_path(root, path)
                size = source.stat().st_size
                if size > settings.max_file_bytes:
                    warnings.append(f"Skipped {path}: file exceeds size limit")
                    continue
                total += size
                if total > settings.max_repository_bytes or len(parsed_files) >= settings.max_files:
                    raise ValueError("Repository exceeds indexing limits")
                try:
                    raw = source.read_text(encoding="utf-8")
                except UnicodeError:
                    continue
                if "\x00" in raw:
                    continue
                if any(len(line.encode("utf-8")) > settings.max_chunk_chars for line in raw.splitlines()):
                    warnings.append(f"Skipped {path}: an oversized line exceeds the {settings.max_chunk_chars}-byte code budget")
                    continue
                content = redact_secrets(raw)
                language = EXTENSIONS[source.suffix.lower()]
                # Ground-truth questions/answers must never enter the retrieval corpus.
                parsed = ParsedFile([], [], []) if source.name == "evaluation.json" else parse_code(content, language, path)
                if any(len(symbol["name"]) > 300 for symbol in parsed.symbols):
                    warnings.append(f"Skipped {path}: symbol name exceeds metadata limits")
                    continue
                parsed_files.append((path, language, content, size, parsed))
            if not parsed_files:
                raise ValueError("No supported text/source files found in this repository")
            # Parsing completes before deleting the old index; failed rebuild retains old data.
            stage("embedding", 55)
            embedder = embedding_provider()
            chunk_data = [(path, language, chunk) for path, language, _, _, parsed in parsed_files for chunk in parsed.chunks]
            if len(chunk_data) > settings.max_chunks:
                raise ValueError(f"Repository exceeds the {settings.max_chunks}-chunk indexing limit")
            texts = [f"{path}\n{chunk['symbol_name']}\n{chunk['content']}" for path, _, chunk in chunk_data]
            vectors = embedder.embed(texts)
            stage("indexing", 85)
            session.execute(delete(CodeChunk).where(CodeChunk.repository_id == repository_id))
            session.execute(delete(RepositoryFile).where(RepositoryFile.repository_id == repository_id))
            file_ids = {}
            for path, language, content, size, parsed in parsed_files:
                file = RepositoryFile(repository_id=repository_id, path=path, language=language, content=content,
                    line_count=len(content.splitlines()), size_bytes=size, symbols=parsed.symbols, imports=parsed.imports)
                session.add(file)
                session.flush()
                file_ids[path] = file.id
            indexed_chunks = []
            for (path, language, chunk), vector in zip(chunk_data, vectors):
                row = CodeChunk(repository_id=repository_id, file_id=file_ids[path], file_path=path, language=language, embedding=vector, **chunk)
                session.add(row)
                indexed_chunks.append(row)
            session.flush()
            repo.file_count = len(parsed_files)
            repo.chunk_count = len(chunk_data)
            repo.languages = dict(Counter(language for _, language, _, _, _ in parsed_files))
            repo.index_warnings = warnings[:20] + ([f"{len(warnings) - 20} more files skipped by size budgets"] if len(warnings) > 20 else [])
            repo.embedding_provider = embedder.name
            repo.indexed_at = utcnow()
            lexical_metadata = build_index(repository_id, index_generation(repo.indexed_at), indexed_chunks)
            if not lexical_metadata["persisted"]:
                repo.index_warnings = [*repo.index_warnings, "Lexical index could not be persisted; queries will rebuild a bounded in-memory index"]
            repo.status = "ready"
            job.status = "completed"
            job.stage = "ready"
            job.progress = 100
            job.finished_at = utcnow()
            session.commit()
            dataset = root / "evaluation.json"
            if dataset.exists() and not session.scalar(select(EvaluationDataset).where(EvaluationDataset.repository_id == repository_id)):
                try:
                    data = json.loads(dataset.read_text())
                    cases = data if isinstance(data, list) else data.get("cases", [])
                    # Avoid taking repository-provided evaluations as arbitrary application config.
                    from app.schemas import EvaluationCase
                    validated = [EvaluationCase.model_validate(case).model_dump() for case in cases[:100]]
                    session.add(EvaluationDataset(repository_id=repository_id, name="Repository evaluation dataset", cases=validated))
                    session.commit()
                except (ValueError, TypeError, AttributeError):
                    session.rollback()
        except Exception as exc:
            session.rollback()
            repo = session.get(Repository, repository_id)
            repo.status = "failed"
            # Scrub exception text before exposing operational errors.
            message = redact_secrets(str(exc))[:500] if isinstance(exc, (ValueError, zipfile.BadZipFile)) else f"Indexing failed ({type(exc).__name__}). Check server configuration and retry."
            repo.error = message
            job.status = "failed"
            job.error = message
            job.finished_at = utcnow()
            session.add(job)
            session.commit()
            logger.warning(json.dumps({"event": "index_failed", "repository_id": repository_id, "error_type": type(exc).__name__}))
