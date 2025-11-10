import zmq
import json
import time
import os
import shutil

DATA_FILE = "data.json"
LOGIN_FILE = "login.json"

def ensure_file(path, default_content):
    """Garante que o arquivo exista e seja válido (recria se for pasta ou corrompido)."""
    # Se for diretório, remove
    if os.path.isdir(path):
        print(f"[WARN] '{path}' é um diretório — removendo e recriando como arquivo.")
        shutil.rmtree(path)

    # Se o arquivo não existir, cria
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default_content, f, indent=4)

    # Se existir, tenta ler; recria se estiver corrompido
    try:
        with open(path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"[WARN] '{path}' corrompido — recriando.")
        with open(path, "w") as f:
            json.dump(default_content, f, indent=4)
        return default_content

def load_data():
    return ensure_file(DATA_FILE, {"users": [], "channels": []})

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def save_login(username):
    """Registra o login do usuário com timestamp em login.json."""
    logins = ensure_file(LOGIN_FILE, [])
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    logins.append({"user": username, "timestamp": timestamp})
    with open(LOGIN_FILE, "w") as f:
        json.dump(logins, f, indent=4)

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
            save_login(username)
            return {"service": "login", "data": {"status": "sucesso", "timestamp": timestamp}}
        else:
            # Mesmo usuário repetindo login: registra tentativa
            save_login(username)
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