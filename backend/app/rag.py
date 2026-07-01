"""RAG primitives built on LangChain.

Uses RecursiveCharacterTextSplitter for chunking, OpenAIEmbeddings for vectors,
and the pure-Python InMemoryVectorStore (numpy cosine, no native faiss dep) as a
per-page index. Per-page chunk counts are small, so in-memory search is instant.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from . import config


@lru_cache(maxsize=1)
def _embeddings() -> OpenAIEmbeddings:
    """Lazily build the embeddings client so import never fails without a key."""
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAIEmbeddings(model=config.EMBED_MODEL, api_key=config.OPENAI_API_KEY)


@lru_cache(maxsize=1)
def _splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )


def split(text: str) -> list[str]:
    """Split raw page text into overlapping chunks."""
    return [c for c in _splitter().split_text(text) if c.strip()]


def build_store(chunks: list[str]) -> InMemoryVectorStore:
    """Embed chunks and return an in-memory vector store for this page."""
    return InMemoryVectorStore.from_texts(chunks, embedding=_embeddings())


def retrieve(store: InMemoryVectorStore, question: str, k: int) -> list[str]:
    """Return the top-k chunk texts most relevant to the question."""
    docs = store.similarity_search(question, k=k)
    return [d.page_content for d in docs]
