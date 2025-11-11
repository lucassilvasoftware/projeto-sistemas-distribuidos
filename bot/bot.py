import zmq
import msgpack
import time
import json
import os
import random
import threading

SERVER = os.getenv("SERVER_HOST", "server_1")
PORT_REQ = 5555

# Relógio lógico
logical_clock = 0
clock_lock = threading.Lock()


def increment_clock():
    global logical_clock
    with clock_lock:
        logical_clock += 1
        return logical_clock


def update_clock(received_clock):
    global logical_clock
    with clock_lock:
        logical_clock = max(logical_clock, received_clock) + 1
        return logical_clock


def send_msgpack(sock, obj):
    data = msgpack.packb(obj, use_bin_type=True)
    sock.send(data)


def recv_msgpack(sock):
    data = sock.recv()
    return msgpack.unpackb(data, raw=False)


def send_request(socket, service, data):
    # Adiciona relógio lógico antes de enviar
    clock = increment_clock()
    data["clock"] = clock
    msg = {"service": service, "data": data}
    print(f"[BOT-REQ] Enviando {service}: {msg}")
    send_msgpack(socket, msg)
    reply = recv_msgpack(socket)
    
    # Atualiza relógio lógico ao receber resposta
    received_clock = reply.get("data", {}).get("clock", 0)
    if received_clock > 0:
        update_clock(received_clock)
    
    print(f"[BOT-REQ] Resposta ({service}): {reply}")
    return reply


def main():
    bot_name = os.getenv("BOT_NAME", "bot_1")

    context = zmq.Context()
    req_socket = context.socket(zmq.REQ)
    req_socket.connect(f"tcp://{SERVER}:{PORT_REQ}")
    print(f"[BOT] {bot_name} conectado a tcp://{SERVER}:{PORT_REQ}")

    # login
    login_resp = send_request(req_socket, "login", {"user": bot_name, "timestamp": time.time()})
    print(f"[BOT] Login realizado: {login_resp}")

    # Cria um canal padrão se não existir
    default_channel = "Geral"
    channels_resp = send_request(req_socket, "channels", {"timestamp": time.time()})
    channels = channels_resp.get("data", {}).get("channels", [])
    
    if default_channel not in channels:
        print(f"[BOT] Criando canal '{default_channel}'...")
        create_resp = send_request(req_socket, "channel", {"channel": default_channel, "timestamp": time.time()})
        print(f"[BOT] Canal criado: {create_resp}")
        channels.append(default_channel)
    
    # Lista de canais para o bot usar
    bot_channels = channels if channels else [default_channel]
    print(f"[BOT] Canais disponíveis: {bot_channels}")
    
    cycle_count = 0
    while True:
        cycle_count += 1
        # Lista canais novamente (pode ter mudado)
        resp = send_request(req_socket, "channels", {"timestamp": time.time()})
        channels = resp.get("data", {}).get("channels", [])
        
        if not channels:
            # Se não há canais, cria um
            channel_name = default_channel
            print(f"[BOT] Nenhum canal disponível. Criando '{channel_name}'...")
            create_resp = send_request(req_socket, "channel", {"channel": channel_name, "timestamp": time.time()})
            if create_resp.get("data", {}).get("status") == "sucesso":
                channels = [channel_name]
                print(f"[BOT] Canal '{channel_name}' criado com sucesso!")
            else:
                print(f"[BOT] Erro ao criar canal: {create_resp}")
                time.sleep(5)
                continue

        # Escolhe um canal aleatório
        channel = random.choice(channels)
        print(f"[BOT] {bot_name} escolhendo canal '{channel}' (ciclo {cycle_count}).")

        # Envia mensagem
        msg_text = f"{bot_name} msg {cycle_count} no canal {channel}"
        publish_resp = send_request(
            req_socket,
            "publish",
            {
                "user": bot_name,
                "channel": channel,
                "message": msg_text,
                "timestamp": time.time(),
            },
        )
        
        if publish_resp.get("data", {}).get("status") == "sucesso":
            print(f"[BOT] Mensagem enviada com sucesso: {msg_text}")
        else:
            print(f"[BOT] Erro ao enviar mensagem: {publish_resp}")

        print(f"[BOT] Ciclo {cycle_count} concluído, recomeçando em 8s...\n")
        time.sleep(8)


if __name__ == "__main__":
    main()
