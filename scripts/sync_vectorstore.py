"""
DocBot Vector Store Sync
========================
Incrementally synchronises the docs/ folder to a vector store.

Strategy
--------
Each markdown file is identified by its repo-relative path (the "source").
An MD5 hash of its content is stored in .vectorstore_hashes.json after every
successful ingest. On the next run, only files whose hash has changed (or that
are new or deleted) are processed — unchanged files are skipped entirely,
keeping CI costs near zero.

Supported backends
------------------
- ``chroma_local`` (default) — ChromaDB on disk, no API key required.
- ``pinecone`` — Pinecone serverless, set via VECTORSTORE_BACKEND=pinecone.

Embedding models
----------------
- Local (default): OllamaEmbeddings with llama3.2 — free, runs on-device.
- CI (CI=true): OpenAI text-embedding-3-small — $0.02/1M tokens, fast.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Path constants ──────────────────────────────────────────────────────────
DOCS_DIR = Path(__file__).parent.parent / "docs"
HASH_FILE = Path(__file__).parent.parent / ".vectorstore_hashes.json"

# ── Runtime configuration from environment ──────────────────────────────────
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", ".chroma_db")
VECTORSTORE_BACKEND = os.getenv("VECTORSTORE_BACKEND", "chroma_local")
# CI=true is set by GitHub Actions; switches embeddings to OpenAI.
IS_CI = os.getenv("CI", "").lower() == "true"


def get_collection_name(filepath: Path) -> str:
    """Derive the collection name from the immediate subdirectory under docs/.

    Args:
        filepath: Absolute path to a markdown file inside DOCS_DIR.

    Returns:
        The name of the containing subdirectory (e.g. "authentication"),
        or "general" if the file sits directly in docs/ with no subfolder.

    Example:
        >>> get_collection_name(Path("/project/docs/auth/biometric.md"))
        'auth'
    """
    rel = filepath.relative_to(DOCS_DIR)
    return rel.parts[0] if len(rel.parts) > 1 else "general"


def md5_file(filepath: Path) -> str:
    """Return the MD5 hex digest of a file's raw bytes.

    Args:
        filepath: Path to any readable file.

    Returns:
        32-character lowercase hex string, e.g. ``"d41d8cd98f00b204..."``.
    """
    return hashlib.md5(filepath.read_bytes()).hexdigest()


def load_hash_registry() -> dict:
    """Load the persisted source-to-hash map from .vectorstore_hashes.json.

    Returns:
        Dict mapping repo-relative source paths to their last-ingested MD5
        hash, e.g. ``{"docs/auth/biometric.md": "a1b2c3..."}``.
        Returns an empty dict on the first run when no file exists yet.
    """
    if HASH_FILE.exists():
        return json.loads(HASH_FILE.read_text())
    return {}


def save_hash_registry(registry: dict) -> None:
    """Persist the source-to-hash map so the next sync can skip unchanged files.

    Args:
        registry: Updated mapping of source paths to MD5 hashes.

    Note:
        The GitHub Actions workflow commits this file back to the repo with a
        ``[skip ci]`` tag so the commit does not re-trigger the sync workflow.
    """
    HASH_FILE.write_text(json.dumps(registry, indent=2))


def get_embeddings():
    """Return the embedding model appropriate for the current environment.

    Returns:
        OpenAIEmbeddings (text-embedding-3-small) when CI=true.
        OllamaEmbeddings (llama3.2) otherwise — free and fully local.

    Raises:
        ImportError: If the required LangChain package is not installed.
        ConnectionError: If Ollama is not running (local mode only).
    """
    if IS_CI:
        from langchain_openai import OpenAIEmbeddings
        print("Using OpenAI embeddings (CI mode)")
        return OpenAIEmbeddings(model="text-embedding-3-small")
    else:
        from langchain_ollama import OllamaEmbeddings
        model = os.getenv("OLLAMA_MODEL", "llama3.2")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        print(f"Using Ollama embeddings: {model}")
        return OllamaEmbeddings(model=model, base_url=base_url)


def get_vectorstore(embeddings, collection: str = "general"):
    """Return a vector store client scoped to a single collection/namespace.

    Args:
        embeddings: The embedding model instance used to convert text to vectors.
        collection: Logical name of the doc set (e.g. "authentication").
                    Maps to a Pinecone namespace or a ChromaDB collection name.

    Returns:
        PineconeVectorStore when VECTORSTORE_BACKEND=pinecone.
        Chroma otherwise, persisted to CHROMA_PERSIST_DIR on disk.

    Raises:
        KeyError: If PINECONE_API_KEY is not set and backend is pinecone.
    """
    if VECTORSTORE_BACKEND == "pinecone":
        from langchain_pinecone import PineconeVectorStore
        from pinecone import Pinecone
        pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        index_name = os.getenv("PINECONE_INDEX", "docbot-docs")
        return PineconeVectorStore(
            index=pc.Index(index_name),
            embedding=embeddings,
            namespace=collection,    # one index, many namespaces = one per collection
        )
    else:
        from langchain_chroma import Chroma
        return Chroma(
            collection_name=collection,
            embedding_function=embeddings,
            persist_directory=CHROMA_PERSIST_DIR,
        )


def delete_chunks_for_source(source: str, collection: str, embeddings) -> None:
    """Remove every stored chunk that originated from a given source file.

    Called before re-ingesting a changed file (to avoid duplicate chunks)
    and when a file has been deleted from the repo.

    Args:
        source: Repo-relative path of the source file, e.g.
                ``"docs/auth/biometric.md"``. Used as the metadata filter key.
        collection: The collection/namespace the chunks were stored in.
        embeddings: Embedding model instance (needed to open the Chroma store).
    """
    if VECTORSTORE_BACKEND == "pinecone":
        from pinecone import Pinecone
        pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        index = pc.Index(os.getenv("PINECONE_INDEX", "docbot-docs"))

        # Pinecone has no direct "delete by metadata" API — it requires a query
        # to fetch matching IDs first. We pass a zero vector because we only care
        # about the metadata filter; the similarity score is irrelevant here.
        results = index.query(
            vector=[0.0] * 1536,
            top_k=1000,
            filter={"source": source},
            namespace=collection,
        )
        ids = [m.id for m in results.matches]
        if ids:
            index.delete(ids=ids, namespace=collection)
    else:
        from langchain_chroma import Chroma
        vs = Chroma(
            collection_name=collection,
            embedding_function=embeddings,
            persist_directory=CHROMA_PERSIST_DIR,
        )
        existing = vs.get(where={"source": source})
        if existing["ids"]:
            vs.delete(ids=existing["ids"])


def ingest_file(filepath: Path, embeddings, registry: dict) -> None:
    """Split a markdown file into overlapping chunks, embed them, and upsert to the vector store.

    Chunk parameters — chunk_size=500, chunk_overlap=100 — were chosen to keep
    each chunk self-contained enough to answer a question while providing enough
    overlap that a sentence split across a boundary is still retrievable.

    Each chunk receives three metadata fields:
    - ``source``: repo-relative path, used for citation and for targeted deletes.
    - ``collection``: the owning subfolder, used as a retrieval filter.
    - ``chunk_index``: position within the file, useful for debugging.

    Args:
        filepath: Absolute path to the markdown file to ingest.
        embeddings: Embedding model instance.
        registry: The live hash registry; updated in-place with the new hash.
    """
    from langchain_community.document_loaders import TextLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    collection = get_collection_name(filepath)
    # Store source as a repo-relative path so it is portable across machines.
    source = str(filepath.relative_to(Path(__file__).parent.parent))

    loader = TextLoader(str(filepath), encoding="utf-8")
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunks = splitter.split_documents(docs)

    # Annotate every chunk with its origin so the query engine can cite it.
    for i, chunk in enumerate(chunks):
        chunk.metadata["source"] = source
        chunk.metadata["collection"] = collection
        chunk.metadata["chunk_index"] = i

    vs = get_vectorstore(embeddings, collection)
    vs.add_documents(chunks)

    print(f"  Ingested {len(chunks)} chunks from {source} → [{collection}]")
    # Record the hash so this file is skipped on the next unchanged run.
    registry[source] = md5_file(filepath)


def sync() -> None:
    """Diff docs/ against the hash registry and sync only new, changed, or deleted files.

    Algorithm:
    1. Load the existing hash registry from disk.
    2. Scan all .md and .txt files under docs/.
    3. For each file:
       - Not in registry → ingest as new.
       - In registry but hash differs → delete old chunks, re-ingest.
       - In registry with matching hash → skip (no API calls made).
    4. For each source in registry that no longer exists on disk → delete chunks.
    5. Save the updated registry.

    Raises:
        SystemExit: If the docs/ directory does not exist.
    """
    print(f"\nDocBot Vector Store Sync")
    print(f"Backend: {VECTORSTORE_BACKEND}")
    print(f"Docs dir: {DOCS_DIR}\n")

    if not DOCS_DIR.exists():
        print(f"ERROR: docs/ directory not found at {DOCS_DIR}")
        sys.exit(1)

    registry = load_hash_registry()
    embeddings = get_embeddings()

    # Build a map of {repo-relative-source: absolute-path} for all current docs.
    all_md_files = list(DOCS_DIR.rglob("*.md")) + list(DOCS_DIR.rglob("*.txt"))
    current_sources = {
        str(f.relative_to(Path(__file__).parent.parent)): f
        for f in all_md_files
    }

    new_count = changed_count = deleted_count = skipped_count = 0

    # ── Pass 1: new and changed files ───────────────────────────────────────
    for source, filepath in current_sources.items():
        current_hash = md5_file(filepath)
        if source not in registry:
            print(f"NEW: {source}")
            ingest_file(filepath, embeddings, registry)
            new_count += 1
        elif registry[source] != current_hash:
            print(f"CHANGED: {source}")
            # Delete stale chunks before re-ingesting to prevent duplicates.
            collection = get_collection_name(filepath)
            delete_chunks_for_source(source, collection, embeddings)
            ingest_file(filepath, embeddings, registry)
            changed_count += 1
        else:
            skipped_count += 1

    # ── Pass 2: files removed from the repo ─────────────────────────────────
    # Iterate over a copy of keys because we mutate registry inside the loop.
    for source in list(registry.keys()):
        if source not in current_sources:
            print(f"DELETED: {source}")
            filepath = Path(__file__).parent.parent / source
            collection = get_collection_name(filepath)
            delete_chunks_for_source(source, collection, embeddings)
            del registry[source]
            deleted_count += 1

    save_hash_registry(registry)

    print(f"\nSync complete:")
    print(f"  New: {new_count}  Changed: {changed_count}  Deleted: {deleted_count}  Skipped: {skipped_count}")


if __name__ == "__main__":
    sync()
