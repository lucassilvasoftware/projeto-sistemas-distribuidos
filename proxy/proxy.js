import zmq from "zeromq";

async function main() {
  const xsub = new zmq.Subscriber(); // recebe do server (PUB)
  const xpub = new zmq.Publisher(); // envia para clients/bots (SUB)

  // assina tudo
  xsub.subscribe();

  await xsub.bind("tcp://*:5557");
  await xpub.bind("tcp://*:5558");

  console.log("🛰️ Proxy MsgPack Pub/Sub iniciado");
  console.log("    entrada  (servers PUB) -> tcp://*:5557");
  console.log("    saída    (clients SUB) -> tcp://*:5558");

  for await (const msg of xsub) {
    // msg pode ser Buffer ou array de Buffers (multipart)
    if (Array.isArray(msg)) {
      console.log(`🛰️ [Proxy] encaminhando multipart (${msg.length} frames)`);
      await xpub.send(msg);
    } else {
      console.log("🛰️ [Proxy] encaminhando single frame");
      await xpub.send(msg);
    }
  }
}

main().catch((err) => {
  console.error("🛰️ Proxy erro fatal:", err);
});