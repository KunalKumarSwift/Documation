"""
query_engine
============
Thin compatibility shim — delegates to ``DocBotFacade``.

Kept so any existing code that imports ``from bot.query_engine import ask``
continues to work without changes. New code should use ``DocBotFacade`` directly.
"""

from bot.docbot_facade import DocBotFacade, QueryResult  # re-export QueryResult

__all__ = ["ask", "QueryResult"]


def ask(question: str, collection=None) -> QueryResult:
    """Delegate to ``DocBotFacade.ask()``.

    Args:
        question:   The engineer's free-text question.
        collection: Optional collection override. Auto-routes when ``None``.

    Returns:
        QueryResult from the full RAG pipeline.
    """
    return DocBotFacade().ask(question, collection=collection)


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "How does biometric auth work?"
    r = ask(q)
    print(f"\nAnswer: {r.answer}")
    print(f"Sources: {', '.join(r.source_files)}")
    print(f"Collection: {r.collection} | Confidence: {r.confidence}")
