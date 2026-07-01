// Minimal service worker. The popup does the heavy lifting; this just ensures a
// stable per-install session id exists so the backend can key page indexes by
// (session, url). A random id is generated once and persisted.
chrome.runtime.onInstalled.addListener(async () => {
  const { session_id } = await chrome.storage.local.get("session_id");
  if (!session_id) {
    await chrome.storage.local.set({ session_id: crypto.randomUUID() });
  }
});
