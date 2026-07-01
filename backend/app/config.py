"""Centralised configuration loaded from environment / .env."""
import os

from dotenv import load_dotenv

# Load .env from the repo root when running locally. On HF Spaces the values
# come from Space "Secrets" injected as real env vars, so load_dotenv is a no-op.
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Shared token the extension must send in the X-App-Token header. Set this as a
# Space secret in production; defaults to a dev value locally.
APP_SHARED_TOKEN = os.getenv("APP_SHARED_TOKEN", "dev-token-change-me")

# Models
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
# Model used by the intent classifier fallback (cheap is fine).
CLASSIFIER_MODEL = os.getenv("CLASSIFIER_MODEL", CHAT_MODEL)

# RAG params. LangChain's RecursiveCharacterTextSplitter is character-based.
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "2000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
TOP_K = int(os.getenv("TOP_K", "6"))

# How many recent conversation turns the backend keeps from the extension-sent history.
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "8"))

# Global (summary/count/list) questions answer over the WHOLE page when it fits in
# the model's context, else use a multi-chunk path (map-reduce / per-chunk extract).
# Fit is decided by a rough token estimate (chars/4) vs this safe budget.
SAFE_CONTEXT_TOKENS = int(os.getenv("SAFE_CONTEXT_TOKENS", "24000"))
# When a page is too big to send whole, group ordered chunks into batches of about
# this many characters per map call. Larger batches mean fewer batch boundaries
# (so fewer items split/double-counted during extraction), while still staying
# well under the model's context window. ~40k chars ≈ ~10k tokens per call.
MAP_BATCH_CHARS = int(os.getenv("MAP_BATCH_CHARS", "40000"))


def fits_in_context(text: str) -> bool:
    """Rough check: does the text fit in one model call? Token ≈ chars/4."""
    return (len(text) // 4) <= SAFE_CONTEXT_TOKENS

# Limits (abuse protection)
MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", "120000"))
MAX_QUESTION_CHARS = int(os.getenv("MAX_QUESTION_CHARS", "2000"))
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "20"))

# Store bounds
MAX_PAGES = int(os.getenv("MAX_PAGES", "50"))
PAGE_TTL_SECONDS = int(os.getenv("PAGE_TTL_SECONDS", "3600"))
