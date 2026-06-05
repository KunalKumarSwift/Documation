"""
OpenAI LLM Provider
===================
Implements ``LLMProvider`` using OpenAI GPT-4o and GPT-4o-mini.

Used when ``CI=true`` (GitHub Actions). Requires ``OPENAI_API_KEY``.

Model selection rationale:
    - ``gpt-4o``       — answer generation: best reasoning and instruction following.
    - ``gpt-4o-mini``  — routing classification: fast and cheap for a simple
                         classification call, no need for a larger model.
"""


class OpenAILLMProvider:
    """LLM provider backed by OpenAI GPT-4o / GPT-4o-mini.

    Satisfies the ``LLMProvider`` Protocol structurally.
    """

    def get_chat(self, temperature: float = 0.1):
        """Return a ChatOpenAI instance configured for answer generation.

        Args:
            temperature: Sampling temperature. 0.1 allows slight fluency
                         variation while keeping answers grounded in context.

        Returns:
            ``langchain_openai.ChatOpenAI`` using ``gpt-4o``.
        """
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o", temperature=temperature)

    def get_router(self):
        """Return a zero-temperature ChatOpenAI instance for deterministic routing.

        Returns:
            ``langchain_openai.ChatOpenAI`` using ``gpt-4o-mini`` at temperature 0.
        """
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o-mini", temperature=0)
