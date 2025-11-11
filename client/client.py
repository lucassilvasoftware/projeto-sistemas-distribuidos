import zmq
import msgpack
import time
import threading
import queue

PROXY = "proxy"
SERVER = "server"
PORT_REQ = 5555
PORT_SUB = 5558

sub_commands = queue.Queue()


def send_msgpack(sock, obj):
    data = msgpack.packb(obj, use_bin_type=True)
    sock.send(data)


def recv_msgpack(sock):
    data = sock.recv()
    return msgpack.unpackb(data, raw=False)


def subscriber_thread():
    context = zmq.Context()
    sub_socket = context.socket(zmq.SUB)
    sub_socket.connect(f"tcp://{PROXY}:{PORT_SUB}")
    print(f"[CLIENT-SUB] Conectado ao proxy em tcp://{PROXY}:{PORT_SUB}")

    poller = zmq.Poller()
    poller.register(sub_socket, zmq.POLLIN)

    while True:
        # aplicar inscrições
        try:
            while True:
                topic = sub_commands.get_nowait()
                sub_socket.setsockopt_string(zmq.SUBSCRIBE, topic)
                print(f"[CLIENT-SUB] Assinado tópico '{topic}'")
        except queue.Empty:
            pass

        socks = dict(poller.poll(100))
        if sub_socket in socks and socks[sub_socket] == zmq.POLLIN:
            frames = sub_socket.recv_multipart()
            if len(frames) < 2:
                print(f"[CLIENT-SUB][WARN] Mensagem inesperada: {frames}")
                continue

            topic = frames[0].decode()
            try:
                payload = msgpack.unpackb(frames[1], raw=False)
            except Exception as e:
                print(f"[CLIENT-SUB][ERRO] Falha ao decodificar msgpack: {e}")
                continue

            user = payload.get("user")
            channel = payload.get("channel", topic)
            text = payload.get("message")
            ts = time.strftime(
                "%H:%M:%S", time.localtime(payload.get("timestamp", time.time()))
            )
            print(f"\n[MSG][{ts}] ({channel}) {user}: {text}\n> ", end="")


def send_request(socket, service, data):
    msg = {"service": service, "data": data}
    print(f"[CLIENT-REQ] Enviando: {msg}")
    send_msgpack(socket, msg)
    reply = recv_msgpack(socket)
    print(f"[CLIENT-REQ] Resposta: {reply}")
    return reply


def main():
    threading.Thread(target=subscriber_thread, daemon=True).start()

    context = zmq.Context()
    req_socket = context.socket(zmq.REQ)
    req_socket.connect(f"tcp://{SERVER}:{PORT_REQ}")
    print(f"[CLIENT] Conectado ao servidor em tcp://{SERVER}:{PORT_REQ}")

    user = input("Digite seu nome de usuário: ")
    send_request(req_socket, "login", {"user": user, "timestamp": time.time()})

    while True:
        print("\n--- MENU ---")
        print("1 - Listar usuários")
        print("2 - Criar canal")
        print("3 - Listar canais")
        print("4 - Inscrever em canal")
        print("5 - Publicar mensagem em canal")
        print("0 - Sair")

        op = input("> ")

        if op == "1":
            send_request(req_socket, "users", {"timestamp": time.time()})

        elif op == "2":
            canal = input("Nome do canal: ")
            send_request(
                req_socket,
                "channel",
                {"channel": canal, "timestamp": time.time()},
            )

        elif op == "3":
            send_request(req_socket, "channels", {"timestamp": time.time()})

        elif op == "4":
            canal = input("Canal para se inscrever: ")
            resp = send_request(
                req_socket,
                "subscribe",
                {"user": user, "channel": canal, "timestamp": time.time()},
            )
            if resp.get("data", {}).get("status") == "sucesso":
                sub_commands.put(canal)

        elif op == "5":
            canal = input("Canal: ")
            texto = input("Mensagem: ")
            send_request(
                req_socket,
                "publish",
                {
                    "user": user,
                    "channel": canal,
                    "message": texto,
                    "timestamp": time.time(),
                },
            )

        elif op == "0":
            print("[CLIENT] Encerrando cliente.")
            break

        else:
            print("[CLIENT] Opção inválida.")


if __name__ == "__main__":
    main()