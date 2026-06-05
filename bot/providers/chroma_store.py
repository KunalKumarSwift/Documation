"""
ChromaDB Vector Store Provider
================================
Implements ``StoreProvider`` using ChromaDB persisted to local disk.

Default persistence directory: ``.chroma_db``. No API key or internet
connection required — free and fully local.

Environment variables:
    CHROMA_PERSIST_DIR  Path where ChromaDB stores its data (default: ``.chroma_db``).
"""

import os

_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", ".chroma_db")


class ChromaStoreProvider:
    """Vector store provider backed by a local ChromaDB instance.

    Satisfies the ``StoreProvider`` Protocol structurally.

    Args:
        embeddings: Embedding model instance used for all vector operations.
    """

    def __init__(self, embeddings):
        self._embeddings = embeddings

    def _store(self, collection: str):
        """Return a Chroma client scoped to the given collection.

        Args:
            collection: ChromaDB collection name.
        """
        from langchain_chroma import Chroma
        return Chroma(
            collection_name=collection,
            embedding_function=self._embeddings,
            persist_directory=_PERSIST_DIR,
        )

    def add_documents(self, documents: list, collection: str) -> None:
        """Embed and upsert Document chunks into a ChromaDB collection.

        Args:
            documents:  LangChain Document objects with source/collection metadata.
            collection: Target ChromaDB collection name.
        """
        self._store(collection).add_documents(documents)

    def search(self, query: str, collection: str, k: int = 3) -> list:
        """Return the top-k closest chunks by L2 distance.

        Args:
            query:      Free-text query string.
            collection: ChromaDB collection to search.
            k:          Maximum number of results.

        Returns:
            List of ``(Document, distance)`` tuples — lower distance = better match.
        """
        return self._store(collection).similarity_search_with_score(query, k=k)

    def delete_source(self, source: str, collection: str) -> None:
        """Delete all chunks with the given source metadata value.

        Args:
            source:     Repo-relative path used as the ``source`` metadata key.
            collection: ChromaDB collection containing the chunks.
        """
        store = self._store(collection)
        existing = store.get(where={"source": source})
        if existing["ids"]:
            store.delete(ids=existing["ids"])
