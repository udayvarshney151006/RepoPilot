"""Persisted lexical search keeps BM25 semantics without retokenizing code on queries."""
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app import lexical
from app.config import settings
from app.retrieval import bm25_scores


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    lexical._cache.clear()
    chunks = [SimpleNamespace(id=str(uuid4()), file_path="shop/payment.py", symbol_name="PaymentService",
                              content="def checkout(): return PaymentService.total"),
              SimpleNamespace(id=str(uuid4()), file_path="shop/auth.py", symbol_name="login",
                              content="def login(): return authenticate_user()"),
              SimpleNamespace(id=str(uuid4()), file_path="README.md", symbol_name="README.md",
                              content="PaymentService checkout " + "noise " * 100)]
    yield str(uuid4()), "generation-1", chunks
    lexical._cache.clear()


def test_atomic_persisted_corpus_matches_actual_bm25_arithmetic(corpus):
    identity, generation, chunks = corpus
    built = lexical.build_index(identity, generation, chunks)
    assert built["persisted"]
    path = lexical._index_path(identity)
    saved = json.loads(path.read_text())
    assert saved["generation"] == generation
    assert set(saved["documents"]) == {chunk.id for chunk in chunks}
    assert saved["document_frequency"]["payment"] > 0
    assert not list(path.parent.glob(".lexical-*"))
    lexical._cache.clear()
    actual = lexical.search_index(identity, generation, "PaymentService checkout", chunks)
    expected = bm25_scores("PaymentService checkout", [f"{chunk.file_path} {chunk.symbol_name} {chunk.symbol_name} {chunk.content}" for chunk in chunks])
    assert dict(actual) == pytest.approx({chunk.id: score for chunk, score in zip(chunks, expected) if score > 0})


def test_persisted_query_tokenizes_only_the_question(corpus, monkeypatch):
    identity, generation, chunks = corpus
    lexical.build_index(identity, generation, chunks)
    lexical._cache.clear()
    original = lexical.tokenize
    observed = []
    def tokenized(text):
        observed.append(text)
        return original(text)
    monkeypatch.setattr(lexical, "tokenize", tokenized)
    assert lexical.search_index(identity, generation, "PaymentService", chunks)
    assert observed == ["PaymentService"]


@pytest.mark.parametrize("corruption", ["{broken-json", '{"version":1}', '[]'])
def test_corrupt_missing_or_stale_disk_index_rebuilds(corpus, corruption):
    identity, generation, chunks = corpus
    lexical.build_index(identity, generation, chunks)
    lexical._cache.clear()
    path = lexical._index_path(identity)
    path.write_text(corruption)
    assert lexical.search_index(identity, generation, "PaymentService", chunks)
    assert json.loads(path.read_text())["generation"] == generation
    lexical._cache.clear()
    path.unlink()
    assert lexical.search_index(identity, "generation-2", "PaymentService", chunks)
    assert json.loads(path.read_text())["generation"] == "generation-2"


def test_changed_chunk_allowlist_invalidates_cached_and_persisted_index(corpus):
    identity, generation, chunks = corpus
    lexical.build_index(identity, generation, chunks)
    newer = [SimpleNamespace(id=str(uuid4()), file_path="new.py", symbol_name="new_function", content="def new_function(): return 1")]
    assert lexical.search_index(identity, generation, "PaymentService", newer) == []
    results = lexical.search_index(identity, generation, "new_function", newer)
    assert [identifier for identifier, _ in results] == [newer[0].id]


def test_evaluation_ground_truth_never_enters_lexical_corpus(corpus):
    identity, generation, chunks = corpus
    evaluation = SimpleNamespace(id=str(uuid4()), file_path="evaluation.json", symbol_name="evaluation.json", content="inventedbenchmarkterm")
    lexical.build_index(identity, generation, [*chunks, evaluation])
    saved = json.loads(lexical._index_path(identity).read_text())
    assert evaluation.id not in saved["documents"]
    assert lexical.search_index(identity, generation, "inventedbenchmarkterm", [*chunks, evaluation]) == []


def test_oversized_artifact_uses_memory_and_removes_temporary_file(corpus, monkeypatch):
    identity, generation, chunks = corpus
    monkeypatch.setattr(lexical, "MAX_INDEX_BYTES", 32)
    built = lexical.build_index(identity, generation, chunks)
    assert built["persisted"] is False
    assert not lexical._index_path(identity).exists()
    assert lexical.search_index(identity, generation, "PaymentService", chunks)
    assert not list(lexical._index_path(identity).parent.glob(".lexical-*"))


def test_cache_retains_at_most_eight_repository_corpora(corpus):
    _, generation, chunks = corpus
    for _ in range(12):
        lexical.build_index(str(uuid4()), generation, chunks)
    assert len(lexical._cache) == 8


@pytest.mark.parametrize("identity", ["../outside", "repo/name", "not-a-uuid", "00000000000000000000000000000000"])
def test_index_storage_path_requires_canonical_uuid(corpus, identity):
    _, generation, chunks = corpus
    with pytest.raises(ValueError, match="UUID"):
        lexical.build_index(identity, generation, chunks)


def test_unflushed_chunk_ids_are_rejected(corpus):
    identity, generation, chunks = corpus
    chunks[0].id = None
    with pytest.raises(ValueError, match="Flush"):
        lexical.build_index(identity, generation, chunks)
