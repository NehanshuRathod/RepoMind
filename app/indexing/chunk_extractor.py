import ast
import hashlib

from app.indexing.models import CodeChunk


class ChunkExtractor:
    def extract_python_chunks(self, tree: ast.AST, source: str, file_path: str) -> list[CodeChunk]:
        lines = source.splitlines()
        chunks: list[CodeChunk] = []

        class Visitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.class_stack: list[str] = []

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self._append_chunk(node=node, class_name=node.name, function_name=None)
                self.class_stack.append(node.name)
                self.generic_visit(node)
                self.class_stack.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._append_chunk(
                    node=node,
                    class_name=self.class_stack[-1] if self.class_stack else None,
                    function_name=node.name,
                )
                self.generic_visit(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self.visit_FunctionDef(node)

            def _append_chunk(
                self,
                node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
                class_name: str | None,
                function_name: str | None,
            ) -> None:
                if node.end_lineno is None:
                    return
                start = node.lineno
                end = node.end_lineno
                code = "\n".join(lines[start - 1 : end])
                content_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
                identity = f"{file_path}:{node.name}:{start}:{end}:{content_hash}"
                chunks.append(
                    CodeChunk(
                        chunk_id=hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                        file_path=file_path,
                        name=node.name,
                        start_line=start,
                        end_line=end,
                        content=code,
                        language="python",
                        class_name=class_name,
                        function_name=function_name,
                        content_hash=content_hash,
                    )
                )

        Visitor().visit(tree)
        return sorted(chunks, key=lambda chunk: (chunk.file_path, chunk.start_line, chunk.end_line))
