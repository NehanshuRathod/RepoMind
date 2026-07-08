from __future__ import annotations

import hashlib
import re
from pathlib import Path

from app.indexing.models import CodeChunk


TREE_SITTER_GRAMMAR = {
    "python": "python",
    "javascript": "javascript",
    "jsx": "javascript",
    "typescript": "typescript",
    "tsx": "typescript",
    "java": "java",
    "go": "go",
}

_PY_EXTENSIONS = {".py"}


def _make_chunk(
    file_path: str,
    name: str,
    start_line: int,
    end_line: int,
    content: str,
    language: str,
    class_name: str | None,
    function_name: str | None,
) -> CodeChunk:
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    identity = f"{file_path}:{name}:{start_line}:{end_line}:{content_hash}"
    return CodeChunk(
        chunk_id=hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        file_path=file_path,
        name=name,
        start_line=start_line,
        end_line=end_line,
        content=content,
        language=language,
        class_name=class_name,
        function_name=function_name,
        content_hash=content_hash,
    )


class MultiLanguageChunker:
    """Extract semantic chunks from non-Python source files.

    Uses Tree-sitter (via ``tree-sitter`` + ``tree-sitter-languages``) when the
    libraries are available, and falls back to a brace-aware regex extractor so
    the service still works in environments where those packages are not
    installed.
    """

    def __init__(self) -> None:
        self._backend = self._build_backend()

    @staticmethod
    def _build_backend() -> str:
        try:
            import tree_sitter  # noqa: F401
            import tree_sitter_languages  # noqa: F401

            return "tree_sitter"
        except Exception:
            return "regex"

    def extract(self, file_path: Path, language: str) -> list[CodeChunk]:
        if language == "python":
            return []
        suffix = file_path.suffix.lower()
        if suffix in _PY_EXTENSIONS:
            return []
        grammar = TREE_SITTER_GRAMMAR.get(language)
        if grammar is None:
            return []
        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            return []
        if not source.strip():
            return []

        if self._backend == "tree_sitter":
            try:
                return _TreeSitterBackend().extract(source, str(file_path), language, grammar)
            except Exception:
                return _RegexBackend().extract(source, str(file_path), language)
        return _RegexBackend().extract(source, str(file_path), language)


class _TreeSitterBackend:
    FUNCTION_NODES = {
        "python": {"function_definition", "async_function_definition"},
        "javascript": {"function_declaration", "method_definition", "generator_function_declaration"},
        "typescript": {
            "function_declaration",
            "method_definition",
            "generator_function_declaration",
            "arrow_function",
        },
        "java": {"method_declaration", "constructor_declaration"},
        "go": {"function_declaration", "method_declaration"},
    }
    CLASS_NODES = {
        "python": {"class_definition"},
        "javascript": {"class_declaration"},
        "typescript": {"class_declaration", "interface_declaration"},
        "java": {"class_declaration", "interface_declaration", "enum_declaration"},
        "go": {"type_declaration"},
    }

    def __init__(self) -> None:
        from tree_sitter import Parser
        from tree_sitter_languages import get_language

        self.Parser = Parser
        self.get_language = get_language
        self._parsers: dict[str, object] = {}

    def _parser_for(self, grammar: str):
        if grammar not in self._parsers:
            self._parsers[grammar] = self.Parser(self.get_language(grammar))
        return self._parsers[grammar]

    def extract(self, source: str, file_path: str, language: str, grammar: str) -> list[CodeChunk]:
        tree = self._parser_for(grammar).parse(source.encode("utf-8"))
        chunks: list[CodeChunk] = []
        class_stack: list[str] = []

        def node_text(node) -> str:
            return node.text.decode("utf-8")

        def node_name(node) -> str:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                return name_node.text.decode("utf-8")
            parent = node.parent
            if parent is not None and parent.type == "variable_declarator":
                name_node = parent.child_by_field_name("name")
                if name_node is not None:
                    return name_node.text.decode("utf-8")
            return "anonymous"

        def go(node) -> None:
            if node.type in self.CLASS_NODES.get(language, set()):
                start, end = node.start_point[0] + 1, node.end_point[0] + 1
                chunks.append(
                    _make_chunk(file_path, node_name(node), start, end, node_text(node), language, None, None)
                )
                class_stack.append(node_name(node))
                for child in node.children:
                    go(child)
                class_stack.pop()
                return
            if node.type in self.FUNCTION_NODES.get(language, set()):
                start, end = node.start_point[0] + 1, node.end_point[0] + 1
                class_name = class_stack[-1] if class_stack else self._go_receiver(node, language)
                chunks.append(
                    _make_chunk(file_path, node_name(node), start, end, node_text(node), language, class_name, node_name(node))
                )
                return
            for child in node.children:
                go(child)

        go(tree.root_node)
        return sorted(chunks, key=lambda chunk: (chunk.file_path, chunk.start_line, chunk.end_line))

    @staticmethod
    def _go_receiver(node, language: str) -> str | None:
        if language != "go" or node.type != "method_declaration":
            return None
        receiver = node.child_by_field_name("receiver")
        if receiver is None:
            return None
        text = receiver.text.decode("utf-8")
        match = re.search(r"\*\s*(\w+)", text) or re.search(r"\(\s*(\w+)", text)
        return match.group(1) if match else None


_KEYWORDS = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "try",
    "do",
    "else",
    "return",
    "typeof",
    "new",
    "delete",
    "await",
    "yield",
    "finally",
    "with",
    "using",
    "lock",
}


class _RegexBackend:
    _RULES: dict[str, list[tuple[re.Pattern[str], str]]] = {
        "javascript": [
            (re.compile(r"(?:export\s+(?:default\s+)?)?(?:abstract\s+)?class\s+(?P<name>\w+)"), "class"),
            (re.compile(r"function\s+(?P<name>\w+)"), "function"),
            (
                re.compile(
                    r"^\s*(?:async\s+|static\s+|public\s+|private\s+|protected\s+|readonly\s+)*?"
                    r"(?P<name>[A-Za-z_$][\w$]*)\s*\([^;{]*\)\s*(?::[^{]+)?(?=\s*\{)",
                    re.MULTILINE,
                ),
                "function",
            ),
        ],
        "typescript": [
            (re.compile(r"(?:export\s+(?:default\s+)?)?(?:abstract\s+)?class\s+(?P<name>\w+)"), "class"),
            (re.compile(r"interface\s+(?P<name>\w+)"), "class"),
            (re.compile(r"function\s+(?P<name>\w+)"), "function"),
            (
                re.compile(
                    r"^\s*(?:async\s+|static\s+|public\s+|private\s+|protected\s+|readonly\s+)*?"
                    r"(?P<name>[A-Za-z_$][\w$]*)\s*\([^;{]*\)\s*(?::[^{]+)?(?=\s*\{)",
                    re.MULTILINE,
                ),
                "function",
            ),
        ],
        "java": [
            (
                re.compile(r"(?:public|private|protected)?\s*(?:abstract\s+|final\s+|static\s+)*?(?:class|interface|enum)\s+(?P<name>\w+)"),
                "class",
            ),
            (
                re.compile(
                    r"^\s*(?:public|private|protected)?\s*(?:static\s+|final\s+|abstract\s+|native\s+|synchronized\s+|transient\s+)*?"
                    r"[\w<>\[\],\s\.]+\s+(?P<name>\w+)\s*\([^;{]*\)\s*(?:throws\s+[\w,\s]+)?(?=\s*\{)",
                    re.MULTILINE,
                ),
                "function",
            ),
        ],
        "go": [
            (re.compile(r"^\s*type\s+(?P<name>\w+)\s+(?:struct|interface)", re.MULTILINE), "class"),
            (re.compile(r"^\s*func\s+\(\s*[^)]*\)\s+(?P<name>\w+)\s*\(", re.MULTILINE), "function"),
            (re.compile(r"^\s*func\s+(?P<name>\w+)\s*\(", re.MULTILINE), "function"),
        ],
    }

    def extract(self, source: str, file_path: str, language: str) -> list[CodeChunk]:
        rules = self._RULES.get(language)
        if not rules:
            return []
        text = source
        matches: list[tuple[int, int, str, str]] = []
        for pattern, kind in rules:
            for match in pattern.finditer(text):
                name = match.group("name")
                if not name or name in _KEYWORDS:
                    continue
                matches.append((match.start(), match.end(), name, kind))
        matches.sort(key=lambda item: item[0])

        lines = text.splitlines()

        def line_of(pos: int) -> int:
            return text.count("\n", 0, pos) + 1

        chunks: list[CodeChunk] = []
        class_stack: list[tuple[str, int]] = []
        for start, end, name, kind in matches:
            brace = text.find("{", end)
            if brace == -1:
                continue
            close = self._find_block_end(text, brace)
            start_line = line_of(start)
            end_line = line_of(close)
            while class_stack and class_stack[-1][1] < start_line:
                class_stack.pop()

            if kind == "class":
                chunks.append(_make_chunk(file_path, name, start_line, end_line, "\n".join(lines[start_line - 1 : end_line]), language, None, None))
                class_stack.append((name, end_line))
            else:
                class_name = class_stack[-1][0] if class_stack else None
                if language == "go" and class_name is None:
                    class_name = self._go_receiver(text, text.find(name, start, end))
                chunks.append(
                    _make_chunk(file_path, name, start_line, end_line, "\n".join(lines[start_line - 1 : end_line]), language, class_name, name)
                )
        return sorted(chunks, key=lambda chunk: (chunk.file_path, chunk.start_line, chunk.end_line))

    @staticmethod
    def _find_block_end(text: str, open_index: int) -> int:
        depth = 0
        i = open_index
        n = len(text)
        in_str: str | None = None
        while i < n:
            ch = text[i]
            if in_str:
                if ch == "\\":
                    i += 2
                    continue
                if ch == in_str:
                    in_str = None
                i += 1
                continue
            if ch in ('"', "'", "`"):
                in_str = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
            elif ch == "/" and i + 1 < n and text[i + 1] == "/":
                while i < n and text[i] != "\n":
                    i += 1
                continue
            elif ch == "/" and i + 1 < n and text[i + 1] == "*":
                i += 2
                while i < n and not (text[i] == "*" and i + 1 < n and text[i + 1] == "/"):
                    i += 1
                i += 2
                continue
            i += 1
        return n - 1

    @staticmethod
    def _go_receiver(text: str, start: int) -> str | None:
        before = text[:start]
        begin = before.rfind("func")
        if begin == -1:
            return None
        segment = text[begin:start]
        match = re.search(r"func\s*\(\s*(?:[^)]*?\*?\s*(\w+))?\s*\)", segment)
        return match.group(1) if match and match.group(1) else None
