"""
DocBot Query Router
Classifies a question into the most relevant documentation collection.
"""

import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

load_dotenv()

COLLECTIONS = ["architecture", "authentication", "payments", "runbooks", "onboarding", "general"]

CollectionName = Literal["architecture", "authentication", "payments", "runbooks", "onboarding", "general"]


class RouterResponse(BaseModel):
    collection: CollectionName = Field(description="The most relevant doc collection")
    confidence: Literal["HIGH", "LOW"] = Field(description="Confidence in the routing decision")
    reasoning: str = Field(description="One sentence explaining the routing choice")


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
    """Route a question to the most appropriate documentation collection."""
    try:
        llm = get_llm()
        parser = JsonOutputParser(pydantic_object=RouterResponse)
        chain = ROUTER_PROMPT | llm | parser
        result = chain.invoke({"question": question})
        return RouterResponse(**result)
    except Exception as e:
        print(f"Router error (falling back to general): {e}")
        return RouterResponse(
            collection="general",
            confidence="LOW",
            reasoning="Router failed, searching all collections",
        )


if __name__ == "__main__":
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
