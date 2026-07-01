# Chat With This Page

A Chrome extension that lets you chat with an AI about **whatever webpage you're
currently on**. The page's main text is extracted, embedded, and answered over
using Retrieval-Augmented Generation (RAG).

```
Chrome extension (popup chat)  ──>  FastAPI + LangChain backend  ──>  OpenAI
   extract page text                 split → embed → retrieve            gpt-4o-mini
```

## Tech stack
- **Backend:** FastAPI, LangChain (`RecursiveCharacterTextSplitter`,
  `OpenAIEmbeddings`, in-memory vector store, `ChatOpenAI` LCEL chain).
- **Models:** `text-embedding-3-small` (embeddings) + `gpt-4o-mini` (chat).
- **Extension:** Manifest V3, vanilla JS popup, self-contained content extractor.
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
1. Create a new **Space** → SDK **Docker** → free CPU (e.g. `chat-with-page`).
2. In the Space **Settings → Secrets**, add `OPENAI_API_KEY` and `APP_SHARED_TOKEN`.
3. Push the contents of `backend/` to the Space repo root (so `Dockerfile`,
   `app/`, `requirements.txt`, and the `README.md` card sit at the top level).
4. After it builds, verify `https://<user>-<space>.hf.space/health`.
5. Set that URL as `BACKEND_URL` in `extension/config.js`, add it to
   `host_permissions` in `extension/manifest.json`, and reload the extension.

## API
| Method | Path      | Body                                   | Notes                         |
|--------|-----------|----------------------------------------|-------------------------------|
| GET    | `/health` | —                                      | liveness                      |
| POST   | `/ingest` | `{session_id, url, title, text}`       | splits + embeds + indexes page|
| POST   | `/chat`   | `{session_id, url, question}`          | retrieves + answers           |

All POST routes require header `X-App-Token: <APP_SHARED_TOKEN>`. There's also a
per-IP rate limit and request-size caps for basic abuse protection.

## Security note
This v1 uses **your** OpenAI key on the backend, so every user's chat costs you.
The shared `X-App-Token` is obfuscation-grade (it ships in the client) — it stops
casual abuse, not a determined attacker. Watch your OpenAI usage if you make the
Space public, and consider switching to a "bring your own key" model before a wide
release.
