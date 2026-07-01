"""Global-question engines that read ORDERED page chunks (never the vector store).

- summarize_page: whole-page summary, single call if it fits else map-reduce.
- extract_items:  per-chunk JSON extraction + case-insensitive dedupe (the shared
                  engine behind exact counting and listing on large pages).
- answer_count / answer_list: format extract_items output as a count / a bulleted list.

These only run for pages too large to send in one call; for pages that fit, main.py
answers COUNT/LIST/SUMMARY with a single whole-page llm.answer call.
"""
from __future__ import annotations

import json
from functools import lru_cache

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from . import config


@lru_cache(maxsize=1)
def _llm() -> ChatOpenAI:
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return ChatOpenAI(model=config.CHAT_MODEL, temperature=0, api_key=config.OPENAI_API_KEY)


def _batch(chunks: list[str], max_chars: int) -> list[str]:
    """Group ordered chunks into batches whose joined length stays under max_chars."""
    batches: list[str] = []
    cur: list[str] = []
    size = 0
    for c in chunks:
        if cur and size + len(c) > max_chars:
            batches.append("\n\n".join(cur))
            cur, size = [], 0
        cur.append(c)
        size += len(c)
    if cur:
        batches.append("\n\n".join(cur))
    return batches


# --- summarization ---------------------------------------------------------
_SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Summarize the page content for a reader who hasn't seen it. Output:\n"
            "- One line: what the page is about.\n"
            "- A short paragraph summary.\n"
            "- 3-6 key points as bullets.\n"
            "Use only the provided content.",
        ),
        ("human", "{content}"),
    ]
)
_REDUCE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are combining several partial summaries of one web page into a single "
            "coherent summary. Output: one line on what the page is about, a short "
            "paragraph, then 3-6 key bullets. Do not lose distinct points.",
        ),
        ("human", "Partial summaries:\n\n{content}"),
    ]
)


def _summary_chain():
    return _SUMMARY_PROMPT | _llm() | StrOutputParser()


def _reduce_chain():
    return _REDUCE_PROMPT | _llm() | StrOutputParser()


def summarize_page(text: str, chunks: list[str]) -> str:
    """Whole-page summary: single call when it fits, else map-reduce over chunks."""
    if config.fits_in_context(text):
        return _summary_chain().invoke({"content": text})

    # map: summarize each batch of ordered chunks
    partials = [
        _summary_chain().invoke({"content": batch})
        for batch in _batch(chunks, config.MAP_BATCH_CHARS)
    ]
    combined = "\n\n---\n\n".join(partials)

    # reduce (recurse once if the combined partials are still too large)
    if not config.fits_in_context(combined):
        partials = [
            _reduce_chain().invoke({"content": batch})
            for batch in _batch(partials, config.MAP_BATCH_CHARS)
        ]
        combined = "\n\n---\n\n".join(partials)
    return _reduce_chain().invoke({"content": combined})


# --- exact extraction (count / list) ---------------------------------------
_EXTRACT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Extract every item from the text that matches the user's request. "
            "Return ONLY a JSON array of short, distinct strings (one per item) and "
            "nothing else. If there are none, return []. Do not invent items.",
        ),
        ("human", "Request: {question}\n\nText:\n{content}"),
    ]
)


def _extract_chain():
    return _EXTRACT_PROMPT | _llm() | StrOutputParser()


def _parse_json_array(raw: str) -> list[str]:
    raw = raw.strip()
    # tolerate code fences or stray prose around the array
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return []
    return [str(x).strip() for x in data if str(x).strip()]


def extract_items(chunks: list[str], question: str) -> list[str]:
    """Extract matching items across all ordered chunks, deduped case-insensitively."""
    seen: set[str] = set()
    items: list[str] = []
    for batch in _batch(chunks, config.MAP_BATCH_CHARS):
        for item in _parse_json_array(
            _extract_chain().invoke({"question": question, "content": batch})
        ):
            key = item.lower()
            if key not in seen:
                seen.add(key)
                items.append(item)
    return items


def format_count(items: list[str]) -> str:
    if not items:
        return "I couldn't find any matching items on this page."
    listing = "\n".join(f"- {it}" for it in items)
    return f"I found {len(items)} on this page:\n\n{listing}"


def format_list(items: list[str]) -> str:
    if not items:
        return "I couldn't find any matching items on this page."
    return "\n".join(f"- {it}" for it in items)
