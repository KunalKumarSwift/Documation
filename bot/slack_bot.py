"""
DocBot Slack Bot
================
Listens for ``@docbot`` mentions in channels and direct messages,
then answers questions by calling the RAG query engine.

Transport: Slack Bolt SDK in Socket Mode — the bot connects outbound
to Slack's servers over a WebSocket, so no public URL or inbound firewall
rules are required. Ideal for local development and private deployments.

Setup
-----
1. Create a Slack app at https://api.slack.com/apps
2. Settings → Socket Mode → enable, generate an App-Level Token (xapp-...)
3. OAuth & Permissions → add Bot Token Scopes:
   ``app_mentions:read``, ``chat:write``, ``im:history``, ``im:read``, ``im:write``
4. Event Subscriptions → subscribe to:
   ``app_mention``, ``message.im``
5. Install the app to your workspace
6. Copy tokens to .env:
   SLACK_BOT_TOKEN=xoxb-...
   SLACK_APP_TOKEN=xapp-...
   SLACK_SIGNING_SECRET=...
7. Run: ``python bot/slack_bot.py``

Interaction model
-----------------
Slack requires an initial response within 3 seconds or it times out and
retries. Because a RAG query can take 5–15 seconds (Ollama inference is
slow on CPU), the bot uses a two-step pattern:

  1. Immediately post a threaded "Searching docs..." placeholder.
  2. Run the full RAG query (blocking the event handler thread).
  3. Update the placeholder in-place with the real answer.

The placeholder satisfies Slack's 3-second window; the update replaces it
so the channel does not show a stale message.
"""

import os
import re
import sys

# Add project root so ``bot`` and ``scripts`` are importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")

# Fail fast at startup rather than surfacing confusing API errors later.
if not SLACK_BOT_TOKEN or SLACK_BOT_TOKEN == "xoxb-your-bot-token":
    print("ERROR: SLACK_BOT_TOKEN not set. See .env.example")
    sys.exit(1)

app = App(token=SLACK_BOT_TOKEN)

# Collection names must match the docs/ subdirectory names exactly.
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
    """Strip the bot mention and detect an optional /collection prefix.

    Slack encodes user and bot mentions as ``<@USERID>`` tokens. This function
    removes those tokens first, then checks if the remaining text starts with
    a ``/collection `` prefix to force a specific search namespace.

    Args:
        text: Raw event text from the Slack API, which may contain
              ``<@U12345>`` mention tokens and a ``/collection`` prefix.

    Returns:
        A tuple of ``(question, collection)`` where:
        - ``question`` is the cleaned question text.
        - ``collection`` is one of the COLLECTIONS strings, or ``None`` if the
          query should be auto-routed.

    Examples:
        >>> extract_question_and_collection("<@U123> /auth session tokens?")
        ('session tokens?', 'authentication')
        >>> extract_question_and_collection("<@U123> how does BFF work?")
        ('how does BFF work?', None)
    """
    # Remove all mention tokens (bot mention, user mentions in threads).
    text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

    # Check for a forced collection prefix like "/auth question text".
    for col in COLLECTIONS:
        if text.lower().startswith(f"/{col} "):
            # Skip "/<col> " (len(col) + 2 chars) to get just the question.
            return text[len(col) + 2:].strip(), col

    return text, None


def format_slack_response(result) -> str:
    """Format a QueryResult as Slack mrkdwn with source citations and a feedback prompt.

    Slack uses its own markdown dialect (mrkdwn) rather than standard Markdown.
    Backtick-quoted text renders as inline code, *bold*, _italic_, etc.

    Args:
        result: A ``QueryResult`` dataclass instance from ``query_engine.ask()``.

    Returns:
        A mrkdwn-formatted string ready to send as a Slack message body.
    """
    confidence_emoji = {"HIGH": "✅", "MEDIUM": "⚠️", "LOW": "❓"}.get(result.confidence, "⚠️")

    lines = [result.answer, ""]

    if result.source_files:
        for src in result.source_files:
            lines.append(f"📄 Source: `{src}`")

    lines.append(f"{confidence_emoji} Confidence: {result.confidence}")
    # Italicised feedback nudge — encourages engineers to react for quality tracking.
    lines.append("\n_Was this helpful? React with 👍 or 👎_")

    return "\n".join(lines)


def handle_question(question: str, collection: str | None, say, thread_ts: str | None = None) -> None:
    """Post a placeholder, run the RAG query, then update the placeholder in-place.

    Slack's 3-second initial response requirement means we cannot wait for the
    full RAG pipeline before posting. The two-step post + ``chat.update`` pattern
    satisfies the window while letting inference run as long as needed.

    Args:
        question:   The extracted question text (no mention tokens or prefixes).
        collection: Collection to search, or None for auto-routing.
        say:        Slack Bolt's ``say`` helper — posts to the current channel.
        thread_ts:  Timestamp of the parent message. When provided, the bot
                    replies in-thread to keep channels tidy.
    """
    # Post the placeholder immediately to satisfy Slack's 3-second SLA.
    placeholder = say(text="Searching docs...", thread_ts=thread_ts)

    try:
        from bot.query_engine import ask
        result = ask(question, collection=collection)
        response_text = format_slack_response(result)
    except Exception as e:
        response_text = (
            f"❌ Error: {str(e)}\n\n"
            "Make sure the vector store is synced: `python scripts/sync_vectorstore.py`"
        )

    # Replace the placeholder with the actual answer using the same channel + ts.
    app.client.chat_update(
        channel=placeholder["channel"],
        ts=placeholder["ts"],
        text=response_text,
    )


@app.event("app_mention")
def handle_mention(event, say) -> None:
    """Handle @docbot mentions in public and private channels.

    Dispatches to the appropriate handler based on the command:
    - ``/help`` → post the help text
    - ``/collections`` → list available collections with file counts
    - Any other text → run the RAG query

    Replies are always threaded to the original message to keep channels clean.

    Args:
        event: Slack event payload dict. Relevant keys:
               ``text`` (raw message text), ``ts`` (message timestamp),
               ``thread_ts`` (parent thread timestamp if already in a thread).
        say:   Slack Bolt helper for posting messages to the current channel.
    """
    text = event.get("text", "")
    # Prefer the existing thread timestamp; fall back to the message's own ts
    # so a new thread is started when the mention is not already in one.
    thread_ts = event.get("thread_ts") or event.get("ts")

    # Strip the bot mention for command matching.
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
def handle_dm(event, say) -> None:
    """Handle direct messages sent to the bot.

    Filters out non-DM channel messages and bot-generated echoes so this
    handler only fires for genuine user messages in a 1:1 conversation.

    Args:
        event: Slack event payload dict. ``channel_type`` is ``"im"`` for DMs.
               ``bot_id`` is present when the message was posted by a bot.
        say:   Slack Bolt helper for posting messages back to the DM channel.
    """
    # The ``message`` event fires for all message subtypes; restrict to DMs only.
    if event.get("channel_type") != "im":
        return
    # Ignore messages the bot itself sent (avoids infinite loops).
    if event.get("bot_id"):
        return

    text = event.get("text", "").strip()
    if not text:
        return

    if text.lower() == "/help":
        say(text=HELP_TEXT)
        return

    question, collection = extract_question_and_collection(text)
    # DMs do not need thread_ts — each DM conversation is already isolated.
    handle_question(question, collection, say)


if __name__ == "__main__":
    print("Starting DocBot Slack bot (Socket Mode)...")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
