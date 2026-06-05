"""
DocBot Vector Store Sync
========================
Incrementally synchronises the docs/ folder to the vector store via
``VectorStoreFacade`` and ``EmbeddingsFacade``.

Algorithm:
1. Load the hash registry from ``.vectorstore_hashes.json``.
2. Scan all ``.md`` / ``.txt`` files in docs/.
3. New file → ingest. Changed file → delete + re-ingest. Deleted → remove chunks.
4. Unchanged files are skipped entirely (no API calls, no cost).
5. Save the updated hash registry.

Run manually::

    python scripts/sync_vectorstore.py

Or via GitHub Actions on every push that touches a ``.md`` file.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from bot.facades.embeddings_facade import EmbeddingsFacade
from bot.facades.vectorstore_facade import VectorStoreFacade

DOCS_DIR = Path(__file__).parent.parent / "docs"
HASH_FILE = Path(__file__).parent.parent / ".vectorstore_hashes.json"
BACKEND = os.getenv("VECTORSTORE_BACKEND", "chroma_local")


def _collection(filepath: Path) -> str:
    """Return the collection name from the immediate docs/ subdirectory.

    Args:
        filepath: Absolute path inside DOCS_DIR.

    Returns:
        Subdirectory name (e.g. ``"authentication"``), or ``"general"``
        when the file sits directly in docs/ with no subfolder.
    """
    rel = filepath.relative_to(DOCS_DIR)
    return rel.parts[0] if len(rel.parts) > 1 else "general"


def _md5(filepath: Path) -> str:
    """Return the MD5 hex digest of a file's raw bytes.

    Args:
        filepath: Path to any readable file.
    """
    return hashlib.md5(filepath.read_bytes()).hexdigest()


def _load_registry() -> dict:
    """Load the persisted source-to-hash map, or return ``{}`` on first run."""
    return json.loads(HASH_FILE.read_text()) if HASH_FILE.exists() else {}


def _save_registry(registry: dict) -> None:
    """Persist the source-to-hash map for the next incremental run.

    Note:
        GitHub Actions commits this file back with ``[skip ci]`` to avoid
        re-triggering the sync workflow.
    """
    HASH_FILE.write_text(json.dumps(registry, indent=2))


def _ingest(filepath: Path, vs: VectorStoreFacade, registry: dict) -> None:
    """Split a file into chunks, embed them, and upsert to the vector store.

    Chunk parameters — size=500, overlap=100 — keep each chunk self-contained
    while preserving context across split boundaries.

    Args:
        filepath: Absolute path to the markdown file.
        vs:       VectorStoreFacade instance.
        registry: Live hash map; updated in-place after successful ingest.
    """
    from langchain_community.document_loaders import TextLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    col = _collection(filepath)
    source = str(filepath.relative_to(Path(__file__).parent.parent))

    chunks = RecursiveCharacterTextSplitter(
        chunk_size=500, chunk_overlap=100
    ).split_documents(TextLoader(str(filepath), encoding="utf-8").load())

    for i, chunk in enumerate(chunks):
        chunk.metadata.update({"source": source, "collection": col, "chunk_index": i})

    vs.add_documents(chunks, col)
    print(f"  Ingested {len(chunks)} chunks from {source} → [{col}]")
    registry[source] = _md5(filepath)


def sync() -> None:
    """Run the full incremental sync: new/changed/deleted files only.

    Raises:
        SystemExit: If the docs/ directory does not exist.
    """
    print(f"\nDocBot Vector Store Sync  |  Backend: {BACKEND}")
    print(f"Docs: {DOCS_DIR}\n")

    if not DOCS_DIR.exists():
        print(f"ERROR: docs/ not found at {DOCS_DIR}")
        sys.exit(1)

    registry = _load_registry()
    vs = VectorStoreFacade(EmbeddingsFacade().get_model())

    all_files = list(DOCS_DIR.rglob("*.md")) + list(DOCS_DIR.rglob("*.txt"))
    current = {str(f.relative_to(DOCS_DIR.parent)): f for f in all_files}
    new = changed = deleted = skipped = 0

    for source, filepath in current.items():
        current_hash = _md5(filepath)
        if source not in registry:
            print(f"NEW:     {source}")
            _ingest(filepath, vs, registry)
            new += 1
        elif registry[source] != current_hash:
            print(f"CHANGED: {source}")
            vs.delete_source(source, _collection(filepath))
            _ingest(filepath, vs, registry)
            changed += 1
        else:
            skipped += 1

    for source in list(registry):
        if source not in current:
            print(f"DELETED: {source}")
            vs.delete_source(source, _collection(Path(source)))
            del registry[source]
            deleted += 1

    _save_registry(registry)
    print(f"\nDone — New:{new}  Changed:{changed}  Deleted:{deleted}  Skipped:{skipped}")


if __name__ == "__main__":
    sync()
