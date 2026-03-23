import ast
from pathlib import Path


class ASTParser:

    def parse_python(self, file_path: Path):
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        return tree, source
