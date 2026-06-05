"""
providers
=========
Concrete implementations of the DocBot provider protocols.

Each module contains exactly one implementation class:

    openai_embeddings  → OpenAIEmbeddingProvider   (EmbeddingProvider)
    ollama_embeddings  → OllamaEmbeddingProvider   (EmbeddingProvider)
    openai_llm         → OpenAILLMProvider          (LLMProvider)
    ollama_llm         → OllamaLLMProvider          (LLMProvider)
    chroma_store       → ChromaStoreProvider        (StoreProvider)
    pinecone_store     → PineconeStoreProvider      (StoreProvider)

Import the Protocol interfaces from ``protocols``:

    from bot.providers.protocols import EmbeddingProvider, LLMProvider, StoreProvider
"""
