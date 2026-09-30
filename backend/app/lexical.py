"""Persisted BM25 term statistics; generation and chunk IDs bind them to the index."""
from __future__ import annotations

import json
import math
import os
import tempfile
from collections import Counter, OrderedDict
from pathlib import Path
from threading import RLock
from uuid import UUID

from .config import settings
from .models import CodeChunk
from .providers import tokenize

MAX_INDEX_BYTES = 64 * 1024 * 1024
MAX_INDEX_CHUNKS = 10000
MAX_CACHE_ENTRIES = 8
_cache: OrderedDict[str, dict] = OrderedDict()
_lock = RLock()


def _index_path(repository_id: str) -> Path:
    try:
        identity = str(UUID(repository_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError("Lexical index repository ID must be a UUID.") from exc
    if identity != repository_id.lower():
        raise ValueError("Lexical index repository ID must use canonical UUID notation.")
    return settings.data_dir / "indexes" / f"{identity}.json"


def _sources(chunks: list[CodeChunk]) -> list[CodeChunk]:
    sources = [chunk for chunk in chunks if chunk.file_path.rsplit("/", 1)[-1] != "evaluation.json"]
    identifiers = [chunk.id for chunk in sources]
    if any(not isinstance(identifier, str) or not identifier for identifier in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError("Flush unique chunk IDs before building the lexical index.")
    return sources


def _corpus(generation: str, chunks: list[CodeChunk]) -> dict:
    documents, frequency = {}, Counter()
    for chunk in chunks:
        counts = Counter(tokenize(f"{chunk.file_path} {chunk.symbol_name} {chunk.symbol_name} {chunk.content}"))
        documents[chunk.id] = {"terms": dict(counts), "length": sum(counts.values())}
        frequency.update(counts.keys())
    return {"version": 1, "generation": generation, "documents": documents, "document_frequency": dict(frequency),
            "average_length": sum(doc["length"] for doc in documents.values()) / max(len(documents), 1) or 1.0}


def _valid(corpus: dict, generation: str, identifiers: set[str]) -> bool:
    try:
        documents = corpus["documents"]
        if corpus["version"] != 1 or corpus["generation"] != generation or set(documents) != identifiers:
            return False
        frequency = Counter()
        for document in documents.values():
            terms = document["terms"]
            if not isinstance(terms, dict) or any(not isinstance(term, str) or type(count) is not int or count <= 0 for term, count in terms.items()):
                return False
            if type(document["length"]) is not int or document["length"] != sum(terms.values()):
                return False
            frequency.update(terms.keys())
        average = sum(doc["length"] for doc in documents.values()) / max(len(documents), 1) or 1.0
        return corpus["document_frequency"] == dict(frequency) and corpus["average_length"] == average
    except (KeyError, TypeError, AttributeError):
        return False


def _remember(key: str, corpus: dict) -> None:
    # Approximate Python-object weight, not just serialized bytes, bounds retained memory.
    weight = sum(80 + len(term) * 2 for document in corpus["documents"].values() for term in document["terms"])
    weight += sum(80 + len(term) * 2 for term in corpus["document_frequency"])
    corpus["cache_weight"] = weight
    if weight > MAX_INDEX_BYTES:
        _cache.pop(key, None)
        return
    _cache[key] = corpus
    _cache.move_to_end(key)
    while len(_cache) > MAX_CACHE_ENTRIES or sum(item["cache_weight"] for item in _cache.values()) > MAX_INDEX_BYTES:
        _cache.popitem(last=False)


def _persist(path: Path, corpus: dict) -> tuple[bool, int]:
    temporary = None
    size = 0
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            return False, 0
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".lexical-", delete=False) as stream:
            temporary = Path(stream.name)
            for segment in json.JSONEncoder(ensure_ascii=False, separators=(",", ":")).iterencode(corpus):
                encoded = segment.encode("utf-8")
                size += len(encoded)
                if size > MAX_INDEX_BYTES:
                    return False, size
                stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        return True, size
    except OSError:
        return False, size
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def build_index(repository_id: str, generation: str, chunks: list[CodeChunk]) -> dict:
    path, sources = _index_path(repository_id), _sources(chunks)
    corpus = _corpus(generation, sources)
    with _lock:
        persisted, size = _persist(path, corpus) if len(sources) <= MAX_INDEX_CHUNKS else (False, 0)
        _remember(str(path.resolve()), corpus)
    return {"generation": generation, "documents": len(sources), "persisted": persisted, "artifact_bytes": size}


def search_index(repository_id: str, generation: str, question: str,
                 chunks: list[CodeChunk], limit: int = 30) -> list[tuple[str, float]]:
    path, sources = _index_path(repository_id), _sources(chunks)
    identifiers = {chunk.id for chunk in sources}
    key = str(path.resolve())
    with _lock:
        corpus = _cache.get(key)
        if corpus is not None and (corpus["generation"] != generation or set(corpus["documents"]) != identifiers):
            corpus = None
        if corpus is None and path.is_file() and not path.is_symlink():
            try:
                if path.stat().st_size <= MAX_INDEX_BYTES:
                    loaded = json.loads(path.read_bytes())
                    if _valid(loaded, generation, identifiers):
                        corpus = loaded
            except (OSError, ValueError, RecursionError):
                pass
        if corpus is None:
            corpus = _corpus(generation, sources)
            if len(sources) <= MAX_INDEX_CHUNKS:
                _persist(path, corpus)
        _remember(key, corpus)
    scores = {identifier: 0.0 for identifier in corpus["documents"]}
    n, average = len(scores), corpus["average_length"]
    for term in set(tokenize(question)):
        df = corpus["document_frequency"].get(term, 0)
        if not df:
            continue
        inverse_frequency = math.log(1 + (n - df + 0.5) / (df + 0.5))
        for identifier, document in corpus["documents"].items():
            frequency = document["terms"].get(term, 0)
            if frequency:
                normalization = 1.5 * (1 - 0.75 + 0.75 * document["length"] / average)
                scores[identifier] += inverse_frequency * frequency * 2.5 / (frequency + normalization)
    return sorted(((identifier, score) for identifier, score in scores.items() if score > 0),
                  key=lambda item: -item[1])[:max(0, min(limit, 100))]
