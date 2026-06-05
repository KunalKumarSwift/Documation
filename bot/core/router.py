"""
Query Router
============
Classifies a free-text question into the most relevant documentation
collection using a single fast LLM call via ``LLMFacade``.

Never raises — any failure returns ``collection="general"`` so the query
engine can fall back to searching all collections.
"""

from typing import Literal
from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

load_dotenv()

COLLECTIONS = ["architecture", "authentication", "payments", "runbooks", "onboarding", "general"]
CollectionName = Literal["architecture", "authentication", "payments", "runbooks", "onboarding", "general"]


class RouterResponse(BaseModel):
    """Structured output from the routing LLM call.

    Attributes:
        collection: Most relevant collection for the question.
        confidence: HIGH when clearly one collection; LOW when ambiguous.
        reasoning:  One sentence explaining the routing decision.
    """

    collection: CollectionName = Field(description="The most relevant doc collection")
    confidence: Literal["HIGH", "LOW"] = Field(description="Routing confidence")
    reasoning: str = Field(description="One sentence explaining the routing choice")


# Double-braces produce literal braces in the rendered prompt (not template vars).
_ROUTER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a documentation router for an iOS banking app team.
Classify the question into the most relevant collection.

Collections:
- architecture: System design, ADRs, BFF layer, offline caching, data models
- authentication: Biometric auth, Face ID, session management, tokens, login flows
- payments: Transfers, Interac, bill pay, payment limits, fraud
- runbooks: Incident response, operational procedures, debugging steps
- onboarding: Getting started, team structure, dev setup, first PR
- general: Unclear or spanning multiple collections

Return JSON: {{"collection":"...","confidence":"HIGH|LOW","reasoning":"..."}}
If unsure, return general with LOW confidence."""),
    ("human", "Question: {question}"),
])


def route_query(question: str) -> RouterResponse:
    """Route a question to the most appropriate documentation collection.

    Args:
        question: The engineer's free-text question.

    Returns:
        RouterResponse with the chosen collection, confidence, and reasoning.
        Falls back to ``collection="general", confidence="LOW"`` on any error.
    """
    from bot.facades.llm_facade import LLMFacade
    try:
        llm = LLMFacade().get_router_llm()
        chain = _ROUTER_PROMPT | llm | JsonOutputParser(pydantic_object=RouterResponse)
        # JsonOutputParser returns a plain dict; unpack into the model for type safety.
        return RouterResponse(**chain.invoke({"question": question}))
    except Exception as e:
        print(f"Router error (falling back to general): {e}")
        return RouterResponse(
            collection="general",
            confidence="LOW",
            reasoning="Router failed, searching all collections",
        )
