/* ===================================================================
   DocuFlex — Chatbot & Mobile Navigation Controller
   =================================================================== */

document.addEventListener("DOMContentLoaded", () => {
  initMobileDrawer();
  initChatWidget();
});

// 1. Mobile Drawer Navigation Controller (iOS & Android)
function initMobileDrawer() {
  const openBtn = document.getElementById("mobile-menu-btn");
  const closeBtn = document.getElementById("mobile-drawer-close-btn");
  const overlay = document.getElementById("mobile-drawer-overlay");
  const drawer = document.getElementById("mobile-drawer");

  function openDrawer() {
    if (overlay && drawer) {
      overlay.classList.add("active");
      drawer.classList.add("active");
      document.body.style.overflow = "hidden"; // Prevent background scroll
    }
  }

  function closeDrawer() {
    if (overlay && drawer) {
      overlay.classList.remove("active");
      drawer.classList.remove("active");
      document.body.style.overflow = "";
    }
  }

  if (openBtn) openBtn.addEventListener("click", openDrawer);
  if (closeBtn) closeBtn.addEventListener("click", closeDrawer);
  if (overlay) overlay.addEventListener("click", closeDrawer);

  // Close drawer if a navigation link is clicked
  document.querySelectorAll(".mobile-nav-link").forEach(link => {
    link.addEventListener("click", closeDrawer);
  });
}

// 2. Chatbot Widget Controller
function initChatWidget() {
  const toggleBtn = document.getElementById("chat-toggle-btn");
  const closeBtn = document.getElementById("chat-close-btn");
  const chatWindow = document.getElementById("chat-window");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");

  function toggleChat() {
    if (!chatWindow) return;
    const isActive = chatWindow.classList.contains("active");
    if (isActive) {
      chatWindow.classList.remove("active");
    } else {
      chatWindow.classList.add("active");
      setTimeout(() => chatInput?.focus(), 150);
      scrollChatToBottom();
    }
  }

  if (toggleBtn) toggleBtn.addEventListener("click", toggleChat);
  if (closeBtn) closeBtn.addEventListener("click", () => chatWindow.classList.remove("active"));

  if (chatForm) {
    chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const text = (chatInput?.value || "").trim();
      if (!text) return;
      chatInput.value = "";
      sendChatMessage(text);
    });
  }
}

// 3. Send and Receive Chat Messages
async function sendChatMessage(userText) {
  const messagesContainer = document.getElementById("chat-messages");
  if (!messagesContainer) return;

  // Append User Bubble
  const userBubble = document.createElement("div");
  userBubble.className = "chat-bubble user";
  userBubble.textContent = userText;
  messagesContainer.appendChild(userBubble);
  scrollChatToBottom();

  // Append Typing Indicator
  const typingBubble = document.createElement("div");
  typingBubble.className = "chat-bubble assistant";
  typingBubble.id = "chat-typing-indicator";
  typingBubble.innerHTML = `<em>Thinking...</em>`;
  messagesContainer.appendChild(typingBubble);
  scrollChatToBottom();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userText })
    });

    const data = await res.json();
    typingBubble.remove();

    const assistantBubble = document.createElement("div");
    assistantBubble.className = "chat-bubble assistant";
    assistantBubble.innerHTML = formatMarkdown(data.reply || "Sorry, I could not process your query.");
    messagesContainer.appendChild(assistantBubble);
    scrollChatToBottom();
  } catch (err) {
    typingBubble.remove();
    const errorBubble = document.createElement("div");
    errorBubble.className = "chat-bubble assistant";
    errorBubble.innerHTML = `<span style="color:var(--accent-rose);">Error connecting to assistant: ${err.message}</span>`;
    messagesContainer.appendChild(errorBubble);
    scrollChatToBottom();
  }
}

// Trigger query from suggestion chips
function askChatbot(promptText) {
  const chatWindow = document.getElementById("chat-window");
  if (chatWindow && !chatWindow.classList.contains("active")) {
    chatWindow.classList.add("active");
  }
  sendChatMessage(promptText);
}

// 4. Lightweight Markdown Formatter
function formatMarkdown(text) {
  let html = text
    // Escaping
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    // Headers
    .replace(/^### (.*$)/gim, '<h4 style="font-size:1rem;font-weight:700;margin:10px 0 6px 0;color:var(--text-main);">$1</h4>')
    .replace(/^## (.*$)/gim, '<h3 style="font-size:1.1rem;font-weight:800;margin:12px 0 8px 0;color:var(--text-main);">$1</h3>')
    // Bold
    .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.*?)\*/gim, '<em>$1</em>')
    // Blockquotes
    .replace(/^\> (.*$)/gim, '<blockquote style="border-left:3px solid var(--primary);padding-left:10px;margin:8px 0;color:var(--text-muted);font-size:0.84rem;">$1</blockquote>')
    // Inline code
    .replace(/\`(.*?)\`/gim, '<code>$1</code>')
    // Links [text](url)
    .replace(/\[([^\]]+)\]\(([^)]+)\)/gim, '<a href="$2">$1</a>')
    // Unordered lists
    .replace(/^\- (.*$)/gim, '<li style="margin-left:16px;">$1</li>')
    // Line breaks
    .replace(/\n\n/gim, '<div style="height:8px;"></div>')
    .replace(/\n/gim, '<br>');

  return html;
}

function scrollChatToBottom() {
  const messagesContainer = document.getElementById("chat-messages");
  if (messagesContainer) {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }
}
