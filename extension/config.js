// Central config for the extension. Swap BACKEND_URL between local dev and the
// deployed Hugging Face Space here, and keep APP_TOKEN in sync with the
// backend's APP_SHARED_TOKEN secret.
//
// NOTE: shipping a shared token in a client is obfuscation-grade only; it stops
// casual abuse of the public endpoint, not a determined attacker. Fine for a
// free v1. For local dev the backend default token is "dev-token-change-me".
export const CONFIG = {
  // Local dev:
  BACKEND_URL: "http://127.0.0.1:8000",
  // Deployed (uncomment and set after creating the HF Space):
  // BACKEND_URL: "https://ahsanrbaloch-chat-with-page.hf.space",
  APP_TOKEN: "dev-token-change-me",
  // How many recent turns of conversation to send with each request.
  MAX_HISTORY_TURNS: 8,
};
