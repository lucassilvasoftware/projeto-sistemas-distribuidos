import zmq
import json
import time
import os
import shutil
import msgpack

DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "data.json")
LOGIN_FILE = os.path.join(DATA_DIR, "login.json")


# ---------- MsgPack helpers ----------
def send_msgpack(sock, obj):
    data = msgpack.packb(obj, use_bin_type=True)
    sock.send(data)


def recv_msgpack(sock):
    data = sock.recv()
    return msgpack.unpackb(data, raw=False)


# ---------- util de arquivos ----------
def ensure_file(path, default_content):
    if os.path.isdir(path):
        print(f"[WARN] {path} é diretório, removendo.")
        shutil.rmtree(path)
    if not os.path.exists(path):
        print(f"[INIT] Criando {path}.")
        with open(path, "w") as f:
            json.dump(default_content, f, indent=4)
    try:
        with open(path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"[WARN] {path} corrompido. Resetando.")
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
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    logins.append({"user": username, "timestamp": ts})
    with open(LOGIN_FILE, "w") as f:
        json.dump(logins, f, indent=4)


# ---------- lógica de serviços ----------
def handle_request(request):
    data = load_data()
    service = request.get("service")
    payload = request.get("data", {})

    print(f"[SERVER] Serviço: {service} | Payload: {payload}")
    pub_info = None  # (topic, payload_dict)

    if service == "login":
        username = payload.get("user")
        ts = time.time()
        if username not in data["users"]:
            data["users"].append(username)
            save_data(data)
            save_login(username)
            print(f"[SERVER] Novo usuário: {username}")
            resp = {"service": "login", "data": {"status": "sucesso", "timestamp": ts}}
        else:
            save_login(username)
            print(f"[SERVER] Login usuário existente: {username}")
            resp = {
                "service": "login",
                "data": {
                    "status": "erro",
                    "timestamp": ts,
                    "description": "Usuário já cadastrado",
                },
            }

    elif service == "users":
        resp = {
            "service": "users",
            "data": {"timestamp": time.time(), "users": data["users"]},
        }

    elif service == "channel":
        ch = payload.get("channel")
        ts = time.time()
        if ch not in data["channels"]:
            data["channels"].append(ch)
            save_data(data)
            print(f"[SERVER] Canal criado: {ch}")
            resp = {
                "service": "channel",
                "data": {"status": "sucesso", "timestamp": ts},
            }
        else:
            resp = {
                "service": "channel",
                "data": {
                    "status": "erro",
                    "timestamp": ts,
                    "description": "Canal já existe",
                },
            }

    elif service == "channels":
        resp = {
            "service": "channels",
            "data": {"timestamp": time.time(), "channels": data["channels"]},
        }

    elif service == "subscribe":
        user = payload.get("user")
        ch = payload.get("channel")
        ts = time.time()

        if user not in data["users"]:
            msg = "Usuário inexistente"
            resp = {
                "service": "subscribe",
                "data": {"status": "erro", "timestamp": ts, "description": msg},
            }
        elif ch not in data["channels"]:
            msg = "Canal inexistente"
            resp = {
                "service": "subscribe",
                "data": {"status": "erro", "timestamp": ts, "description": msg},
            }
        else:
            subs = data.setdefault("subscriptions", {})
            user_subs = subs.setdefault(user, [])
            if ch not in user_subs:
                user_subs.append(ch)
                save_data(data)
                print(f"[SERVER] {user} inscrito em {ch}")
            resp = {
                "service": "subscribe",
                "data": {"status": "sucesso", "timestamp": ts},
            }

    elif service == "publish":
        user = payload.get("user")
        ch = payload.get("channel")
        msg_txt = payload.get("message")
        ts = payload.get("timestamp", time.time())

        if user not in data["users"]:
            msg = "Usuário inexistente"
            resp = {
                "service": "publish",
                "data": {
                    "status": "erro",
                    "timestamp": time.time(),
                    "description": msg,
                },
            }
        elif ch not in data["channels"]:
            msg = "Canal inexistente"
            resp = {
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
                "channel": ch,
                "message": msg_txt,
                "timestamp": ts,
            }
            data.setdefault("messages", []).append(msg_obj)
            save_data(data)
            print(f"[SERVER] Msg {user}@{ch}: {msg_txt}")
            resp = {
                "service": "publish",
                "data": {"status": "sucesso", "timestamp": ts},
            }
            pub_info = (ch, msg_obj)

    elif service == "history":
        ch = payload.get("channel")
        msgs = [m for m in data.get("messages", []) if m.get("channel") == ch]
        resp = {
            "service": "history",
            "data": {
                "status": "sucesso",
                "timestamp": time.time(),
                "messages": msgs,
            },
        }

    else:
        resp = {
            "service": "error",
            "data": {
                "status": "erro",
                "timestamp": time.time(),
                "description": "Serviço inválido",
            },
        }

    return resp, pub_info


# ---------- main ----------
def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    ctx = zmq.Context()

    rep = ctx.socket(zmq.REP)
    rep.bind("tcp://*:5555")
    print("[SERVER] REP em tcp://*:5555")

    pub = ctx.socket(zmq.PUB)
    pub.connect("tcp://proxy:5557")
    print("[SERVER] PUB -> proxy tcp://proxy:5557")

    print("[SERVER] Online (MsgPack).")

    while True:
        req = recv_msgpack(rep)
        resp, pub_info = handle_request(req)
        send_msgpack(rep, resp)

        if pub_info:
            topic, payload = pub_info
            packed = msgpack.packb(payload, use_bin_type=True)
            pub.send_multipart([topic.encode(), packed])


if __name__ == "__main__":
    main()
