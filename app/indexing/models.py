from dataclasses import dataclass


@dataclass(frozen=True)
class CodeChunk:
    chunk_id: str
    file_path: str
    name: str
    start_line: int
    end_line: int
    content: str
    language: str = "python"
    class_name: str | None = None
    function_name: str | None = None
    content_hash: str = ""
