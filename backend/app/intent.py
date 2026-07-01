"""Hybrid intent router: keyword rules first, LLM classifier only as a fallback.

Resolves a user question to one of four intents that drive how /chat answers:
- GLOBAL_SUMMARY: condense the whole page.
- GLOBAL_COUNT:   count items across the whole page (exact, no compression).
- GLOBAL_LIST:    enumerate items across the whole page (exact, no compression).
- SPECIFIC:       targeted question answered from top-k retrieved chunks.

Default is SPECIFIC, which keeps cost low (cheap retrieval, no LLM router call).
"""
from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from . import config

GLOBAL_SUMMARY = "GLOBAL_SUMMARY"
GLOBAL_COUNT = "GLOBAL_COUNT"
GLOBAL_LIST = "GLOBAL_LIST"
SPECIFIC = "SPECIFIC"
_LABELS = {GLOBAL_SUMMARY, GLOBAL_COUNT, GLOBAL_LIST, SPECIFIC}

# Order matters: count/list are checked before summary so "list all key points"
# routes to LIST rather than SUMMARY.
_COUNT_TRIGGERS = ("how many", "count", "number of", "total of", "how much")
_LIST_TRIGGERS = (
    "list all",
    "show all",
    "extract all",
    "give me all",
    "all items",
    "all headings",
    "all products",
    "all names",
    "all the",
    "every ",
    "each of",
    "enumerate",
)
_SUMMARY_TRIGGERS = (
    "summarize",
    "summary",
    "tl;dr",
    "tldr",
    "overview",
    "main point",
    "key point",
    "takeaway",
    "what is this page about",
    "what is this article about",
    "what's this page about",
    "what's this about",
    "the gist",
    "gist of",
)


def _rule_match(q: str) -> str | None:
    if any(t in q for t in _COUNT_TRIGGERS):
        return GLOBAL_COUNT
    if any(t in q for t in _LIST_TRIGGERS):
        return GLOBAL_LIST
    if any(t in q for t in _SUMMARY_TRIGGERS):
        return GLOBAL_SUMMARY
    return None


_SYSTEM = (
    "You are an intent classifier for questions about a single web page. "
    "Reply with EXACTLY one label and nothing else:\n"
    "GLOBAL_SUMMARY - asks to summarize / give the gist of the whole page\n"
    "GLOBAL_COUNT - asks how many of something there are across the page\n"
    "GLOBAL_LIST - asks to list/enumerate all of something across the page\n"
    "SPECIFIC - a targeted question about part of the page\n"
    "If unsure, answer SPECIFIC."
)


@lru_cache(maxsize=1)
def _classifier() -> ChatOpenAI:
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return ChatOpenAI(
        model=config.CLASSIFIER_MODEL,
        temperature=0,
        max_tokens=4,
        api_key=config.OPENAI_API_KEY,
    )


def _llm_classify(question: str) -> str:
    try:
        resp = _classifier().invoke(
            [("system", _SYSTEM), ("human", question)]
        )
        label = (resp.content or "").strip().upper()
        return label if label in _LABELS else SPECIFIC
    except Exception:
        # Never let classification failure break the request; degrade to SPECIFIC.
        return SPECIFIC


def classify(question: str) -> str:
    """Return one of the four intent labels for the given question."""
    q = question.lower().strip()
    ruled = _rule_match(q)
    if ruled is not None:
        return ruled
    return _llm_classify(question)
