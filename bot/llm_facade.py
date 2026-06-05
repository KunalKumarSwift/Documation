"""
LLMFacade
=========
Subsystem facade that hides chat-LLM provider selection from all callers.

Provides two factory methods:
- ``get_chat()`` — answer-generation model (slight temperature for fluency).
- ``get_router_llm()`` — classification model (temperature=0 for determinism).

Callers never import ``ChatOpenAI`` or ``ChatOllama`` directly.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class LLMFacade:
    """Subsystem facade: returns the appropriate chat LLM for the environment."""

    def get_chat(self, temperature: float = 0.1):
        """Return the answer-generation LLM.

        Args:
            temperature: Sampling temperature. 0.1 allows slight fluency
                         variation while keeping answers grounded in context.

        Returns:
            ``ChatOpenAI`` (gpt-4o) when ``CI=true``.
            ``ChatOllama`` (llama3.2) otherwise — free and local.
        """
        if os.getenv("CI", "").lower() == "true":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model="gpt-4o", temperature=temperature)

        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=temperature,
        )

    def get_router_llm(self):
        """Return a zero-temperature LLM for deterministic collection routing.

        Temperature is fixed at 0 so the same question always routes to the
        same collection — important for reproducible debugging.

        Returns:
            ``ChatOpenAI`` (gpt-4o-mini) when ``CI=true`` — cheap classification.
            ``ChatOllama`` (llama3.2) otherwise.
        """
        if os.getenv("CI", "").lower() == "true":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model="gpt-4o-mini", temperature=0)

        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=0,
        )
