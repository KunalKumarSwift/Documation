# Coding Style Prompt

Copy and paste this at the start of any AI session to get consistent code output.

---

## Prompt

Write code following these rules exactly:

### Architecture

Use the **Facade + Protocol Provider** pattern when the system has swappable backends (e.g. local vs cloud, free vs paid):

1. **`providers/protocols`** — Define interface contracts. One interface per concern (embeddings, LLM, vector store, etc.). Use whatever interface/protocol/abstract-type mechanism your language provides.
2. **`providers/<name>_<concern>`** — One file per concrete implementation. One class per file. Each class satisfies the interface for its concern.
3. **`facades/<concern>_facade`** — Contains **only** the switch logic. Reads an environment variable, instantiates and returns the correct provider. Zero implementation logic lives here.
4. **`<domain>_facade`** (main facade) — The single public entry point clients use. Coordinates the sub-facades. Clients never import from `providers/` or `facades/` directly.

Example structure:
```
bot/
  providers/
    protocols          # Interface definitions
    openai_embeddings  # OpenAIEmbeddingProvider
    ollama_embeddings  # OllamaEmbeddingProvider
  facades/
    embeddings_facade  # switch: CI=true → OpenAI, else Ollama
  docbot_facade        # main facade — only thing clients call
```

### File size

**Every file must be under 150 lines of logic**, excluding docstrings and comments. If a file would exceed this, split it. String/HTML/template constants are data — put them in a separate file and do not count them toward the limit.

### Documentation

Every module, class, and non-trivial function must be documented. Use this format, adapted to your language's doc comment style:

**Module/file header** — top of every file:
```
ModuleName
==========
One sentence explaining what this module does.

Longer explanation of how it works, design decisions, or usage notes.

Environment variables (if any):
    VAR_NAME   Description (default: value).
```

**Class doc**:
```
One sentence role description.

Longer explanation if needed.

Args/Params:
    param: Description.
```

**Method/function doc** — always include Params, Returns, Throws where applicable:
```
One sentence summary.

Args/Params:
    x: Description of x.
    y: Description of y (default: value).

Returns:
    Description of what is returned and its type/shape.

Throws/Raises:
    ErrorType: When this specific condition is violated.

Note:
    Any non-obvious constraint, invariant, or gotcha.
```

### Inline comments

Add an inline comment **only** when the WHY is non-obvious — a hidden constraint, a workaround for a specific bug, a subtle invariant. Never explain what the code does (the code does that). One line max.

```
// Pinecone has no delete-by-metadata API; query with a zero vector to retrieve IDs first.
results = index.query(vector=zeroVector, filter: {source: source})
```

### Code conventions

- **Type hints/annotations** on every function/method signature, using whatever type system the language provides.
- **Lazy / deferred imports** inside methods when loading heavy libraries or breaking circular dependencies.
- **Module-level constants** for config read from environment at startup:
  ```
  IS_CI = env("CI", default: false)
  BACKEND = env("VECTORSTORE_BACKEND", default: "chroma_local")
  ```
- **`_underscore` prefix** (or language-equivalent private marker) for private helpers and internal names.
- **Value/result objects** as plain structs or data classes — no behaviour, just data.
- **Load environment variables** at module level in every file that reads env vars.
- **Entry-point scripts** must set up the module path so they run correctly when executed directly.
- **No nullable wrappers** — use native `T | null`, `Option<T>`, `T?`, etc. instead of wrapper types where the language allows it.

### Design principles

- **Single responsibility**: one class per file, one concern per module.
- **Open/closed**: adding a new provider means creating one new file and adding one branch to the facade. Nothing else changes.
- **No implementation in facades**: facades import and return; all logic lives in providers.
- **No premature abstractions**: three similar lines is better than a helper. Only extract when there are 3+ real call sites.
- **No defensive error handling** for scenarios that cannot happen. Only validate at system boundaries (user input, external APIs).
- **No comments for obvious code**. Never write a comment that restates what the identifier already says.
- **No backwards-compatibility shims** unless explicitly required.

### Example: adding a new provider

To add a Cohere embedding backend:

1. Create `providers/cohere_embeddings`:
```
CohereEmbeddingProvider
-----------------------
Implements EmbeddingProvider using Cohere embed-english-v3.0.
Requires COHERE_API_KEY.

class CohereEmbeddingProvider:
    """Satisfies the EmbeddingProvider interface."""

    getModel():
        // lazy-import Cohere SDK
        return CohereEmbeddings(model: "embed-english-v3.0")
```

2. Add one branch to `facades/embeddings_facade`:
```
if PROVIDER == "cohere":
    return new CohereEmbeddingProvider()
```

Nothing else changes.

### Checklist before finishing

- [ ] Every file is under 150 lines of logic (excluding docstrings/comments)
- [ ] Every public class and function has a doc with Params/Returns/Throws
- [ ] No implementation logic lives inside a facade file
- [ ] Inline comments explain WHY, not WHAT
- [ ] Heavy library imports are deferred (inside methods/functions)
- [ ] File/module header docstring present in every file
- [ ] Type annotations on every function signature
- [ ] Private names use `_underscore` (or language-equivalent) prefix
