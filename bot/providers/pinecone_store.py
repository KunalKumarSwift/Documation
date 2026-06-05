"""
Pinecone Vector Store Provider
================================
Implements ``StoreProvider`` using Pinecone serverless.

Each doc collection maps to a separate Pinecone namespace within a single index.
Requires ``PINECONE_API_KEY`` and ``PINECONE_INDEX`` environment variables.

Environment variables:
    PINECONE_API_KEY  Pinecone API key (from https://app.pinecone.io).
    PINECONE_INDEX    Index name (default: ``docbot-docs``).
"""

import os

_INDEX_NAME = os.getenv("PINECONE_INDEX", "docbot-docs")


class PineconeStoreProvider:
    """Vector store provider backed by Pinecone serverless.

    Satisfies the ``StoreProvider`` Protocol structurally.

    Args:
        embeddings: Embedding model instance used for all vector operations.
    """

    def __init__(self, embeddings):
        self._embeddings = embeddings

    def _store(self, collection: str):
        """Return a PineconeVectorStore scoped to the given namespace.

        Args:
            collection: Pinecone namespace (one per doc collection).

        Raises:
            KeyError: If ``PINECONE_API_KEY`` is not set.
        """
        from langchain_pinecone import PineconeVectorStore
        from pinecone import Pinecone
        pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        return PineconeVectorStore(
            index=pc.Index(_INDEX_NAME),
            embedding=self._embeddings,
            namespace=collection,
        )

    def add_documents(self, documents: list, collection: str) -> None:
        """Embed and upsert Document chunks into a Pinecone namespace.

        Args:
            documents:  LangChain Document objects with source/collection metadata.
            collection: Target Pinecone namespace.
        """
        self._store(collection).add_documents(documents)

    def search(self, query: str, collection: str, k: int = 3) -> list:
        """Return the top-k closest chunks by cosine similarity.

        Args:
            query:      Free-text query string.
            collection: Pinecone namespace to search.
            k:          Maximum number of results.

        Returns:
            List of ``(Document, score)`` tuples — higher score = better match.
        """
        return self._store(collection).similarity_search_with_score(query, k=k)

    def delete_source(self, source: str, collection: str) -> None:
        """Delete all chunks with the given source metadata value.

        Pinecone has no delete-by-metadata API, so we first query with a
        zero vector and a metadata filter to retrieve the chunk IDs, then
        delete by those IDs.

        Args:
            source:     Repo-relative path used as the ``source`` metadata key.
            collection: Pinecone namespace containing the chunks.
        """
        from pinecone import Pinecone
        pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        index = pc.Index(_INDEX_NAME)
        results = index.query(
            vector=[0.0] * 1536, top_k=1000,
            filter={"source": source}, namespace=collection,
        )
        ids = [m.id for m in results.matches]
        if ids:
            index.delete(ids=ids, namespace=collection)
