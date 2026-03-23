from fastapi import APIRouter, UploadFile, File
from pathlib import Path
import shutil
import tempfile

from app.indexing.repository_manager import RepositoryManager
from app.indexing.file_loader import FileLoader
from app.indexing.file_filter import FileFilter
from app.indexing.ast_parser import ASTParser
from app.indexing.chunk_extractor import ChunkExtractor


router = APIRouter(prefix="/index", tags=["Indexing"])


# services
repo_manager = RepositoryManager()
loader = FileLoader()
filterer = FileFilter()
parser = ASTParser()
extractor = ChunkExtractor()



# Debug: chunk extraction

@router.post("/debug/chunks")
def debug_chunks(repo_url: str):

    workspace = repo_manager.clone_repo(repo_url)

    files = loader.load_files(workspace)
    filtered = filterer.filter(files)

    chunks = []

    for f in filtered:
        if f.suffix == ".py":
            tree, source = parser.parse_python(f)
            chunks.extend(
                extractor.extract_python_chunks(tree, source, str(f))
            )

    return {
        "total_chunks": len(chunks),
        "sample": [c.name for c in chunks[:10]]
    }



# GitHub repo

@router.post("/github")
def index_github(repo_url: str):

    workspace = repo_manager.clone_repo(repo_url)

    files = loader.load_files(workspace)
    filtered = filterer.filter(files)

    return {
        "workspace": str(workspace),
        "total_files": len(files),
        "code_files": len(filtered)
    }


# Zip upload
@router.post("/upload")
async def index_upload(file: UploadFile = File(...)):

    temp_dir = Path(tempfile.gettempdir())
    temp_zip = temp_dir / file.filename

    with open(temp_zip, "wb") as f:
        shutil.copyfileobj(file.file, f)

    workspace = repo_manager.extract_zip(temp_zip)

    files = loader.load_files(workspace)
    filtered = filterer.filter(files)

    return {
        "workspace": str(workspace),
        "total_files": len(files),
        "code_files": len(filtered)
    }
