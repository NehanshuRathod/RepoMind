import ast
from typing import List
from app.indexing.models import CodeChunk


class ChunkExtractor:

    def extract_python_chunks(self, tree, source: str, file_path: str) -> List[CodeChunk]:

        lines = source.splitlines()
        chunks = []

        for node in ast.walk(tree):

            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):

                start = node.lineno
                end = node.end_lineno

                code = "\n".join(lines[start-1:end])

                chunks.append(
                    CodeChunk(
                        file_path=file_path,
                        name=node.name,
                        start_line=start,
                        end_line=end,
                        content=code
                    )
                )

        return chunks
