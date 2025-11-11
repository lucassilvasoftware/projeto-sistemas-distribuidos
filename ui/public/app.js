const usernameInput = document.getElementById("username");
const channelList = document.getElementById("channel-list");
const userList = document.getElementById("user-list");
const newChannelInput = document.getElementById("new-channel");
const createChannelBtn = document.getElementById("create-channel");
const refreshChannelsBtn = document.getElementById("refresh-channels");
const refreshUsersBtn = document.getElementById("refresh-users");
const messagesEl = document.getElementById("messages");
const activeChannelTitle = document.getElementById("active-channel-title");
const messageInput = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const eventLog = document.getElementById("event-log");

const loginOverlay = document.getElementById("login-overlay");
const loginUsernameInput = document.getElementById("login-username");
const loginBtn = document.getElementById("login-btn");

let activeChannel = null;
let currentUser = null;

// -------- utils --------
function logEvent(text) {
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

// -------- login (sempre por overlay, sem persistência) --------
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

    const status = reply?.data?.status || "sucesso";

    currentUser = username;
    usernameInput.value = username;
    loginOverlay.style.display = "none";

    if (status === "sucesso") {
      logEvent(`Login realizado como '${username}'.`);
    } else {
      // ex: usuário já cadastrado -> ok pra entrar também
      logEvent(`Login em '${username}' (usuário já existia).`);
    }

    await loadChannels();
    await loadUsers();
  } catch (e) {
    console.error("Erro no login:", e);
    logEvent("Erro ao tentar fazer login.");
  }
}

loginBtn.addEventListener("click", () => {
  doLogin(loginUsernameInput.value);
});

loginUsernameInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    doLogin(loginUsernameInput.value);
  }
});

// Não há auto-login: toda atualização exige login manual
logEvent("UI carregada. Faça login para começar.");

// -------- canais / usuários --------
async function loadChannels() {
  try {
    const reply = await fetchJSON("/api/channels");
    const channels = reply?.data?.channels || [];
    channelList.innerHTML = "";

    channels.forEach((ch) => {
      const li = document.createElement("li");
      li.textContent = ch;
      li.dataset.channel = ch;
      if (ch === activeChannel) li.classList.add("active");
      li.addEventListener("click", () => selectChannel(ch));
      channelList.appendChild(li);
    });

    logEvent("Canais atualizados.");
  } catch (e) {
    logEvent("Erro ao carregar canais.");
    console.error(e);
  }
}

async function loadUsers() {
  try {
    const reply = await fetchJSON("/api/users");
    const users = reply?.data?.users || [];
    userList.innerHTML = "";
    users.forEach((u) => {
      const li = document.createElement("li");
      li.textContent = u;
      userList.appendChild(li);
    });
    logEvent("Usuários atualizados.");
  } catch (e) {
    logEvent("Erro ao carregar usuários.");
    console.error(e);
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
      logEvent(`Canal #${ch} criado.`);
      newChannelInput.value = "";
      await loadChannels();
    } else {
      logEvent(`Falha ao criar canal #${ch}.`);
      console.warn(reply);
    }
  } catch (e) {
    logEvent(`Erro ao criar canal #${ch}.`);
  }
}

// -------- histórico ao trocar de canal --------
async function selectChannel(ch) {
  if (!currentUser) {
    logEvent("Faça login antes de entrar em um canal.");
    return;
  }

  activeChannel = ch;
  activeChannelTitle.textContent = `Canal #${ch}`;
  [...channelList.children].forEach((n) =>
    n.classList.toggle("active", n.dataset.channel === ch)
  );

  messagesEl.innerHTML = "";
  logEvent(`Entrando em #${ch}, carregando histórico...`);

  try {
    const reply = await fetchJSON(
      `/api/history?channel=${encodeURIComponent(ch)}`
    );
    const msgs = reply?.data?.messages || [];

    msgs.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));
    msgs.forEach((m) => renderMessage(m, ch, true));

    logEvent(`Histórico de #${ch} carregado (${msgs.length} mensagens).`);
  } catch (e) {
    logEvent(`Erro ao carregar histórico de #${ch}.`);
    console.error(e);
  }
}

// -------- envio de mensagem --------
async function sendMessage() {
  if (!currentUser) {
    logEvent("Faça login antes de enviar mensagens.");
    return;
  }
  if (!activeChannel) {
    logEvent("Selecione um canal antes de enviar.");
    return;
  }

  const text = messageInput.value.trim();
  if (!text) return;

  try {
    const reply = await fetchJSON("/api/publish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user: currentUser,
        channel: activeChannel,
        message: text,
      }),
    });
    if (reply?.data?.status === "sucesso") {
      messageInput.value = "";
    } else {
      logEvent("Falha ao enviar mensagem.");
      console.warn(reply);
    }
  } catch (e) {
    logEvent("Erro ao enviar mensagem.");
    console.error(e);
  }
}

// -------- renderização de mensagens --------
function renderMessage(msg, forcedChannel = null) {
  const { topic, user, channel, message, timestamp } = msg;
  const ch = forcedChannel || channel || topic;
  if (!ch) return;

  // só mostra mensagens do canal ativo
  if (!activeChannel || ch !== activeChannel) return;

  const div = document.createElement("div");
  div.classList.add("msg");

  if (currentUser && user === currentUser) {
    div.classList.add("self");
  }
  if (
    String(user || "")
      .toLowerCase()
      .includes("bot")
  ) {
    div.classList.add("bot");
  }

  const meta = document.createElement("div");
  meta.classList.add("meta");

  const u = document.createElement("span");
  u.classList.add("user");
  u.textContent = user || "???";

  const c = document.createElement("span");
  c.textContent = `#${ch}`;

  const t = document.createElement("span");
  const ts = timestamp
    ? new Date(
        String(timestamp).length > 11 ? timestamp : timestamp * 1000
      ).toLocaleTimeString()
    : new Date().toLocaleTimeString();
  t.textContent = ts;

  meta.appendChild(u);
  meta.appendChild(c);
  meta.appendChild(t);

  const text = document.createElement("div");
  text.classList.add("text");
  text.textContent = message;

  div.appendChild(meta);
  div.appendChild(text);
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// -------- botões e eventos --------
createChannelBtn.addEventListener("click", createChannel);
newChannelInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") createChannel();
});

refreshChannelsBtn.addEventListener("click", loadChannels);
refreshUsersBtn.addEventListener("click", loadUsers);

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

// -------- SSE: mensagens novas --------
const es = new EventSource("/api/events");
es.addEventListener("message", (e) => {
  try {
    const data = JSON.parse(e.data);
    renderMessage(data);
  } catch (err) {
    console.error("Erro ao parsear SSE", err);
  }
});
