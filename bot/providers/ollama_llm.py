"""
Ollama LLM Provider
===================
Implements ``LLMProvider`` using a locally running Ollama model.

Default chat model: ``phi3:latest``. No API key required — free and fully local.
Requires Ollama to be running: ``ollama serve`` and ``ollama pull phi3:latest``.

Environment variables:
    OLLAMA_LLM_MODEL    Chat model (default: ``phi3:latest``).
    OLLAMA_BASE_URL     Ollama API base URL (default: ``http://localhost:11434``).
"""

import os


class OllamaLLMProvider:
    """LLM provider backed by a locally running Ollama model.

    Satisfies the ``LLMProvider`` Protocol structurally.
    """

    def _base(self) -> dict:
        """Return shared kwargs used by all ChatOllama instances."""
        return {
            "model": os.getenv(
                "OLLAMA_LLM_MODEL", os.getenv("OLLAMA_MODEL", "phi3:latest")
            ),
            "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        }

    def get_chat(self, temperature: float = 0.1):
        """Return a ChatOllama instance configured for answer generation.

        Args:
            temperature: Sampling temperature.

        Returns:
            ``langchain_ollama.ChatOllama`` with the configured model.

        Raises:
            httpx.ConnectError: If Ollama is not running at ``OLLAMA_BASE_URL``.
        """
        from langchain_ollama import ChatOllama

        return ChatOllama(**self._base(), temperature=temperature)

    def get_router(self):
        """Return a zero-temperature ChatOllama instance for deterministic routing.

        Returns:
            ``langchain_ollama.ChatOllama`` at temperature 0.
        """
        from langchain_ollama import ChatOllama

        return ChatOllama(**self._base(), temperature=0)
