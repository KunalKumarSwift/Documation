"""
DocBot Slack Bot
Listens for @docbot mentions and DMs, answers questions from the docs.

Setup:
1. Create a Slack app at https://api.slack.com/apps
2. Enable Socket Mode
3. Add bot scopes: app_mentions:read, chat:write, im:history, im:read, im:write
4. Set env vars: SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_SIGNING_SECRET
5. Run: python bot/slack_bot.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")

if not SLACK_BOT_TOKEN or SLACK_BOT_TOKEN == "xoxb-your-bot-token":
    print("ERROR: SLACK_BOT_TOKEN not set. See .env.example")
    sys.exit(1)

app = App(token=SLACK_BOT_TOKEN)

COLLECTIONS = ["architecture", "authentication", "payments", "runbooks", "onboarding"]

HELP_TEXT = """*DocBot* — iOS Platform Documentation Assistant

*Usage:*
• `@docbot <question>` — Ask anything (auto-routes to the right collection)
• `@docbot /auth <question>` — Query authentication docs
• `@docbot /payments <question>` — Query payments docs
• `@docbot /runbooks <question>` — Query runbooks
• `@docbot /onboarding <question>` — Query onboarding docs
• `@docbot /architecture <question>` — Query architecture docs
• `@docbot /help` — Show this help
• `@docbot /collections` — List doc collections

*Examples:*
> @docbot how does Face ID fallback work?
> @docbot /runbooks push notifications not working in prod
> @docbot /architecture why did we choose Core Data over Realm?"""


def extract_question_and_collection(text: str) -> tuple[str, str | None]:
    """Strip the @bot mention and detect an optional /collection prefix from the message text."""
    # Remove bot mention
    text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

    # Check for forced collection
    for col in COLLECTIONS:
        if text.lower().startswith(f"/{col} "):
            return text[len(col) + 2:].strip(), col

    return text, None


def format_slack_response(result) -> str:
    """Format a QueryResult as Slack mrkdwn with source citations and a feedback prompt."""
    confidence_emoji = {"HIGH": "✅", "MEDIUM": "⚠️", "LOW": "❓"}.get(result.confidence, "⚠️")

    lines = [result.answer, ""]

    if result.source_files:
        for src in result.source_files:
            lines.append(f"📄 Source: `{src}`")

    lines.append(f"{confidence_emoji} Confidence: {result.confidence}")
    lines.append("\n_Was this helpful? React with 👍 or 👎_")

    return "\n".join(lines)


def handle_question(question: str, collection: str | None, say, thread_ts: str | None = None):
    """Post a 'Searching...' placeholder immediately, run the RAG query, then update the message.

    Slack requires an initial response within 3 seconds; the two-step post+edit
    pattern keeps us under that limit while the query runs.
    """
    placeholder = say(text="Searching docs...", thread_ts=thread_ts)

    try:
        from bot.query_engine import ask
        result = ask(question, collection=collection)
        response_text = format_slack_response(result)
    except Exception as e:
        response_text = f"❌ Error: {str(e)}\n\nMake sure the vector store is synced: `python scripts/sync_vectorstore.py`"

    # Update placeholder
    app.client.chat_update(
        channel=placeholder["channel"],
        ts=placeholder["ts"],
        text=response_text,
    )


@app.event("app_mention")
def handle_mention(event, say):
    """Handle @docbot mentions in channels; supports /help, /collections, and RAG queries."""
    text = event.get("text", "")
    thread_ts = event.get("thread_ts") or event.get("ts")

    # Strip bot mention
    clean = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

    if clean.lower() in ("/help", "help"):
        say(text=HELP_TEXT, thread_ts=thread_ts)
        return

    if clean.lower() == "/collections":
        from pathlib import Path
        docs_dir = Path(__file__).parent.parent / "docs"
        lines = ["*Available doc collections:*"]
        for col in COLLECTIONS:
            count = len(list((docs_dir / col).rglob("*.md"))) if (docs_dir / col).exists() else 0
            lines.append(f"• `{col}` — {count} files")
        say(text="\n".join(lines), thread_ts=thread_ts)
        return

    question, collection = extract_question_and_collection(text)
    if not question:
        say(text="Please ask a question! Type `@docbot /help` for usage.", thread_ts=thread_ts)
        return

    handle_question(question, collection, say, thread_ts)


@app.event("message")
def handle_dm(event, say):
    """Handle direct messages to the bot; ignores channel messages and bot echoes."""
    if event.get("channel_type") != "im":
        return
    if event.get("bot_id"):
        return

    text = event.get("text", "").strip()
    if not text:
        return

    if text.lower() == "/help":
        say(text=HELP_TEXT)
        return

    question, collection = extract_question_and_collection(text)
    handle_question(question, collection, say)


if __name__ == "__main__":
    print("Starting DocBot Slack bot (Socket Mode)...")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
