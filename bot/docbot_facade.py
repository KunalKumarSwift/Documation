"""
DocBotFacade
============
The primary facade of the DocBot system.

Clients (CLI, Web UI, Slack bot) call only one method::

    result = DocBotFacade().ask("How does Face ID fallback work?")

Internally, the facade coordinates three subsystem facades:

- ``EmbeddingsFacade``  — chooses Ollama vs OpenAI embeddings
- ``VectorStoreFacade`` — chooses ChromaDB vs Pinecone, runs search/delete
- ``LLMFacade``         — chooses llama3.2 vs GPT-4o for answer generation

And one supporting module:

- ``router``            — classifies the question into a collection

No caller ever needs to know which backend is active.
"""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

_BACKEND = os.getenv("VECTORSTORE_BACKEND", "chroma_local")
_ALL_COLLECTIONS = ["architecture", "authentication", "payments", "runbooks", "onboarding"]

_RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are DocBot, an AI assistant for an iOS banking app team.
Answer the question using ONLY the documentation context provided below.

Rules:
- Base your answer entirely on the provided context.
- If context is insufficient say: "I don't have documentation on that. Check docs/ manually."
- Do not fabricate APIs, facts, or decisions.
- Be concise: 3-5 sentences maximum.
- Always cite which document your answer comes from.

Context:
{context}"""),
    ("human", "{question}"),
])


@dataclass
class QueryResult:
    """Structured response returned by ``DocBotFacade.ask()``.

    Attributes:
        answer:       LLM-generated answer grounded in retrieved doc chunks.
        source_files: Deduplicated repo-relative paths that contributed context.
        collection:   Collection that was actually searched.
        confidence:   ``"HIGH"``, ``"MEDIUM"``, or ``"LOW"`` based on retrieval score.
    """

    answer: str
    source_files: list[str]
    collection: str
    confidence: str


class DocBotFacade:
    """Primary facade: exposes ``ask()`` as the single entry point to DocBot.

    Hides all subsystem complexity — routing, embedding, retrieval, scoring,
    and LLM generation — behind one simple method call.
    """

    def ask(self, question: str, collection: Optional[str] = None) -> QueryResult:
        """Retrieve relevant doc chunks and generate a grounded answer.

        Args:
            question:   The engineer's free-text question.
            collection: Collection to search. Auto-routes when ``None`` or ``"general"``.

        Returns:
            QueryResult with the answer, source files, collection, and confidence level.
        """
        from bot.core.router import route_query
        from bot.facades.embeddings_facade import EmbeddingsFacade
        from bot.facades.vectorstore_facade import VectorStoreFacade
        from bot.facades.llm_facade import LLMFacade

        if collection is None or collection == "general":
            route = route_query(question)
            collection = route.collection
            print(f"Routed to: {collection} ({route.confidence})")

        vs = VectorStoreFacade(EmbeddingsFacade().get_model())
        docs_with_scores = (
            self._search_all(vs, question)
            if collection == "general"
            else vs.search(question, collection, k=3)
        )

        if not docs_with_scores:
            return QueryResult(
                answer="No docs indexed yet. Run `python scripts/sync_vectorstore.py` first.",
                source_files=[], collection=collection, confidence="LOW",
            )

        confidence = self._score_confidence(docs_with_scores[0][1])
        if confidence == "LOW":
            return QueryResult(
                answer="I'm not confident I have relevant docs for that. Check the docs/ folder directly.",
                source_files=[], collection=collection, confidence="LOW",
            )

        chunks = [doc for doc, _ in docs_with_scores]
        context = "\n\n---\n\n".join(
            f"[{d.metadata.get('source','unknown')}]\n{d.page_content}" for d in chunks
        )
        source_files = list({d.metadata.get("source", "unknown") for d in chunks})

        response = (_RAG_PROMPT | LLMFacade().get_chat()).invoke(
            {"context": context, "question": question}
        )
        answer = response.content if hasattr(response, "content") else str(response)

        return QueryResult(
            answer=answer, source_files=source_files,
            collection=collection, confidence=confidence,
        )

    def _search_all(self, vs, question: str) -> list:
        """Fetch the best match from every collection and return top-3 globally.

        Uses k=1 per collection so no single domain dominates the merged results.
        """
        results = []
        for col in _ALL_COLLECTIONS:
            try:
                results.extend(vs.search(question, col, k=1))
            except Exception:
                pass
        results.sort(key=lambda x: x[1])
        return results[:3]

    def _score_confidence(self, top_score: float) -> str:
        """Map a raw retrieval score to a confidence level.

        ChromaDB returns L2 distance (lower = better).
        Pinecone returns cosine similarity (higher = better).
        """
        if _BACKEND == "pinecone":
            return "HIGH" if top_score > 0.7 else ("MEDIUM" if top_score > 0.4 else "LOW")
        return "HIGH" if top_score < 0.5 else ("MEDIUM" if top_score < 0.9 else "LOW")
