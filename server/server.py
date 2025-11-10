import zmq
import json
import time
import os
import shutil

DATA_FILE = "data.json"

def load_data():
    # Se "data.json" for um diretório (erro comum em Docker), remove e recria como arquivo
    if os.path.isdir(DATA_FILE):
        print(f"[WARN] '{DATA_FILE}' é um diretório — removendo e recriando corretamente.")
        shutil.rmtree(DATA_FILE)  # remove diretório e conteúdo (se houver)

    # Se o arquivo não existir, cria com estrutura inicial
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({"users": [], "channels": []}, f)

    # Agora lê os dados normalmente
    with open(DATA_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            # Se o arquivo estiver corrompido, recria do zero
            print(f"[WARN] '{DATA_FILE}' corrompido — recriando novo arquivo.")
            with open(DATA_FILE, "w") as fw:
                json.dump({"users": [], "channels": []}, fw)
            return {"users": [], "channels": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def handle_request(request):
    data = load_data()
    service = request.get("service")
    payload = request.get("data", {})

    if service == "login":
        username = payload.get("user")
        timestamp = time.time()
        if username not in data["users"]:
            data["users"].append(username)
            save_data(data)
            return {"service": "login", "data": {"status": "sucesso", "timestamp": timestamp}}
        else:
            return {
                "service": "login",
                "data": {
                    "status": "erro",
                    "timestamp": timestamp,
                    "description": "Usuário já cadastrado"
                }
            }

    elif service == "users":
        return {
            "service": "users",
            "data": {"timestamp": time.time(), "users": data["users"]}
        }

    elif service == "channel":
        channel_name = payload.get("channel")
        timestamp = time.time()
        if channel_name not in data["channels"]:
            data["channels"].append(channel_name)
            save_data(data)
            return {"service": "channel", "data": {"status": "sucesso", "timestamp": timestamp}}
        else:
            return {
                "service": "channel",
                "data": {
                    "status": "erro",
                    "timestamp": timestamp,
                    "description": "Canal já existe"
                }
            }

    elif service == "channels":
        return {
            "service": "channels",
            "data": {"timestamp": time.time(), "channels": data["channels"]}
        }

    else:
        return {
            "service": "error",
            "data": {
                "status": "erro",
                "timestamp": time.time(),
                "description": "Serviço inválido"
            }
        }

def main():
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://*:5555")

    print("Servidor iniciado na porta 5555...")

    while True:
        message = socket.recv_json()
        print(f"Recebido: {message}")
        response = handle_request(message)
        socket.send_json(response)

if __name__ == "__main__":
    main()