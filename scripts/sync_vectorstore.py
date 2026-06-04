"""
DocBot Vector Store Sync
Scans docs/ folder, detects changes via MD5 hashing, syncs to vector store.
Supports: ChromaDB (local, default) and Pinecone (cloud, set VECTORSTORE_BACKEND=pinecone)
"""

import hashlib
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DOCS_DIR = Path(__file__).parent.parent / "docs"
HASH_FILE = Path(__file__).parent.parent / ".vectorstore_hashes.json"
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", ".chroma_db")
VECTORSTORE_BACKEND = os.getenv("VECTORSTORE_BACKEND", "chroma_local")
IS_CI = os.getenv("CI", "").lower() == "true"


def get_collection_name(filepath: Path) -> str:
    """Derive collection name from the docs subfolder name."""
    rel = filepath.relative_to(DOCS_DIR)
    return rel.parts[0] if len(rel.parts) > 1 else "general"


def md5_file(filepath: Path) -> str:
    return hashlib.md5(filepath.read_bytes()).hexdigest()


def load_hash_registry() -> dict:
    if HASH_FILE.exists():
        return json.loads(HASH_FILE.read_text())
    return {}


def save_hash_registry(registry: dict):
    HASH_FILE.write_text(json.dumps(registry, indent=2))


def get_embeddings():
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
    if VECTORSTORE_BACKEND == "pinecone":
        from langchain_pinecone import PineconeVectorStore
        from pinecone import Pinecone
        pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        index_name = os.getenv("PINECONE_INDEX", "docbot-docs")
        return PineconeVectorStore(
            index=pc.Index(index_name),
            embedding=embeddings,
            namespace=collection,
        )
    else:
        from langchain_chroma import Chroma
        return Chroma(
            collection_name=collection,
            embedding_function=embeddings,
            persist_directory=CHROMA_PERSIST_DIR,
        )


def delete_chunks_for_source(source: str, collection: str, embeddings):
    """Remove all chunks for a given source file from the vector store."""
    if VECTORSTORE_BACKEND == "pinecone":
        from langchain_pinecone import PineconeVectorStore
        from pinecone import Pinecone
        pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        index = pc.Index(os.getenv("PINECONE_INDEX", "docbot-docs"))
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


def ingest_file(filepath: Path, embeddings, registry: dict):
    from langchain_community.document_loaders import TextLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    collection = get_collection_name(filepath)
    source = str(filepath.relative_to(Path(__file__).parent.parent))

    loader = TextLoader(str(filepath), encoding="utf-8")
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunks = splitter.split_documents(docs)

    for i, chunk in enumerate(chunks):
        chunk.metadata["source"] = source
        chunk.metadata["collection"] = collection
        chunk.metadata["chunk_index"] = i

    vs = get_vectorstore(embeddings, collection)
    vs.add_documents(chunks)

    print(f"  Ingested {len(chunks)} chunks from {source} → [{collection}]")
    registry[source] = md5_file(filepath)


def sync():
    print(f"\nDocBot Vector Store Sync")
    print(f"Backend: {VECTORSTORE_BACKEND}")
    print(f"Docs dir: {DOCS_DIR}\n")

    if not DOCS_DIR.exists():
        print(f"ERROR: docs/ directory not found at {DOCS_DIR}")
        sys.exit(1)

    registry = load_hash_registry()
    embeddings = get_embeddings()

    all_md_files = list(DOCS_DIR.rglob("*.md")) + list(DOCS_DIR.rglob("*.txt"))
    current_sources = {
        str(f.relative_to(Path(__file__).parent.parent)): f
        for f in all_md_files
    }

    new_count = changed_count = deleted_count = skipped_count = 0

    # Process new and changed files
    for source, filepath in current_sources.items():
        current_hash = md5_file(filepath)
        if source not in registry:
            print(f"NEW: {source}")
            ingest_file(filepath, embeddings, registry)
            new_count += 1
        elif registry[source] != current_hash:
            print(f"CHANGED: {source}")
            collection = get_collection_name(filepath)
            delete_chunks_for_source(source, collection, embeddings)
            ingest_file(filepath, embeddings, registry)
            changed_count += 1
        else:
            skipped_count += 1

    # Delete removed files
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
