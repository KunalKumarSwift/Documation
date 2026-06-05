"""
VectorStoreFacade
=================
Selects the correct ``StoreProvider`` implementation based on the environment.

This facade contains *only* the switching logic — no vector store code lives here.
All implementation details are in ``bot/providers/``.

Switch:
    VECTORSTORE_BACKEND=pinecone  →  ``PineconeStoreProvider``
    default (chroma_local)        →  ``ChromaStoreProvider``
"""

import os
from dotenv import load_dotenv
from bot.providers.protocols import StoreProvider

load_dotenv()

_IS_PINECONE = os.getenv("VECTORSTORE_BACKEND", "chroma_local") == "pinecone"


class VectorStoreFacade:
    """Facade that selects and delegates to the appropriate StoreProvider.

    Args:
        embeddings: Embedding model instance forwarded to the provider.

    Callers use ``add_documents``, ``search``, and ``delete_source`` directly —
    they never need to know which backend is active.
    """

    def __init__(self, embeddings):
        self._provider: StoreProvider = self._build_provider(embeddings)

    @staticmethod
    def _build_provider(embeddings) -> StoreProvider:
        """Instantiate the StoreProvider for the current environment.

        Args:
            embeddings: Embedding model to pass to the provider constructor.

        Returns:
            ``PineconeStoreProvider`` when ``VECTORSTORE_BACKEND=pinecone``.
            ``ChromaStoreProvider`` otherwise.
        """
        if _IS_PINECONE:
            from bot.providers.pinecone_store import PineconeStoreProvider
            return PineconeStoreProvider(embeddings)
        from bot.providers.chroma_store import ChromaStoreProvider
        return ChromaStoreProvider(embeddings)

    def add_documents(self, documents: list, collection: str) -> None:
        """Delegate to the active provider's add_documents.

        Args:
            documents:  LangChain Document objects with populated metadata.
            collection: Target collection/namespace.
        """
        self._provider.add_documents(documents, collection)

    def search(self, query: str, collection: str, k: int = 3) -> list:
        """Delegate to the active provider's search.

        Args:
            query:      Query string.
            collection: Collection to search.
            k:          Maximum number of results.

        Returns:
            List of ``(Document, score)`` tuples from the active provider.
        """
        return self._provider.search(query, collection, k)

    def delete_source(self, source: str, collection: str) -> None:
        """Delegate to the active provider's delete_source.

        Args:
            source:     Repo-relative path of the file to remove.
            collection: Collection/namespace containing its chunks.
        """
        self._provider.delete_source(source, collection)
