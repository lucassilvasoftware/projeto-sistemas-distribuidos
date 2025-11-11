import zmq
import json
import time
import threading

PROXY = "proxy"  # conecta ao proxy para PUB/SUB
PORT_REQ = 5555
PORT_SUB = 5558  # XPUB do proxy

# --- Subscriber para receber mensagens do proxy ---
def subscriber_thread():
    context = zmq.Context()
    sub_socket = context.socket(zmq.SUB)
    sub_socket.connect(f"tcp://{PROXY}:{PORT_SUB}")
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")  # inscreve em todos os tópicos

    while True:
        try:
            msg = sub_socket.recv_string()
            print(f"\n[Pub recebido] {msg}\n> ", end="")
        except zmq.error.ZMQError:
            break

# --- Função para enviar requisições REQ ---
def send_request(service, data):
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(f"tcp://{PROXY}:{PORT_REQ}")  # conecta ao servidor via proxy

    message = {"service": service, "data": data}
    socket.send_json(message)
    reply = socket.recv_json()
    print(json.dumps(reply, indent=4))

# --- Menu interativo ---
def main():
    threading.Thread(target=subscriber_thread, daemon=True).start()

    print("Cliente iniciado.")
    user = input("Digite seu nome de usuário: ")
    send_request("login", {"user": user, "timestamp": time.time()})

    while True:
        print("\nEscolha uma opção:")
        print("1 - Listar usuários")
        print("2 - Criar canal")
        print("3 - Listar canais")
        print("0 - Sair")

        op = input("Opção: ")

        if op == "1":
            send_request("users", {"timestamp": time.time()})
        elif op == "2":
            canal = input("Nome do canal: ")
            send_request("channel", {"channel": canal, "timestamp": time.time()})
        elif op == "3":
            send_request("channels", {"timestamp": time.time()})
        elif op == "0":
            print("Saindo...")
            break
        else:
            print("Opção inválida.")

if __name__ == "__main__":
    main()