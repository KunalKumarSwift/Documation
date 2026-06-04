"""
DocBot RAG Query Engine
=======================
Implements the full Retrieval-Augmented Generation pipeline:

  question → [router] → collection
           → [embeddings] → query vector
           → [vector store] → top-k chunks
           → [confidence check] → early exit if no good match
           → [LLM] → grounded answer
           → QueryResult

The engine is the single entry point for all interfaces (CLI, web UI,
Slack bot). It is stateless — every call to ``ask()`` is independent.

Confidence scoring
------------------
Vector similarity scores are backend-specific:
- ChromaDB returns L2 *distance*: lower = more similar (0.0 is a perfect match).
  Thresholds: HIGH < 0.5, MEDIUM < 0.9, LOW ≥ 0.9.
- Pinecone returns cosine *similarity*: higher = more similar (1.0 is perfect).
  Thresholds: HIGH > 0.7, MEDIUM > 0.4, LOW ≤ 0.4.

LangSmith tracing
-----------------
If LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY are set, every call to
``ask()`` is automatically traced in LangSmith — no code changes needed.
"""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# Read at import time so every call uses a consistent backend.
VECTORSTORE_BACKEND = os.getenv("VECTORSTORE_BACKEND", "chroma_local")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", ".chroma_db")

# ── RAG system prompt ────────────────────────────────────────────────────────
# "Answer only from context" is the key instruction that prevents hallucination.
# The LLM is explicitly told to admit ignorance rather than fabricate an answer.
RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are DocBot, an AI assistant for an iOS banking app development team.
Answer the engineer's question using ONLY the documentation context provided below.

Rules:
- Base your answer entirely on the provided context
- If the context does not contain enough information, say: "I don't have documentation on that. Check the docs/ folder manually."
- Do not make up APIs, decisions, or facts not in the context
- Be concise: 3–5 sentences maximum
- Always mention which document your answer comes from

Context:
{context}"""),
    ("human", "{question}"),
])


@dataclass
class QueryResult:
    """Structured response returned by the RAG pipeline.

    Attributes:
        answer:       The LLM-generated answer, grounded in retrieved chunks.
        source_files: Deduplicated list of repo-relative paths that contributed
                      context, e.g. ``["docs/auth/biometric.md"]``.
        collection:   The collection that was searched (may differ from what
                      the caller requested if routing overrode it).
        confidence:   Retrieval confidence — "HIGH", "MEDIUM", or "LOW".
                      LOW means the vector store had no close matches and the
                      answer field contains a canned "I don't know" response.
    """

    answer: str
    source_files: list[str]
    collection: str
    confidence: str


def get_embeddings():
    """Return the embedding model appropriate for the current environment.

    Returns:
        OpenAIEmbeddings (text-embedding-3-small) when CI=true.
        OllamaEmbeddings (llama3.2) otherwise.

    Note:
        The embedding model used at query time must match the one used during
        ingest — mixing models produces meaningless similarity scores.
    """
    is_ci = os.getenv("CI", "").lower() == "true"
    if is_ci:
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model="text-embedding-3-small")
    else:
        from langchain_ollama import OllamaEmbeddings
        model = os.getenv("OLLAMA_MODEL", "llama3.2")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return OllamaEmbeddings(model=model, base_url=base_url)


def get_vectorstore(embeddings, collection: str = "general"):
    """Return a vector store client scoped to a single collection/namespace.

    Args:
        embeddings: The embedding model instance used to convert query text to a vector.
        collection: Collection name to scope the search. Maps to a Pinecone namespace
                    or a ChromaDB collection name.

    Returns:
        PineconeVectorStore when VECTORSTORE_BACKEND=pinecone.
        Chroma otherwise, reading from CHROMA_PERSIST_DIR on disk.

    Raises:
        KeyError: If PINECONE_API_KEY is not set and backend is pinecone.
    """
    if VECTORSTORE_BACKEND == "pinecone":
        from langchain_pinecone import PineconeVectorStore
        from pinecone import Pinecone
        pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        index_name = os.getenv("PINECONE_INDEX", "docbot-docs")
        return PineconeVectorStore(
            index=pc.Index(index_name),
            embedding=embeddings,
            namespace=collection,
        )
    else:
        from langchain_chroma import Chroma
        return Chroma(
            collection_name=collection,
            embedding_function=embeddings,
            persist_directory=CHROMA_PERSIST_DIR,
        )


def get_llm():
    """Return the answer-generation LLM for the current environment.

    Temperature 0.1 allows slight fluency variation while keeping the answer
    grounded — pure 0 can produce overly mechanical prose.

    Returns:
        ChatOpenAI (gpt-4o) when CI=true — best answer quality for production.
        ChatOllama (llama3.2) otherwise — free, local, good enough for dev/test.
    """
    is_ci = os.getenv("CI", "").lower() == "true"
    if is_ci:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o", temperature=0.1)
    else:
        from langchain_ollama import ChatOllama
        model = os.getenv("OLLAMA_MODEL", "llama3.2")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return ChatOllama(model=model, base_url=base_url, temperature=0.1)


def query_all_collections(embeddings, question: str, k: int = 3) -> list:
    """Search every collection and return the globally top-k results.

    Used when the router returns "general" — either because the question
    spans multiple topics or because the router could not classify it.

    Fetches the single best match from each collection (k=1 per collection)
    to avoid any one collection dominating the results, then merges and
    re-ranks by score across all collections.

    Args:
        embeddings: Embedding model instance.
        question:   The raw query string.
        k:          Maximum number of chunks to return across all collections.

    Returns:
        List of (Document, score) tuples, sorted ascending by score
        (lower distance = better for ChromaDB).
    """
    all_docs = []

    collections = ["architecture", "authentication", "payments", "runbooks", "onboarding"]
    for col in collections:
        try:
            vs = get_vectorstore(embeddings, col)
            # k=1 per collection so results are spread across domains.
            docs = vs.similarity_search_with_score(question, k=1)
            all_docs.extend(docs)
        except Exception:
            # A collection may not exist yet if no docs have been ingested for it.
            pass

    # Sort ascending: ChromaDB scores are distances (lower = better).
    all_docs.sort(key=lambda x: x[1])
    return all_docs[:k]


def ask(question: str, collection: Optional[str] = None) -> QueryResult:
    """Run the full RAG pipeline: route → retrieve → score → generate.

    Args:
        question:   The engineer's free-text question.
        collection: Optional collection name to search directly. When None or
                    "general", the router determines the collection automatically.

    Returns:
        QueryResult containing the answer, list of source files, the collection
        that was searched, and a confidence level ("HIGH", "MEDIUM", or "LOW").

    Note:
        A LOW confidence result returns a canned "I don't know" message and
        empty source_files rather than asking the LLM to guess from poor context.
    """
    from bot.router import route_query

    # ── Step 1: determine which collection to search ─────────────────────────
    if collection is None or collection == "general":
        route = route_query(question)
        collection = route.collection
        print(f"Routed to: {collection} ({route.confidence})")

    embeddings = get_embeddings()

    # ── Step 2: retrieve the top-3 most relevant chunks ──────────────────────
    if collection == "general":
        # Router was not confident — cast a wider net across all collections.
        docs_with_scores = query_all_collections(embeddings, question)
    else:
        vs = get_vectorstore(embeddings, collection)
        docs_with_scores = vs.similarity_search_with_score(question, k=3)

    if not docs_with_scores:
        return QueryResult(
            answer="I don't have any documentation indexed yet. Run `python scripts/sync_vectorstore.py` first.",
            source_files=[],
            collection=collection,
            confidence="LOW",
        )

    # ── Step 3: score the retrieval quality ──────────────────────────────────
    # Score semantics differ between backends:
    # - ChromaDB: L2 distance (0 = identical, higher = less similar)
    # - Pinecone: cosine similarity (1 = identical, lower = less similar)
    top_score = docs_with_scores[0][1]
    if VECTORSTORE_BACKEND == "pinecone":
        confidence = "HIGH" if top_score > 0.7 else ("MEDIUM" if top_score > 0.4 else "LOW")
    else:
        confidence = "HIGH" if top_score < 0.5 else ("MEDIUM" if top_score < 0.9 else "LOW")

    if confidence == "LOW":
        # Rather than letting the LLM hallucinate from poor context, return early.
        return QueryResult(
            answer="I'm not confident I have relevant documentation for that question. The docs may not cover this topic yet — try checking the `docs/` folder directly.",
            source_files=[],
            collection=collection,
            confidence="LOW",
        )

    # ── Step 4: build the context string passed to the LLM ───────────────────
    chunks = [doc for doc, _ in docs_with_scores]
    # Prefix each chunk with its source path so the LLM can cite it in the answer.
    context = "\n\n---\n\n".join(
        f"[{doc.metadata.get('source', 'unknown')}]\n{doc.page_content}"
        for doc in chunks
    )

    # Use a set comprehension to deduplicate sources (multiple chunks from one file).
    source_files = list({doc.metadata.get("source", "unknown") for doc in chunks})

    # ── Step 5: generate the grounded answer ─────────────────────────────────
    llm = get_llm()
    chain = RAG_PROMPT | llm
    response = chain.invoke({"context": context, "question": question})
    # LangChain chat models return an AIMessage; fall back to str() for edge cases.
    answer = response.content if hasattr(response, "content") else str(response)

    return QueryResult(
        answer=answer,
        source_files=source_files,
        collection=collection,
        confidence=confidence,
    )


if __name__ == "__main__":
    import sys
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "How does biometric auth work?"
    result = ask(question)
    print(f"\nAnswer: {result.answer}")
    print(f"\nSources: {', '.join(result.source_files)}")
    print(f"Collection: {result.collection} | Confidence: {result.confidence}")
