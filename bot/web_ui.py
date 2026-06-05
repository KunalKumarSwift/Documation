"""
DocBot Web UI
=============
FastAPI server exposing a browser-based chat interface for DocBot.
No Slack account or tokens needed.

Endpoints:
    GET  /        Single-page chat UI (HTML from ``web_template``).
    POST /ask     Runs the RAG pipeline via ``DocBotFacade``.
    GET  /health  Liveness check.

Usage::

    python bot/web_ui.py
    # Open http://localhost:8000
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

from bot.web_template import HTML
from bot.docbot_facade import DocBotFacade

app = FastAPI(title="DocBot", description="iOS Documentation Assistant")
_facade = DocBotFacade()


class QuestionRequest(BaseModel):
    """Request body for POST /ask.

    Attributes:
        question:   The engineer's free-text question.
        collection: Optional collection to search. ``None`` triggers auto-routing.
                    Valid values: architecture, authentication, payments,
                    runbooks, onboarding.
    """

    question: str
    collection: str | None = None


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Serve the single-page chat UI.

    Returns:
        Full HTML document from ``web_template.HTML``.
    """
    return HTMLResponse(content=HTML)


@app.post("/ask")
async def ask_question(req: QuestionRequest):
    """Run the RAG pipeline and return a structured answer.

    Args:
        req: Request body with the question and optional collection override.

    Returns:
        JSON: ``{answer, source_files, collection, confidence}``.
        HTTP 500 on any internal error, with the error message in ``answer``.
    """
    try:
        result = _facade.ask(req.question, collection=req.collection)
        return {
            "answer": result.answer,
            "source_files": result.source_files,
            "collection": result.collection,
            "confidence": result.confidence,
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"answer": f"Error: {e}", "source_files": [],
                     "collection": "unknown", "confidence": "LOW"},
        )


@app.get("/health")
async def health() -> dict:
    """Liveness check.

    Returns:
        JSON: ``{status: "ok", backend: "<active backend name>"}``.
    """
    return {"status": "ok", "backend": os.getenv("VECTORSTORE_BACKEND", "chroma_local")}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"\nDocBot Web UI starting on http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
