import zmq from "zeromq";

async function main() {
  const xsub = new zmq.Subscriber(); // entrada: servers (PUB)
  const xpub = new zmq.Publisher(); // saída: clients/bots (SUB)

  xsub.subscribe(); // assina todos tópicos

  await xsub.bind("tcp://*:5557"); // server PUB conecta aqui
  await xpub.bind("tcp://*:5558"); // clients SUB conectam aqui

  console.log("🛰️ Proxy iniciado");
  console.log("  XSUB tcp://*:5557");
  console.log("  XPUB tcp://*:5558");

  for await (const msg of xsub) {
    // msg pode ser Buffer ou array de Buffers (multipart)
    if (Array.isArray(msg)) {
      await xpub.send(msg);
    } else {
      await xpub.send(msg);
    }
  }
}

main().catch((err) => {
  console.error("Proxy error:", err);
});
