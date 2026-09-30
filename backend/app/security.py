"""Untrusted repository boundaries; no repository text is executable policy."""
import re
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

IGNORED = {".git", "node_modules", "dist", "build", "coverage", "__pycache__", ".next", ".venv", "venv", ".idea", ".pytest_cache", ".mypy_cache"}
SECRET_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519", "credentials.json", "secrets.json"}
EXTENSIONS = {".py": "python", ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".ts": "typescript", ".tsx": "tsx", ".md": "markdown", ".json": "json", ".toml": "toml", ".yml": "yaml", ".yaml": "yaml", ".txt": "text", ".ini": "text"}


def validate_github_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com" or parsed.query or parsed.fragment:
        raise ValueError("Use a public HTTPS GitHub repository URL: https://github.com/owner/repo")
    match = re.fullmatch(r"/([A-Za-z0-9][A-Za-z0-9-]{0,38})/([A-Za-z0-9_.-]{1,100})/?", parsed.path)
    if not match or match[2] in {".", ".."}:
        raise ValueError("URL must point to a repository, without a branch or file path")
    name = match[2].removesuffix(".git")
    if not name or name in {".", ".."}:
        raise ValueError("Invalid repository name")
    return f"https://github.com/{match[1]}/{name}"


def safe_path(root: Path, relative: str) -> Path:
    if not relative or len(relative) > 500 or "\\" in relative or ":" in relative or "\x00" in relative:
        raise ValueError("Invalid repository path")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or any(p in {"..", "."} for p in pure.parts):
        raise ValueError("Path must be relative and cannot traverse directories")
    reserved = {"CON", "PRN", "AUX", "NUL", *{f"COM{i}" for i in range(1, 10)}, *{f"LPT{i}" for i in range(1, 10)}}
    if any(len(part.encode("utf-8")) > 255 or part.endswith((" ", ".")) or part.split(".", 1)[0].upper() in reserved for part in pure.parts):
        raise ValueError("Path contains a reserved or nonportable filename")
    base = root.resolve()
    target = (base / relative).resolve()
    if not target.is_relative_to(base):
        raise ValueError("Path escapes the repository")
    return target


def allowed_file(path: str) -> bool:
    pure = PurePosixPath(path)
    return not any(p in IGNORED or p.startswith(".env") for p in pure.parts) and pure.name not in SECRET_NAMES and pure.suffix.lower() in EXTENSIONS and not pure.name.endswith((".min.js", ".d.ts")) and pure.name not in {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}


def redact_secrets(content: str) -> str:
    content = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----", lambda m: "[REDACTED PRIVATE KEY]" + "\n" * m[0].count("\n"), content)
    content = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b", "[REDACTED SECRET]", content)
    return re.sub(r"(?im)(\b(?:api_key|secret_key|jwt_secret|password|access_token)\s*[:=]\s*)(['\"])([^'\"\n]{8,})(\2)", r"\1\2[REDACTED]\4", content)
