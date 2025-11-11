import zmq
import msgpack
import time
import json
import os
import random

SERVER = "server"
PORT_REQ = 5555


def send_msgpack(sock, obj):
    data = msgpack.packb(obj, use_bin_type=True)
    sock.send(data)


def recv_msgpack(sock):
    data = sock.recv()
    return msgpack.unpackb(data, raw=False)


def send_request(socket, service, data):
    msg = {"service": service, "data": data}
    print(f"[BOT-REQ] Enviando {service}: {msg}")
    send_msgpack(socket, msg)
    reply = recv_msgpack(socket)
    print(f"[BOT-REQ] Resposta ({service}): {reply}")
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
            print("[BOT] Nenhum canal disponível. Esperando...")
            time.sleep(5)
            continue

        channel = random.choice(channels)
        print(f"[BOT] {bot_name} escolhendo canal '{channel}'.")

        # manda 1 msg
        for i in range(1):
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

        print("[BOT] Ciclo concluído, recomeçando em 8s...\n")
        time.sleep(8)


if __name__ == "__main__":
    main()
