"""
Ollama Embedding Provider
=========================
Implements ``EmbeddingProvider`` using a locally running Ollama model.

Default model: ``llama3.2``. No API key required — free and fully local.
Requires Ollama to be running: ``ollama serve`` and ``ollama pull llama3.2``.

Environment variables:
    OLLAMA_MODEL    Model name (default: ``llama3.2``).
    OLLAMA_BASE_URL Ollama API base URL (default: ``http://localhost:11434``).
"""

import os


class OllamaEmbeddingProvider:
    """Embedding provider backed by a locally running Ollama model.

    Satisfies the ``EmbeddingProvider`` Protocol structurally.
    """

    def get_model(self):
        """Return an OllamaEmbeddings instance for the configured local model.

        Returns:
            ``langchain_ollama.OllamaEmbeddings`` pointed at the local Ollama server.

        Raises:
            httpx.ConnectError: If Ollama is not running at ``OLLAMA_BASE_URL``.
        """
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
