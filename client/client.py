import zmq
import msgpack
import time
import threading
import queue
import sys

PROXY = "proxy"
SERVER = "server"
PORT_REQ = 5555
PORT_SUB = 5558

sub_commands = queue.Queue()

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


# ---------- Helpers MsgPack ----------
def send_msgpack(sock, obj):
    data = msgpack.packb(obj, use_bin_type=True)
    sock.send(data)


def recv_msgpack(sock):
    data = sock.recv()
    return msgpack.unpackb(data, raw=False)


# ---------- Subscriber Thread ----------
def subscriber_thread():
    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.connect(f"tcp://{PROXY}:{PORT_SUB}")
    print(f"[SUB] Conectado em tcp://{PROXY}:{PORT_SUB}")

    poller = zmq.Poller()
    poller.register(sub, zmq.POLLIN)

    while True:
        # Verifica novos tópicos para assinar
        try:
            while True:
                topic = sub_commands.get_nowait()
                sub.setsockopt_string(zmq.SUBSCRIBE, topic)
                print(f"[SUB] Assinado no canal '{topic}'")
        except queue.Empty:
            pass

        # Lê mensagens
        socks = dict(poller.poll(100))
        if sub in socks and socks[sub] == zmq.POLLIN:
            try:
                frames = sub.recv_multipart()
                if len(frames) < 2:
                    continue
                topic = frames[0].decode()
                payload = msgpack.unpackb(frames[1], raw=False)
                # Atualiza relógio lógico ao receber mensagem
                received_clock = payload.get("clock", 0)
                if received_clock > 0:
                    update_clock(received_clock)
                
                ts = time.strftime(
                    "%H:%M:%S", time.localtime(payload.get("timestamp", time.time()))
                )
                # Detecta se é mensagem privada ou de canal
                if payload.get("dst"):
                    # Mensagem privada
                    src = payload.get("src") or payload.get("user")
                    print(
                        f"\n[{ts}] [PRIVADA de {src}]: {payload.get('message')}\n> ",
                        end="",
                    )
                else:
                    # Mensagem de canal
                    print(
                        f"\n[{ts}] ({topic}) {payload.get('user')}: {payload.get('message')}\n> ",
                        end="",
                    )
            except Exception as e:
                print(f"[ERRO][SUB] Falha ao decodificar mensagem: {e}")


# ---------- REQ Helper ----------
def send_request(sock, service, data):
    # Adiciona relógio lógico antes de enviar
    clock = increment_clock()
    data["clock"] = clock
    msg = {"service": service, "data": data}
    send_msgpack(sock, msg)
    resp = recv_msgpack(sock)
    
    # Atualiza relógio lógico ao receber resposta
    received_clock = resp.get("data", {}).get("clock", 0)
    if received_clock > 0:
        update_clock(received_clock)
    
    print(f"[RESP] {resp}")
    return resp


# ---------- UI Terminal ----------
def main():
    ctx = zmq.Context()
    req = ctx.socket(zmq.REQ)
    req.connect(f"tcp://{SERVER}:{PORT_REQ}")
    print(f"[CLIENT] REQ conectado em tcp://{SERVER}:{PORT_REQ}")

    # Thread do subscriber
    threading.Thread(target=subscriber_thread, daemon=True).start()

    # Login
    user = input("Digite seu nome de usuário: ").strip()
    if not user:
        print("Usuário inválido.")
        sys.exit(1)
    send_request(req, "login", {"user": user, "timestamp": time.time()})
    
    # Inscreve no próprio tópico para receber mensagens privadas
    sub_commands.put(user)
    print(f"[CLIENT] Inscrito no tópico '{user}' para receber mensagens privadas")

    current_channel = None

    while True:
        print("\n=== MENU ===")
        print("1. Listar usuários")
        print("2. Criar canal")
        print("3. Listar canais")
        print("4. Entrar em canal")
        print("5. Enviar mensagem no canal")
        print("6. Enviar mensagem privada")
        print("7. Sair")
        choice = input("> ").strip()

        if choice == "1":
            send_request(req, "users", {})

        elif choice == "2":
            ch = input("Nome do canal: ").strip()
            if ch:
                send_request(req, "channel", {"channel": ch})

        elif choice == "3":
            send_request(req, "channels", {})

        elif choice == "4":
            ch = input("Entrar em canal: ").strip()
            if not ch:
                continue
            send_request(req, "subscribe", {"user": user, "channel": ch})
            sub_commands.put(ch)
            current_channel = ch

            # Carrega histórico
            print(f"[INFO] Carregando histórico de '{ch}'...")
            resp = send_request(req, "history", {"channel": ch})
            msgs = resp.get("data", {}).get("messages", [])
            if not msgs:
                print(f"[INFO] Nenhuma mensagem anterior em '{ch}'.")
            else:
                print(f"[INFO] Últimas {len(msgs)} mensagens:")
                for m in msgs:
                    ts = time.strftime(
                        "%H:%M:%S", time.localtime(m.get("timestamp", time.time()))
                    )
                    print(f"[{ts}] {m['user']}: {m['message']}")

        elif choice == "5":
            if not current_channel:
                print("⚠️  Entre em um canal primeiro.")
                continue
            msg_txt = input("Mensagem: ").strip()
            if not msg_txt:
                continue
            send_request(
                req,
                "publish",
                {
                    "user": user,
                    "channel": current_channel,
                    "message": msg_txt,
                    "timestamp": time.time(),
                },
            )

        elif choice == "6":
            # Enviar mensagem privada
            dst_user = input("Destinatário: ").strip()
            if not dst_user:
                print("Destinatário inválido.")
                continue
            msg_txt = input("Mensagem: ").strip()
            if not msg_txt:
                continue
            send_request(
                req,
                "message",
                {
                    "src": user,
                    "dst": dst_user,
                    "message": msg_txt,
                    "timestamp": time.time(),
                },
            )

        elif choice == "7":
            print("Saindo...")
            break

        else:
            print("Opção inválida.")


if __name__ == "__main__":
    main()