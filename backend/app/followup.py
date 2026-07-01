"""Follow-up detection and handling: refine a prior answer, or answer scoped to a
previously listed set of items.

Detection is cheap keyword matching; the actual transforms are small LLM calls.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from . import config

# Cues that ask to reshape the PREVIOUS answer (length/format), not fetch new facts.
_REFINE_CUES = (
    "shorter",
    "longer",
    "simpler",
    "simplify",
    "more concise",
    "concise",
    "in bullets",
    "bullet point",
    "as bullets",
    "as a list",
    "expand",
    "elaborate",
    "rephrase",
    "reword",
    "one sentence",
    "in one line",
    "tl;dr",
    "tldr",
    "make it ",
    "make that ",
    "turn it into",
    "turn that into",
)

# Cues that REFERENCE the previously returned set of items.
_REFERENCE_CUES = (
    "those",
    "these",
    "them",
    "that one",
    "which one",
    "which of",
    "among these",
    "among those",
    "of those",
    "of these",
    "from those",
    "from these",
    "the first one",
    "the second one",
    "the third one",
    "the last one",
    "the second",
    "the third",
)


def is_refinement(q: str) -> bool:
    ql = q.lower()
    return any(c in ql for c in _REFINE_CUES)


def is_reference(q: str) -> bool:
    ql = q.lower()
    return any(c in ql for c in _REFERENCE_CUES)


@lru_cache(maxsize=1)
def _llm() -> ChatOpenAI:
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return ChatOpenAI(model=config.CHAT_MODEL, temperature=0.2, api_key=config.OPENAI_API_KEY)


_REFINE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Reshape the PREVIOUS answer according to the user's instruction (e.g. make it "
            "shorter, use bullet points, simplify, expand). Use ONLY the information already "
            "in the previous answer — do not add new facts. If the instruction asks for "
            "detail that isn't in the previous answer, say it isn't covered there.",
        ),
        ("human", "Previous answer:\n{prev}\n\n---\n\nInstruction: {instruction}"),
    ]
)

_ON_LIST_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "The user is asking a follow-up about a specific set of items they were just "
            "shown. Answer considering ONLY those items. Use the page excerpts for details "
            "about them. If the excerpts don't contain what's needed, say so briefly.",
        ),
        (
            "human",
            "Items:\n{items}\n\nPage excerpts:\n{context}\n\n---\n\nQuestion: {question}",
        ),
    ]
)


def _refine_chain() -> Runnable:
    return _REFINE_PROMPT | _llm() | StrOutputParser()


def _on_list_chain() -> Runnable:
    return _ON_LIST_PROMPT | _llm() | StrOutputParser()


def transform_prior(prev_text: str, instruction: str) -> str:
    if not prev_text:
        return "There's no previous answer to adjust yet."
    return _refine_chain().invoke({"prev": prev_text, "instruction": instruction})


def answer_on_list(items: list[str], question: str, excerpts: list[str]) -> str:
    items_block = "\n".join(f"- {it}" for it in items) or "(none)"
    context = "\n\n---\n\n".join(excerpts) if excerpts else "(no relevant excerpts found)"
    return _on_list_chain().invoke(
        {"items": items_block, "context": context, "question": question}
    )
