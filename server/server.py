import zmq
import json
import time
import os
import shutil

DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "data.json")
LOGIN_FILE = os.path.join(DATA_DIR, "login.json")


# ---------- util de arquivos ----------
def ensure_file(path, default_content):
    if os.path.isdir(path):
        print(f"[WARN] {path} é diretório, removendo para recriar arquivo.")
        shutil.rmtree(path)
    if not os.path.exists(path):
        print(f"[INIT] Criando {path} com conteúdo padrão.")
        with open(path, "w") as f:
            json.dump(default_content, f, indent=4)
    try:
        with open(path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"[WARN] {path} corrompido. Recriando com conteúdo padrão.")
        with open(path, "w") as f:
            json.dump(default_content, f, indent=4)
        return default_content


def load_data():
    data = ensure_file(
        DATA_FILE,
        {"users": [], "channels": [], "subscriptions": {}, "messages": []},
    )
    data.setdefault("users", [])
    data.setdefault("channels", [])
    data.setdefault("subscriptions", {})
    data.setdefault("messages", [])
    return data


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


def save_login(username):
    logins = ensure_file(LOGIN_FILE, [])
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    logins.append({"user": username, "timestamp": timestamp})
    with open(LOGIN_FILE, "w") as f:
        json.dump(logins, f, indent=4)


# ---------- lógica de serviços ----------
def handle_request(request):
    data = load_data()
    service = request.get("service")
    payload = request.get("data", {})

    print(f"[SERVER] Serviço recebido: {service} | Payload: {payload}")

    pub_info = None  # (topic, payload_dict) caso precise publicar

    if service == "login":
        username = payload.get("user")
        timestamp = time.time()
        if username not in data["users"]:
            data["users"].append(username)
            save_data(data)
            save_login(username)
            print(f"[SERVER] Novo usuário registrado: {username}")
            response = {
                "service": "login",
                "data": {"status": "sucesso", "timestamp": timestamp},
            }
        else:
            save_login(username)
            print(f"[SERVER] Login repetido para usuário existente: {username}")
            response = {
                "service": "login",
                "data": {
                    "status": "Sucesso",
                    "timestamp": timestamp,
                    "description": "Usuário logado com sucesso!",
                },
            }

    elif service == "users":
        response = {
            "service": "users",
            "data": {"timestamp": time.time(), "users": data["users"]},
        }

    elif service == "channel":
        channel_name = payload.get("channel")
        timestamp = time.time()
        if channel_name not in data["channels"]:
            data["channels"].append(channel_name)
            save_data(data)
            print(f"[SERVER] Canal criado: {channel_name}")
            response = {
                "service": "channel",
                "data": {"status": "sucesso", "timestamp": timestamp},
            }
        else:
            print(f"[SERVER] Tentativa de criar canal já existente: {channel_name}")
            response = {
                "service": "channel",
                "data": {
                    "status": "erro",
                    "timestamp": timestamp,
                    "description": "Canal já existe",
                },
            }

    elif service == "channels":
        response = {
            "service": "channels",
            "data": {"timestamp": time.time(), "channels": data["channels"]},
        }

    elif service == "subscribe":
        user = payload.get("user")
        channel_name = payload.get("channel")
        timestamp = time.time()

        if user not in data["users"]:
            msg = "Usuário inexistente"
            print(f"[SERVER][ERRO][subscribe] {msg}: {user}")
            response = {
                "service": "subscribe",
                "data": {"status": "erro", "timestamp": timestamp, "description": msg},
            }
        elif channel_name not in data["channels"]:
            msg = "Canal inexistente"
            print(f"[SERVER][ERRO][subscribe] {msg}: {channel_name}")
            response = {
                "service": "subscribe",
                "data": {"status": "erro", "timestamp": timestamp, "description": msg},
            }
        else:
            subs = data.setdefault("subscriptions", {})
            user_subs = subs.setdefault(user, [])
            if channel_name not in user_subs:
                user_subs.append(channel_name)
                save_data(data)
                print(f"[SERVER] {user} inscrito no canal {channel_name}")
            else:
                print(f"[SERVER] {user} já estava inscrito em {channel_name}")
            response = {
                "service": "subscribe",
                "data": {"status": "sucesso", "timestamp": timestamp},
            }

    elif service == "publish":
        user = payload.get("user")
        channel_name = payload.get("channel")
        message_text = payload.get("message")
        timestamp = payload.get("timestamp", time.time())

        if user not in data["users"]:
            msg = "Usuário inexistente"
            print(f"[SERVER][ERRO][publish] {msg}: {user}")
            response = {
                "service": "publish",
                "data": {
                    "status": "erro",
                    "timestamp": time.time(),
                    "description": msg,
                },
            }
        elif channel_name not in data["channels"]:
            msg = "Canal inexistente"
            print(f"[SERVER][ERRO][publish] {msg}: {channel_name}")
            response = {
                "service": "publish",
                "data": {
                    "status": "erro",
                    "timestamp": time.time(),
                    "description": msg,
                },
            }
        else:
            msg_obj = {
                "user": user,
                "channel": channel_name,
                "message": message_text,
                "timestamp": timestamp,
            }
            data.setdefault("messages", []).append(msg_obj)
            save_data(data)
            print(
                f"[SERVER] Msg publicada por {user} em {channel_name}: {message_text}"
            )

            response = {
                "service": "publish",
                "data": {"status": "sucesso", "timestamp": timestamp},
            }

            # publica no tópico = nome do canal
            pub_info = (channel_name, msg_obj)

    else:
        print(f"[SERVER][ERRO] Serviço inválido: {service}")
        response = {
            "service": "error",
            "data": {
                "status": "erro",
                "timestamp": time.time(),
                "description": "Serviço inválido",
            },
        }

    return response, pub_info


# ---------- main ----------
def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    context = zmq.Context()

    # REP para clientes/bots
    rep_socket = context.socket(zmq.REP)
    rep_socket.bind("tcp://*:5555")
    print("[SERVER] Socket REP bind tcp://*:5555")

    # PUB -> conecta no proxy (XSUB)
    pub_socket = context.socket(zmq.PUB)
    pub_socket.connect("tcp://proxy:5557")
    print("[SERVER] Socket PUB conectado em tcp://proxy:5557")

    print("[SERVER] Servidor iniciado. Aguardando requisições...")

    while True:
        request = rep_socket.recv_json()
        response, pub_info = handle_request(request)
        rep_socket.send_json(response)

        if pub_info is not None:
            topic, payload = pub_info
            msg = f"{topic} {json.dumps(payload)}"
            print(f"[SERVER][PUB] topic='{topic}' msg={payload}")
            pub_socket.send_string(msg)
            # pequeno delay ajuda o roteamento
            time.sleep(0.01)


if __name__ == "__main__":
    main()
