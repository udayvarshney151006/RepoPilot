import json

import httpx
import pytest

from app.config import settings
from app.parsing import parse_code
from app.providers import OpenAIEmbedding, OpenAIGeneration


def test_no_evidence_never_calls_llm(monkeypatch):
    class UnexpectedClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("No-evidence generation must not make a provider request")
    monkeypatch.setattr(httpx, "Client", UnexpectedClient)
    response = OpenAIGeneration().generate("Invent a payment flow", [])
    assert response["citation_ids"] == []
    assert "evidence" in response["answer"]
    assert response["input_tokens"] is None


def client_for(body):
    class Client:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, *args, **kwargs):
            return httpx.Response(200, json=body)
    return Client


def test_unknown_citations_reject_the_whole_generated_answer(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-provider-key")
    content = json.dumps({"answer": "Invented source claim", "citation_ids": ["valid", "invented"]})
    monkeypatch.setattr(httpx, "Client", client_for({"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}))
    result = OpenAIGeneration().generate("auth", [{"chunk_id": "valid", "content": "def auth(): pass"}])
    assert result["citation_ids"] == []
    assert "Invented source claim" not in result["answer"]
    assert result["input_tokens"] == 10


def test_external_embeddings_are_validated_and_normalized(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-provider-key")
    vector = [3.0, 4.0] + [0.0] * 382
    monkeypatch.setattr(httpx, "Client", client_for({"data": [{"index": 0, "embedding": vector}]}))
    result = OpenAIEmbedding().embed(["auth"])[0]
    assert result[:2] == [0.6, 0.8]
    monkeypatch.setattr(httpx, "Client", client_for({"data": [{"index": 0, "embedding": [0.0] * 384}]}))
    with pytest.raises(ValueError, match="empty vector"):
        OpenAIEmbedding().embed(["auth"])


def test_unicode_chunks_obey_byte_budget_without_losing_lines(monkeypatch):
    monkeypatch.setattr(settings, "max_chunk_chars", 80)
    source = "def unicode_example():\n" + "    text = 'भारत'\n" * 8
    chunks = parse_code(source, "python", "unicode.py").chunks
    assert all(len(row["content"].encode("utf-8")) <= 80 for row in chunks)
    assert "\n".join(row["content"] for row in chunks) == source.rstrip("\n")
