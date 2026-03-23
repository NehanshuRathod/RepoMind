from dataclasses import dataclass


@dataclass
class CodeChunk:
    file_path: str
    name: str
    start_line: int
    end_line: int
    content: str
