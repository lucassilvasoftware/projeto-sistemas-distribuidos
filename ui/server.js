import express from "express";
import * as zmq from "zeromq";
import { encode, decode } from "@msgpack/msgpack";
import { spawn } from "child_process";

const app = express();
app.use(express.json());
app.use(express.static("public"));

const SERVER_ADDR = "tcp://server:5555";
const PROXY_SUB_ADDR = "tcp://proxy:5558";

// ---------- RPC genérico via MessagePack ----------
async function rpc(service, data = {}) {
  const sock = new zmq.Request();

  console.log(
    `[UI][RPC] Conectando ao servidor em ${SERVER_ADDR} para serviço '${service}'`
  );
  sock.connect(SERVER_ADDR);

  const payload = { service, data };
  const encoded = encode(payload);

  console.log(`[UI][RPC] Enviando (MessagePack) ->`, payload);
  await sock.send(encoded);

  const [replyBuf] = await sock.receive();
  const reply = decode(replyBuf);

  console.log(`[UI][RPC] Resposta (decodificada) <-`, reply);
  sock.close();

  return reply;
}

// ---------- SSE global para eventos (Pub/Sub) ----------
const sseClients = new Set();

app.get("/api/events", (req, res) => {
  console.log("[UI][SSE] Novo cliente conectado em /api/events");

  res.set({
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
  });
  res.flushHeaders();
  res.write("retry: 1000\n\n");

  sseClients.add(res);

  req.on("close", () => {
    console.log("[UI][SSE] Cliente desconectado de /api/events");
    sseClients.delete(res);
  });
});

function broadcast(event, data) {
  const chunk = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
  for (const client of sseClients) {
    client.write(chunk);
  }
}

// ---------- SUB no Proxy: recebe publicações e repassa para SSE ----------
(async () => {
  try {
    const sub = new zmq.Subscriber();
    sub.connect(PROXY_SUB_ADDR);
    sub.subscribe(); // todos os tópicos

    console.log("🛰️ [UI][SUB] Conectado ao proxy em", PROXY_SUB_ADDR);

    // Cada mensagem do broker vem como [topicBuf, payloadBuf]
    for await (const [topicBuf, payloadBuf] of sub) {
      try {
        const topic = topicBuf.toString();
        const decoded = decode(payloadBuf); // {user, channel, message, timestamp}

        const enriched = {
          topic,
          ...decoded,
        };

        console.log("[UI][SUB] Recebido do proxy:", enriched);

        // Envia para todos os clientes SSE (usado no chat + debug)
        broadcast("message", enriched);
      } catch (err) {
        console.error("🛰️ [UI][SUB] Erro ao decodificar MessagePack:", err);
      }
    }
  } catch (err) {
    console.error("🛰️ [UI][SUB] Erro no loop do subscriber:", err);
  }
})();

// ---------- APIs HTTP (front -> server.py via RPC MsgPack) ----------

// Login
app.post("/api/login", async (req, res) => {
  const { user } = req.body;
  if (!user) return res.status(400).json({ error: "user required" });

  try {
    const reply = await rpc("login", {
      user,
      timestamp: Date.now() / 1000,
    });
    return res.json(reply);
  } catch (err) {
    console.error("[UI][API][login] Erro:", err);
    return res.status(500).json({ error: "failed" });
  }
});

// Lista de usuários
app.get("/api/users", async (_req, res) => {
  try {
    const reply = await rpc("users", {});
    return res.json(reply);
  } catch (err) {
    console.error("[UI][API][users] Erro:", err);
    return res.status(500).json({ error: "failed" });
  }
});

// Lista de canais
app.get("/api/channels", async (_req, res) => {
  try {
    const reply = await rpc("channels", {});
    return res.json(reply);
  } catch (err) {
    console.error("[UI][API][channels] Erro:", err);
    return res.status(500).json({ error: "failed" });
  }
});

// Criar canal
app.post("/api/channel", async (req, res) => {
  const { channel } = req.body;
  if (!channel) return res.status(400).json({ error: "channel required" });

  try {
    const reply = await rpc("channel", { channel });
    return res.json(reply);
  } catch (err) {
    console.error("[UI][API][channel] Erro:", err);
    return res.status(500).json({ error: "failed" });
  }
});

// Publicar mensagem
app.post("/api/publish", async (req, res) => {
  const { user, channel, message, timestamp } = req.body;
  if (!user || !channel || !message) {
    return res.status(400).json({ error: "user, channel, message required" });
  }

  try {
    const reply = await rpc("publish", {
      user,
      channel,
      message,
      timestamp: timestamp || Date.now() / 1000,
    });
    return res.json(reply);
  } catch (err) {
    console.error("[UI][API][publish] Erro:", err);
    return res.status(500).json({ error: "failed" });
  }
});

// Histórico por canal
app.get("/api/history", async (req, res) => {
  const { channel } = req.query;
  if (!channel) return res.status(400).json({ error: "channel required" });

  try {
    const reply = await rpc("history", { channel });
    return res.json(reply);
  } catch (err) {
    console.error("[UI][API][history] Erro:", err);
    return res.status(500).json({ error: "failed" });
  }
});

// ---------- Logs para Debug (SSE único centralizado) ----------
app.get("/api/debug/logs", (req, res) => {
  console.log("[UI][DEBUG] Cliente conectado em /api/debug/logs");

  res.set({
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
  });
  res.flushHeaders();
  res.write("retry: 1500\n\n");

  // Aqui usamos docker compose logs -f para centralizar logs
  const proc = spawn("docker", ["compose", "logs", "-f"]);

  proc.stdout.on("data", (chunk) => {
    const line = chunk.toString().replace(/\x1B\[[0-9;]*m/g, "");
    // Envia tudo (ou filtra se quiser)
    res.write(`data: ${line.trim()}\n\n`);
  });

  proc.stderr.on("data", (chunk) => {
    const line = chunk.toString().replace(/\x1B\[[0-9;]*m/g, "");
    res.write(`data: [ERR] ${line.trim()}\n\n`);
  });

  req.on("close", () => {
    console.log("[UI][DEBUG] Cliente saiu de /api/debug/logs");
    proc.kill("SIGINT");
  });
});

// ---------- Status dos containers ----------
app.get("/api/status", (req, res) => {
  const proc = spawn("docker", ["ps", "--format", "{{.Names}}\t{{.Status}}"]);
  let out = "";

  proc.stdout.on("data", (d) => (out += d.toString()));

  proc.on("close", () => {
    const list = out
      .trim()
      .split("\n")
      .filter(Boolean)
      .map((line) => {
        const [name, status] = line.split("\t");
        return { name, status };
      });

    res.json(list);
  });
});

// ---------- Inicialização ----------
const PORT = 8080;
app.listen(PORT, () => {
  console.log(`🌐 [UI] Servidor iniciado em http://localhost:${PORT}`);
});
