"""FastAPI app: routes, CORS, shared-token auth, simple rate limiting."""
from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from . import condense, config, followup, intent, llm, rag, store, summarize
from .schemas import (
    ChatRequest,
    ChatResponse,
    IngestRequest,
    IngestResponse,
)

app = FastAPI(title="Chat With This Page", version="1.0.0")

# Extensions call from a chrome-extension:// origin. Allowing all origins is fine
# because the real gate is the shared token + rate limit, not the browser origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- simple in-memory per-client rate limiter ------------------------------
_hits: dict[str, deque] = defaultdict(deque)


def _client_id(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request) -> None:
    now = time.time()
    dq = _hits[_client_id(request)]
    while dq and now - dq[0] > 60:
        dq.popleft()
    if len(dq) >= config.RATE_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again shortly.")
    dq.append(now)


def require_token(x_app_token: str = Header(default="")) -> None:
    if x_app_token != config.APP_SHARED_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing app token.")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
def ingest(
    body: IngestRequest,
    request: Request,
    _auth: None = Depends(require_token),
    _rl: None = Depends(rate_limit),
) -> IngestResponse:
    if len(body.text) > config.MAX_TEXT_CHARS:
        body.text = body.text[: config.MAX_TEXT_CHARS]

    content_hash = hashlib.sha256(body.text.encode()).hexdigest()

    # Reuse the existing index only if the page content is unchanged; a page that
    # changed under the same URL gets re-indexed (and its cached summary dropped).
    existing = store.get(body.session_id, body.url)
    if existing is not None and existing.content_hash == content_hash:
        return IngestResponse(
            cached=True, chunks=existing.n_chunks, content_hash=content_hash
        )

    chunks = rag.split(body.text)
    if not chunks:
        raise HTTPException(status_code=400, detail="No usable text found on the page.")
    vector_store = rag.build_store(chunks)
    store.put(body.session_id, body.url, vector_store, body.text, chunks, content_hash)
    return IngestResponse(cached=False, chunks=len(chunks), content_hash=content_hash)


@app.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    request: Request,
    _auth: None = Depends(require_token),
    _rl: None = Depends(rate_limit),
) -> ChatResponse:
    if len(body.question) > config.MAX_QUESTION_CHARS:
        raise HTTPException(status_code=400, detail="Question is too long.")

    entry = store.get(body.session_id, body.url)
    if entry is None:
        raise HTTPException(
            status_code=409,
            detail="This page hasn't been ingested yet. Call /ingest first.",
        )

    history = body.history[-config.MAX_HISTORY_TURNS :]
    state = body.state
    fits = config.fits_in_context(entry.text)
    entities: list[str] | None = None

    # The Summarize button always forces the cached canonical summary.
    if body.mode == "summary":
        if entry.summary is None:
            entry.summary = summarize.summarize_page(entry.text, entry.chunks)
        return _respond(entry.summary, intent.GLOBAL_SUMMARY, entry.n_chunks)

    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question is required.")
    q = body.question

    # 1) Refinement of the previous answer (shorter/bullets/expand …) — transform the
    #    prior answer text, no page access.
    if history and state and state.last_answer and followup.is_refinement(q):
        answer_text = followup.transform_prior(state.last_answer, q)
        return _respond(answer_text, "REFINE_PRIOR", 0)

    # 2) Follow-up referencing the previously listed items ("which of those …").
    if (
        history
        and state
        and state.last_entity_list
        and state.last_entity_list.items
        and followup.is_reference(q)
    ):
        standalone = condense.condense_question(history, q)
        excerpts = rag.retrieve(entry.store, standalone, config.TOP_K)
        items = state.last_entity_list.items
        answer_text = followup.answer_on_list(items, q, excerpts)
        return _respond(answer_text, "FOLLOWUP_ON_LIST", len(excerpts), entities=items)

    # 3) Normal path — condense a follow-up to standalone, then route by intent.
    standalone = condense.condense_question(history, q) if history else q
    resolved = intent.classify(standalone)

    if resolved == intent.GLOBAL_SUMMARY:
        if entry.summary is None:
            entry.summary = summarize.summarize_page(entry.text, entry.chunks)
        answer_text = entry.summary
        used = entry.n_chunks
    elif resolved in (intent.GLOBAL_COUNT, intent.GLOBAL_LIST):
        source = [entry.text] if fits else entry.chunks
        entities = summarize.extract_items(source, standalone)
        answer_text = (
            summarize.format_count(entities)
            if resolved == intent.GLOBAL_COUNT
            else summarize.format_list(entities)
        )
        used = entry.n_chunks
    else:  # SPECIFIC — cheap top-k retrieval
        excerpts = rag.retrieve(entry.store, standalone, config.TOP_K)
        answer_text = llm.answer(excerpts, standalone, history=history)
        used = len(excerpts)

    return _respond(answer_text, resolved, used, entities=entities)


def _respond(
    answer: str, route: str, used: int, entities: list[str] | None = None
) -> ChatResponse:
    return ChatResponse(
        answer=answer, route=route, mode=route, used_chunks=used, entities=entities
    )
