import express from "express";
import * as zmq from "zeromq";
import { encode, decode } from "@msgpack/msgpack";

const app = express();
app.use(express.json());
app.use(express.static("public"));

const SERVER_ADDR = "tcp://server:5555";
const PROXY_SUB_ADDR = "tcp://proxy:5558";

// ---------- helpers RPC (REQ/REP) com MsgPack ----------

async function rpc(service, data = {}) {
  const sock = new zmq.Request();
  sock.connect(SERVER_ADDR);

  const payload = { service, data };
  const packed = encode(payload);
  await sock.send(packed);

  const [replyBuf] = await sock.receive();
  sock.close();

  return decode(replyBuf);
}

// ---------- SSE: conexões dos navegadores ----------

const sseClients = new Set();

app.get("/api/events", (req, res) => {
  res.set({
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
  });
  res.flushHeaders();
  res.write("retry: 1000\n\n");

  sseClients.add(res);

  req.on("close", () => {
    sseClients.delete(res);
  });
});

function broadcast(event, data) {
  const line = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
  for (const client of sseClients) {
    client.write(line);
  }
}

// ---------- SUB: recebe mensagens do proxy ----------

(async () => {
  const sub = new zmq.Subscriber();
  sub.connect(PROXY_SUB_ADDR);
  sub.subscribe(); // tudo

  console.log("🛰️ UI SUB conectado em", PROXY_SUB_ADDR);

  for await (const msg of sub) {
    let topic, payloadBuf;

    if (Array.isArray(msg) && msg.length >= 2) {
      topic = msg[0].toString();
      payloadBuf = msg[1];
    } else if (!Array.isArray(msg)) {
      // fallback: se vier single frame, ignora formato
      topic = "unknown";
      payloadBuf = msg;
    } else {
      continue;
    }

    try {
      const payload = decode(payloadBuf);
      const enriched = {
        topic,
        ...payload,
      };

      console.log("🛰️ [UI] msg recebida:", enriched);
      broadcast("message", enriched);
    } catch (e) {
      console.error("🛰️ [UI] erro ao decodificar msgpack:", e);
    }
  }
})().catch((err) => {
  console.error("🛰️ [UI] erro loop SUB:", err);
});

// ---------- APIs REST ----------

app.get("/api/users", async (req, res) => {
  try {
    const reply = await rpc("users", { timestamp: Date.now() / 1000 });
    res.json(reply);
  } catch (e) {
    console.error("[UI] /api/users erro", e);
    res.status(500).json({ error: "failed" });
  }
});

app.get("/api/channels", async (req, res) => {
  try {
    const reply = await rpc("channels", { timestamp: Date.now() / 1000 });
    res.json(reply);
  } catch (e) {
    console.error("[UI] /api/channels erro", e);
    res.status(500).json({ error: "failed" });
  }
});

app.post("/api/channel", async (req, res) => {
  const { channel } = req.body;
  if (!channel) return res.status(400).json({ error: "channel required" });

  try {
    const reply = await rpc("channel", {
      channel,
      timestamp: Date.now() / 1000,
    });
    res.json(reply);
  } catch (e) {
    console.error("[UI] /api/channel erro", e);
    res.status(500).json({ error: "failed" });
  }
});

app.post("/api/publish", async (req, res) => {
  const { user, channel, message } = req.body;
  if (!user || !channel || !message) {
    return res.status(400).json({ error: "user, channel, message required" });
  }

  try {
    const reply = await rpc("publish", {
      user,
      channel,
      message,
      timestamp: Date.now() / 1000,
    });
    res.json(reply);
  } catch (e) {
    console.error("[UI] /api/publish erro", e);
    res.status(500).json({ error: "failed" });
  }
});

// ---------- start ----------
const PORT = 8080;
app.listen(PORT, () => {
  console.log(`🌐 UI disponível em http://localhost:${PORT}`);
});
