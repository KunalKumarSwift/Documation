"""
EmbeddingsFacade
================
Selects the correct ``EmbeddingProvider`` implementation based on the environment.

This facade contains *only* the switching logic — no embedding code lives here.
All implementation details are in ``bot/providers/``.

Switch:
    CI=true  →  ``OpenAIEmbeddingProvider``
    default  →  ``OllamaEmbeddingProvider``
"""

import os
from dotenv import load_dotenv
from bot.providers.protocols import EmbeddingProvider

load_dotenv()

_IS_CI = os.getenv("CI", "").lower() == "true"


class EmbeddingsFacade:
    """Facade that selects and exposes the appropriate EmbeddingProvider.

    Callers use ``get_provider()`` to obtain the typed provider, or the
    convenience ``get_model()`` shortcut to go directly to the model instance.
    """

    def get_provider(self) -> EmbeddingProvider:
        """Return the EmbeddingProvider for the current environment.

        Returns:
            ``OpenAIEmbeddingProvider`` when ``CI=true``.
            ``OllamaEmbeddingProvider`` otherwise.
        """
        if _IS_CI:
            from bot.providers.openai_embeddings import OpenAIEmbeddingProvider
            return OpenAIEmbeddingProvider()
        from bot.providers.ollama_embeddings import OllamaEmbeddingProvider
        return OllamaEmbeddingProvider()

    def get_model(self):
        """Convenience shortcut: return the embedding model instance directly.

        Returns:
            A LangChain-compatible ``Embeddings`` object from the active provider.
        """
        return self.get_provider().get_model()
