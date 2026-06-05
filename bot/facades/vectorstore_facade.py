"""
VectorStoreFacade
=================
Subsystem facade that hides ChromaDB vs Pinecone vector store details.

Exposes three operations — ``add_documents``, ``search``, ``delete_source`` —
that work identically regardless of which backend is active. The active
backend is selected via the ``VECTORSTORE_BACKEND`` environment variable.
"""

import os
from dotenv import load_dotenv

load_dotenv()

_BACKEND = os.getenv("VECTORSTORE_BACKEND", "chroma_local")
_CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", ".chroma_db")


class VectorStoreFacade:
    """Subsystem facade: unified add/search/delete API for ChromaDB and Pinecone.

    Args:
        embeddings: Embedding model instance used for all vector operations.
    """

    def __init__(self, embeddings):
        self._embeddings = embeddings

    def _get_store(self, collection: str):
        """Return a store client scoped to the given collection/namespace.

        Args:
            collection: Maps to a ChromaDB collection name or Pinecone namespace.

        Raises:
            KeyError: If ``PINECONE_API_KEY`` is not set and backend is pinecone.
        """
        if _BACKEND == "pinecone":
            from langchain_pinecone import PineconeVectorStore
            from pinecone import Pinecone
            pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
            return PineconeVectorStore(
                index=pc.Index(os.getenv("PINECONE_INDEX", "docbot-docs")),
                embedding=self._embeddings,
                namespace=collection,
            )
        from langchain_chroma import Chroma
        return Chroma(
            collection_name=collection,
            embedding_function=self._embeddings,
            persist_directory=_CHROMA_DIR,
        )

    def add_documents(self, documents: list, collection: str) -> None:
        """Embed and upsert Document chunks into the collection.

        Args:
            documents: LangChain Document objects with source/collection metadata.
            collection: Target collection/namespace.
        """
        self._get_store(collection).add_documents(documents)

    def search(self, query: str, collection: str, k: int = 3) -> list:
        """Return the top-k most similar chunks with scores.

        Args:
            query: Free-text query string to embed and compare.
            collection: Collection to search.
            k: Maximum number of results to return.

        Returns:
            List of ``(Document, score)`` tuples ordered by relevance.
        """
        return self._get_store(collection).similarity_search_with_score(query, k=k)

    def delete_source(self, source: str, collection: str) -> None:
        """Delete all chunks that originated from the given source file.

        Args:
            source: Repo-relative path used as the metadata ``source`` key.
            collection: Collection/namespace containing the chunks.
        """
        if _BACKEND == "pinecone":
            self._delete_pinecone(source, collection)
        else:
            self._delete_chroma(source, collection)

    def _delete_pinecone(self, source: str, collection: str) -> None:
        from pinecone import Pinecone
        pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        index = pc.Index(os.getenv("PINECONE_INDEX", "docbot-docs"))
        # Pinecone has no delete-by-metadata API; we query with a zero vector
        # plus a metadata filter to fetch the chunk IDs, then delete by ID.
        results = index.query(
            vector=[0.0] * 1536, top_k=1000,
            filter={"source": source}, namespace=collection,
        )
        ids = [m.id for m in results.matches]
        if ids:
            index.delete(ids=ids, namespace=collection)

    def _delete_chroma(self, source: str, collection: str) -> None:
        from langchain_chroma import Chroma
        vs = Chroma(
            collection_name=collection,
            embedding_function=self._embeddings,
            persist_directory=_CHROMA_DIR,
        )
        existing = vs.get(where={"source": source})
        if existing["ids"]:
            vs.delete(ids=existing["ids"])
