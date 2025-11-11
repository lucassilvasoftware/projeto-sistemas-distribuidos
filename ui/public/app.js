// ---------- Elementos principais ----------

// Login
const loginOverlay = document.getElementById("login-overlay");
const loginUsernameInput = document.getElementById("login-username");
const loginBtn = document.getElementById("login-btn");

// Sidebar
const usernameInput = document.getElementById("username");
const channelListEl = document.getElementById("channel-list");
const userListEl = document.getElementById("user-list");
const newChannelInput = document.getElementById("new-channel");
const createChannelBtn = document.getElementById("create-channel");
const refreshChannelsBtn = document.getElementById("refresh-channels");
const refreshUsersBtn = document.getElementById("refresh-users");

// Chat
const messagesEl = document.getElementById("messages");
const activeChannelTitle = document.getElementById("active-channel-title");
const messageInput = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");

// Eventos gerais (lado do chat)
const eventLog = document.getElementById("event-log");

// Debug (sub-abas)
const debugTabs = document.querySelectorAll(".debug .tabs .tab");
const debugContents = document.querySelectorAll(".tab-content");

const refreshStatusBtn = document.getElementById("refresh-status");
const statusList = document.getElementById("status-list");
const debugEventsList = document.getElementById("debug-events-list");
const debugPayloadViewer = document.getElementById("debug-payload-viewer");
const debugLogOutput = document.getElementById("debug-log-output");
const msgpackRaw = document.getElementById("msgpack-raw");

// Logs buttons
const startLogsBtn = document.getElementById("start-logs");
const stopLogsBtn = document.getElementById("stop-logs");

// ---------- Estado ----------
let currentUser = null;
let activeChannel = null;
let debugLogSource = null;
let debugMessages = [];

// ---------- Utils ----------
function logEvent(text) {
  if (!eventLog) return;
  const li = document.createElement("li");
  li.textContent = text;
  eventLog.prepend(li);
  const max = 80;
  while (eventLog.children.length > max) {
    eventLog.removeChild(eventLog.lastChild);
  }
}

async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ---------- Sub-abas Debug ----------
debugTabs.forEach((btn) => {
  btn.addEventListener("click", () => {
    const target = btn.dataset.tab;

    debugTabs.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");

    debugContents.forEach((c) => c.classList.remove("active"));
    const pane = document.getElementById(`tab-${target}`);
    if (pane) pane.classList.add("active");
  });
});

// ---------- Login (obrigatório em todo reload) ----------
async function doLogin(username) {
  username = (username || "").trim();
  if (!username) {
    logEvent("Informe um nome de usuário para entrar.");
    return;
  }

  try {
    const reply = await fetchJSON("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user: username }),
    });

    currentUser = username;
    usernameInput.value = username;
    loginOverlay.classList.remove("active");

    logEvent(`Login realizado como '${username}'.`);

    await loadChannels();
    await loadUsers();
    refreshStatus();
  } catch (e) {
    console.error("Erro no login:", e);
    logEvent("Erro ao tentar fazer login.");
  }
}

loginBtn.addEventListener("click", () => {
  doLogin(loginUsernameInput.value);
});

loginUsernameInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") doLogin(loginUsernameInput.value);
});

logEvent("UI carregada. Faça login para começar.");

// ---------- Canais / Usuários ----------
async function loadChannels() {
  try {
    const reply = await fetchJSON("/api/channels");
    const channels = reply?.data?.channels || [];
    channelListEl.innerHTML = "";

    channels.forEach((ch) => {
      const li = document.createElement("li");
      li.textContent = ch;
      li.dataset.channel = ch;
      if (ch === activeChannel) li.classList.add("active");
      li.addEventListener("click", () => selectChannel(ch));
      channelListEl.appendChild(li);
    });
    logEvent("Canais atualizados.");
  } catch (e) {
    logEvent("Erro ao carregar canais.");
  }
}

async function loadUsers() {
  try {
    const reply = await fetchJSON("/api/users");
    const users = reply?.data?.users || [];
    userListEl.innerHTML = "";
    users.forEach((u) => {
      const li = document.createElement("li");
      li.textContent = u;
      userListEl.appendChild(li);
    });
    logEvent("Usuários atualizados.");
  } catch {
    logEvent("Erro ao carregar usuários.");
  }
}

async function createChannel() {
  const ch = newChannelInput.value.trim();
  if (!ch) return;

  try {
    const reply = await fetchJSON("/api/channel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel: ch }),
    });
    if (reply?.data?.status === "sucesso") {
      newChannelInput.value = "";
      await loadChannels();
    }
  } catch {
    logEvent(`Erro ao criar canal #${ch}.`);
  }
}

createChannelBtn.addEventListener("click", createChannel);
newChannelInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") createChannel();
});

refreshChannelsBtn.addEventListener("click", loadChannels);
refreshUsersBtn.addEventListener("click", loadUsers);

// ---------- Seleção de canal + histórico ----------
async function selectChannel(ch) {
  if (!currentUser) {
    logEvent("Faça login antes de entrar em um canal.");
    return;
  }

  activeChannel = ch;
  activeChannelTitle.textContent = `Canal #${ch}`;
  [...channelListEl.children].forEach((n) =>
    n.classList.toggle("active", n.dataset.channel === ch)
  );
  messagesEl.innerHTML = "";
  logEvent(`Entrando em #${ch}...`);

  try {
    const reply = await fetchJSON(
      `/api/history?channel=${encodeURIComponent(ch)}`
    );
    const msgs = reply?.data?.messages || [];
    msgs
      .sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0))
      .forEach((m) => renderMessage(m, ch));
    logEvent(`Histórico de #${ch} carregado (${msgs.length} mensagens).`);
  } catch {
    logEvent(`Erro ao carregar histórico de #${ch}.`);
  }
}

// ---------- Enviar mensagem ----------
async function sendMessage() {
  if (!currentUser || !activeChannel) return;
  const text = messageInput.value.trim();
  if (!text) return;

  try {
    await fetchJSON("/api/publish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user: currentUser,
        channel: activeChannel,
        message: text,
        timestamp: Date.now() / 1000,
      }),
    });
    messageInput.value = "";
  } catch {
    logEvent("Erro ao enviar mensagem.");
  }
}

sendBtn.addEventListener("click", (e) => {
  e.preventDefault();
  sendMessage();
});

messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    sendMessage();
  }
});

// ---------- Renderizar mensagens ----------
function renderMessage(msg, forcedChannel = null) {
  const { topic, user, channel, message, timestamp } = msg;
  const ch = forcedChannel || channel || topic;
  if (!ch || ch !== activeChannel) return;

  const div = document.createElement("div");
  div.classList.add("msg");
  if (user === currentUser) div.classList.add("self");
  if ((user || "").toLowerCase().includes("bot")) div.classList.add("bot");

  const meta = document.createElement("div");
  meta.classList.add("meta");
  meta.innerHTML = `<span class="user">${user}</span> #${ch} <span>${new Date(
    (timestamp || Date.now() / 1000) * 1000
  ).toLocaleTimeString()}</span>`;
  div.append(meta);

  const txt = document.createElement("div");
  txt.classList.add("text");
  txt.textContent = message;
  div.append(txt);

  messagesEl.append(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ---------- SSE: eventos ----------
const es = new EventSource("/api/events");
es.addEventListener("message", (e) => {
  try {
    const data = JSON.parse(e.data);
    pushDebugMessage(data);
    renderMessage(data);
  } catch {}
});

// ---------- Status ----------
async function refreshStatus() {
  try {
    const list = await fetchJSON("/api/status");
    statusList.innerHTML = list
      .map(
        (c) =>
          `<li>${c.status.startsWith("Up") ? "🟢" : "🔴"} <b>${c.name}</b> — ${
            c.status
          }</li>`
      )
      .join("");
  } catch {}
}

// ---------- Debug: eventos + MessagePack ----------
function pushDebugMessage(msg) {
  debugMessages.unshift(msg);
  if (debugMessages.length > 80) debugMessages.pop();

  debugEventsList.innerHTML = debugMessages
    .map(
      (m) =>
        `<li>[${m.channel || m.topic}] <b>${m.user}</b>: ${(
          m.message || ""
        ).slice(0, 60)}</li>`
    )
    .join("");

  const jsonStr = JSON.stringify(msg, null, 2);
  const size = new TextEncoder().encode(jsonStr).length;

  debugPayloadViewer.textContent = `// Payload MessagePack decodificado como JSON\n// ${size} bytes\n\n${jsonStr}`;
  msgpackRaw.textContent = `// Representação bruta do último pacote MessagePack\n\n${jsonStr}`;
}
