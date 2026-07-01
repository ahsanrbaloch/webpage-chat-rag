"""Grounded answer generation via a LangChain LCEL chain."""
from __future__ import annotations

from functools import lru_cache

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from . import config

SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions about a single web page. "
    "Answer using ONLY the page excerpts provided. If the answer is not contained "
    "in the excerpts, say you couldn't find it on this page. Be concise and cite "
    "concrete details from the page when relevant. Use the prior conversation only "
    "to resolve references (like 'it' or 'that one'), not as a source of facts."
)

_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("history"),
        ("human", "Page excerpts:\n\n{context}\n\n---\n\nQuestion: {question}"),
    ]
)


def to_messages(history) -> list[BaseMessage]:
    """Convert a list of schema Turns (or dicts) into LangChain chat messages."""
    msgs: list[BaseMessage] = []
    for t in history or []:
        role = getattr(t, "role", None) or (t.get("role") if isinstance(t, dict) else None)
        content = getattr(t, "content", None)
        if content is None and isinstance(t, dict):
            content = t.get("content", "")
        content = content or ""
        if not content:
            continue
        msgs.append(AIMessage(content) if role == "assistant" else HumanMessage(content))
    return msgs


@lru_cache(maxsize=1)
def _chain() -> Runnable:
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")
    llm = ChatOpenAI(
        model=config.CHAT_MODEL,
        temperature=0.2,
        api_key=config.OPENAI_API_KEY,
    )
    return _PROMPT | llm | StrOutputParser()


def answer(chunks: list[str], question: str, history=None) -> str:
    if not chunks:
        return "I couldn't find anything on this page to answer that."
    context = "\n\n---\n\n".join(
        f"[Excerpt {i + 1}]\n{c}" for i, c in enumerate(chunks)
    )
    return _chain().invoke(
        {"context": context, "question": question, "history": to_messages(history)}
    )
