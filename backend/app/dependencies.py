from collections import deque
from pathlib import PurePosixPath
import re

from sqlalchemy import select

from app.models import RepositoryFile


def resolve_import(source: str, imported: str, known: set[str], language: str) -> str | None:
    if language == "python":
        dots = len(imported) - len(imported.lstrip("."))
        module = imported[dots:].replace(".", "/")
        if dots:
            parts = list(PurePosixPath(source).parent.parts)
            for _ in range(dots - 1):
                if parts:
                    parts.pop()
            base = "/".join(parts + ([module] if module else []))
        else:
            base = module
        candidates = [base + ".py", base + "/__init__.py", "src/" + base + ".py", "src/" + base + "/__init__.py"]
    elif imported.startswith("."):
        parts = list(PurePosixPath(source).parent.parts)
        for part in imported.split("/"):
            if part == "..":
                if parts:
                    parts.pop()
            elif part != ".":
                parts.append(part)
        base = "/".join(parts)
        candidates = [base, *[base + ext for ext in [".ts", ".tsx", ".js", ".jsx"]], *[base + "/index" + ext for ext in [".ts", ".tsx", ".js"]]]
    else:
        return None
    return next((candidate for candidate in candidates if candidate in known and candidate != source), None)


def graph(session, repository_id: str) -> dict:
    files = list(session.scalars(select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)))
    paths = {file.path for file in files}
    edges = set()
    for file in files:
        for imported in file.imports:
            target = resolve_import(file.path, imported, paths, file.language)
            if target:
                edges.add((file.path, target))
    return {"nodes": [{"id": file.path, "path": file.path, "language": file.language} for file in files],
            "edges": [{"source": source, "target": target, "kind": "imports"} for source, target in sorted(edges)],
            "limitations": "Conservative file import analysis. Dynamic imports, aliases, external packages and runtime call relationships may be unresolved."}


def impact(session, repository_id: str, path: str) -> dict:
    data = graph(session, repository_id)
    if path not in {node["path"] for node in data["nodes"]}:
        raise ValueError("File is not indexed")
    incoming: dict[str, list[str]] = {}
    for edge in data["edges"]:
        incoming.setdefault(edge["target"], []).append(edge["source"])
    queue = deque([path])
    visited = {path}
    toward_target = {}
    while queue:
        current = queue.popleft()
        for dependent in incoming.get(current, []):
            if dependent not in visited:
                visited.add(dependent)
                toward_target[dependent] = current
                queue.append(dependent)
    affected = sorted(visited - {path})
    # Detailed chains are bounded; traversal still counts every reachable file.
    chains = []
    truncated = len(affected) > 8
    for dependent in affected[:8]:
        chain = [dependent]
        while chain[-1] != path and len(chain) < 16:
            chain.append(toward_target[chain[-1]])
        truncated = truncated or chain[-1] != path
        chains.append(chain)
    return {"path": path, "affected_files": affected, "chains": chains, "chains_truncated": truncated,
            "dependencies": [edge["target"] for edge in data["edges"] if edge["source"] == path],
            "explanation": "These files transitively import this file and may need review after a change. An import relationship is evidence of potential impact, not proof that a specific function is used."}


def dependency_question(session, repository_id: str, question: str) -> dict | None:
    """Resolve an explicit impact target; ambiguous identifiers must not be guessed."""
    intent = re.search(
        r"\b(?:impact(?:ed|s)?|affect(?:ed|s)?|depend(?:s|ents|encies|ency|ent)?|callers)\b"
        r"|\b(?:who|which|what)\b.*\b(?:imports?|uses?)\b"
        r"|\bif\b.*\b(?:change|changes|modify|modified|edit)\b", question, re.IGNORECASE,
    )
    if not intent:
        return None
    files = list(session.scalars(select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)))

    def mentioned(value: str, path=False) -> bool:
        boundary = r"[\w/.]" if path else r"[\w.]"
        return bool(re.search(r"(?<!" + boundary + r")" + re.escape(value) + r"(?!" + boundary + r")", question, re.IGNORECASE))

    candidates = {file.path for file in files if mentioned(file.path, path=True)}
    if not candidates:
        candidates = {file.path for file in files if mentioned(PurePosixPath(file.path).name, path=True)}
    if not candidates:
        candidates = {file.path for file in files for symbol in file.symbols
                      if mentioned(symbol["name"]) or mentioned(symbol["name"].rsplit(".", 1)[-1])}
    if len(candidates) != 1:
        return {"status": "ambiguous" if candidates else "unresolved", "candidate_paths": sorted(candidates)[:8],
                "explanation": "Name an indexed file path or a uniquely identifiable symbol so import impact can be traced without guessing."}
    result = impact(session, repository_id, candidates.pop())
    result["status"] = "resolved"
    return result
