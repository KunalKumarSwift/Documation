"""
OpenAI Embedding Provider
=========================
Implements ``EmbeddingProvider`` using OpenAI ``text-embedding-3-small``.

Used when ``CI=true`` (GitHub Actions). Requires ``OPENAI_API_KEY``.
Cost: $0.02 per 1M tokens — a full doc sync of 200 files costs under $0.01.
"""

import os


class OpenAIEmbeddingProvider:
    """Embedding provider backed by OpenAI text-embedding-3-small.

    Satisfies the ``EmbeddingProvider`` Protocol structurally.
    """

    def get_model(self):
        """Return an OpenAIEmbeddings instance using text-embedding-3-small.

        Returns:
            ``langchain_openai.OpenAIEmbeddings`` configured for the
            text-embedding-3-small model.

        Raises:
            openai.AuthenticationError: If ``OPENAI_API_KEY`` is missing or invalid.
        """
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model="text-embedding-3-small")
