from pathlib import Path

from app.indexing.file_filter import FileFilter


def test_file_filter_keeps_supported_code_and_ignores_vendor_dirs():
    files = [
        Path("repo/app/main.py"),
        Path("repo/node_modules/pkg/index.js"),
        Path("repo/README.md"),
        Path("repo/src/app.ts"),
    ]

    filtered = FileFilter().filter(files)

    assert filtered == [Path("repo/app/main.py"), Path("repo/src/app.ts")]
