import express from "express";
import * as zmq from "zeromq";
import { encode, decode } from "@msgpack/msgpack";
import { spawn } from "child_process";

const app = express();
app.use(express.json());
app.use(express.static("public"));

const SERVER_ADDR = "tcp://server_1:5555";
const PROXY_SUB_ADDR = "tcp://proxy:5558";
const REFERENCE_ADDR = "tcp://reference:5559";

// ---------- Relógio lógico do cliente UI ----------
let logicalClock = 0;

function incrementClock() {
  logicalClock += 1;
  return logicalClock;
}

function updateClock(receivedClock) {
  logicalClock = Math.max(logicalClock, receivedClock) + 1;
  return logicalClock;
}

// ---------- RPC genérico via MessagePack ----------
async function rpc(service, data = {}) {
  const sock = new zmq.Request();

  console.log(
    `[UI][RPC] Conectando ao servidor em ${SERVER_ADDR} para serviço '${service}'`
  );
  sock.connect(SERVER_ADDR);

  // Adiciona relógio lógico antes de enviar
  const clock = incrementClock();
  data.clock = clock;
  
  const payload = { service, data };
  const encoded = encode(payload);

  console.log(`[UI][RPC] Enviando (MessagePack) ->`, payload);
  await sock.send(encoded);

  const [replyBuf] = await sock.receive();
  const reply = decode(replyBuf);

  // Atualiza relógio lógico ao receber resposta
  const receivedClock = reply?.data?.clock || 0;
  if (receivedClock > 0) {
    updateClock(receivedClock);
  }

  console.log(`[UI][RPC] Resposta (decodificada) <-`, reply);
  sock.close();

  return reply;
}

// ---------- RPC para serviço de referência ----------
async function rpcReference(service, data = {}) {
  const sock = new zmq.Request();
  sock.connect(REFERENCE_ADDR);

  const clock = incrementClock();
  data.clock = clock;

  const payload = { service, data };
  const encoded = encode(payload);
  await sock.send(encoded);

  const [replyBuf] = await sock.receive();
  const reply = decode(replyBuf);

  const receivedClock = reply?.data?.clock || 0;
  if (receivedClock > 0) {
    updateClock(receivedClock);
  }

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
    sub.subscribe(); // todos os tópicos (incluindo "servers")

    console.log("[UI][SUB] Conectado ao proxy em", PROXY_SUB_ADDR);

    // Cada mensagem do broker vem como [topicBuf, payloadBuf]
    for await (const [topicBuf, payloadBuf] of sub) {
      try {
        const topic = topicBuf.toString();
        const decoded = decode(payloadBuf); // {user, channel, message, timestamp, clock, service, coordinator}

        // Atualiza relógio lógico ao receber mensagem
        const receivedClock = decoded.clock || 0;
        if (receivedClock > 0) {
          updateClock(receivedClock);
        }

        const enriched = {
          topic,
          ...decoded,
        };

        console.log("[UI][SUB] Recebido do proxy:", enriched);

        // Envia para todos os clientes SSE (usado no chat + debug)
        // Inclui mensagens de canais e anúncios de coordenador
        broadcast("message", enriched);
      } catch (err) {
        console.error("[UI][SUB] Erro ao decodificar MessagePack:", err);
      }
    }
  } catch (err) {
    console.error("[UI][SUB] Erro no loop do subscriber:", err);
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

// Publicar mensagem em canal
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

// Enviar mensagem privada
app.post("/api/message", async (req, res) => {
  const { src, dst, message, timestamp } = req.body;
  if (!src || !dst || !message) {
    return res.status(400).json({ error: "src, dst, message required" });
  }

  try {
    const reply = await rpc("message", {
      src,
      dst,
      message,
      timestamp: timestamp || Date.now() / 1000,
    });
    return res.json(reply);
  } catch (err) {
    console.error("[UI][API][message] Erro:", err);
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

// Histórico de mensagens privadas
app.get("/api/private-history", async (req, res) => {
  const { user1, user2 } = req.query;
  if (!user1 || !user2) {
    return res.status(400).json({ error: "user1 e user2 são obrigatórios" });
  }

  try {
    const reply = await rpc("private_history", { user1, user2 });
    return res.json(reply);
  } catch (err) {
    console.error("[UI][API][private-history] Erro:", err);
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

// ---------- Informações dos servidores (do serviço de referência) ----------
app.get("/api/servers", async (_req, res) => {
  try {
    const reply = await rpcReference("list", {
      timestamp: Date.now() / 1000,
    });
    return res.json({
      servers: reply?.data?.list || [],
      logicalClock: logicalClock,
    });
  } catch (err) {
    console.error("[UI][API][servers] Erro:", err);
    return res.status(500).json({ error: "failed" });
  }
});

// ---------- Relógio lógico do cliente ----------
app.get("/api/clock", (_req, res) => {
  res.json({ logicalClock });
});

// ---------- Testes Automatizados ----------
app.get("/api/tests", async (_req, res) => {
  try {
    const { spawn } = await import("child_process");
    const fs = await import("fs");
    const path = await import("path");
    
    // Estratégia: Executar testes via Docker usando docker compose run
    // Isso cria um container temporário com Python que tem acesso ao volume de scripts
    // e à rede Docker para acessar os outros containers
    
    console.log("[UI][API][tests] Iniciando execucao de testes...");
    
    let proc;
    const dockerSock = "/var/run/docker.sock";
    
    if (fs.existsSync(dockerSock)) {
      // Estamos dentro do Docker, vamos executar o teste via docker exec no server_1
      // O server_1 tem Python, as dependências (pyzmq, msgpack) e acesso à rede
      console.log("[UI][API][tests] Executando testes via docker exec no server_1...");
      
      // O script test.py se conecta a localhost, mas dentro do Docker precisa usar
      // os nomes dos serviços. Por enquanto, vamos executar e ver o que acontece.
      // Se falhar, podemos ajustar o script para usar variáveis de ambiente.
      
      // Passa variável de ambiente para o script saber que está no Docker
      proc = spawn("docker", [
        "exec",
        "-e", "REFERENCE_HOST=reference",
        "server_1",
        "python3",
        "/scripts/test.py",
        "--json"
      ], {
        env: { ...process.env },
      });
      
    } else {
      // Não estamos no Docker, tenta executar localmente se Python estiver disponível
      console.log("[UI][API][tests] Tentando executar localmente...");
      
      const testScript = "/scripts/test.py";
      if (!fs.existsSync(testScript)) {
        return res.status(500).json({
          error: "Script nao encontrado",
          message: `Script nao encontrado em ${testScript}`,
          success: false,
          passed: 0,
          total: 0,
          tests: {},
        });
      }
      
      // Tenta executar com python3
      proc = spawn("python3", [testScript, "--json"], {
        env: { ...process.env, PYTHONIOENCODING: "utf-8" },
      });
    }
    
    let stdout = "";
    let stderr = "";
    let hasError = false;
    
    proc.stdout.on("data", (data) => {
      const text = data.toString();
      stdout += text;
      // Log em tempo real para debug
      if (text.trim()) {
        console.log("[UI][API][tests] Stdout:", text.trim());
      }
    });
    
    proc.stderr.on("data", (data) => {
      const text = data.toString();
      stderr += text;
      // Log em tempo real para debug
      if (text.trim() && !text.includes("WARNING")) {
        console.error("[UI][API][tests] Stderr:", text.trim());
      }
    });
    
    proc.on("error", (err) => {
      hasError = true;
      console.error("[UI][API][tests] Erro ao executar processo:", err);
      return res.status(500).json({
        error: "Erro ao executar testes",
        message: err.message,
        details: "Verifique se Docker esta rodando e se o script test.py existe",
        success: false,
        passed: 0,
        total: 0,
        tests: {},
      });
    });
    
    proc.on("close", (code) => {
      if (hasError) return;
      
      console.log(`[UI][API][tests] Processo finalizado com codigo: ${code}`);
      console.log(`[UI][API][tests] Stdout length: ${stdout.length}, Stderr length: ${stderr.length}`);
      
      try {
        // Tenta encontrar JSON no stdout
        let jsonResult = null;
        
        // Método 1: Procura por objeto JSON completo
        const jsonMatch = stdout.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
          try {
            jsonResult = JSON.parse(jsonMatch[0]);
            console.log("[UI][API][tests] JSON encontrado e parseado com sucesso");
            return res.json(jsonResult);
          } catch (e) {
            console.error("[UI][API][tests] Erro ao parsear JSON encontrado:", e.message);
          }
        }
        
        // Método 2: Procura na última linha que parece JSON
        const lines = stdout.split("\n").filter(line => line.trim());
        for (let i = lines.length - 1; i >= 0; i--) {
          const line = lines[i].trim();
          if (line.startsWith("{") && line.endsWith("}")) {
            try {
              jsonResult = JSON.parse(line);
              console.log("[UI][API][tests] JSON encontrado na ultima linha");
              return res.json(jsonResult);
            } catch (e) {
              // Continua procurando
            }
          }
        }
        
        // Método 3: Tenta parsear todo o stdout como JSON
        if (stdout.trim()) {
          try {
            jsonResult = JSON.parse(stdout.trim());
            console.log("[UI][API][tests] JSON parseado do stdout completo");
            return res.json(jsonResult);
          } catch (e) {
            // Não é JSON válido
          }
        }
        
        // Se não encontrou JSON, retorna erro com detalhes
        console.error("[UI][API][tests] Nenhum JSON valido encontrado");
        console.error("[UI][API][tests] Primeiros 1000 chars do stdout:", stdout.substring(0, 1000));
        console.error("[UI][API][tests] Primeiros 500 chars do stderr:", stderr.substring(0, 500));
        
        return res.status(500).json({
          error: "Erro ao executar testes",
          message: "Nenhum JSON valido encontrado na saida",
          code: code,
          stdout: stdout.substring(0, 1000),
          stderr: stderr.substring(0, 500),
          success: false,
          passed: 0,
          total: 0,
          tests: {},
        });
        
      } catch (err) {
        console.error("[UI][API][tests] Erro ao processar resultado:", err);
        return res.status(500).json({
          error: "Erro ao processar resultados",
          message: err.message,
          stdout: stdout.substring(0, 500),
          stderr: stderr.substring(0, 500),
          success: false,
          passed: 0,
          total: 0,
          tests: {},
        });
      }
    });
    
    // Timeout de 60 segundos
    setTimeout(() => {
      if (!proc.killed) {
        proc.kill();
        return res.status(500).json({
          error: "Timeout",
          message: "Testes demoraram mais de 60 segundos para executar",
          success: false,
          passed: 0,
          total: 0,
          tests: {},
        });
      }
    }, 60000);
    
  } catch (err) {
    console.error("[UI][API][tests] Erro geral:", err);
    return res.status(500).json({
      error: "Erro ao executar testes",
      message: err.message,
      success: false,
      passed: 0,
      total: 0,
      tests: {},
    });
  }
});

// ---------- Inicialização ----------
const PORT = 8080;
app.listen(PORT, () => {
  console.log(`[UI] Servidor iniciado em http://localhost:${PORT}`);
});
