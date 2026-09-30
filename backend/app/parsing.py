"""Tree-sitter semantic units with bounded, line-preserving oversized fallback."""
import re
from dataclasses import dataclass
from functools import lru_cache

from tree_sitter import Language, Parser
import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_typescript

from app.config import settings


@dataclass
class ParsedFile:
    chunks: list[dict]
    symbols: list[dict]
    imports: list[str]


@lru_cache(maxsize=4)
def get_parser(language: str) -> Parser:
    grammar = {"python": tree_sitter_python.language, "javascript": tree_sitter_javascript.language,
               "typescript": tree_sitter_typescript.language_typescript, "tsx": tree_sitter_typescript.language_tsx}[language]
    return Parser(Language(grammar()))


def parse_code(content: str, language: str, path: str) -> ParsedFile:
    lines = content.splitlines()
    if not lines:
        return ParsedFile([], [], [])
    symbols: list[dict] = []
    imports: list[str] = []
    units: list[tuple[int, int, str, str]] = []
    if language in {"python", "javascript", "typescript", "tsx"}:
        encoded = content.encode()
        tree = get_parser(language).parse(encoded)
        definitions = {"function_definition": "function", "class_definition": "class", "function_declaration": "function", "class_declaration": "class", "method_definition": "method", "method_signature": "method"}

        def walk(node, parent_symbol=""):
            name_node = node.child_by_field_name("name")
            kind = definitions.get(node.type)
            if node.type == "variable_declarator":
                value = node.child_by_field_name("value")
                if value is not None and value.type in {"arrow_function", "function_expression"}:
                    kind = "function"
            current = parent_symbol
            if kind and name_node:
                name = encoded[name_node.start_byte:name_node.end_byte].decode()
                current = f"{parent_symbol}.{name}" if parent_symbol else name
                start = node.start_point.row + 1
                end = node.end_point.row + (1 if node.end_point.column > 0 else 0)
                end = max(start, end)
                symbols.append({"name": current, "type": kind, "start_line": start, "end_line": end})
                units.append((start, end, current, kind))
            if node.type in {"import_statement", "import_from_statement", "import_declaration"}:
                text = encoded[node.start_byte:node.end_byte].decode()
                if language == "python":
                    match = re.search(r"^from\s+([.\w]+)\s+import", text)
                    if match:
                        imports.append(match[1])
                    else:
                        imports.extend(re.findall(r"(?:^import\s+|,\s*)([\w.]+)", text))
                else:
                    imports.extend(re.findall(r"['\"]([^'\"]+)['\"]", text))
            if node.type == "call_expression":
                text = encoded[node.start_byte:node.end_byte].decode()
                imports.extend(re.findall(r"^require\(['\"]([^'\"]+)['\"]\)", text))
            for child in node.children:
                walk(child, current)

        walk(tree.root_node)
    # Preserve module-level imports/configuration and every uncovered source line.
    covered = set()
    for start, end, _, _ in units:
        covered.update(range(start, end + 1))
    gap_start = None
    for number in range(1, len(lines) + 2):
        uncovered = number <= len(lines) and number not in covered
        if uncovered and gap_start is None:
            gap_start = number
        elif not uncovered and gap_start is not None:
            if any(line.strip() for line in lines[gap_start - 1:number - 1]):
                units.append((gap_start, number - 1, path, "module"))
            gap_start = None
    chunks = []
    for start, end, name, kind in sorted(units):
        segment = start
        while segment <= end:
            last = segment
            size = len(lines[segment - 1].encode("utf-8"))
            if size > settings.max_chunk_chars:
                raise ValueError("Source contains a line too large for the chunk budget")
            while last < end and last - segment + 1 < settings.max_chunk_lines and size + len(lines[last].encode("utf-8")) + 1 <= settings.max_chunk_chars:
                size += len(lines[last].encode("utf-8")) + 1
                last += 1
            chunks.append({"symbol_name": name, "symbol_type": kind, "start_line": segment, "end_line": last,
                           "content": "\n".join(lines[segment - 1:last])})
            segment = last + 1
    return ParsedFile(chunks, symbols, sorted(set(imports)))
