import zmq
import json
import time
import os
import shutil

DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "data.json")
LOGIN_FILE = os.path.join(DATA_DIR, "login.json")

# --- funções de persistência ---
def ensure_file(path, default_content):
    if os.path.isdir(path):
        shutil.rmtree(path)
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default_content, f, indent=4)
    try:
        with open(path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        with open(path, "w") as f:
            json.dump(default_content, f, indent=4)
        return default_content

def load_data():
    return ensure_file(DATA_FILE, {"users": [], "channels": []})

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def save_login(username):
    logins = ensure_file(LOGIN_FILE, [])
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    logins.append({"user": username, "timestamp": timestamp})
    with open(LOGIN_FILE, "w") as f:
        json.dump(logins, f, indent=4)

# --- lógica de serviços ---
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
            save_login(username)
            return {"service": "login", "data": {"status": "erro", "timestamp": timestamp, "description": "Usuário já cadastrado"}}

    elif service == "users":
        return {"service": "users", "data": {"timestamp": time.time(), "users": data["users"]}}

    elif service == "channel":
        channel_name = payload.get("channel")
        timestamp = time.time()
        if channel_name not in data["channels"]:
            data["channels"].append(channel_name)
            save_data(data)
            return {"service": "channel", "data": {"status": "sucesso", "timestamp": timestamp}}
        else:
            return {"service": "channel", "data": {"status": "erro", "timestamp": timestamp, "description": "Canal já existe"}}

    elif service == "channels":
        return {"service": "channels", "data": {"timestamp": time.time(), "channels": data["channels"]}}

    else:
        return {"service": "error", "data": {"status": "erro", "timestamp": time.time(), "description": "Serviço inválido"}}

# --- servidor REQ/REP + PUB ---
def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    context = zmq.Context()

    # REQ/REP
    rep_socket = context.socket(zmq.REP)
    rep_socket.bind("tcp://*:5555")

    # PUB (conecta no XSUB do proxy)
    pub_socket = context.socket(zmq.PUB)
    pub_socket.connect("tcp://proxy:5557")  # proxy XSUB

    print("Servidor iniciado (REQ/REP + PUB)")

    while True:
        message = rep_socket.recv_json()
        print(f"[REQ recebido] {message}")
        response = handle_request(message)
        rep_socket.send_json(response)

        # Publica atualização no proxy
        pub_socket.send_string(f"UPDATE: {json.dumps(response)}")
        time.sleep(0.1)

if __name__ == "__main__":
    main()