"""
Provider Protocols
==================
Structural interfaces (PEP 544 Protocols) that all concrete providers must satisfy.

Using ``Protocol`` instead of ``ABC`` allows structural subtyping — a class
satisfies a Protocol without explicitly inheriting from it, so third-party
LangChain objects can satisfy the interface where needed.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Contract for embedding model providers.

    Implementors return a LangChain-compatible embeddings object that
    converts text strings into dense float vectors.
    """

    def get_model(self) -> Any:
        """Return a configured, ready-to-use embeddings model instance.

        Returns:
            Any LangChain ``Embeddings`` subclass (e.g. ``OllamaEmbeddings``,
            ``OpenAIEmbeddings``). The caller treats it as a black box.

        Note:
            The provider used at query time must match the one used during
            ingest — mixing models produces meaningless similarity scores.
        """
        ...


@runtime_checkable
class LLMProvider(Protocol):
    """Contract for chat LLM providers.

    Provides two factory methods because the router requires a different
    model configuration (temperature=0) than the answer generator.
    """

    def get_chat(self, temperature: float = 0.1) -> Any:
        """Return the answer-generation chat model.

        Args:
            temperature: Sampling temperature. Higher = more varied output.

        Returns:
            Any LangChain ``BaseChatModel`` subclass.
        """
        ...

    def get_router(self) -> Any:
        """Return a zero-temperature model for deterministic collection routing.

        Returns:
            Any LangChain ``BaseChatModel`` subclass configured with temperature=0.
        """
        ...


@runtime_checkable
class StoreProvider(Protocol):
    """Contract for vector store providers.

    Defines the three operations the rest of the system needs: write chunks,
    read chunks, and delete chunks. Hides all backend-specific details.
    """

    def add_documents(self, documents: list, collection: str) -> None:
        """Embed and upsert Document chunks into the collection.

        Args:
            documents:  LangChain ``Document`` objects with populated metadata.
            collection: Target collection or namespace.
        """
        ...

    def search(self, query: str, collection: str, k: int = 3) -> list:
        """Return the top-k most similar chunks with scores.

        Args:
            query:      Free-text query string to embed and compare.
            collection: Collection to search.
            k:          Maximum number of results.

        Returns:
            List of ``(Document, score)`` tuples ordered by relevance.
        """
        ...

    def delete_source(self, source: str, collection: str) -> None:
        """Delete all chunks that originated from the given source file.

        Args:
            source:     Repo-relative path used as the ``source`` metadata key.
            collection: Collection/namespace containing the chunks.
        """
        ...
