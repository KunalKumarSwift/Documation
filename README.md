# DocBot

**Chat with your team's docs. Runs 100% locally. No API keys needed.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Local First](https://img.shields.io/badge/local--first-no%20API%20keys-orange.svg)]()

Drop your team's `.md` files into a folder. Ask questions in plain English. Get answers with source citations — via web UI, CLI, or Slack.

> **One command to run. Everything included.**

---

## Demo

![DocBot web UI — ask a question, get an answer with source citations](.github/assets/demo.gif)

*Web UI · CLI · Slack bot — all included out of the box.*

---

## Quick Start

**With Docker (recommended):**

```bash
git clone https://github.com/KunalKumarSwift/Documation.git && cd Documation
docker compose up
```

Open [http://localhost:8000](http://localhost:8000). Done.

> First run downloads Ollama models (~2 GB). Subsequent starts are instant.

---

**Without Docker:**

```bash
# Install Ollama (local LLM — free, no account needed)
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull nomic-embed-text && ollama pull phi3:latest

# Install and run
git clone https://github.com/KunalKumarSwift/Documation.git && cd Documation
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync && cp .env.example .env
ollama serve &
uv run python scripts/sync_vectorstore.py
uv run python bot/web_ui.py
```

---

## Add your docs

Drop `.md` or `.txt` files anywhere under `docs/`:

```
docs/
  architecture/     # ADRs, system design
  authentication/   # Auth flows, session tokens
  payments/         # Transfer flows, limits
  runbooks/         # Incident response
  onboarding/       # Getting started
```

DocBot auto-routes questions to the right collection. Re-sync after adding files:

```bash
uv run python scripts/sync_vectorstore.py
# or just restart Docker — it syncs on every startup
```

---

## Use DocBot in your own repo

Any repo with a `docs/` folder can sync to DocBot automatically. Add one file to `.github/workflows/`:

```yaml
# .github/workflows/sync-docs.yml
name: Sync Docs to DocBot
on:
  push:
    branches: [main]
    paths: ['docs/**']

jobs:
  sync:
    uses: KunalKumarSwift/Documation/.github/workflows/sync-vectorstore.yml@main
    with:
      docs_path: docs
      pinecone_index: my-team-docs   # your own index
    secrets:
      PINECONE_API_KEY: ${{ secrets.PINECONE_API_KEY }}
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

Every push to `main` that touches `docs/` will sync automatically. No DocBot code lives in your repo.

---

## Stack

| Layer | Local (default) | Production (opt-in) |
|---|---|---|
| LLM | Ollama + phi3 | OpenAI GPT-4o |
| Embeddings | Ollama + nomic-embed-text | OpenAI text-embedding-3-small |
| Vector store | ChromaDB (local disk) | Pinecone |
| Observability | — | LangSmith (free tier) |

Switch to production by setting env vars — no code changes needed.

---

## Interfaces

**Web UI** (`localhost:8000`) — dark-mode chat, source citations, confidence score

**CLI:**
```bash
uv run python bot/cli.py                          # interactive
uv run python bot/cli.py "How does auth work?"    # single question
uv run python bot/cli.py --auth "session tokens"  # force collection
```

**Slack:** mention `@docbot` in any channel or DM it directly. See [Slack setup](#slack-setup) below.

---

## Architecture

```
docs/*.md ──► sync_vectorstore.py ──► ChromaDB (local) / Pinecone (cloud)
                                                │
                              ┌─────────────────┘
                              ▼
                  router.py (auto-routes by topic)
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
           CLI            Web UI          Slack Bot
        (cli.py)       (web_ui.py)     (slack_bot.py)
```

Code follows the **Facade + Provider** pattern — swap backends by changing env vars, not code. See [CODING_STYLE_PROMPT.md](CODING_STYLE_PROMPT.md) for the full architecture guide.

---

## Slack Setup

1. Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps)
2. Enable **Socket Mode** → generate an App-Level Token (`xapp-`)
3. Add Bot Token Scopes: `app_mentions:read`, `chat:write`, `im:history`, `im:read`, `im:write`
4. Subscribe to events: `app_mention`, `message.im`
5. Set in `.env`:
   ```
   SLACK_BOT_TOKEN=xoxb-...
   SLACK_APP_TOKEN=xapp-...
   ```
6. Run: `uv run python bot/slack_bot.py`

---

## GitHub Actions (Auto-Sync)

Sync runs automatically on every push that touches `.md` files. Add these secrets to your repo:

| Secret | Where |
|---|---|
| `PINECONE_API_KEY` | [app.pinecone.io](https://app.pinecone.io) → API Keys |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/api-keys) |
| `LANGCHAIN_API_KEY` | [smith.langchain.com](https://smith.langchain.com) (optional) |

---

## Environment Variables

See [.env.example](.env.example) for all options.

| Variable | Default | Description |
|---|---|---|
| `VECTORSTORE_BACKEND` | `chroma_local` | `chroma_local` or `pinecone` |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| `OLLAMA_LLM_MODEL` | `phi3:latest` | Chat model |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `CI` | unset | `true` → use OpenAI instead of Ollama |
| `OPENAI_API_KEY` | — | Required when `CI=true` |
| `PINECONE_API_KEY` | — | Required when backend is `pinecone` |

---

## Contributing

1. Fork → branch → PR
2. Follow the coding style in [CODING_STYLE_PROMPT.md](CODING_STYLE_PROMPT.md)
3. Keep every file under 150 lines of logic

---

## License

Apache 2.0 — see [LICENSE](LICENSE)
