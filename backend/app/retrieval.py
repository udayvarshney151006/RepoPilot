import json
import logging
import math
import time
from collections import Counter
from uuid import uuid4

from sqlalchemy import select

from app import cache
from app.config import settings
from app.models import CodeChunk, Conversation, Message, Repository, index_generation
from app.lexical import search_index
from app.providers import IdentifierReranker, embedding_provider, generation_provider, tokenize

logger = logging.getLogger("repopilot.requests")
STRATEGIES = {"vector", "bm25", "hybrid", "hybrid_rerank"}


def bm25_scores(query: str, documents: list[str]) -> list[float]:
    tokens = [tokenize(doc) for doc in documents]
    counts = [Counter(doc) for doc in tokens]
    n = len(tokens)
    average = sum(map(len, tokens)) / max(n, 1) or 1
    scores = [0.0] * n
    for term in set(tokenize(query)):
        df = sum(term in doc for doc in counts)
        idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
        for index, doc in enumerate(counts):
            frequency = doc[term]
            length_norm = 1.5 * (1 - 0.75 + 0.75 * len(tokens[index]) / average)
            scores[index] += idf * frequency * 2.5 / (frequency + length_norm) if frequency else 0
    return scores


def reciprocal_rank_fusion(rankings: list[list[str]], constant: int = 60) -> dict[str, float]:
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking, 1):
            fused[cid] = fused.get(cid, 0) + 1 / (constant + rank)
    return fused


def citation(chunk: CodeChunk, score=0.0) -> dict:
    return {"chunk_id": chunk.id, "file_path": chunk.file_path, "language": chunk.language,
            "symbol_name": chunk.symbol_name, "symbol_type": chunk.symbol_type,
            "start_line": chunk.start_line, "end_line": chunk.end_line, "content": chunk.content, "score": score}


class VectorStore:
    """SQL pgvector in PostgreSQL; exact cosine over JSON vectors in local SQLite."""
    def search(self, session, repository_id: str, query_vector: list[float], chunks: list[CodeChunk], limit: int = 30):
        if session.bind.dialect.name == "postgresql":
            distance = CodeChunk.embedding.cosine_distance(query_vector)
            rows = session.execute(select(CodeChunk.id, distance.label("distance"))
                .where(CodeChunk.repository_id == repository_id, ~CodeChunk.file_path.like("%evaluation.json")).order_by(distance).limit(limit)).all()
            return [(cid, 1 - float(dist)) for cid, dist in rows if dist is not None and 1 - float(dist) > 0.10]
        query_norm = math.sqrt(sum(v * v for v in query_vector)) or 1
        scores = [(row.id, sum(a * b for a, b in zip(row.embedding, query_vector)) / (query_norm * (math.sqrt(sum(v * v for v in row.embedding)) or 1))) for row in chunks]
        return sorted((item for item in scores if item[1] > 0.10), key=lambda x: -x[1])[:limit]


def retrieve(session, repository_id: str, question: str, strategy: str = "hybrid_rerank", k: int = 8):
    start = time.perf_counter()
    if strategy not in STRATEGIES:
        raise ValueError("Unknown retrieval strategy")
    repo = session.get(Repository, repository_id)
    if not repo or repo.status != "ready":
        raise ValueError("Repository must finish indexing before retrieval")
    embedder = embedding_provider()
    if repo.embedding_provider != embedder.name:
        raise ValueError("Embedding provider changed; reindex this repository before querying")
    chunks = [row for row in session.scalars(select(CodeChunk).where(CodeChunk.repository_id == repository_id))
              if row.file_path.rsplit("/", 1)[-1] != "evaluation.json"]
    by_id = {row.id: row for row in chunks}
    lexical = []
    dense = []
    if strategy != "vector":
        lexical = search_index(repository_id, index_generation(repo.indexed_at), question, chunks, limit=30)
    if strategy != "bm25":
        dense = VectorStore().search(session, repository_id, embedder.embed([question])[0], chunks)
    if strategy in {"hybrid", "hybrid_rerank"}:
        fused = reciprocal_rank_fusion([[cid for cid, _ in lexical], [cid for cid, _ in dense]])
        ranked = sorted(fused.items(), key=lambda x: -x[1])[:30]
    else:
        fused = {}
        ranked = lexical if strategy == "bm25" else dense
    rows = [citation(by_id[cid], round(float(score), 6)) for cid, score in ranked]
    retrieval_ms = (time.perf_counter() - start) * 1000
    rerank_start = time.perf_counter()
    if strategy == "hybrid_rerank":
        for row in rows:
            row["fusion_score"] = fused[row["chunk_id"]]
        rows = IdentifierReranker().rank(question, rows)
    reranking_ms = (time.perf_counter() - rerank_start) * 1000 if strategy == "hybrid_rerank" else 0.0
    selected = []
    context_chars = 0
    for row in rows[:k]:
        size = len(row["content"]) + len(row["file_path"]) + len(row["symbol_name"])
        if context_chars + size <= settings.max_context_chars:
            selected.append(row)
            context_chars += size
    return selected, {"retrieval_ms": round(retrieval_ms, 2), "reranking_ms": round(reranking_ms, 2), "candidate_count": len(ranked), "context_chars": context_chars}


def answer_question(session, repository_id: str, question: str, strategy="hybrid_rerank", conversation_id=None):
    start = time.perf_counter()
    repo = session.get(Repository, repository_id)
    if not repo or repo.status != "ready":
        raise ValueError("Repository is not ready")
    if conversation_id:
        conversation = session.get(Conversation, conversation_id)
        if not conversation or conversation.repository_id != repository_id:
            raise ValueError("Conversation does not belong to this repository")
    else:
        conversation = Conversation(repository_id=repository_id, title=question[:160])
        session.add(conversation)
        session.flush()
    cache_key = cache.key(repository_id, str(repo.indexed_at), repo.embedding_provider, generation_provider().__class__.__name__, settings.llm_model, question, strategy)
    cached = cache.get(cache_key)
    if cached:
        response = cached
        response["metrics"]["cached_original_total_ms"] = response["metrics"]["total_ms"]
        response["metrics"]["cache_hit"] = True
        response["metrics"].update({"retrieval_ms": 0, "reranking_ms": 0, "llm_ms": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost": 0})
        response["metrics"]["total_ms"] = round((time.perf_counter() - start) * 1000, 2)
    else:
        evidence, metrics = retrieve(session, repository_id, question, strategy)
        llm_start = time.perf_counter()
        generated = generation_provider().generate(question, evidence)
        metrics.update({"llm_ms": round((time.perf_counter() - llm_start) * 1000, 2),
            "total_ms": round((time.perf_counter() - start) * 1000, 2), "retrieved_chunks": len(evidence),
            "model": generated["model"], "input_tokens": generated.get("input_tokens"),
            "output_tokens": generated.get("output_tokens"), "estimated_cost": None, "cache_hit": False})
        if metrics["input_tokens"] is not None and metrics["output_tokens"] is not None and settings.llm_input_cost_per_million is not None and settings.llm_output_cost_per_million is not None:
            metrics["estimated_cost"] = (metrics["input_tokens"] * settings.llm_input_cost_per_million + metrics["output_tokens"] * settings.llm_output_cost_per_million) / 1_000_000
        response = {"answer": generated["answer"], "citations": [row for row in evidence if row["chunk_id"] in generated["citation_ids"]],
                    "retrieval": evidence, "metrics": metrics, "mode": "extractive" if generated["model"] == "extractive-offline" else "llm"}
        cache.put(cache_key, response)
    response["conversation_id"] = conversation.id
    session.add(Message(conversation_id=conversation.id, role="user", content=question))
    session.add(Message(conversation_id=conversation.id, role="assistant", content=response["answer"], citations=response["citations"], metrics=response["metrics"]))
    session.commit()
    logger.info(json.dumps({"event": "query", "request_id": str(uuid4()), "repository_id": repository_id, "strategy": strategy, **response["metrics"]}))
    return response
