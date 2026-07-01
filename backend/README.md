---
title: Chat With This Page
emoji: 💬
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Chat With This Page — Backend

FastAPI + LangChain RAG backend for the "Chat With This Page" Chrome extension.

- `GET /health` — liveness check.
- `POST /ingest` — `{session_id, url, title, text}` → splits, embeds, indexes the page.
- `POST /chat` — `{session_id, url, question}` → retrieves relevant chunks and answers.

All POST routes require an `X-App-Token` header matching the `APP_SHARED_TOKEN` secret.

## Required Space secrets
- `OPENAI_API_KEY` — your OpenAI key (pays for embeddings + chat).
- `APP_SHARED_TOKEN` — shared token the extension sends; keep it in sync with the
  extension's `config.js` `APP_TOKEN`.

## Stack
- LangChain `RecursiveCharacterTextSplitter`, `OpenAIEmbeddings`,
  pure-Python `InMemoryVectorStore`, and a `ChatOpenAI` LCEL chain.
- Models: `text-embedding-3-small` + `gpt-4o-mini` (override via `EMBED_MODEL` /
  `CHAT_MODEL` env vars).

Indexes are kept in memory per `(session_id, url)`, LRU- and TTL-bounded — they
reset when the Space restarts, which is fine for ephemeral page chat.
