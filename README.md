# DocBot — iOS Platform Documentation Assistant

DocBot is an AI chatbot that makes your team's GitHub markdown docs instantly queryable. Ask questions in natural language and get grounded answers with source citations — works via web UI, CLI, or Slack.

## Architecture

```
docs/*.md ──> sync_vectorstore.py ──> ChromaDB (local) or Pinecone (cloud)
                                               |
                             ┌─────────────────┘
                             v
                 query_engine.py + router.py
                             |
             ┌───────────────┼───────────────┐
             v               v               v
          CLI            Web UI          Slack Bot
       (cli.py)       (web_ui.py)     (slack_bot.py)
       Terminal        Browser         Slack channels
```

**Free tier stack (default — zero API keys needed):**
- Vector store: ChromaDB local (completely free)
- LLM + Embeddings: Ollama + llama3.2 (local, free)

**Production stack (opt-in):**
- Vector store: Pinecone free tier (1 index, 2GB)
- Embeddings: OpenAI text-embedding-3-small (~$0.01/full sync)
- LLM: GPT-4o via OpenAI
- Observability: LangSmith free tier (10k traces/month)

---

## Quick Start (Local Dev — No API Keys)

### 1. Prerequisites

```bash
# Python package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Local LLM (free, ~2GB download)
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.2
```

### 2. Install

```bash
git clone <your-repo> && cd docbot
uv sync
cp .env.example .env   # defaults work for local dev
```

### 3. Index your docs

```bash
# Make sure Ollama is running first
ollama serve &

uv run python scripts/sync_vectorstore.py
```

### 4. Start the web UI

```bash
uv run python bot/web_ui.py
# Open http://localhost:8000
```

Or use the CLI:

```bash
uv run python bot/cli.py                              # interactive
uv run python bot/cli.py "How does Face ID work?"     # single question
uv run python bot/cli.py --authentication "session tokens"  # force collection
```

---

## Adding Documentation

Drop `.md` files into the right `docs/` subfolder:

```
docs/
  architecture/     # System design, ADRs, BFF layer
  authentication/   # Auth flows, session management
  payments/         # Transfer flows, limits, fraud
  runbooks/         # Incident response procedures
  onboarding/       # Getting started, team structure
```

Then re-sync:

```bash
uv run python scripts/sync_vectorstore.py
```

With GitHub Actions configured, sync runs automatically on every push to `main`.

---

## CLI Commands

```bash
uv run python bot/cli.py                   # interactive mode
uv run python bot/cli.py "your question"   # single question

# In interactive mode:
/sync              # re-index all docs
/collections       # list available doc collections
/auth <q>          # query authentication docs
/payments <q>      # query payments docs
/runbooks <q>      # query runbooks
/architecture <q>  # query architecture docs
/onboarding <q>    # query onboarding docs
/help              # show all commands
/quit              # exit
```

---

## Slack Bot Setup

1. Create a Slack app at https://api.slack.com/apps
2. Enable **Socket Mode** (Settings → Socket Mode)
3. Add **Bot Token Scopes**: `app_mentions:read`, `chat:write`, `im:history`, `im:read`, `im:write`
4. Subscribe to bot events: `app_mention`, `message.im`
5. Install the app to your workspace
6. Update `.env` with your tokens:
   ```
   SLACK_BOT_TOKEN=xoxb-...
   SLACK_APP_TOKEN=xapp-...
   SLACK_SIGNING_SECRET=...
   ```
7. Run: `uv run python bot/slack_bot.py`

### Slack commands

| Command | Description |
|---------|-------------|
| `@docbot <question>` | Auto-routed question |
| `@docbot /auth <q>` | Force authentication collection |
| `@docbot /payments <q>` | Force payments collection |
| `@docbot /runbooks <q>` | Force runbooks collection |
| `@docbot /help` | Show help |
| `@docbot /collections` | List indexed collections |

---

## GitHub Actions (Auto-Sync)

The workflow at `.github/workflows/sync-vectorstore.yml` syncs docs automatically when `.md` files change on `main`.

**Required GitHub Secrets:**

| Secret | Where to get it |
|--------|----------------|
| `PINECONE_API_KEY` | https://app.pinecone.io → API Keys |
| `PINECONE_INDEX` | Your index name (e.g. `docbot-docs`) |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| `LANGCHAIN_API_KEY` | https://smith.langchain.com → Settings (optional) |

---

## Environment Variables

See `.env.example` for all options with comments.

| Variable | Default | Description |
|----------|---------|-------------|
| `VECTORSTORE_BACKEND` | `chroma_local` | `chroma_local` or `pinecone` |
| `CHROMA_PERSIST_DIR` | `.chroma_db` | Local ChromaDB storage path |
| `OLLAMA_MODEL` | `llama3.2` | Ollama model for LLM + embeddings |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `CI` | unset | Set to `true` to use OpenAI instead of Ollama |
| `OPENAI_API_KEY` | — | Required when `CI=true` |
| `PINECONE_API_KEY` | — | Required when backend is `pinecone` |
| `SLACK_BOT_TOKEN` | — | Required for Slack bot |

---

## Project Structure

```
docbot/
  bot/
    __init__.py
    cli.py           # Interactive CLI interface
    web_ui.py        # Browser chat UI (FastAPI)
    slack_bot.py     # Slack bot (Bolt SDK)
    query_engine.py  # RAG query engine
    router.py        # Collection router
  docs/
    architecture/    # Architecture docs and ADRs
    authentication/  # Auth and session docs
    payments/        # Payment flow docs
    runbooks/        # Operational runbooks
    onboarding/      # Getting started guides
  scripts/
    sync_vectorstore.py  # Doc ingestion pipeline
  .github/workflows/
    sync-vectorstore.yml  # CI auto-sync
  .env.example
  pyproject.toml
```
