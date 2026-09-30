from collections import deque
from pathlib import PurePosixPath

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
    while queue:
        for dependent in incoming.get(queue.popleft(), []):
            if dependent not in visited:
                visited.add(dependent)
                queue.append(dependent)
    return {"path": path, "affected_files": sorted(visited - {path}),
            "dependencies": [edge["target"] for edge in data["edges"] if edge["source"] == path],
            "explanation": "These files transitively import this file and may need review after a change. An import relationship is evidence of potential impact, not proof that a specific function is used."}
