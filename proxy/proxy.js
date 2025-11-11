import zmq from "zeromq";

async function main() {
  const xsub = new zmq.Subscriber();  // recebe do servidor (PUB)
  const xpub = new zmq.Publisher();   // envia para clientes (SUB)

  // Bind
  await xsub.bind("tcp://*:5557"); // XSUB
  await xpub.bind("tcp://*:5558"); // XPUB

  console.log("🛰️ Proxy Pub/Sub iniciado (XSUB=5557, XPUB=5558)");

  for await (const [msg] of xsub) {
    // repassa mensagem para todos os clientes SUB
    await xpub.send(msg);
  }
}

main().catch(console.error);