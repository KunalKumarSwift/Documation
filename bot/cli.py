#!/usr/bin/env python3
"""
DocBot CLI — Interactive command-line interface for testing DocBot.
No Slack or API keys needed (uses Ollama + ChromaDB by default).

Usage:
    python bot/cli.py                     # interactive mode
    python bot/cli.py "your question"     # single question mode

Commands in interactive mode:
    /help                    Show help
    /sync                    Re-sync docs to vector store
    /collections             List available collections
    /auth <question>         Query authentication docs
    /payments <question>     Query payments docs
    /runbooks <question>     Query runbooks
    /onboarding <question>   Query onboarding docs
    /architecture <question> Query architecture docs
    /quit or /exit           Exit
"""

import sys
import os

# Ensure project root is on path
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

COLLECTIONS = ["architecture", "authentication", "payments", "runbooks", "onboarding"]


def format_result(result) -> str:
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
        lines.append(f"  [{confidence_icon} {result.confidence} confidence]")

    lines.append("")
    return "\n".join(lines)


def do_sync():
    print("\nRunning doc sync...\n")
    from scripts.sync_vectorstore import sync
    sync()
    print()


def list_collections():
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


def handle_input(user_input: str):
    user_input = user_input.strip()
    if not user_input:
        return

    # Check for collection-specific commands
    forced_collection = None
    question = user_input

    for col in COLLECTIONS:
        if user_input.lower().startswith(f"/{col} "):
            forced_collection = col
            question = user_input[len(col) + 2:].strip()
            break

    if not question:
        print(f"Usage: /{forced_collection} <your question>")
        return

    print("\nSearching docs...", end="", flush=True)
    try:
        from bot.query_engine import ask
        result = ask(question, collection=forced_collection)
        print("\r" + " " * 20 + "\r", end="")  # clear "Searching..."
        print(format_result(result))
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure Ollama is running: ollama serve\n")


def run_interactive():
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
            handle_input(user_input[1:])  # strip leading /
        else:
            handle_input(user_input)


def main():
    if len(sys.argv) > 1:
        # Single question mode
        question = " ".join(sys.argv[1:])

        # Check for collection flag like --auth
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
