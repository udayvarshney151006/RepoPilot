"""Executed retrieval benchmarks and explicitly limited answer/citation proxies."""
from __future__ import annotations

import json
from datetime import timezone
import logging
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from sqlalchemy import select

from .config import settings
from .db import SessionLocal
from .models import CodeChunk, EvaluationDataset, EvaluationRun, Repository, utcnow

logger = logging.getLogger(__name__)
STRATEGIES = ("vector", "bm25", "hybrid", "hybrid_rerank")


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    question: str = Field(min_length=1, max_length=2000)
    expected_file: str = Field(min_length=1, max_length=500)
    expected_symbol: str = Field(default="", max_length=300)
    expected_answer_keywords: list[str] = Field(default_factory=list, max_length=30)


def validated_cases(cases: list[dict]) -> list[dict]:
    if not isinstance(cases, list) or not 1 <= len(cases) <= 100:
        raise ValueError("An evaluation requires between 1 and 100 cases.")
    return [case.model_dump() for case in TypeAdapter(list[EvaluationCase]).validate_python(cases)]


def ensure_dataset(session, repository_id: str) -> EvaluationDataset:
    existing = session.scalar(select(EvaluationDataset).where(EvaluationDataset.repository_id == repository_id))
    if existing:
        return existing
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise ValueError("Repository does not exist.")
    chunks = session.scalars(select(CodeChunk).where(CodeChunk.repository_id == repository_id)
                              .order_by(CodeChunk.file_path, CodeChunk.start_line)).all()
    if not chunks:
        raise ValueError("Index source code before creating an evaluation dataset.")
    locations = {(chunk.file_path, chunk.symbol_name) for chunk in chunks}
    supplied = Path(repository.root_path) / "evaluation.json"
    cases = []
    if supplied.is_file() and not supplied.is_symlink() and supplied.stat().st_size < 1024 * 1024:
        try:
            parsed = validated_cases(json.loads(supplied.read_text(encoding="utf-8")))
            cases = [case for case in parsed if (case["expected_file"], case["expected_symbol"]) in locations]
        except (ValueError, OSError):
            cases = []
    if cases:
        name = "Repository evaluation.json — source-validated cases"
    else:
        seen = set()
        for chunk in chunks:
            identity = (chunk.file_path, chunk.symbol_name)
            if identity in seen or chunk.symbol_type == "module":
                continue
            seen.add(identity)
            cases.append({"question": f"Where is {chunk.symbol_name} defined?",
                          "expected_file": chunk.file_path, "expected_symbol": chunk.symbol_name,
                          "expected_answer_keywords": [chunk.symbol_name]})
            if len(cases) >= 12:
                break
        if not cases:
            chunk = chunks[0]
            cases = [{"question": f"Explain the code in {chunk.file_path}.", "expected_file": chunk.file_path,
                      "expected_symbol": chunk.symbol_name, "expected_answer_keywords": []}]
        name = "Generated identifier discovery cases — limited ground truth"
    dataset = EvaluationDataset(repository_id=repository_id, name=name, cases=cases)
    session.add(dataset)
    session.commit()
    return dataset


def score_case(case: dict, retrieved: list[dict], answer: str, citation_ids: list,
               valid_chunks: dict[str, CodeChunk], k: int) -> dict:
    """One gold file/symbol target per case; split chunks count as the same target."""
    ranked = retrieved[:k]
    rank = next((index for index, chunk in enumerate(ranked, 1)
                 if chunk["file_path"] == case["expected_file"]
                 and (not case.get("expected_symbol") or chunk["symbol_name"] == case["expected_symbol"])), None)
    keywords = case.get("expected_answer_keywords", [])
    matched = [keyword for keyword in keywords if keyword.casefold() in answer.casefold()]
    evidence = {chunk["chunk_id"]: chunk for chunk in retrieved}
    valid_ids, invalid_ids = [], []
    for identifier in citation_ids:
        row = evidence.get(identifier) if isinstance(identifier, str) else None
        source = valid_chunks.get(identifier) if isinstance(identifier, str) else None
        if (row and source and row.get("file_path") == source.file_path
                and row.get("symbol_name") == source.symbol_name
                and row.get("start_line") == source.start_line
                and row.get("end_line") == source.end_line
                and row.get("content") == source.content):
            valid_ids.append(identifier)
        else:
            invalid_ids.append(str(identifier)[:200])
    return {"recall_at_k": float(rank is not None), "reciprocal_rank": 1 / rank if rank else 0.0,
            "first_relevant_rank": rank, "answer_keyword_coverage": len(matched) / len(keywords) if keywords else None,
            "matched_keywords": matched, "citation_validity": len(valid_ids) / len(citation_ids) if citation_ids else 0.0,
            "valid_citation_ids": valid_ids, "invalid_citation_ids": invalid_ids}


def _mean(rows: list[dict], key: str) -> float | None:
    values = [row[key] for row in rows if row.get(key) is not None]
    return round(sum(values) / len(values), 6) if values else None


def _sum_known(rows: list[dict], key: str) -> int | float | None:
    values = [row[key] for row in rows if row.get(key) is not None]
    return sum(values) if len(values) == len(rows) else None


def aggregate(strategy: str, results: list[dict], k: int) -> dict:
    return {"strategy": strategy, "k": k, "cases": len(results),
            "recall_at_k": _mean(results, "recall_at_k"), "mrr": _mean(results, "reciprocal_rank"),
            "avg_latency_ms": _mean(results, "latency_ms"), "avg_retrieval_ms": _mean(results, "retrieval_ms"),
            "avg_retrieved_chunks": _mean(results, "retrieved_chunks"),
            "answer_keyword_coverage": _mean(results, "answer_keyword_coverage"),
            "citation_validity": _mean(results, "citation_validity"),
            "input_tokens": _sum_known(results, "input_tokens"), "output_tokens": _sum_known(results, "output_tokens"),
            "estimated_cost": _sum_known(results, "estimated_cost"),
            "answer_assessment": "Keyword coverage is a relevance proxy; citation validity checks source locations and the retrieval allowlist. Neither measures semantic correctness or entailment."}


def execute_evaluation(run_id: str) -> None:
    from .providers import generation_provider
    from .retrieval import retrieve
    with SessionLocal() as session:
        run = session.get(EvaluationRun, run_id)
        if run is None or run.status not in {"queued", "running"}:
            return
        try:
            repository = session.get(Repository, run.repository_id)
            if repository is None or repository.status != "ready":
                raise ValueError("Repository must be indexed before evaluating.")
            run.status, run.error = "running", None
            run.metrics, run.results = [], []
            cases = validated_cases(run.cases or ensure_dataset(session, run.repository_id).cases)
            k = max(1, min(run.k, 20))
            session.commit()
            chunks = {chunk.id: chunk for chunk in session.scalars(select(CodeChunk).where(
                CodeChunk.repository_id == run.repository_id)).all()}
            provider = generation_provider()
            input_price = getattr(settings, "llm_input_cost_per_million", None)
            output_price = getattr(settings, "llm_output_cost_per_million", None)
            for strategy in STRATEGIES:
                strategy_results = []
                for index, case in enumerate(cases):
                    started = time.perf_counter()
                    retrieved, timing = retrieve(session, run.repository_id, case["question"], strategy=strategy, k=k)
                    retrieval_ms = (time.perf_counter() - started) * 1000
                    generation_started = time.perf_counter()
                    generated = provider.generate(case["question"], retrieved)
                    answer = generated["answer"]
                    citation_ids = generated.get("citation_ids", [])
                    if not isinstance(citation_ids, list):
                        raise ValueError("Generation provider returned invalid citation identifiers.")
                    input_tokens, output_tokens = generated.get("input_tokens"), generated.get("output_tokens")
                    cost = None
                    if (input_price is not None and output_price is not None
                            and input_tokens is not None and output_tokens is not None):
                        cost = (input_tokens * input_price + output_tokens * output_price) / 1000000
                    scored = score_case(case, retrieved, answer, citation_ids, chunks, k)
                    row = {"strategy": strategy, "case_index": index, "question": case["question"],
                           "expected_file": case["expected_file"], "expected_symbol": case["expected_symbol"],
                           "answer": answer[:12000], "retrieved_chunk_ids": [chunk["chunk_id"] for chunk in retrieved],
                           "retrieved_chunks": len(retrieved), "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                           "retrieval_ms": round(retrieval_ms, 3),
                           "generation_ms": round((time.perf_counter() - generation_started) * 1000, 3),
                           "retrieval_timing": timing, "model": generated.get("model"), "input_tokens": input_tokens,
                           "output_tokens": output_tokens, "estimated_cost": cost, **scored}
                    strategy_results.append(row)
                    run.results = [*(run.results or []), row]
                    session.commit()
                run.metrics = [*(run.metrics or []), aggregate(strategy, strategy_results, k)]
                session.commit()
            run.status = "completed"
            run.finished_at = utcnow()
            session.commit()
            logger.info(json.dumps({"event": "evaluation_completed", "run_id": run_id,
                                    "cases": len(cases), "strategies": len(STRATEGIES)}))
        except Exception as exc:
            session.rollback()
            run = session.get(EvaluationRun, run_id)
            if run:
                run.status = "failed"
                run.error = str(exc)[:500] if isinstance(exc, ValueError) else f"Evaluation failed ({type(exc).__name__})."
                run.finished_at = utcnow()
                session.commit()
            logger.warning(json.dumps({"event": "evaluation_failed", "run_id": run_id,
                                       "error_type": type(exc).__name__}))


def serialize_evaluation(run: EvaluationRun) -> dict:
    created_at = run.created_at.replace(tzinfo=timezone.utc) if run.created_at.tzinfo is None else run.created_at
    return {"id": run.id, "repository_id": run.repository_id, "status": run.status,
            "error": run.error, "created_at": created_at.isoformat(), "k": run.k,
            "metrics": run.metrics or [], "results": run.results or []}
