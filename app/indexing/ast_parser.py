import ast
from pathlib import Path


class ASTParser:
    def parse_python(self, file_path: Path) -> tuple[ast.AST, str]:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(file_path))
        return tree, source
