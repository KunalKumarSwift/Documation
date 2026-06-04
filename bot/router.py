"""
DocBot Query Router
===================
Classifies an engineer's free-text question into the most relevant
documentation collection using a single fast LLM call.

How it works
------------
The router sends the question to a zero-temperature LLM with a structured
prompt that lists the available collections and their topic domains. The LLM
returns a JSON object that is parsed into a ``RouterResponse``. If anything
fails (network error, malformed JSON, unexpected collection name), the router
silently falls back to "general" so the query engine searches all collections.

Collections
-----------
- architecture   — System design decisions, ADRs, BFF layer, data models
- authentication — Biometric auth, Face ID/Touch ID, sessions, tokens
- payments       — Transfers, Interac, bill pay, limits, fraud detection
- runbooks       — Incident response, on-call procedures, debug steps
- onboarding     — Dev environment setup, team structure, first PR guide
- general        — Fallback when the question spans multiple domains
"""

import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

load_dotenv()

# All valid collection names — kept as a list so other modules can import it.
COLLECTIONS = ["architecture", "authentication", "payments", "runbooks", "onboarding", "general"]

# Type alias used in RouterResponse for IDE autocompletion and runtime validation.
CollectionName = Literal["architecture", "authentication", "payments", "runbooks", "onboarding", "general"]


class RouterResponse(BaseModel):
    """Structured output produced by the routing LLM call.

    Attributes:
        collection: The collection the LLM judged to be most relevant.
        confidence: HIGH when the topic clearly maps to one collection;
                    LOW when the question is ambiguous or cross-cutting.
        reasoning:  One-sentence explanation of the routing decision,
                    useful for debugging unexpected routes.
    """

    collection: CollectionName = Field(description="The most relevant doc collection")
    confidence: Literal["HIGH", "LOW"] = Field(description="Confidence in the routing decision")
    reasoning: str = Field(description="One sentence explaining the routing choice")


# ── System prompt instructs the LLM to output strict JSON ───────────────────
# The double-braces in the format string are escaped literal braces, not
# LangChain template variables.
ROUTER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a documentation router for an iOS banking app team.
Given a question, classify it into the most relevant documentation collection.

Collections:
- architecture: System design, ADRs, BFF layer, offline caching, data models
- authentication: Biometric auth, Face ID, session management, tokens, login flows
- payments: Transfers, Interac, bill pay, payment limits, fraud
- runbooks: Incident response, operational procedures, debugging steps
- onboarding: Getting started, team structure, dev setup, first PR
- general: Unclear or spanning multiple collections

Return JSON matching: {{"collection": "...", "confidence": "HIGH|LOW", "reasoning": "..."}}
If unsure, return general with LOW confidence."""),
    ("human", "Question: {question}"),
])


def get_llm():
    """Return a zero-temperature LLM for deterministic collection classification.

    Temperature is fixed at 0 so the same question always routes to the same
    collection — important for reproducible debugging and LangSmith trace comparisons.

    Returns:
        ChatOpenAI (gpt-4o-mini) when CI=true — fast and cheap for a classification call.
        ChatOllama (llama3.2) otherwise — fully local, no API cost.
    """
    is_ci = os.getenv("CI", "").lower() == "true"
    if is_ci:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o-mini", temperature=0)
    else:
        from langchain_ollama import ChatOllama
        model = os.getenv("OLLAMA_MODEL", "llama3.2")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return ChatOllama(model=model, base_url=base_url, temperature=0)


def route_query(question: str) -> RouterResponse:
    """Route a question to the most appropriate documentation collection.

    Builds a LCEL chain: prompt → LLM → JsonOutputParser, invokes it, and
    unpacks the result dict into a typed ``RouterResponse``.

    Args:
        question: The raw question text from the engineer.

    Returns:
        RouterResponse with the chosen collection, confidence level, and
        a one-sentence reasoning string.

    Note:
        This function never raises. Any exception (LLM timeout, JSON parse
        failure, unknown collection value) is caught and returns a safe
        ``RouterResponse(collection="general", confidence="LOW")``.
    """
    try:
        llm = get_llm()
        parser = JsonOutputParser(pydantic_object=RouterResponse)
        chain = ROUTER_PROMPT | llm | parser
        result = chain.invoke({"question": question})
        # JsonOutputParser returns a plain dict; unpack into the model for type safety.
        return RouterResponse(**result)
    except Exception as e:
        print(f"Router error (falling back to general): {e}")
        return RouterResponse(
            collection="general",
            confidence="LOW",
            reasoning="Router failed, searching all collections",
        )


if __name__ == "__main__":
    # Quick smoke-test: run five representative questions and print routing decisions.
    questions = [
        "How does biometric authentication fall back if Face ID fails?",
        "Why did we choose Core Data over Realm?",
        "What do we do when push notifications stop working?",
        "How do I set up my dev environment?",
        "What are the transfer limits for Interac?",
    ]
    for q in questions:
        r = route_query(q)
        print(f"Q: {q}")
        print(f"   -> {r.collection} ({r.confidence}): {r.reasoning}\n")
