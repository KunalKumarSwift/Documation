#!/usr/bin/env python3
"""
DocBot CLI
==========
Interactive command-line interface for querying DocBot without Slack.
Works entirely offline using Ollama + ChromaDB — no API keys required.

Usage
-----
Interactive mode (REPL)::

    python bot/cli.py

Single-question mode::

    python bot/cli.py "How does Face ID fallback work?"

Force a specific collection::

    python bot/cli.py --auth "What is the session token expiry?"
    python bot/cli.py --runbooks "push notifications not working"

REPL commands
-------------
/help                   Show this help
/sync                   Re-index docs/ to the vector store
/collections            List collections and their file counts
/auth <q>               Query authentication docs
/payments <q>           Query payments docs
/runbooks <q>           Query runbooks
/onboarding <q>         Query onboarding docs
/architecture <q>       Query architecture docs
/quit, /exit            Exit the REPL
"""

import sys
import os

# Add the project root to sys.path so ``bot`` and ``scripts`` are importable
# when this file is run directly (e.g. ``python bot/cli.py``).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


BANNER = """
╔═══════════════════════════════════════════════════╗
║           DocBot — iOS Docs Assistant             ║
║   Ask questions about the iOS platform codebase  ║
╚═══════════════════════════════════════════════════╝
Type your question, or /help for commands. /quit to exit.
"""

HELP_TEXT = """
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

Examples:
  How does Face ID fallback work?
  /auth What is the session token expiry?
  /runbooks push notifications not working
"""

# Valid collection names — must match the docs/ subdirectory names.
COLLECTIONS = ["architecture", "authentication", "payments", "runbooks", "onboarding"]


def format_result(result) -> str:
    """Format a QueryResult for terminal display.

    Renders the answer, a confidence indicator, and the list of source files
    that contributed context to the answer.

    Args:
        result: A ``QueryResult`` dataclass instance from ``query_engine.ask()``.

    Returns:
        A multi-line string ready to print to stdout, with leading/trailing
        blank lines for visual breathing room.
    """
    confidence_icon = {"HIGH": "✓", "MEDIUM": "~", "LOW": "?"}.get(result.confidence, "?")

    lines = [
        "",
        f"  {result.answer}",
        "",
    ]

    if result.source_files:
        lines.append(f"  Sources [{confidence_icon} {result.confidence}]:")
        for src in result.source_files:
            lines.append(f"    • {src}")
    else:
        # No sources means confidence was LOW and the engine returned early.
        lines.append(f"  [{confidence_icon} {result.confidence} confidence]")

    lines.append("")
    return "\n".join(lines)


def do_sync() -> None:
    """Trigger an incremental sync of the docs/ folder to the vector store.

    Calls the same ``sync()`` function used by GitHub Actions, so this
    is the exact same code path that runs in CI.
    """
    print("\nRunning doc sync...\n")
    from scripts.sync_vectorstore import sync
    sync()
    print()


def list_collections() -> None:
    """Print each docs/ subfolder alongside its count of markdown files.

    Walks each expected collection directory with rglob so nested subfolders
    (e.g. docs/auth/flows/*.md) are counted correctly.
    """
    from pathlib import Path
    docs_dir = Path(__file__).parent.parent / "docs"
    print("\nAvailable collections:")
    for col in COLLECTIONS:
        col_dir = docs_dir / col
        if col_dir.exists():
            count = len(list(col_dir.rglob("*.md")))
            print(f"  • {col:<20} ({count} files)")
        else:
            print(f"  • {col:<20} (no files yet)")
    print()


def handle_input(user_input: str) -> None:
    """Parse an optional /collection prefix, then run and print the RAG query.

    The function detects prefixes of the form ``/collectionname question text``
    (e.g. ``/auth what is session expiry?``) and routes accordingly.
    Plain text with no prefix is sent to the auto-router.

    Args:
        user_input: Raw text from the user, with any leading slash already
                    stripped by the REPL (the REPL calls this for ``/auth``,
                    ``/payments``, etc. after removing the leading ``/``).
    """
    user_input = user_input.strip()
    if not user_input:
        return

    forced_collection = None
    question = user_input

    # Check whether the text begins with a known collection name prefix.
    # The prefix format is: "collectionname rest of question"
    # (the leading slash was already stripped by the caller).
    for col in COLLECTIONS:
        if user_input.lower().startswith(f"/{col} "):
            forced_collection = col
            question = user_input[len(col) + 2:].strip()
            break

    if not question:
        print(f"Usage: /{forced_collection} <your question>")
        return

    # Print inline so the cursor stays on the same line while querying.
    print("\nSearching docs...", end="", flush=True)
    try:
        from bot.query_engine import ask
        result = ask(question, collection=forced_collection)
        # Overwrite "Searching docs..." with spaces to clear the line cleanly.
        print("\r" + " " * 20 + "\r", end="")
        print(format_result(result))
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure Ollama is running: ollama serve\n")


def run_interactive() -> None:
    """Run the interactive REPL until the user types /quit or sends EOF.

    Handles special commands (/help, /sync, /collections, /quit) directly.
    All other input — whether plain text or /collection-prefixed — is
    delegated to ``handle_input()``.

    Exits cleanly on Ctrl-C (KeyboardInterrupt) or Ctrl-D (EOFError).
    """
    print(BANNER)
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
            print("Goodbye!")
            break
        elif user_input.lower() == "/help":
            print(HELP_TEXT)
        elif user_input.lower() == "/sync":
            do_sync()
        elif user_input.lower() == "/collections":
            list_collections()
        elif user_input.startswith("/"):
            # Strip the leading "/" and let handle_input detect the collection prefix.
            handle_input(user_input[1:])
        else:
            handle_input(user_input)


def main() -> None:
    """Entry point: single-question mode when args are provided, REPL otherwise.

    Single-question mode accepts an optional ``--<collection>`` flag to force
    a specific collection, e.g.::

        python bot/cli.py --auth "what is the session token TTL?"

    The flag is stripped from the question string before querying.
    Exits with code 1 if the query raises an exception.
    """
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])

        # Detect an optional --collectionname flag anywhere in the argument list.
        collection = None
        for col in COLLECTIONS:
            flag = f"--{col}"
            if flag in sys.argv:
                collection = col
                question = question.replace(flag, "").strip()
                break

        try:
            from bot.query_engine import ask
            result = ask(question, collection=collection)
            print(format_result(result))
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        run_interactive()


if __name__ == "__main__":
    main()
