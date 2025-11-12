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

// Mensagens Privadas
const privateMessageDst = { value: null }; // Objeto para manter estado
const privateMessageInfo = document.getElementById("private-message-info");
const privateMessageUser = document.getElementById("private-message-user");
const closePrivateChatBtn = document.getElementById("close-private-chat-btn");

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
const clientClockEl = document.getElementById("client-clock");
const refreshServersBtn = document.getElementById("refresh-servers");
const serversList = document.getElementById("servers-list");
const coordinatorInfo = document.getElementById("coordinator-info");

// Logs buttons
const startLogsBtn = document.getElementById("start-logs");
const stopLogsBtn = document.getElementById("stop-logs");

// ---------- Estado ----------
let currentUser = null;
let activeChannel = null;
let debugLogSource = null;
let debugMessages = [];
let coordinator = null;

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
    
    // Atualiza informações quando a aba de relógios é aberta
    if (target === "clocks") {
      updateClockDisplay();
      refreshServers();
    }
    
    // Atualiza informações quando a aba de testes é aberta
    if (target === "tests") {
      // Pode carregar resultados anteriores se houver
    }
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

// Inicializa estado do campo de mensagem
messageInput.disabled = true;
messageInput.placeholder = "Selecione um canal ou clique em um usuário para enviar mensagem privada";

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
      // Não permitir conversar com si mesmo
      if (u !== currentUser) {
        li.style.cursor = "pointer";
        li.title = "Clique para abrir conversa privada";
        li.addEventListener("click", () => openPrivateChat(u));
      }
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
  renderedMessages.clear(); // Limpa cache ao mudar de canal
  
  // Habilita campo de envio de mensagem
  messageInput.disabled = false;
  messageInput.placeholder = "Digite uma mensagem...";
  
  // Limpa conversa privada
  privateMessageDst.value = null;
  privateMessageInfo.style.display = "none";
  
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
  if (!currentUser) return;
  const text = messageInput.value.trim();
  if (!text) return;

  // Verifica se é mensagem de canal ou privada
  if (activeChannel) {
    // Mensagem de canal
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
  } else if (privateMessageDst.value) {
    // Mensagem privada
    const dst = privateMessageDst.value;
    try {
      const reply = await fetchJSON("/api/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          src: currentUser,
          dst: dst,
          message: text,
          timestamp: Date.now() / 1000,
        }),
      });
      
      if (reply?.data?.status === "sucesso") {
        messageInput.value = "";
        // Renderiza a mensagem enviada imediatamente para o remetente
        // O servidor publica apenas no tópico do destinatário, então o remetente
        // não recebe via SSE e precisa ver a mensagem renderizada manualmente
        // Usa o timestamp e clock retornados pelo servidor para garantir consistência
        const sentMsg = {
          src: currentUser,
          dst: dst,
          user: currentUser,
          message: text,
          timestamp: reply?.data?.timestamp || Date.now() / 1000,
          clock: reply?.data?.clock || 0,
        };
        // Renderiza a mensagem (a verificação de duplicação está na função renderMessage)
        renderMessage(sentMsg);
      } else {
        logEvent(`Erro ao enviar mensagem: ${reply?.data?.description || "Erro desconhecido"}.`);
      }
    } catch (e) {
      console.error("Erro ao enviar mensagem privada:", e);
      logEvent("Erro ao enviar mensagem privada.");
    }
  }
}

// ---------- Mensagens Privadas ----------
async function openPrivateChat(dstUser) {
  if (!currentUser) {
    logEvent("Faça login antes de abrir conversa privada.");
    return;
  }
  if (dstUser === currentUser) {
    logEvent("Você não pode conversar com si mesmo.");
    return;
  }
  
  // Define destinatário da conversa privada
  privateMessageDst.value = dstUser;
  activeChannel = null; // Limpa canal ativo
  
  // Atualiza UI
  activeChannelTitle.textContent = `Conversa privada com ${dstUser}`;
  privateMessageUser.textContent = dstUser;
  privateMessageInfo.style.display = "block";
  
  // Habilita campo de mensagem para conversa privada
  messageInput.disabled = false;
  messageInput.placeholder = `Digite uma mensagem para ${dstUser}...`;
  
  // Desmarca canais ativos
  [...channelListEl.children].forEach((n) => n.classList.remove("active"));
  
  // Carrega histórico
  await loadPrivateHistory(dstUser);
}

function closePrivateChat() {
  privateMessageDst.value = null;
  privateMessageInfo.style.display = "none";
  activeChannelTitle.textContent = "Selecione um canal";
  messageInput.disabled = true;
  messageInput.placeholder = "Selecione um canal ou clique em um usuário para enviar mensagem privada";
  messagesEl.innerHTML = "";
  activeChannel = null;
}

async function loadPrivateHistory(dstUser) {
  if (!currentUser || !dstUser) return;
  
  try {
    const reply = await fetchJSON(
      `/api/private-history?user1=${encodeURIComponent(currentUser)}&user2=${encodeURIComponent(dstUser)}`
    );
    const msgs = reply?.data?.messages || [];
    
    // Limpa área de mensagens e cache de mensagens renderizadas
    messagesEl.innerHTML = "";
    renderedMessages.clear();
    
    // Renderiza mensagens do histórico (ordenadas por timestamp)
    msgs
      .sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0))
      .forEach((m) => {
        renderMessage(m);
      });
    
    if (msgs.length > 0) {
      logEvent(`Histórico de mensagens privadas com ${dstUser} carregado (${msgs.length} mensagens).`);
    } else {
      logEvent(`Nenhuma mensagem anterior com ${dstUser}.`);
    }
  } catch (e) {
    console.error("Erro ao carregar histórico de mensagens privadas:", e);
    logEvent("Erro ao carregar histórico de mensagens privadas.");
  }
}

closePrivateChatBtn.addEventListener("click", closePrivateChat);

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
// Cache de mensagens já renderizadas para evitar duplicatas
const renderedMessages = new Set();

function getMessageId(msg) {
  const { src, dst, user, channel, message, timestamp, clock } = msg;
  if (dst) {
    // Mensagem privada: usa src, dst, timestamp e clock
    return `private_${src || user}_${dst}_${timestamp}_${clock}`;
  } else {
    // Mensagem de canal: usa user, channel, timestamp e clock
    return `channel_${user}_${channel}_${message}_${timestamp}_${clock}`;
  }
}

function renderMessage(msg, forcedChannel = null) {
  const { topic, user, channel, message, timestamp, clock, src, dst } = msg;
  
  // Gera ID único para a mensagem
  const msgId = getMessageId(msg);
  
  // Verifica se a mensagem já foi renderizada
  if (renderedMessages.has(msgId)) {
    return; // Já renderizada, ignora
  }
  
  // Mensagens privadas são renderizadas sempre (não dependem de canal ativo)
  if (dst) {
    // É mensagem privada
    // Só renderiza se a mensagem for para o usuário atual ou do usuário atual
    const sender = src || user;
    if (sender !== currentUser && dst !== currentUser) {
      // Mensagem entre outros usuários, não renderizar
      return;
    }
    
    const div = document.createElement("div");
    div.classList.add("msg", "private");
    div.dataset.src = sender;
    div.dataset.dst = dst;
    div.dataset.msgId = msgId;
    if (sender === currentUser) div.classList.add("self");
    if ((sender || "").toLowerCase().includes("bot")) div.classList.add("bot");

    const meta = document.createElement("div");
    meta.classList.add("meta");
    const timeStr = new Date(
      (timestamp || Date.now() / 1000) * 1000
    ).toLocaleTimeString();
    const clockStr = clock !== undefined ? ` [C:${clock}]` : "";
    
    // Mostra de forma mais clara quem está conversando
    let direction;
    if (sender === currentUser) {
      direction = `→ ${dst}`;
    } else {
      direction = `${sender} → você`;
    }
    
    meta.innerHTML = `<span class="user">[PRIVADA] ${direction}</span> <span>${timeStr}${clockStr}</span>`;
    div.append(meta);

    const txt = document.createElement("div");
    txt.classList.add("text");
    txt.textContent = message;
    div.append(txt);

    // Mensagens privadas: renderiza se estiver visualizando esta conversa privada
    const isPrivateConversation = activeChannelTitle.textContent.includes("Conversa privada");
    const relatedUser = sender === currentUser ? dst : sender;
    const currentDst = privateMessageDst.value;
    
    // Só mostra mensagens privadas se estiver visualizando essa conversa
    if (isPrivateConversation && currentDst && relatedUser === currentDst) {
      messagesEl.append(div);
      messagesEl.scrollTop = messagesEl.scrollHeight;
      renderedMessages.add(msgId); // Marca como renderizada
    }
    return;
  }
  
  // Mensagem de canal
  const ch = forcedChannel || channel || topic;
  // Não renderiza mensagens de canal se estiver visualizando conversa privada
  if (activeChannelTitle.textContent.includes("Conversa privada")) {
    return;
  }
  if (!ch || ch !== activeChannel) return;

  const div = document.createElement("div");
  div.classList.add("msg");
  div.dataset.msgId = msgId;
  if (user === currentUser) div.classList.add("self");
  if ((user || "").toLowerCase().includes("bot")) div.classList.add("bot");

  const meta = document.createElement("div");
  meta.classList.add("meta");
  const timeStr = new Date(
    (timestamp || Date.now() / 1000) * 1000
  ).toLocaleTimeString();
  const clockStr = clock !== undefined ? ` [C:${clock}]` : "";
  meta.innerHTML = `<span class="user">${user}</span> #${ch} <span>${timeStr}${clockStr}</span>`;
  div.append(meta);

  const txt = document.createElement("div");
  txt.classList.add("text");
  txt.textContent = message;
  div.append(txt);

  messagesEl.append(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  renderedMessages.add(msgId); // Marca como renderizada
}

// ---------- SSE: eventos ----------
const es = new EventSource("/api/events");
es.addEventListener("message", (e) => {
  try {
    const data = JSON.parse(e.data);
    pushDebugMessage(data);
    
    // Verifica se é anúncio de coordenador
    if (data.topic === "servers" && data.service === "election" && data.data?.coordinator) {
      coordinator = data.data.coordinator;
      updateCoordinatorInfo();
      logEvent(`Novo coordenador eleito: ${coordinator}`);
    } else if (data.dst || data.channel || (data.topic && data.topic !== "servers")) {
      // Renderiza mensagens privadas (dst) ou de canais, mas não anúncios de servidores
      // Se for mensagem privada e estiver visualizando conversa privada, atualiza título se necessário
      if (data.dst && currentUser) {
        const sender = data.src || data.user;
        const dst = data.dst;
        const isForCurrentUser = dst === currentUser || sender === currentUser;
        
        if (isForCurrentUser) {
          const isPrivateConversation = activeChannelTitle.textContent.includes("Conversa privada");
          const relatedUser = sender === currentUser ? dst : sender;
          const currentDst = privateMessageDst.value;
          
          // Se não está visualizando conversa privada, abre conversa privada
          if (!isPrivateConversation) {
            openPrivateChat(relatedUser);
          } else if (relatedUser !== currentDst) {
            // É de outra conversa - muda para esta conversa
            openPrivateChat(relatedUser);
          }
          // Renderiza a mensagem (só aparece se estiver na conversa correta)
          renderMessage(data);
        }
      } else {
        // Mensagem de canal - só renderiza se não estiver visualizando conversa privada
        if (!activeChannelTitle.textContent.includes("Conversa privada")) {
          renderMessage(data);
        }
      }
    }
  } catch {}
});

// ---------- Status ----------
async function refreshStatus() {
  try {
    const list = await fetchJSON("/api/status");
    statusList.innerHTML = list
      .map(
        (c) =>
          `<li>${c.status.startsWith("Up") ? "[OK]" : "[ERRO]"} <b>${c.name}</b> — ${
            c.status
          }</li>`
      )
      .join("");
  } catch {}
}

// ---------- Relógios e Servidores ----------
async function updateClockDisplay() {
  try {
    const data = await fetchJSON("/api/clock");
    if (clientClockEl) {
      clientClockEl.textContent = data.logicalClock || 0;
    }
  } catch (e) {
    console.error("Erro ao atualizar relógio:", e);
  }
}

async function refreshServers() {
  try {
    const data = await fetchJSON("/api/servers");
    const servers = data.servers || [];
    
    if (clientClockEl) {
      clientClockEl.textContent = data.logicalClock || 0;
    }
    
    // Se não temos coordenador mas temos servidores, assume que o servidor com menor rank é o coordenador
    // (Isso é uma heurística - o coordenador real é o servidor com menor rank que está ativo)
    if (!coordinator && servers.length > 0) {
      // Ordena servidores por rank (menor rank = maior prioridade)
      const sortedServers = [...servers].sort((a, b) => (a.rank || 999) - (b.rank || 999));
      const candidateCoordinator = sortedServers[0];
      if (candidateCoordinator) {
        coordinator = candidateCoordinator.name;
        console.log(`[UI] Coordenador inferido (menor rank): ${coordinator}`);
        updateCoordinatorInfo();
      }
    }
    
    if (serversList) {
      if (servers.length === 0) {
        serversList.innerHTML = "<li>Nenhum servidor registrado</li>";
      } else {
        serversList.innerHTML = servers
          .map(
            (s) =>
              `<li>[SERVER] <b>${s.name}</b> — Rank: ${s.rank} ${
                s.name === coordinator ? "[COORDENADOR]" : ""
              }</li>`
          )
          .join("");
      }
    }
    
    updateCoordinatorInfo();
  } catch (e) {
    console.error("Erro ao atualizar servidores:", e);
    if (serversList) {
      serversList.innerHTML = "<li>Erro ao carregar servidores</li>";
    }
  }
}

function updateCoordinatorInfo() {
  if (coordinatorInfo) {
    if (coordinator) {
      coordinatorInfo.innerHTML = `<strong>[COORDENADOR] ${coordinator}</strong>`;
      coordinatorInfo.style.background = "rgba(79, 70, 229, 0.2)";
    } else {
      coordinatorInfo.textContent = "Aguardando eleicao...";
      coordinatorInfo.style.background = "rgba(255, 255, 255, 0.05)";
    }
  }
}

// ---------- Testes Automatizados ----------
async function runTests() {
  const runTestsBtn = document.getElementById("run-tests");
  const testsStatus = document.getElementById("tests-status");
  const testsStatusIcon = document.getElementById("tests-status-icon");
  const testsStatusText = document.getElementById("tests-status-text");
  const testsResults = document.getElementById("tests-results");
  const testsSummary = document.getElementById("tests-summary");
  const testsProgress = document.getElementById("tests-progress");
  const testsProgressFill = document.getElementById("tests-progress-fill");
  const testsTimestamp = document.getElementById("tests-timestamp");
  const testsTotal = document.getElementById("tests-total");
  const testsPassed = document.getElementById("tests-passed");
  const testsFailed = document.getElementById("tests-failed");
  const testsSuccessRate = document.getElementById("tests-success-rate");
  
  if (!runTestsBtn || !testsStatus) return;
  
  // Estado: executando
  runTestsBtn.disabled = true;
  runTestsBtn.textContent = "Executando...";
  testsStatusIcon.textContent = "...";
  testsStatusIcon.style.color = "#fbbf24";
  testsStatusText.textContent = "Executando testes...";
  testsStatus.className = "tests-status-box tests-status-running";
  testsProgress.style.display = "block";
  testsResults.style.display = "none";
  testsSummary.style.display = "none";
  testsTimestamp.style.display = "none";
  testsResults.innerHTML = "";
  
  // Simula progresso (animação)
  let progress = 0;
  const progressInterval = setInterval(() => {
    progress = Math.min(progress + 2, 90);
    testsProgressFill.style.width = progress + "%";
  }, 100);
  
  try {
    const startTime = Date.now();
    const response = await fetch("/api/tests");
    
    if (!response.ok) {
      // Se a resposta não for OK, tenta parsear o erro
      const errorData = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error(errorData.message || errorData.error || `Erro HTTP ${response.status}`);
    }
    
    const data = await response.json();
    const duration = ((Date.now() - startTime) / 1000).toFixed(1);
    
    clearInterval(progressInterval);
    testsProgressFill.style.width = "100%";
    
    // Aguarda um pouco para mostrar 100%
    await new Promise(resolve => setTimeout(resolve, 200));
    testsProgress.style.display = "none";
    
    const passed = data.passed || 0;
    const total = data.total || 0;
    const failed = total - passed;
    const successRate = total > 0 ? ((passed / total) * 100).toFixed(1) : 0;
    
    // Atualiza resumo
    testsTotal.textContent = total;
    testsPassed.textContent = passed;
    testsFailed.textContent = failed;
    testsSuccessRate.textContent = successRate + "%";
    testsSummary.style.display = "block";
    
    // Estado: concluído
    if (data.success && passed === total) {
      testsStatusIcon.textContent = "[OK]";
      testsStatusIcon.style.color = "#10b981";
      testsStatusText.textContent = `Todos os testes passaram! (${duration}s)`;
      testsStatus.className = "tests-status-box tests-status-success";
    } else if (passed > 0) {
      testsStatusIcon.textContent = "[!]";
      testsStatusIcon.style.color = "#f59e0b";
      testsStatusText.textContent = `${passed}/${total} testes passaram (${duration}s)`;
      testsStatus.className = "tests-status-box tests-status-warning";
    } else {
      testsStatusIcon.textContent = "[X]";
      testsStatusIcon.style.color = "#ef4444";
      testsStatusText.textContent = `Nenhum teste passou (${duration}s)`;
      testsStatus.className = "tests-status-box tests-status-error";
    }
    
    // Mostra resultados dos testes
    let resultsHTML = "<div class='tests-results-header'>Resultados Detalhados:</div>";
    resultsHTML += "<div class='tests-list'>";
    
    // Ordena testes: falhados primeiro
    const testEntries = Object.entries(data.tests || {}).sort((a, b) => {
      if (a[1].passed !== b[1].passed) {
        return a[1].passed ? 1 : -1;
      }
      return a[0].localeCompare(b[0]);
    });
    
    for (const [testName, testData] of testEntries) {
      const testClass = testData.passed ? "test-item-passed" : "test-item-failed";
      const statusIcon = testData.passed ? "[OK]" : "[X]";
      const statusText = testData.passed ? "PASSOU" : "FALHOU";
      
      resultsHTML += `<div class="test-item ${testClass}">`;
      resultsHTML += `<div class="test-item-header">`;
      resultsHTML += `<span class="test-status-icon">${statusIcon}</span>`;
      resultsHTML += `<span class="test-name">${formatTestName(testName)}</span>`;
      resultsHTML += `<span class="test-status-badge ${testData.passed ? 'test-badge-passed' : 'test-badge-failed'}">${statusText}</span>`;
      resultsHTML += `</div>`;
      resultsHTML += `<div class="test-message">${testData.message || "Sem mensagem"}</div>`;
      resultsHTML += `</div>`;
    }
    resultsHTML += "</div>";
    testsResults.innerHTML = resultsHTML;
    testsResults.style.display = "block";
    
    // Timestamp
    const now = new Date();
    testsTimestamp.textContent = `Executado em ${now.toLocaleTimeString()} - ${now.toLocaleDateString()}`;
    testsTimestamp.style.display = "block";
    
  } catch (e) {
    clearInterval(progressInterval);
    testsProgress.style.display = "none";
    
    testsStatusIcon.textContent = "[X]";
    testsStatusIcon.style.color = "#ef4444";
    
    // Tenta extrair mensagem de erro mais detalhada
    let errorMessage = e.message;
    let errorDetails = "";
    
    try {
      if (e.response) {
        const errorData = await e.response.json();
        errorMessage = errorData.message || errorData.error || e.message;
        errorDetails = errorData.details || errorData.stdout || errorData.stderr || "";
      }
    } catch (parseErr) {
      // Ignora erros ao parsear resposta de erro
    }
    
    testsStatusText.textContent = `Erro ao executar testes: ${errorMessage}`;
    testsStatus.className = "tests-status-box tests-status-error";
    
    let errorHTML = `<div class="test-item test-item-failed">
      <div class="test-item-header">
        <span class="test-status-icon">[X]</span>
        <span class="test-name">Erro de Execucao</span>
      </div>
      <div class="test-message" style="color: #ef4444;">${errorMessage}</div>`;
    
    if (errorDetails) {
      errorHTML += `<div class="test-message" style="color: #f59e0b; margin-top: 5px; font-size: 10px;">${errorDetails.substring(0, 500)}</div>`;
    }
    
    errorHTML += `</div>`;
    testsResults.innerHTML = errorHTML;
    testsResults.style.display = "block";
  } finally {
    runTestsBtn.disabled = false;
    runTestsBtn.textContent = "Executar Testes";
  }
}

// Formata nome do teste para exibição
function formatTestName(name) {
  const names = {
    "reference": "Serviço de Referência",
    "servers_status": "Status dos Servidores",
    "server_connection": "Conexão do Servidor",
    "election": "Eleição de Coordenador",
    "bots_running": "Bots em Execução",
    "bot_messages": "Mensagens dos Bots",
    "channels": "Canais",
    "logical_clock": "Relógio Lógico",
    "replication": "Replicação de Dados"
  };
  return names[name] || name.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
}

// Adiciona event listener para o botao de testes
const runTestsBtn = document.getElementById("run-tests");
if (runTestsBtn) {
  runTestsBtn.addEventListener("click", runTests);
}

refreshServersBtn?.addEventListener("click", refreshServers);

// Atualiza relógio a cada segundo
setInterval(updateClockDisplay, 1000);
setInterval(refreshServers, 5000); // Atualiza servidores a cada 5 segundos

// ---------- Debug: eventos + MessagePack ----------
function pushDebugMessage(msg) {
  debugMessages.unshift(msg);
  if (debugMessages.length > 80) debugMessages.pop();

  const clockStr = msg.clock !== undefined ? ` [C:${msg.clock}]` : "";
  debugEventsList.innerHTML = debugMessages
    .map(
      (m) =>
        `<li>[${m.channel || m.topic}] <b>${m.user}</b>: ${(
          m.message || ""
        ).slice(0, 50)}${m.clock !== undefined ? ` [C:${m.clock}]` : ""}</li>`
    )
    .join("");

  const jsonStr = JSON.stringify(msg, null, 2);
  const size = new TextEncoder().encode(jsonStr).length;

  debugPayloadViewer.textContent = `// Payload MessagePack decodificado como JSON\n// ${size} bytes\n\n${jsonStr}`;
  msgpackRaw.textContent = `// Representação bruta do último pacote MessagePack\n\n${jsonStr}`;
}

