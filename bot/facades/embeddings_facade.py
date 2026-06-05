"""
EmbeddingsFacade
================
Subsystem facade that hides embedding-provider selection from all callers.

Selects OpenAI text-embedding-3-small (CI) or Ollama llama3.2 (local)
based on the ``CI`` environment variable. Callers never import from
``langchain_openai`` or ``langchain_ollama`` directly.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class EmbeddingsFacade:
    """Subsystem facade: returns the appropriate embedding model for the environment.

    The model used at query time must match the one used during ingest —
    mixing providers produces meaningless similarity scores.
    """

    def get(self):
        """Return the configured embedding model instance.

        Returns:
            ``OpenAIEmbeddings`` (text-embedding-3-small) when ``CI=true``.
            ``OllamaEmbeddings`` (llama3.2) otherwise — free and local.

        Raises:
            ConnectionError: If Ollama is not running (local mode only).
        """
        if os.getenv("CI", "").lower() == "true":
            from langchain_openai import OpenAIEmbeddings
            return OpenAIEmbeddings(model="text-embedding-3-small")

        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
