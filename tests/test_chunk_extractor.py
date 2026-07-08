import ast

from app.indexing.chunk_extractor import ChunkExtractor


def test_extract_python_chunks_includes_classes_methods_and_functions():
    source = """
class Service:
    def run(self):
        return True

async def fetch():
    return 1
""".strip()
    tree = ast.parse(source)

    chunks = ChunkExtractor().extract_python_chunks(tree, source, "app/service.py")

    names = [chunk.name for chunk in chunks]
    assert names == ["Service", "run", "fetch"]
    method = next(chunk for chunk in chunks if chunk.name == "run")
    assert method.class_name == "Service"
    assert method.function_name == "run"
    assert method.file_path == "app/service.py"
    assert method.content_hash
    assert method.chunk_id
