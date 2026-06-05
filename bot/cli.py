#!/usr/bin/env python3
"""
DocBot CLI
==========
Interactive REPL and single-question interface for DocBot.
No Slack account or API keys needed (Ollama + ChromaDB by default).

Usage::

    python bot/cli.py                          # interactive REPL
    python bot/cli.py "your question"          # single question
    python bot/cli.py --auth "session tokens"  # force collection

REPL commands::

    /help, /sync, /collections
    /auth <q>, /payments <q>, /runbooks <q>, /onboarding <q>, /architecture <q>
    /quit, /exit
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from bot.docbot_facade import DocBotFacade

COLLECTIONS = ["architecture", "authentication", "payments", "runbooks", "onboarding"]

_BANNER = """
╔═══════════════════════════════════════════════════╗
║           DocBot — iOS Docs Assistant             ║
║   Ask questions about the iOS platform codebase  ║
╚═══════════════════════════════════════════════════╝
Type your question, or /help for commands. /quit to exit.
"""

_HELP = """
Commands:
  /help                    Show this help
  /sync                    Re-sync docs/ to vector store
  /collections             List available doc collections
  /auth <q>                Force-query authentication docs
  /payments <q>            Force-query payments docs
  /runbooks <q>            Force-query runbooks
  /onboarding <q>          Force-query onboarding docs
  /architecture <q>        Force-query architecture docs
  /quit, /exit             Exit
"""

_facade = DocBotFacade()


def _format(result) -> str:
    """Render a QueryResult for terminal display with confidence icon and sources.

    Args:
        result: ``QueryResult`` from ``DocBotFacade.ask()``.

    Returns:
        Multi-line string ready to print to stdout.
    """
    icon = {"HIGH": "✓", "MEDIUM": "~", "LOW": "?"}.get(result.confidence, "?")
    lines = ["", f"  {result.answer}", ""]
    if result.source_files:
        lines.append(f"  Sources [{icon} {result.confidence}]:")
        for src in result.source_files:
            lines.append(f"    • {src}")
    else:
        lines.append(f"  [{icon} {result.confidence} confidence]")
    lines.append("")
    return "\n".join(lines)


def _do_sync() -> None:
    """Run an incremental sync of docs/ to the vector store."""
    print("\nRunning doc sync...\n")
    from scripts.sync_vectorstore import sync
    sync()
    print()


def _list_collections() -> None:
    """Print each docs/ subfolder with its markdown file count."""
    from pathlib import Path
    docs_dir = Path(__file__).parent.parent / "docs"
    print("\nAvailable collections:")
    for col in COLLECTIONS:
        col_dir = docs_dir / col
        count = len(list(col_dir.rglob("*.md"))) if col_dir.exists() else 0
        status = f"{count} files" if col_dir.exists() else "no files yet"
        print(f"  • {col:<20} ({status})")
    print()


def _handle_query(text: str) -> None:
    """Parse an optional /collection prefix from text, then run and print the query.

    Args:
        text: User input with any leading slash already stripped by the REPL.
    """
    text = text.strip()
    if not text:
        return

    forced_collection, question = None, text
    for col in COLLECTIONS:
        if text.lower().startswith(f"/{col} "):
            forced_collection = col
            question = text[len(col) + 2:].strip()
            break

    if not question:
        print(f"Usage: /{forced_collection} <your question>")
        return

    print("\nSearching docs...", end="", flush=True)
    try:
        result = _facade.ask(question, collection=forced_collection)
        print("\r" + " " * 20 + "\r", end="")
        print(_format(result))
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure Ollama is running: ollama serve\n")


def _repl() -> None:
    """Run the interactive REPL until the user exits or sends EOF."""
    print(_BANNER)
    while True:
        try:
            line = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        if not line:
            continue
        if line.lower() in ("/quit", "/exit", "quit", "exit"):
            print("Goodbye!")
            break
        elif line.lower() == "/help":
            print(_HELP)
        elif line.lower() == "/sync":
            _do_sync()
        elif line.lower() == "/collections":
            _list_collections()
        elif line.startswith("/"):
            _handle_query(line[1:])
        else:
            _handle_query(line)


def main() -> None:
    """Single-question mode when CLI args are given; interactive REPL otherwise.

    Supports ``--<collection>`` flags, e.g. ``--auth``, to force a collection.
    """
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        collection = None
        for col in COLLECTIONS:
            if f"--{col}" in sys.argv:
                collection = col
                question = question.replace(f"--{col}", "").strip()
                break
        try:
            print(_format(_facade.ask(question, collection=collection)))
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        _repl()


if __name__ == "__main__":
    main()
