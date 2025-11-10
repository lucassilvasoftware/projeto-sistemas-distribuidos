import zmq
import json
import time

SERVER = "server"
PORT = 5555

def send_request(service, data):
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(f"tcp://{SERVER}:{PORT}")

    message = {"service": service, "data": data}
    socket.send_json(message)
    reply = socket.recv_json()
    print(json.dumps(reply, indent=4))

def main():
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
            break
        else:
            print("Opção inválida.")

if __name__ == "__main__":
    main()