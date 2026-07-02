# webpage-chat-rag

A Chrome extension that lets you chat with an AI about **whatever webpage you're
currently on**. The page's main text is extracted, embedded, and answered over using
Retrieval-Augmented Generation (RAG), with intent-aware routing and multi-turn
conversation memory.

Repo: https://github.com/ahsanrbaloch/webpage-chat-rag

```
Chrome extension (popup chat)  ──>  FastAPI + LangChain backend  ──>  OpenAI
   extract page text                 route by intent → answer          gpt-4o-mini
```

## Features
- **Ask anything** about the current page — answered from its actual content, not
  the model's general knowledge.
- **Summarize** the whole page with one click (map-reduce for very long pages).
- **Count / list** questions ("how many…", "list all…") are answered by exact
  extraction across the full page, not just a few retrieved snippets.
- **Follow-ups work**: "which of those is best for X?", "tell me more about the
  second one", "make it shorter" — the extension keeps conversation state and the
  backend resolves references and refinements.
- Answers render as formatted Markdown (bold, bullets, links) in the popup.

## Tech stack
- **Backend:** FastAPI, LangChain (`RecursiveCharacterTextSplitter`,
  `OpenAIEmbeddings`, in-memory vector store, `ChatOpenAI` LCEL chains).
- **Models:** `text-embedding-3-small` (embeddings) + `gpt-4o-mini` (chat).
- **Extension:** Manifest V3, vanilla JS popup, self-contained content extractor,
  a small in-house Markdown renderer.
- **Deploy:** Docker on Hugging Face Spaces.

## Repo layout
- `backend/` — FastAPI app (`app/`), `requirements.txt`, `Dockerfile`, HF Space card.
- `extension/` — the unpacked Chrome extension (load this folder in Chrome).

---

## Run the backend locally
```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
# .env lives at the repo root and is auto-loaded (OPENAI_API_KEY, APP_SHARED_TOKEN)
.venv/bin/uvicorn app.main:app --reload --port 8000
```
Check it: `curl http://127.0.0.1:8000/health` → `{"status":"ok"}`.

> Note: `faiss`/`tiktoken` are intentionally avoided — the backend uses LangChain's
> pure-Python `InMemoryVectorStore`, so it installs cleanly on Python 3.11–3.14.

## Load the extension
1. `chrome://extensions` → enable **Developer mode**.
2. **Load unpacked** → select the `extension/` folder.
3. Make sure `extension/config.js` `BACKEND_URL` points at your backend
   (`http://127.0.0.1:8000` for local) and `APP_TOKEN` matches the backend's
   `APP_SHARED_TOKEN`.
4. Open any article, click the extension icon, wait for **Ready**, and ask away.

## Deploy the backend to Hugging Face Spaces
1. Create a new **Space** at huggingface.co → SDK **Docker** → free CPU
   (e.g. name it `webpage-chat-rag` to match this repo).
2. In the Space **Settings → Secrets**, add `OPENAI_API_KEY` and `APP_SHARED_TOKEN`.
3. Push the contents of `backend/` to the Space repo root (so `Dockerfile`,
   `app/`, `requirements.txt`, and the `README.md` card sit at the top level).
4. After it builds, verify `https://<your-hf-username>-webpage-chat-rag.hf.space/health`.
5. Set that URL as `BACKEND_URL` in `extension/config.js`, add it to
   `host_permissions` in `extension/manifest.json`, and reload the extension.

## API
| Method | Path      | Body                                                                 | Notes                                    |
|--------|-----------|-----------------------------------------------------------------------|-------------------------------------------|
| GET    | `/health` | —                                                                     | liveness                                   |
| POST   | `/ingest` | `{session_id, url, title, text}`                                       | splits + embeds + indexes the page; returns `content_hash` |
| POST   | `/chat`   | `{session_id, url, question, mode, history[], state}`                 | routes by intent, returns `{answer, route, entities?}` |

- `mode`: `"auto"` (default, routes by intent) or `"summary"` (forces the whole-page summary).
- `history`: recent `{role, content}` turns — the extension keeps and sends these.
- `state`: `{last_entity_list, last_answer, last_route}` — used to resolve follow-ups
  like "those", "the second one", or "make it shorter".
- Response `route`: one of `GLOBAL_SUMMARY`, `GLOBAL_COUNT`, `GLOBAL_LIST`, `SPECIFIC`,
  `REFINE_PRIOR`, `FOLLOWUP_ON_LIST`.

All POST routes require header `X-App-Token: <APP_SHARED_TOKEN>`. There's also a
per-IP rate limit and request-size caps for basic abuse protection.

## Security note
This v1 uses **your** OpenAI key on the backend, so every user's chat costs you.
The shared `X-App-Token` is obfuscation-grade (it ships in the client) — it stops
casual abuse, not a determined attacker. Watch your OpenAI usage if you make the
Space public, and consider switching to a "bring your own key" model before a wide
release.
