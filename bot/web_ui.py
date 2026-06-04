"""
DocBot Web UI — Browser-based chat interface for DocBot.
No Slack needed. Runs on http://localhost:8000

Usage:
    python bot/web_ui.py
    # Then open http://localhost:8000 in your browser
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

app = FastAPI(title="DocBot", description="iOS Documentation Assistant")

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DocBot — iOS Docs Assistant</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f0f0f; color: #e0e0e0; height: 100vh; display: flex; flex-direction: column; }
  header { background: #1a1a2e; border-bottom: 1px solid #2d2d4a; padding: 16px 24px; display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 20px; font-weight: 700; color: #7c9de8; }
  header p { font-size: 13px; color: #888; }
  .collections { display: flex; gap: 8px; padding: 12px 24px; background: #111; border-bottom: 1px solid #222; flex-wrap: wrap; }
  .col-btn { background: #1e1e2e; border: 1px solid #333; color: #aaa; padding: 4px 12px; border-radius: 16px; font-size: 12px; cursor: pointer; transition: all 0.2s; }
  .col-btn:hover, .col-btn.active { background: #7c9de8; border-color: #7c9de8; color: #fff; }
  .chat-area { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 16px; }
  .message { max-width: 780px; }
  .message.user { margin-left: auto; text-align: right; }
  .message.user .bubble { background: #7c9de8; color: #fff; border-radius: 18px 18px 4px 18px; padding: 12px 16px; display: inline-block; }
  .message.bot .bubble { background: #1e1e2e; border: 1px solid #2d2d4a; border-radius: 18px 18px 18px 4px; padding: 14px 18px; display: inline-block; text-align: left; max-width: 100%; }
  .message.bot .answer { line-height: 1.6; white-space: pre-wrap; }
  .sources { margin-top: 10px; padding-top: 10px; border-top: 1px solid #2d2d4a; }
  .sources .label { font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
  .sources .src { font-size: 12px; color: #7c9de8; font-family: monospace; }
  .confidence { display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: 10px; margin-top: 8px; }
  .confidence.HIGH { background: #1a3a1a; color: #4caf50; }
  .confidence.MEDIUM { background: #3a2a00; color: #ffa726; }
  .confidence.LOW { background: #3a1a1a; color: #ef5350; }
  .thinking { color: #555; font-style: italic; font-size: 14px; }
  .input-area { padding: 16px 24px; border-top: 1px solid #222; background: #111; display: flex; gap: 12px; align-items: flex-end; }
  textarea { flex: 1; background: #1e1e2e; border: 1px solid #333; border-radius: 12px; padding: 12px 16px; color: #e0e0e0; font-size: 15px; resize: none; outline: none; min-height: 48px; max-height: 200px; font-family: inherit; line-height: 1.5; }
  textarea:focus { border-color: #7c9de8; }
  button#send-btn { background: #7c9de8; border: none; border-radius: 12px; width: 48px; height: 48px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background 0.2s; flex-shrink: 0; }
  button#send-btn:hover { background: #5a7ec8; }
  button#send-btn svg { width: 20px; height: 20px; fill: white; }
  button#send-btn:disabled { background: #333; cursor: not-allowed; }
  .welcome { text-align: center; padding: 40px 20px; color: #555; }
  .welcome h2 { color: #7c9de8; margin-bottom: 12px; font-size: 22px; }
  .example-questions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 20px; }
  .eq { background: #1a1a2e; border: 1px solid #2d2d4a; border-radius: 12px; padding: 8px 14px; font-size: 13px; cursor: pointer; color: #aaa; transition: all 0.2s; }
  .eq:hover { border-color: #7c9de8; color: #7c9de8; }
</style>
</head>
<body>
<header>
  <div>
    <h1>DocBot</h1>
    <p>iOS Platform Documentation Assistant</p>
  </div>
</header>
<div class="collections">
  <span style="font-size:12px;color:#666;align-self:center;margin-right:4px">Filter:</span>
  <button class="col-btn active" data-col="auto">Auto-route</button>
  <button class="col-btn" data-col="architecture">Architecture</button>
  <button class="col-btn" data-col="authentication">Authentication</button>
  <button class="col-btn" data-col="payments">Payments</button>
  <button class="col-btn" data-col="runbooks">Runbooks</button>
  <button class="col-btn" data-col="onboarding">Onboarding</button>
</div>
<div class="chat-area" id="chat">
  <div class="welcome">
    <h2>Ask about your iOS platform docs</h2>
    <p>I'll search the indexed documentation and give you a grounded answer with sources.</p>
    <div class="example-questions">
      <div class="eq">How does Face ID fallback work?</div>
      <div class="eq">Why did we choose Core Data over Realm?</div>
      <div class="eq">What do we do when push notifications fail?</div>
      <div class="eq">How does the BFF layer reduce latency?</div>
      <div class="eq">How do I set up my dev environment?</div>
      <div class="eq">What are the transfer limits for Interac?</div>
    </div>
  </div>
</div>
<div class="input-area">
  <textarea id="input" placeholder="Ask a question about the iOS platform docs..." rows="1"></textarea>
  <button id="send-btn">
    <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
  </button>
</div>
<script>
let selectedCollection = 'auto';

document.querySelectorAll('.col-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.col-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedCollection = btn.dataset.col;
  });
});

document.querySelectorAll('.eq').forEach(eq => {
  eq.addEventListener('click', () => {
    document.getElementById('input').value = eq.textContent;
    sendMessage();
  });
});

const input = document.getElementById('input');
input.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 200) + 'px';
});

document.getElementById('send-btn').addEventListener('click', sendMessage);

function appendMessage(role, content) {
  const chat = document.getElementById('chat');
  const welcome = chat.querySelector('.welcome');
  if (welcome) welcome.remove();

  const div = document.createElement('div');
  div.className = `message ${role}`;
  div.innerHTML = content;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

async function sendMessage() {
  const q = input.value.trim();
  if (!q) return;

  input.value = '';
  input.style.height = 'auto';
  document.getElementById('send-btn').disabled = true;

  appendMessage('user', `<div class="bubble">${escapeHtml(q)}</div>`);

  const thinking = appendMessage('bot', '<div class="bubble"><span class="thinking">Searching docs...</span></div>');

  try {
    const col = selectedCollection === 'auto' ? null : selectedCollection;
    const resp = await fetch('/ask', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ question: q, collection: col })
    });
    const data = await resp.json();

    let srcHtml = '';
    if (data.source_files && data.source_files.length > 0) {
      srcHtml = `<div class="sources"><div class="label">Sources</div>${
        data.source_files.map(s => `<div class="src">📄 ${escapeHtml(s)}</div>`).join('')
      }</div>`;
    }

    const confClass = data.confidence || 'MEDIUM';
    thinking.innerHTML = `<div class="bubble">
      <div class="answer">${escapeHtml(data.answer)}</div>
      ${srcHtml}
      <span class="confidence ${confClass}">${confClass} confidence</span>
    </div>`;
  } catch(e) {
    thinking.innerHTML = `<div class="bubble"><span style="color:#ef5350">Error: ${escapeHtml(e.message)}</span></div>`;
  }

  document.getElementById('send-btn').disabled = false;
  input.focus();
}

function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
</script>
</body>
</html>"""


class QuestionRequest(BaseModel):
    """Request body for the /ask endpoint."""

    question: str
    collection: str | None = None  # None triggers auto-routing


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the single-page chat UI."""
    return HTMLResponse(content=HTML)


@app.post("/ask")
async def ask_question(req: QuestionRequest):
    """Run a RAG query and return the answer, sources, and confidence level."""
    try:
        from bot.query_engine import ask
        result = ask(req.question, collection=req.collection)
        return {
            "answer": result.answer,
            "source_files": result.source_files,
            "collection": result.collection,
            "confidence": result.confidence,
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"answer": f"Error: {str(e)}", "source_files": [], "collection": "unknown", "confidence": "LOW"},
        )


@app.get("/health")
async def health():
    """Liveness check — returns the active vector store backend."""
    return {"status": "ok", "backend": os.getenv("VECTORSTORE_BACKEND", "chroma_local")}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"\nDocBot Web UI starting on http://localhost:{port}")
    print("Open your browser and start asking questions!\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
