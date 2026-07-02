---
title: webpage-chat-rag
emoji: 💬
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# webpage-chat-rag — Backend

FastAPI + LangChain RAG backend for the **webpage-chat-rag** Chrome extension
(source: https://github.com/ahsanrbaloch/webpage-chat-rag). Lets users chat with an
AI about the content of whatever webpage they're on.

- `GET /health` — liveness check.
- `POST /ingest` — `{session_id, url, title, text}` → splits, embeds, indexes the
  page. Returns `{cached, chunks, content_hash}`.
- `POST /chat` — `{session_id, url, question, mode, history[], state}` → routes the
  question by intent and answers. Returns `{answer, route, mode, used_chunks, entities?}`.

All POST routes require an `X-App-Token` header matching the `APP_SHARED_TOKEN` secret.

## Intent routing
- **GLOBAL_SUMMARY** — whole-page summary (single call if it fits in context, else
  map-reduce over ordered chunks). Triggered by keywords or the extension's
  "Summarize this page" button (`mode: "summary"`).
- **GLOBAL_COUNT** / **GLOBAL_LIST** — exact extraction across the whole page
  ("how many…", "list all…"), not just a handful of retrieved chunks.
- **SPECIFIC** — cheap top-k retrieval for targeted questions.
- **REFINE_PRIOR** — "make it shorter/bullets/expand" reshapes the previous answer.
- **FOLLOWUP_ON_LIST** — "which of those…", "the second one" resolves against the
  previously listed items, using `state.last_entity_list`.

Intent is resolved by a hybrid router: keyword rules first, a cheap LLM classifier
fallback only when rules don't match (default `SPECIFIC` to keep cost low).

## Required Space secrets
- `OPENAI_API_KEY` — your OpenAI key (pays for embeddings + chat).
- `APP_SHARED_TOKEN` — shared token the extension sends; keep it in sync with the
  extension's `config.js` `APP_TOKEN`.

## Stack
- LangChain `RecursiveCharacterTextSplitter`, `OpenAIEmbeddings`,
  pure-Python `InMemoryVectorStore`, and `ChatOpenAI` LCEL chains.
- Models: `text-embedding-3-small` + `gpt-4o-mini` (override via `EMBED_MODEL` /
  `CHAT_MODEL` env vars).

Indexes are kept in memory per `(session_id, url)`, content-hash checked, LRU- and
TTL-bounded — they reset when the Space restarts, which is fine for ephemeral page
chat. Conversation history/state is **not** stored server-side; the extension holds
it (in `chrome.storage.session`) and sends it with each request.
