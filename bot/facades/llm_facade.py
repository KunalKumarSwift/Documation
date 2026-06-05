"""
LLMFacade
=========
Selects the correct ``LLMProvider`` implementation based on the environment.

This facade contains *only* the switching logic — no LLM code lives here.
All implementation details are in ``bot/providers/``.

Switch:
    CI=true  →  ``OpenAILLMProvider``   (gpt-4o / gpt-4o-mini)
    default  →  ``OllamaLLMProvider``   (llama3.2, local)
"""

import os
from dotenv import load_dotenv
from bot.providers.protocols import LLMProvider

load_dotenv()

_IS_CI = os.getenv("CI", "").lower() == "true"


class LLMFacade:
    """Facade that selects and exposes the appropriate LLMProvider.

    Callers use ``get_provider()`` for the typed provider, or the convenience
    methods ``get_chat()`` / ``get_router_llm()`` to skip the extra call.
    """

    def get_provider(self) -> LLMProvider:
        """Return the LLMProvider for the current environment.

        Returns:
            ``OpenAILLMProvider`` when ``CI=true``.
            ``OllamaLLMProvider`` otherwise.
        """
        if _IS_CI:
            from bot.providers.openai_llm import OpenAILLMProvider
            return OpenAILLMProvider()
        from bot.providers.ollama_llm import OllamaLLMProvider
        return OllamaLLMProvider()

    def get_chat(self, temperature: float = 0.1):
        """Convenience shortcut: return the answer-generation model directly.

        Args:
            temperature: Forwarded to the provider's ``get_chat()`` method.

        Returns:
            A LangChain-compatible ``BaseChatModel`` from the active provider.
        """
        return self.get_provider().get_chat(temperature)

    def get_router_llm(self):
        """Convenience shortcut: return the zero-temperature routing model.

        Returns:
            A LangChain-compatible ``BaseChatModel`` at temperature 0.
        """
        return self.get_provider().get_router()
