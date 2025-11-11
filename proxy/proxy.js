import zmq from "zeromq";

async function main() {
  const xsub = new zmq.Subscriber();   // recebe dos servidores (PUB)
  const xpub = new zmq.Publisher();    // envia para clientes/bots (SUB)

  // XSUB precisa assinar tudo
  xsub.subscribe();

  await xsub.bind("tcp://*:5557"); // entrada (servidores)
  await xpub.bind("tcp://*:5558"); // saída (clientes/bots)

  console.log("🛰️ Proxy Pub/Sub iniciado");
  console.log("    XSUB (from server PUB)  -> tcp://*:5557");
  console.log("    XPUB (to client SUBs)   -> tcp://*:5558");

  for await (const [msg] of xsub) {
    console.log(`🛰️ [Proxy] encaminhando mensagem (${msg.length} bytes)`);
    await xpub.send(msg);
  }
}

main().catch((err) => {
  console.error("🛰️ Proxy erro fatal:", err);
});