from pathlib import Path
from pydantic import Field, model_validator

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMAGE_REFERENCE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/@-]*$"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(str(PROJECT_ROOT / ".env"), ".env"), extra="ignore")

    database_url: str = f"sqlite:///{(PROJECT_ROOT / '.data' / 'repopilot.db').as_posix()}"
    data_dir: Path = PROJECT_ROOT / ".data"
    redis_url: str = ""
    job_backend: str = "local"
    llm_provider: str = "extractive"
    embedding_provider: str = "local"
    llm_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=384, ge=384, le=384)
    llm_input_cost_per_million: float | None = None
    llm_output_cost_per_million: float | None = None
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    provider_timeout: int = 90
    query_cache_ttl: int = 120
    api_auth_token: str = ""
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    max_upload_bytes: int = 25 * 1024 * 1024
    max_repository_bytes: int = 64 * 1024 * 1024
    max_file_bytes: int = 512 * 1024
    max_files: int = 2000
    max_chunks: int = 10000
    max_chunk_lines: int = 100
    max_chunk_chars: int = 6000
    max_context_chars: int = 30000
    sandbox_enabled: bool = True
    sandbox_timeout: int = 45
    sandbox_image: str = Field(default="repopilot-sandbox:local", min_length=1, max_length=256,
                               pattern=IMAGE_REFERENCE_PATTERN)
    sandbox_node_image: str = Field(default="node:22-alpine", min_length=1, max_length=256,
                                    pattern=IMAGE_REFERENCE_PATTERN)
    sandbox_max_output: int = 20000
    agent_max_steps: int = 12

    @model_validator(mode="after")
    def resolve_storage(self):
        if not self.data_dir.is_absolute():
            self.data_dir = (PROJECT_ROOT / self.data_dir).resolve()
        if self.database_url.startswith("sqlite:///"):
            filename = self.database_url.removeprefix("sqlite:///")
            if filename != ":memory:" and not Path(filename).is_absolute():
                target = (PROJECT_ROOT / filename).resolve()
                target.parent.mkdir(parents=True, exist_ok=True)
                self.database_url = "sqlite:///" + target.as_posix()
        return self


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
