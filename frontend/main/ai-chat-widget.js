/**
 * VeeraOps Store "Ask AI" assistant widget.
 *
 * Self-contained: injects its own floating button, panel, and styles, and
 * talks to the backend-proxied /api/ai/chat endpoint (see nginx.conf --
 * same-origin, so no CORS setup is needed on this page).
 *
 * Auth: reads the JWT the storefront login flow already stores in
 * localStorage under AI_TOKEN_KEY (set by saveUser() in index.html). If the
 * customer isn't signed in, the assistant still works for product
 * questions, but order questions get a clear "please sign in" answer from
 * the backend/AI -- this file never fakes or assumes an identity.
 */
(function () {
  "use strict";

  const AI_TOKEN_KEY = "googleStoreAuthToken";
  const CHAT_ENDPOINT = "/api/ai/chat";
  const HISTORY_KEY = "googleStoreAiChatHistory";
  const MAX_HISTORY = 20;

  function getToken() {
    try {
      return localStorage.getItem(AI_TOKEN_KEY) || null;
    } catch {
      return null;
    }
  }

  function loadHistory() {
    try {
      return JSON.parse(sessionStorage.getItem(HISTORY_KEY) || "[]");
    } catch {
      return [];
    }
  }

  function saveHistory(history) {
    try {
      sessionStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(-MAX_HISTORY)));
    } catch {
      /* ignore quota errors */
    }
  }

  const styles = `
    .ai-assist-fab {
      position: fixed; right: 22px; bottom: 22px; z-index: 9999;
      width: 58px; height: 58px; border-radius: 50%; border: none; cursor: pointer;
      background: linear-gradient(135deg, var(--brand, #c1121f), var(--brand-dark, #780000));
      color: #fff; font-size: 24px; display: flex; align-items: center; justify-content: center;
      box-shadow: 0 8px 24px rgba(120,0,0,0.35);
      transition: transform .15s ease;
    }
    .ai-assist-fab:hover { transform: scale(1.06); }
    .ai-assist-panel {
      position: fixed; right: 22px; bottom: 92px; z-index: 9999;
      width: 360px; max-width: calc(100vw - 32px); height: 480px; max-height: calc(100vh - 140px);
      background: #fff; border-radius: 16px; box-shadow: 0 16px 48px rgba(0,0,0,0.22);
      display: none; flex-direction: column; overflow: hidden;
      border: 1px solid #e5e7eb; font-family: inherit;
    }
    .ai-assist-panel.open { display: flex; }
    .ai-assist-header {
      background: linear-gradient(135deg, var(--brand, #c1121f), var(--brand-dark, #780000));
      color: #fff; padding: 14px 16px; font-weight: 800; display: flex;
      align-items: center; justify-content: space-between; flex-shrink: 0;
    }
    .ai-assist-header span.title { display:flex; align-items:center; gap:8px; }
    .ai-assist-close { background: none; border: none; color: #fff; font-size: 20px; cursor: pointer; line-height: 1; }
    .ai-assist-messages { flex: 1; overflow-y: auto; padding: 14px; background: #f8f9fb; display: flex; flex-direction: column; gap: 10px; }
    .ai-assist-msg { max-width: 85%; padding: 9px 12px; border-radius: 12px; font-size: 13.5px; line-height: 1.45; white-space: pre-wrap; }
    .ai-assist-msg.user { align-self: flex-end; background: var(--brand, #c1121f); color: #fff; border-bottom-right-radius: 3px; }
    .ai-assist-msg.assistant { align-self: flex-start; background: #fff; color: #111827; border: 1px solid #e5e7eb; border-bottom-left-radius: 3px; }
    .ai-assist-msg.assistant.error { border-color: #f3c1c1; background: #fff5f5; color: #9b1c1c; }
    .ai-assist-typing { align-self: flex-start; font-size: 12.5px; color: #6b7280; padding: 4px 12px; }
    .ai-assist-inputbar { display: flex; gap: 8px; padding: 10px; border-top: 1px solid #e5e7eb; background: #fff; flex-shrink: 0; }
    .ai-assist-inputbar input {
      flex: 1; border: 1px solid #d1d5db; border-radius: 20px; padding: 9px 14px; font-size: 13.5px; outline: none;
    }
    .ai-assist-inputbar input:focus { border-color: var(--brand, #c1121f); }
    .ai-assist-send {
      width: 38px; height: 38px; border-radius: 50%; border: none; cursor: pointer;
      background: var(--brand, #c1121f); color: #fff; font-size: 16px; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
    }
    .ai-assist-send:disabled { opacity: .5; cursor: not-allowed; }
    .ai-assist-hint { padding: 6px 14px 10px; font-size: 11px; color: #9ca3af; text-align: center; }
    @media (max-width: 480px) {
      .ai-assist-panel { right: 12px; left: 12px; width: auto; bottom: 84px; }
      .ai-assist-fab { right: 16px; bottom: 16px; }
    }
  `;

  function injectStyles() {
    const el = document.createElement("style");
    el.textContent = styles;
    document.head.appendChild(el);
  }

  function el(tag, className, html) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (html !== undefined) node.innerHTML = html;
    return node;
  }

  function buildWidget() {
    const fab = el("button", "ai-assist-fab", "🤖");
    fab.setAttribute("aria-label", "Ask AI");
    fab.type = "button";

    const panel = el("div", "ai-assist-panel");
    const header = el(
      "div",
      "ai-assist-header",
      `<span class="title">🤖 Ask AI</span>`
    );
    const closeBtn = el("button", "ai-assist-close", "&times;");
    closeBtn.type = "button";
    closeBtn.setAttribute("aria-label", "Close");
    header.appendChild(closeBtn);

    const messages = el("div", "ai-assist-messages");
    const hint = el(
      "div",
      "ai-assist-hint",
      "Ask about orders, tracking, products, or prices."
    );

    const inputBar = el("div", "ai-assist-inputbar");
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Ask anything...";
    input.maxLength = 2000;
    const sendBtn = el("button", "ai-assist-send", "&#10148;");
    sendBtn.type = "button";
    inputBar.appendChild(input);
    inputBar.appendChild(sendBtn);

    panel.appendChild(header);
    panel.appendChild(messages);
    panel.appendChild(hint);
    panel.appendChild(inputBar);

    document.body.appendChild(fab);
    document.body.appendChild(panel);

    return { fab, panel, closeBtn, messages, input, sendBtn };
  }

  function renderMessage(container, role, text, isError) {
    const msg = el(
      "div",
      `ai-assist-msg ${role}${isError ? " error" : ""}`,
      escapeHtml(text)
    );
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  async function sendMessage(ui, text) {
    renderMessage(ui.messages, "user", text, false);
    const history = loadHistory();
    history.push({ role: "user", text });
    saveHistory(history);

    const typing = el("div", "ai-assist-typing", "Ask AI is typing...");
    ui.messages.appendChild(typing);
    ui.messages.scrollTop = ui.messages.scrollHeight;
    ui.sendBtn.disabled = true;
    ui.input.disabled = true;

    try {
      const headers = { "Content-Type": "application/json" };
      const token = getToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(CHAT_ENDPOINT, {
        method: "POST",
        headers,
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json().catch(() => ({}));
      typing.remove();

      if (!res.ok || data.success === false) {
        const msg = (data && data.message) || "The assistant is temporarily unavailable. Please try again.";
        renderMessage(ui.messages, "assistant", msg, true);
        return;
      }
      renderMessage(ui.messages, "assistant", data.message || "...", false);
      const h = loadHistory();
      h.push({ role: "assistant", text: data.message });
      saveHistory(h);
    } catch (err) {
      typing.remove();
      renderMessage(ui.messages, "assistant", "Network error. Please check your connection and try again.", true);
    } finally {
      ui.sendBtn.disabled = false;
      ui.input.disabled = false;
      ui.input.focus();
    }
  }

  function init() {
    injectStyles();
    const ui = buildWidget();

    // Replay this tab's chat history (not persisted across browser
    // restarts on purpose -- it's a lightweight session convenience, not a
    // record of truth; the backend/MCP data is always the source of truth).
    loadHistory().forEach((m) => renderMessage(ui.messages, m.role, m.text, false));

    ui.fab.addEventListener("click", () => {
      ui.panel.classList.toggle("open");
      if (ui.panel.classList.contains("open")) ui.input.focus();
    });
    ui.closeBtn.addEventListener("click", () => ui.panel.classList.remove("open"));

    function handleSend() {
      const text = ui.input.value.trim();
      if (!text) return;
      ui.input.value = "";
      sendMessage(ui, text);
    }
    ui.sendBtn.addEventListener("click", handleSend);
    ui.input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") handleSend();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
