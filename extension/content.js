// Self-contained page-text extractor. Injected into the active tab via
// chrome.scripting.executeScript({ func: extractPageContent }); its return value
// is handed back to the popup. Must not reference anything outside its own body
// (it runs in the page's context, serialized by source).
export function extractPageContent() {
  const pick = (sel) => document.querySelector(sel);

  // Prefer the main article/content region; fall back to <body>.
  const root =
    pick("article") ||
    pick("main") ||
    pick('[role="main"]') ||
    document.body;

  if (!root) {
    return { url: location.href, title: document.title, text: "" };
  }

  // Work on a clone so we don't mutate the live page.
  const clone = root.cloneNode(true);
  clone
    .querySelectorAll(
      "script, style, noscript, nav, header, footer, aside, form, iframe, svg"
    )
    .forEach((el) => el.remove());

  // innerText respects visibility and collapses whitespace reasonably.
  const text = (clone.innerText || "").replace(/\n{3,}/g, "\n\n").trim();

  return {
    url: location.href,
    title: document.title || "",
    text,
  };
}
