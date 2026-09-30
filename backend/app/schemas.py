from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.security import validate_github_url


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RepositoryCreate(StrictRequest):
    url: str = Field(min_length=10, max_length=300)

    @field_validator("url")
    @classmethod
    def github(cls, value):
        return validate_github_url(value)


class QueryRequest(StrictRequest):
    question: str = Field(min_length=2, max_length=2000)
    strategy: Literal["vector", "bm25", "hybrid", "hybrid_rerank"] = "hybrid_rerank"
    conversation_id: str | None = Field(default=None, max_length=36)


class AgentRequest(StrictRequest):
    task: str = Field(min_length=5, max_length=4000)
    max_steps: int = Field(default=12, ge=1, le=20)


class EvaluationCase(StrictRequest):
    question: str = Field(min_length=2, max_length=2000)
    expected_file: str = Field(min_length=1, max_length=300)
    expected_symbol: str = Field(default="", max_length=300)
    expected_answer_keywords: list[str] = Field(default_factory=list, max_length=30)


class EvaluationRequest(StrictRequest):
    cases: list[EvaluationCase] | None = Field(default=None, max_length=100)
    k: int = Field(default=5, ge=1, le=10)
