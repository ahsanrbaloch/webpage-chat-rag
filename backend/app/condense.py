"""Rewrite a conversational follow-up into a standalone question.

Only called when there IS prior history; the standalone question then drives intent
classification and retrieval so vague follow-ups ("what about its price?") resolve.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from . import config
from .llm import to_messages

_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Given the conversation so far and a follow-up message, rewrite the "
            "follow-up as a standalone question that can be understood without the "
            "conversation. Resolve references (it, that, those, the second one) to the "
            "concrete entities they refer to. Keep the user's intent. If the message is "
            "already standalone, return it unchanged. Return ONLY the rewritten question.",
        ),
        MessagesPlaceholder("history"),
        ("human", "Follow-up: {question}"),
    ]
)


@lru_cache(maxsize=1)
def _chain() -> Runnable:
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")
    llm = ChatOpenAI(model=config.CHAT_MODEL, temperature=0, api_key=config.OPENAI_API_KEY)
    return _PROMPT | llm | StrOutputParser()


def condense_question(history, question: str) -> str:
    """Return a standalone version of `question` given prior `history` turns."""
    msgs = to_messages(history)
    if not msgs:
        return question
    try:
        out = _chain().invoke({"history": msgs, "question": question}).strip()
        return out or question
    except Exception:
        return question  # degrade gracefully to the literal question
