"""
DocBot Slack Bot
================
Listens for ``@docbot`` mentions and DMs via Slack Socket Mode,
then answers using ``DocBotFacade``.

Setup:
1. Create a Slack app at https://api.slack.com/apps
2. Settings → Socket Mode → enable, generate App-Level Token (xapp-...)
3. OAuth → add scopes: app_mentions:read, chat:write, im:history, im:read, im:write
4. Events → subscribe to: app_mention, message.im
5. Install app; copy tokens to .env
6. Run: ``python bot/slack_bot.py``

Response pattern:
    Post a "Searching..." placeholder immediately (satisfies Slack's 3-second
    window), then update it with the real answer once the RAG query completes.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from bot.docbot_facade import DocBotFacade

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")

if not SLACK_BOT_TOKEN or SLACK_BOT_TOKEN == "xoxb-your-bot-token":
    print("ERROR: SLACK_BOT_TOKEN not set. See .env.example")
    sys.exit(1)

app = App(token=SLACK_BOT_TOKEN)
_facade = DocBotFacade()

COLLECTIONS = ["architecture", "authentication", "payments", "runbooks", "onboarding"]

_HELP = """*DocBot* — iOS Platform Documentation Assistant

*Usage:*
• `@docbot <question>` — Ask anything (auto-routes to the right collection)
• `@docbot /auth <question>` — Query authentication docs
• `@docbot /payments <question>` — Query payments docs
• `@docbot /runbooks <question>` — Query runbooks
• `@docbot /onboarding <question>` — Query onboarding docs
• `@docbot /architecture <question>` — Query architecture docs
• `@docbot /help` — Show this help
• `@docbot /collections` — List doc collections"""


def _parse(text: str) -> tuple[str, str | None]:
    """Strip the bot mention and detect an optional /collection prefix.

    Args:
        text: Raw Slack event text containing ``<@USERID>`` mention tokens.

    Returns:
        ``(question, collection)`` — collection is ``None`` when not specified.
    """
    text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
    for col in COLLECTIONS:
        if text.lower().startswith(f"/{col} "):
            return text[len(col) + 2:].strip(), col
    return text, None


def _format(result) -> str:
    """Format a QueryResult as Slack mrkdwn with source citations.

    Args:
        result: ``QueryResult`` from ``DocBotFacade.ask()``.

    Returns:
        mrkdwn-formatted string for the Slack message body.
    """
    emoji = {"HIGH": "✅", "MEDIUM": "⚠️", "LOW": "❓"}.get(result.confidence, "⚠️")
    lines = [result.answer, ""]
    lines += [f"📄 Source: `{s}`" for s in result.source_files]
    lines.append(f"{emoji} Confidence: {result.confidence}")
    lines.append("\n_Was this helpful? React with 👍 or 👎_")
    return "\n".join(lines)


def _answer(question: str, collection: str | None, say, thread_ts=None) -> None:
    """Post a placeholder, run the RAG query, then update the placeholder.

    Slack requires an initial response within 3 seconds. The placeholder
    satisfies that deadline while the full query runs synchronously.

    Args:
        question:   Cleaned question text.
        collection: Collection override or ``None`` for auto-routing.
        say:        Slack Bolt ``say`` helper.
        thread_ts:  Parent message timestamp to keep replies in-thread.
    """
    placeholder = say(text="Searching docs...", thread_ts=thread_ts)
    try:
        text = _format(_facade.ask(question, collection=collection))
    except Exception as e:
        text = f"❌ Error: {e}\n\nSync the vector store first: `python scripts/sync_vectorstore.py`"
    app.client.chat_update(channel=placeholder["channel"], ts=placeholder["ts"], text=text)


@app.event("app_mention")
def handle_mention(event, say) -> None:
    """Handle @docbot mentions; supports /help, /collections, and RAG queries.

    Args:
        event: Slack event payload (text, ts, thread_ts).
        say:   Bolt helper for posting to the current channel.
    """
    text = event.get("text", "")
    thread_ts = event.get("thread_ts") or event.get("ts")
    clean = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

    if clean.lower() in ("/help", "help"):
        say(text=_HELP, thread_ts=thread_ts)
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

    question, collection = _parse(text)
    if not question:
        say(text="Please ask a question! Type `@docbot /help` for usage.", thread_ts=thread_ts)
        return
    _answer(question, collection, say, thread_ts)


@app.event("message")
def handle_dm(event, say) -> None:
    """Handle direct messages; ignores non-DM messages and bot echoes.

    Args:
        event: Slack event payload (channel_type, bot_id, text).
        say:   Bolt helper for posting replies to the DM channel.
    """
    if event.get("channel_type") != "im" or event.get("bot_id"):
        return
    text = event.get("text", "").strip()
    if not text:
        return
    if text.lower() == "/help":
        say(text=_HELP)
        return
    question, collection = _parse(text)
    _answer(question, collection, say)


if __name__ == "__main__":
    print("Starting DocBot Slack bot (Socket Mode)...")
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
