"""In-memory, LRU + TTL bounded store of per-URL LangChain vector stores.

Keyed by (session_id, url) so different users/pages don't collide. Single
uvicorn worker is assumed so this in-process dict is the source of truth.
"""
from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass

from langchain_core.vectorstores import InMemoryVectorStore

from . import config


@dataclass
class PageEntry:
    store: InMemoryVectorStore  # vector index, for SPECIFIC top-k retrieval
    text: str  # full cleaned page text, for whole-page (non-RAG) answers
    chunks: list[str]  # ordered chunks, for map-reduce / per-chunk extraction
    content_hash: str  # sha256 of the page text; detects changed pages
    ts: float
    summary: str | None = None  # lazily-cached whole-page summary

    @property
    def n_chunks(self) -> int:
        return len(self.chunks)


_store: "OrderedDict[str, PageEntry]" = OrderedDict()


def _key(session_id: str, url: str) -> str:
    return hashlib.sha256(f"{session_id}\n{url}".encode()).hexdigest()


def _evict_expired() -> None:
    now = time.time()
    expired = [k for k, v in _store.items() if now - v.ts > config.PAGE_TTL_SECONDS]
    for k in expired:
        _store.pop(k, None)


def get(session_id: str, url: str) -> PageEntry | None:
    _evict_expired()
    key = _key(session_id, url)
    entry = _store.get(key)
    if entry is not None:
        _store.move_to_end(key)  # mark as recently used
    return entry


def put(
    session_id: str,
    url: str,
    store: InMemoryVectorStore,
    text: str,
    chunks: list[str],
    content_hash: str,
) -> None:
    _evict_expired()
    key = _key(session_id, url)
    _store[key] = PageEntry(
        store=store,
        text=text,
        chunks=chunks,
        content_hash=content_hash,
        ts=time.time(),
    )
    _store.move_to_end(key)
    while len(_store) > config.MAX_PAGES:
        _store.popitem(last=False)  # drop least-recently-used
