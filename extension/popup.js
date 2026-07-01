import { CONFIG } from "./config.js";
import { extractPageContent } from "./content.js";
import { renderMarkdown } from "./markdown.js";

const messagesEl = document.getElementById("messages");
const statusEl = document.getElementById("status");
const dotEl = document.getElementById("status-dot");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("input");
const sendEl = document.getElementById("send");
const summarizeEl = document.getElementById("summarize");

let page = null; // { url, title, text }
let sessionId = null;
let storeKey = null; // chat:{session}:{url}:{contentHash}
let history = []; // [{ role, content }] — content is RAW text (not HTML)
let state = { last_entity_list: null, last_answer: null, last_route: null };

function setStatus(text, state) {
  statusEl.textContent = text;
  dotEl.className = "dot" + (state ? " " + state : "");
}

function setReady(ready) {
  inputEl.disabled = !ready;
  sendEl.disabled = !ready;
  summarizeEl.disabled = !ready;
  if (ready) inputEl.focus();
}

function addMessage(text, role) {
  const empty = messagesEl.querySelector(".empty");
  if (empty) empty.remove();
  const el = document.createElement("div");
  el.className = "msg " + role;
  el.textContent = text;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return el;
}

function showEmpty(text) {
  messagesEl.innerHTML = "";
  const el = document.createElement("div");
  el.className = "empty";
  el.textContent = text;
  messagesEl.appendChild(el);
}

async function api(path, body) {
  const res = await fetch(CONFIG.BACKEND_URL + path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-App-Token": CONFIG.APP_TOKEN,
    },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return data;
}

async function getSessionId() {
  const stored = await chrome.storage.local.get("session_id");
  if (stored.session_id) return stored.session_id;
  const id = crypto.randomUUID();
  await chrome.storage.local.set({ session_id: id });
  return id;
}

// --- conversation persistence (survives closing/reopening the popup) --------
// chrome.storage.session is in-memory, cleared when the browser closes.
async function loadThread() {
  if (!storeKey) return;
  const got = await chrome.storage.session.get(storeKey);
  const saved = got[storeKey];
  if (saved) {
    history = saved.history || [];
    state = saved.state || state;
  }
}

async function saveThread() {
  if (!storeKey) return;
  await chrome.storage.session.set({ [storeKey]: { history, state } });
}

function renderThread() {
  messagesEl.innerHTML = "";
  for (const t of history) {
    if (t.role === "user") {
      addMessage(t.content, "user");
    } else {
      const el = addMessage("", "bot");
      el.innerHTML = renderMarkdown(t.content);
    }
  }
}

async function init() {
  try {
    sessionId = await getSessionId();

    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });
    if (!tab || !tab.id || !/^https?:/.test(tab.url || "")) {
      setStatus("Can't read this page", "error");
      showEmpty("Open the extension on a normal web page (http/https) to chat about it.");
      return;
    }

    setStatus("Reading page…");
    const [{ result } = {}] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractPageContent,
    });

    if (!result || !result.text || result.text.length < 20) {
      setStatus("No readable text", "error");
      showEmpty("Couldn't find readable text on this page.");
      return;
    }
    page = result;

    setStatus("Indexing page…");
    const ingest = await api("/ingest", {
      session_id: sessionId,
      url: page.url,
      title: page.title,
      text: page.text,
    });

    // Key the conversation to this exact page content; a changed page starts fresh.
    storeKey = `chat:${sessionId}:${page.url}:${ingest.content_hash}`;
    await loadThread();

    setStatus(`Ready · ${ingest.chunks} chunks`, "ready");
    if (history.length) {
      renderThread(); // restore the prior conversation for this page
    } else {
      showEmpty(`Ask anything about “${page.title || "this page"}”.`);
    }
    setReady(true);
  } catch (err) {
    setStatus("Backend error", "error");
    showEmpty(
      "Couldn't reach the backend.\n\n" +
        err.message +
        "\n\nIs the server running at " +
        CONFIG.BACKEND_URL +
        " ?"
    );
  }
}

// label = what to show in the user bubble; payload = extra /chat fields (e.g. mode).
async function ask(label, payload = {}) {
  addMessage(label, "user");
  setReady(false);
  const typing = addMessage("Thinking…", "bot");
  typing.classList.add("typing");
  try {
    const data = await api("/chat", {
      session_id: sessionId,
      url: page.url,
      question: "",
      history: history.slice(-CONFIG.MAX_HISTORY_TURNS),
      state,
      ...payload,
    });
    const answer = data.answer || "(no answer)";
    typing.classList.remove("typing");
    // The AI answers in Markdown; render it as formatted HTML (safe: escaped first).
    typing.innerHTML = renderMarkdown(answer);

    // Update conversation state for the next turn, then persist it.
    history.push({ role: "user", content: label });
    history.push({ role: "assistant", content: answer });
    state.last_answer = answer;
    state.last_route = data.route || null;
    if (Array.isArray(data.entities)) {
      state.last_entity_list = { type: "", filter: "", items: data.entities };
    }
    await saveThread();
  } catch (err) {
    typing.remove();
    addMessage(err.message, "error");
  } finally {
    setReady(true);
  }
}

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const q = inputEl.value.trim();
  if (!q) return;
  inputEl.value = "";
  inputEl.style.height = "auto";
  ask(q, { question: q });
});

summarizeEl.addEventListener("click", () => {
  ask("Summarize this page", { mode: "summary" });
});

// Enter to send, Shift+Enter for newline; auto-grow the textarea.
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    formEl.requestSubmit();
  }
});
inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + "px";
});

init();
