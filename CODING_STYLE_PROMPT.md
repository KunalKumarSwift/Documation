# Coding Style Prompt

Copy and paste this at the start of any AI session to get consistent code output.

---

## Prompt

Write Python code following these rules exactly:

### Architecture

Use the **Facade + Protocol Provider** pattern when the system has swappable backends (e.g. local vs cloud, free vs paid):

1. **`providers/protocols.py`** — Define `typing.Protocol` interfaces. Use `@runtime_checkable`. One Protocol per concern (embeddings, LLM, vector store, etc.).
2. **`providers/<name>_<concern>.py`** — One file per concrete implementation. One class per file. The class satisfies the Protocol structurally (no explicit inheritance needed).
3. **`facades/<concern>_facade.py`** — Contains **only** the switch logic. Imports the correct provider based on an env var, returns it. Zero implementation logic lives here.
4. **`<domain>_facade.py`** (main facade) — The single public entry point clients use. Coordinates the sub-facades. Clients never import from `providers/` or `facades/` directly.

Example structure:
```
bot/
  providers/
    protocols.py           # Protocol interfaces
    openai_embeddings.py   # OpenAIEmbeddingProvider
    ollama_embeddings.py   # OllamaEmbeddingProvider
  facades/
    embeddings_facade.py   # switch: CI=true → OpenAI, else Ollama
  docbot_facade.py         # main facade — only thing clients call
```

### File size

**Every file must be under 150 lines of Python code**, excluding docstrings and comments. If a file would exceed this, split it. HTML/CSS/JS string constants are data — put them in a `templates/` file and do not count them toward the limit.

### Documentation

Every module, class, and non-trivial function must be documented. Use this format:

**Module docstring** — top of every file:
```python
"""
ModuleName
==========
One sentence explaining what this module does.

Longer explanation of how it works, design decisions, or usage notes.

Environment variables (if any):
    VAR_NAME   Description (default: ``value``).
"""
```

**Class docstring**:
```python
class Foo:
    """One sentence role description.

    Longer explanation if needed.

    Args:
        param: Description.
    """
```

**Method/function docstring** — always include Args, Returns, Raises where applicable:
```python
def bar(self, x: str, y: int = 3) -> list:
    """One sentence summary.

    Args:
        x: Description of x.
        y: Description of y (default: 3).

    Returns:
        Description of what is returned and its type/shape.

    Raises:
        ValueError: When this specific condition is violated.
        KeyError: When required env var is missing.

    Note:
        Any non-obvious constraint, invariant, or gotcha.
    """
```

### Inline comments

Add an inline comment **only** when the WHY is non-obvious — a hidden constraint, a workaround for a specific bug, a subtle invariant. Never explain what the code does (the code does that). One line max.

```python
# Pinecone has no delete-by-metadata API; query with a zero vector to retrieve IDs first.
results = index.query(vector=[0.0] * 1536, filter={"source": source})
```

### Code conventions

- **Python 3.11+**: use `str | None` not `Optional[str]`, use `list[str]` not `List[str]`.
- **Type hints** on every function signature.
- **Lazy imports** inside methods when importing heavy libraries or when avoiding circular imports:
  ```python
  def get_model(self):
      from langchain_openai import OpenAIEmbeddings   # imported lazily
      return OpenAIEmbeddings(model="text-embedding-3-small")
  ```
- **Module-level constants** for config read from env at import time:
  ```python
  _IS_CI = os.getenv("CI", "").lower() == "true"
  _BACKEND = os.getenv("VECTORSTORE_BACKEND", "chroma_local")
  ```
- **`_underscore` prefix** for private helpers and module-level internals.
- **`@dataclass`** for plain value/result objects.
- **`load_dotenv()`** at module level in every file that reads env vars.
- **`sys.path.insert(0, ...)`** at the top of runnable scripts so they work when executed directly.
- **No `Optional`** — use `X | None` instead.
- **No `Union`** — use `X | Y` instead.

### Design principles

- **Single responsibility**: one class per file, one concern per module.
- **Open/closed**: adding a new provider means creating one new file and adding one `elif` to the facade. Nothing else changes.
- **No implementation in facades**: facades import and return; all logic lives in providers.
- **No premature abstractions**: three similar lines is better than a helper. Only extract when there are 3+ real call sites.
- **No defensive error handling** for scenarios that cannot happen. Only validate at system boundaries (user input, external APIs).
- **No comments for obvious code**. No `# increment counter` or `# return result`.
- **No backwards-compatibility shims** unless explicitly required.

### Example: adding a new provider

To add a Cohere embedding backend:

1. Create `providers/cohere_embeddings.py`:
```python
"""
Cohere Embedding Provider
=========================
Implements ``EmbeddingProvider`` using Cohere embed-english-v3.0.
Requires ``COHERE_API_KEY``.
"""

class CohereEmbeddingProvider:
    """Embedding provider backed by Cohere embed-english-v3.0.

    Satisfies the ``EmbeddingProvider`` Protocol structurally.
    """

    def get_model(self):
        """Return a CohereEmbeddings instance.

        Returns:
            ``langchain_cohere.CohereEmbeddings`` configured for embed-english-v3.0.

        Raises:
            cohere.AuthenticationError: If ``COHERE_API_KEY`` is missing or invalid.
        """
        from langchain_cohere import CohereEmbeddings
        return CohereEmbeddings(model="embed-english-v3.0")
```

2. Add one branch to `facades/embeddings_facade.py`:
```python
if _PROVIDER == "cohere":
    from bot.providers.cohere_embeddings import CohereEmbeddingProvider
    return CohereEmbeddingProvider()
```

Nothing else changes.

### Checklist before finishing

- [ ] Every file is under 150 lines of Python code (excluding docstrings/comments)
- [ ] Every public class and function has a docstring with Args/Returns/Raises
- [ ] No implementation logic lives inside a facade file
- [ ] Inline comments explain WHY, not WHAT
- [ ] All imports from heavy libraries are lazy (inside methods)
- [ ] Module-level docstring present in every file
- [ ] Type hints on every function signature
- [ ] `_underscore` prefix on all private names
