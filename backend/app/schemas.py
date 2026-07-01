"""Pydantic request/response models."""
from typing import Literal

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    url: str = Field(..., min_length=1, max_length=2048)
    title: str = Field(default="", max_length=512)
    text: str = Field(..., min_length=1)


class IngestResponse(BaseModel):
    cached: bool
    chunks: int
    content_hash: str  # lets the extension key its stored conversation state


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(default="", max_length=8000)


class EntityList(BaseModel):
    type: str = ""
    filter: str = ""
    items: list[str] = Field(default_factory=list)


class ChatState(BaseModel):
    """Structured conversation state the extension carries between turns."""

    last_entity_list: EntityList | None = None
    last_answer: str | None = None
    last_route: str | None = None


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    url: str = Field(..., min_length=1, max_length=2048)
    question: str = Field(default="", max_length=4000)
    # "summary" (from the Summarize button) forces the whole-page summary path;
    # "auto" lets the intent router decide from the question text.
    mode: Literal["auto", "summary"] = "auto"
    # Conversation context, owned and sent by the extension (backend stays stateless).
    history: list[Turn] = Field(default_factory=list)
    state: ChatState | None = None


class ChatResponse(BaseModel):
    answer: str
    # Resolved route/intent that produced the answer (GLOBAL_SUMMARY, GLOBAL_COUNT,
    # GLOBAL_LIST, SPECIFIC, REFINE_PRIOR, FOLLOWUP_ON_LIST).
    route: str
    mode: str  # kept for backwards-compat; same value as route
    used_chunks: int
    # Structured items for COUNT / LIST / FOLLOWUP_ON_LIST so the extension can
    # remember them as last_entity_list for the next turn.
    entities: list[str] | None = None
