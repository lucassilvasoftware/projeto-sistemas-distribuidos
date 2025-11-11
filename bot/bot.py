import zmq
import time
import json
import os
import random

SERVER = "server"
PORT_REQ = 5555


def send_request(socket, service, data):
    msg = {"service": service, "data": data}
    print(f"[BOT-REQ] Enviando {service}: {msg}")
    socket.send_json(msg)
    reply = socket.recv_json()
    print(f"[BOT-REQ] Resposta ({service}): {json.dumps(reply, indent=2)}")
    return reply


def main():
    bot_name = os.getenv("BOT_NAME", "bot_1")

    context = zmq.Context()
    req_socket = context.socket(zmq.REQ)
    req_socket.connect(f"tcp://{SERVER}:{PORT_REQ}")
    print(f"[BOT] {bot_name} conectado a tcp://{SERVER}:{PORT_REQ}")

    # login
    send_request(req_socket, "login", {"user": bot_name, "timestamp": time.time()})

    while True:
        # lista canais
        resp = send_request(req_socket, "channels", {"timestamp": time.time()})
        channels = resp.get("data", {}).get("channels", [])

        if not channels:
            print("[BOT] Nenhum canal disponível. Esperando para tentar de novo...")
            time.sleep(5)
            continue

        channel = random.choice(channels)
        print(f"[BOT] {bot_name} escolhendo canal '{channel}' para enviar mensagens.")

        # manda 2 mensagens
        for i in range(2):
            msg_text = f"{bot_name} msg {i} no canal {channel}"
            send_request(
                req_socket,
                "publish",
                {
                    "user": bot_name,
                    "channel": channel,
                    "message": msg_text,
                    "timestamp": time.time(),
                },
            )
            time.sleep(0.5)

        print("[BOT] Ciclo concluído, recomeçando em 4s...\n")
        time.sleep(4)


if __name__ == "__main__":
    main()