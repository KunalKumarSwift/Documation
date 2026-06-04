"""
DocBot RAG Query Engine
Retrieves relevant doc chunks and generates grounded answers.
"""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

LANGSMITH_TRACING = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
VECTORSTORE_BACKEND = os.getenv("VECTORSTORE_BACKEND", "chroma_local")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", ".chroma_db")
LOW_CONFIDENCE_THRESHOLD = 1.5  # Pinecone score; for Chroma we use distance > 0.8

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
    answer: str
    source_files: list[str]
    collection: str
    confidence: str  # HIGH, MEDIUM, LOW


def get_embeddings():
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
    is_ci = os.getenv("CI", "").lower() == "true"
    if is_ci:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o", temperature=0.1)
    else:
        from langchain_ollama import ChatOllama
        model = os.getenv("OLLAMA_MODEL", "llama3.2")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return ChatOllama(model=model, base_url=base_url, temperature=0.1)


def query_all_collections(embeddings, question: str, k: int = 3):
    """Search across all collections when routing returns 'general'."""
    all_docs = []

    collections = ["architecture", "authentication", "payments", "runbooks", "onboarding"]
    for col in collections:
        try:
            vs = get_vectorstore(embeddings, col)
            docs = vs.similarity_search_with_score(question, k=1)
            all_docs.extend(docs)
        except Exception:
            pass

    # Sort by score and return top k
    all_docs.sort(key=lambda x: x[1])
    return all_docs[:k]


def ask(question: str, collection: Optional[str] = None) -> QueryResult:
    """
    Ask a question and get a grounded answer from the docs.

    Args:
        question: The user's question
        collection: Optional collection to search. Auto-routes if None.

    Returns:
        QueryResult with answer, sources, and confidence
    """
    from bot.router import route_query

    # Route if no collection specified
    if collection is None or collection == "general":
        route = route_query(question)
        collection = route.collection
        print(f"Routed to: {collection} ({route.confidence})")

    embeddings = get_embeddings()

    # Retrieve relevant chunks
    if collection == "general":
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

    # Check confidence via retrieval score
    # For ChromaDB: lower distance = better match (< 0.5 is good, > 1.0 is poor)
    # For Pinecone: higher score = better match (< 0.3 is poor)
    top_score = docs_with_scores[0][1]
    if VECTORSTORE_BACKEND == "pinecone":
        confidence = "HIGH" if top_score > 0.7 else ("MEDIUM" if top_score > 0.4 else "LOW")
    else:
        confidence = "HIGH" if top_score < 0.5 else ("MEDIUM" if top_score < 0.9 else "LOW")

    if confidence == "LOW":
        return QueryResult(
            answer="I'm not confident I have relevant documentation for that question. The docs may not cover this topic yet — try checking the `docs/` folder directly.",
            source_files=[],
            collection=collection,
            confidence="LOW",
        )

    # Build context from retrieved chunks
    chunks = [doc for doc, _ in docs_with_scores]
    context = "\n\n---\n\n".join(
        f"[{doc.metadata.get('source', 'unknown')}]\n{doc.page_content}"
        for doc in chunks
    )

    source_files = list({doc.metadata.get("source", "unknown") for doc in chunks})

    # Generate answer
    llm = get_llm()
    chain = RAG_PROMPT | llm
    response = chain.invoke({"context": context, "question": question})
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
