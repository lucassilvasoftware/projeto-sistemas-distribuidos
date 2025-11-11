import zmq
import json
import time
import os
import shutil
import msgpack
import threading
import socket

DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "data.json")
LOGIN_FILE = os.path.join(DATA_DIR, "login.json")

# Variáveis globais para relógio e sincronização
logical_clock = 0
clock_lock = threading.Lock()
server_name = os.getenv("SERVER_NAME", f"server_{socket.gethostname()}")
server_rank = None
coordinator = None
coordinator_lock = threading.Lock()
message_count = 0
message_count_lock = threading.Lock()
REFERENCE_HOST = os.getenv("REFERENCE_HOST", "reference")
REFERENCE_PORT = 5559
SYNC_INTERVAL = 10  # Sincronizar a cada 10 mensagens
replication_enabled = True  # Flag para habilitar/desabilitar replicação
replication_lock = threading.Lock()  # Lock para operações de replicação


# ---------- Relógio Lógico ----------
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


def get_clock():
    with clock_lock:
        return logical_clock


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


# ---------- Comunicação com Referência ----------
def get_rank_from_reference():
    global server_rank
    try:
        ctx = zmq.Context()
        req = ctx.socket(zmq.REQ)
        req.setsockopt(zmq.LINGER, 0)
        req.connect(f"tcp://{REFERENCE_HOST}:{REFERENCE_PORT}")
        
        clock = increment_clock()
        msg = {
            "service": "rank",
            "data": {
                "user": server_name,
                "timestamp": time.time(),
                "clock": clock,
            },
        }
        send_msgpack(req, msg)
        resp = recv_msgpack(req)
        req.close()
        ctx.term()
        
        if resp.get("service") == "rank":
            server_rank = resp.get("data", {}).get("rank")
            received_clock = resp.get("data", {}).get("clock", 0)
            update_clock(received_clock)
            print(f"[SERVER] Rank recebido: {server_rank}")
            return server_rank
    except Exception as e:
        print(f"[SERVER] Erro ao obter rank: {e}")
    return None


def send_heartbeat():
    try:
        ctx = zmq.Context()
        req = ctx.socket(zmq.REQ)
        req.setsockopt(zmq.LINGER, 0)
        req.setsockopt(zmq.RCVTIMEO, 2000)
        req.connect(f"tcp://{REFERENCE_HOST}:{REFERENCE_PORT}")
        
        clock = increment_clock()
        msg = {
            "service": "heartbeat",
            "data": {
                "user": server_name,
                "timestamp": time.time(),
                "clock": clock,
            },
        }
        send_msgpack(req, msg)
        try:
            resp = recv_msgpack(req)
            received_clock = resp.get("data", {}).get("clock", 0)
            update_clock(received_clock)
        except:
            pass
        req.close()
        ctx.term()
    except Exception as e:
        print(f"[SERVER] Erro no heartbeat: {e}")


def get_server_list():
    try:
        ctx = zmq.Context()
        req = ctx.socket(zmq.REQ)
        req.setsockopt(zmq.LINGER, 0)
        req.setsockopt(zmq.RCVTIMEO, 2000)
        req.connect(f"tcp://{REFERENCE_HOST}:{REFERENCE_PORT}")
        
        clock = increment_clock()
        msg = {
            "service": "list",
            "data": {
                "timestamp": time.time(),
                "clock": clock,
            },
        }
        send_msgpack(req, msg)
        resp = recv_msgpack(req)
        req.close()
        ctx.term()
        
        received_clock = resp.get("data", {}).get("clock", 0)
        update_clock(received_clock)
        
        if resp.get("service") == "list":
            return resp.get("data", {}).get("list", [])
    except Exception as e:
        print(f"[SERVER] Erro ao obter lista de servidores: {e}")
    return []


# ---------- Sincronização de Relógio Físico (Berkeley) ----------
def sync_physical_clock():
    global coordinator
    with coordinator_lock:
        coord = coordinator
    
    if not coord or coord == server_name:
        # Sou o coordenador ou não há coordenador
        return
    
    try:
        # Conecta ao coordenador (usando hostname do Docker)
        # O coordenador é o nome do servidor (ex: server_1)
        ctx = zmq.Context()
        req = ctx.socket(zmq.REQ)
        req.setsockopt(zmq.LINGER, 0)
        req.setsockopt(zmq.RCVTIMEO, 2000)
        # No Docker, os hostnames são server_1, server_2, server_3
        req.connect(f"tcp://{coord}:5555")
        
        clock = increment_clock()
        msg = {
            "service": "clock",
            "data": {
                "timestamp": time.time(),
                "clock": clock,
            },
        }
        send_msgpack(req, msg)
        resp = recv_msgpack(req)
        req.close()
        ctx.term()
        
        received_clock = resp.get("data", {}).get("clock", 0)
        update_clock(received_clock)
        
        if resp.get("service") == "clock":
            coord_time = resp.get("data", {}).get("time")
            if coord_time:
                # Ajusta relógio físico (simulado)
                diff = coord_time - time.time()
                print(f"[SERVER] Sincronização: diferença = {diff:.3f}s")
    except Exception as e:
        print(f"[SERVER] Erro na sincronização com coordenador: {e}")
        # Tenta eleição
        start_election()


def start_election():
    global coordinator, server_rank
    servers = get_server_list()
    if not servers:
        print("[SERVER] Nenhum servidor na lista, pulando eleição")
        return
    
    # Verifica se temos rank
    if server_rank is None:
        print("[SERVER] Rank não disponível ainda, aguardando...")
        return
    
    # Filtra servidores com rank menor (maior prioridade)
    # Rank menor = número menor = maior prioridade
    candidates = [s for s in servers if s.get("rank", 999) < server_rank]
    
    print(f"[SERVER] Iniciando eleição. Meu rank: {server_rank}, Candidatos com rank menor: {len(candidates)}")
    
    if not candidates:
        # Sou o coordenador (tenho o menor rank ou sou o único)
        with coordinator_lock:
            coordinator = server_name
        announce_coordinator()
        print(f"[SERVER] Eleito como coordenador (rank {server_rank})")
    else:
        # Envia requisição de eleição para servidores com rank menor
        print(f"[SERVER] Enviando requisição de eleição para {len(candidates)} servidores")
        for srv in candidates:
            try:
                srv_name = srv.get('name')
                srv_rank = srv.get('rank', 999)
                print(f"[SERVER] Tentando conectar com {srv_name} (rank {srv_rank})")
                ctx = zmq.Context()
                req = ctx.socket(zmq.REQ)
                req.setsockopt(zmq.LINGER, 0)
                req.setsockopt(zmq.RCVTIMEO, 2000)
                req.connect(f"tcp://{srv_name}:5555")
                
                clock = increment_clock()
                msg = {
                    "service": "election",
                    "data": {
                        "timestamp": time.time(),
                        "clock": clock,
                    },
                }
                send_msgpack(req, msg)
                resp = recv_msgpack(req)
                req.close()
                ctx.term()
                
                received_clock = resp.get("data", {}).get("clock", 0)
                update_clock(received_clock)
                print(f"[SERVER] Resposta de eleição recebida de {srv_name}")
                break
            except Exception as e:
                print(f"[SERVER] Erro ao conectar com {srv.get('name')}: {e}")
                continue


def announce_coordinator():
    # Publica no tópico "servers"
    try:
        ctx = zmq.Context()
        pub = ctx.socket(zmq.PUB)
        pub.connect("tcp://proxy:5557")
        
        clock = increment_clock()
        msg = {
            "service": "election",
            "data": {
                "coordinator": server_name,
                "timestamp": time.time(),
                "clock": clock,
            },
        }
        packed = msgpack.packb(msg, use_bin_type=True)
        pub.send_multipart([b"servers", packed])
        pub.close()
        ctx.term()
        print(f"[SERVER] Coordenador anunciado: {server_name}")
    except Exception as e:
        print(f"[SERVER] Erro ao anunciar coordenador: {e}")


# ---------- Threads de background ----------
def heartbeat_thread():
    while True:
        time.sleep(5)
        send_heartbeat()


def sync_thread():
    while True:
        time.sleep(30)
        if coordinator:
            sync_physical_clock()


def election_thread():
    """Thread que tenta fazer eleição periodicamente se necessário"""
    global server_rank, coordinator
    while True:
        time.sleep(10)  # Tenta a cada 10 segundos
        # Se não temos rank, tenta obter
        if server_rank is None:
            print("[SERVER] Tentando obter rank novamente...")
            get_rank_from_reference()
        # Se temos rank mas não temos coordenador, tenta eleição
        if server_rank is not None:
            with coordinator_lock:
                coord = coordinator
            if not coord:
                print("[SERVER] Sem coordenador, tentando eleição...")
                start_election()


# ---------- Replicação de dados ----------
def replicate_operation(service, payload, pub_socket):
    """Publica operação no tópico de replicação para outros servidores"""
    global replication_enabled
    if not replication_enabled:
        return
    
    try:
        clock = increment_clock()
        replication_msg = {
            "service": f"replicate_{service}",
            "data": {
                "operation": service,
                "payload": payload,
                "source": server_name,
                "timestamp": time.time(),
                "clock": clock,
            },
        }
        packed = msgpack.packb(replication_msg, use_bin_type=True)
        pub_socket.send_multipart([b"replication", packed])
        print(f"[REPLICATION] Operação '{service}' replicada para outros servidores")
    except Exception as e:
        print(f"[REPLICATION] Erro ao replicar operação: {e}")


def apply_replication(operation, payload):
    """Aplica uma operação de replicação recebida de outro servidor"""
    global replication_enabled
    if not replication_enabled:
        return
    
    try:
        data = load_data()
        source = payload.get("source", "unknown")
        
        # Não aplicar se for do próprio servidor (evitar loops)
        if source == server_name:
            return
        
        print(f"[REPLICATION] Aplicando operação '{operation}' de {source}")
        
        if operation == "login":
            username = payload.get("payload", {}).get("user")
            if username and username not in data["users"]:
                data["users"].append(username)
                save_data(data)
                save_login(username)
                print(f"[REPLICATION] Usuário '{username}' replicado de {source}")
        
        elif operation == "channel":
            ch = payload.get("payload", {}).get("channel")
            if ch and ch not in data["channels"]:
                data["channels"].append(ch)
                save_data(data)
                print(f"[REPLICATION] Canal '{ch}' replicado de {source}")
        
        elif operation == "publish":
            payload_data = payload.get("payload", {})
            msg_obj = {
                "user": payload_data.get("user"),
                "channel": payload_data.get("channel"),
                "message": payload_data.get("message"),
                "timestamp": payload_data.get("timestamp"),
                "clock": payload.get("clock", 0),
            }
            # Verifica se a mensagem já existe (evitar duplicatas) usando user, channel, message, timestamp e clock
            messages = data.get("messages", [])
            exists = any(
                m.get("user") == msg_obj.get("user") and
                m.get("channel") == msg_obj.get("channel") and
                m.get("message") == msg_obj.get("message") and
                abs(m.get("timestamp", 0) - msg_obj.get("timestamp", 0)) < 1.0 and
                m.get("clock") == msg_obj.get("clock")
                for m in messages
            )
            if not exists:
                data.setdefault("messages", []).append(msg_obj)
                save_data(data)
                print(f"[REPLICATION] Mensagem replicada de {source}")
        
        elif operation == "message":
            payload_data = payload.get("payload", {})
            msg_obj = {
                "src": payload_data.get("src"),
                "dst": payload_data.get("dst"),
                "user": payload_data.get("src"),
                "message": payload_data.get("message"),
                "timestamp": payload_data.get("timestamp"),
                "clock": payload.get("clock", 0),
            }
            # Verifica se a mensagem já existe (evitar duplicatas) usando src, dst, message, timestamp e clock
            messages = data.get("messages", [])
            exists = any(
                m.get("src") == msg_obj.get("src") and
                m.get("dst") == msg_obj.get("dst") and
                m.get("message") == msg_obj.get("message") and
                abs(m.get("timestamp", 0) - msg_obj.get("timestamp", 0)) < 1.0 and
                m.get("clock") == msg_obj.get("clock")
                for m in messages
            )
            if not exists:
                data.setdefault("messages", []).append(msg_obj)
                save_data(data)
                print(f"[REPLICATION] Mensagem privada replicada de {source}")
        
        elif operation == "subscribe":
            user = payload.get("payload", {}).get("user")
            ch = payload.get("payload", {}).get("channel")
            if user and ch:
                subs = data.setdefault("subscriptions", {})
                user_subs = subs.setdefault(user, [])
                if ch not in user_subs:
                    user_subs.append(ch)
                    save_data(data)
                    print(f"[REPLICATION] Inscrição {user}@{ch} replicada de {source}")
    
    except Exception as e:
        print(f"[REPLICATION] Erro ao aplicar replicação: {e}")


# ---------- lógica de serviços ----------
def handle_request(request, is_replication=False, pub_socket=None):
    global coordinator, message_count
    
    # Atualiza relógio lógico ao receber mensagem
    received_clock = request.get("data", {}).get("clock", 0)
    if received_clock > 0:
        update_clock(received_clock)
    
    data = load_data()
    service = request.get("service")
    payload = request.get("data", {})
    
    # Se for uma operação de replicação, aplica e retorna sem processar
    if service and service.startswith("replicate_"):
        operation = service.replace("replicate_", "")
        apply_replication(operation, payload)
        # Retorna resposta vazia para operações de replicação
        return {"service": "replication", "data": {"status": "ok"}}, None
    
    print(f"[SERVER] Serviço: {service} | Payload: {payload} | Clock: {get_clock()}")
    pub_info = None  # (topic, payload_dict)
    needs_replication = False  # Flag para indicar se precisa replicar
    
    # Incrementa contador de mensagens (apenas se não for replicação)
    if not is_replication:
        with message_count_lock:
            message_count += 1
            if message_count % SYNC_INTERVAL == 0:
                sync_physical_clock()

    if service == "login":
        username = payload.get("user")
        ts = time.time()
        clock = increment_clock()
        if username not in data["users"]:
            data["users"].append(username)
            save_data(data)
            save_login(username)
            print(f"[SERVER] Novo usuário: {username}")
            needs_replication = True  # Precisa replicar novo usuário
        else:
            save_login(username)
            print(f"[SERVER] Login usuário existente: {username}")
        # Login sempre retorna sucesso (é login, não cadastro)
        resp = {"service": "login", "data": {"status": "sucesso", "timestamp": ts, "clock": clock}}
        
        # Replica operação se não for de replicação
        if needs_replication and not is_replication and pub_socket:
            replicate_operation("login", payload, pub_socket)

    elif service == "users":
        clock = increment_clock()
        resp = {
            "service": "users",
            "data": {"timestamp": time.time(), "clock": clock, "users": data["users"]},
        }

    elif service == "channel":
        ch = payload.get("channel")
        ts = time.time()
        clock = increment_clock()
        if ch not in data["channels"]:
            data["channels"].append(ch)
            save_data(data)
            print(f"[SERVER] Canal criado: {ch}")
            resp = {
                "service": "channel",
                "data": {"status": "sucesso", "timestamp": ts, "clock": clock},
            }
            # Replica operação se não for de replicação
            if not is_replication and pub_socket:
                replicate_operation("channel", payload, pub_socket)
        else:
            resp = {
                "service": "channel",
                "data": {
                    "status": "erro",
                    "timestamp": ts,
                    "clock": clock,
                    "description": "Canal já existe",
                },
            }

    elif service == "channels":
        clock = increment_clock()
        resp = {
            "service": "channels",
            "data": {"timestamp": time.time(), "clock": clock, "channels": data["channels"]},
        }

    elif service == "subscribe":
        user = payload.get("user")
        ch = payload.get("channel")
        ts = time.time()
        clock = increment_clock()

        if user not in data["users"]:
            msg = "Usuário inexistente"
            resp = {
                "service": "subscribe",
                "data": {"status": "erro", "timestamp": ts, "clock": clock, "description": msg},
            }
        elif ch not in data["channels"]:
            msg = "Canal inexistente"
            resp = {
                "service": "subscribe",
                "data": {"status": "erro", "timestamp": ts, "clock": clock, "description": msg},
            }
        else:
            subs = data.setdefault("subscriptions", {})
            user_subs = subs.setdefault(user, [])
            if ch not in user_subs:
                user_subs.append(ch)
                save_data(data)
                print(f"[SERVER] {user} inscrito em {ch}")
                # Replica operação se não for de replicação
                if not is_replication and pub_socket:
                    replicate_operation("subscribe", payload, pub_socket)
            resp = {
                "service": "subscribe",
                "data": {"status": "sucesso", "timestamp": ts, "clock": clock},
            }

    elif service == "publish":
        user = payload.get("user")
        ch = payload.get("channel")
        msg_txt = payload.get("message")
        ts = payload.get("timestamp", time.time())
        clock = increment_clock()

        if user not in data["users"]:
            msg = "Usuário inexistente"
            resp = {
                "service": "publish",
                "data": {
                    "status": "erro",
                    "timestamp": time.time(),
                    "clock": clock,
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
                    "clock": clock,
                    "description": msg,
                },
            }
        else:
            msg_obj = {
                "user": user,
                "channel": ch,
                "message": msg_txt,
                "timestamp": ts,
                "clock": clock,
            }
            data.setdefault("messages", []).append(msg_obj)
            save_data(data)
            print(f"[SERVER] Msg {user}@{ch}: {msg_txt}")
            resp = {
                "service": "publish",
                "data": {"status": "sucesso", "timestamp": ts, "clock": clock},
            }
            pub_info = (ch, msg_obj)
            # Replica operação se não for de replicação
            if not is_replication and pub_socket:
                replicate_operation("publish", payload, pub_socket)

    elif service == "message":
        # Mensagens privadas entre usuários
        src = payload.get("src")
        dst = payload.get("dst")
        msg_txt = payload.get("message")
        ts = payload.get("timestamp", time.time())
        clock = increment_clock()

        if src not in data["users"]:
            msg = "Usuário de origem inexistente"
            resp = {
                "service": "message",
                "data": {
                    "status": "erro",
                    "timestamp": time.time(),
                    "clock": clock,
                    "description": msg,
                },
            }
        elif dst not in data["users"]:
            msg = "Usuário de destino inexistente"
            resp = {
                "service": "message",
                "data": {
                    "status": "erro",
                    "timestamp": time.time(),
                    "clock": clock,
                    "description": msg,
                },
            }
        else:
            msg_obj = {
                "src": src,
                "dst": dst,
                "user": src,  # Para compatibilidade com renderização
                "message": msg_txt,
                "timestamp": ts,
                "clock": clock,
            }
            # Persiste mensagem privada
            data.setdefault("messages", []).append(msg_obj)
            save_data(data)
            print(f"[SERVER] Msg privada {src} -> {dst}: {msg_txt}")
            resp = {
                "service": "message",
                "data": {"status": "sucesso", "timestamp": ts, "clock": clock},
            }
            # Publica no tópico do usuário destino
            pub_info = (dst, msg_obj)
            # Replica operação se não for de replicação
            if not is_replication and pub_socket:
                replicate_operation("message", payload, pub_socket)

    elif service == "history":
        ch = payload.get("channel")
        clock = increment_clock()
        msgs = [m for m in data.get("messages", []) if m.get("channel") == ch]
        resp = {
            "service": "history",
            "data": {
                "status": "sucesso",
                "timestamp": time.time(),
                "clock": clock,
                "messages": msgs,
            },
        }
    
    elif service == "clock":
        # Serviço para sincronização de relógio físico (Berkeley)
        clock = increment_clock()
        resp = {
            "service": "clock",
            "data": {
                "time": time.time(),
                "timestamp": time.time(),
                "clock": clock,
            },
        }
    
    elif service == "election":
        # Serviço para eleição de coordenador
        # Responde que está vivo e disponível para eleição
        clock = increment_clock()
        print(f"[SERVER] Requisição de eleição recebida de outro servidor")
        # Não inicia eleição aqui para evitar loops - a thread de eleição vai cuidar disso
        resp = {
            "service": "election",
            "data": {
                "election": "OK",
                "rank": server_rank,
                "name": server_name,
                "timestamp": time.time(),
                "clock": clock,
            },
        }

    else:
        clock = increment_clock()
        resp = {
            "service": "error",
            "data": {
                "status": "erro",
                "timestamp": time.time(),
                "clock": clock,
                "description": "Serviço inválido",
            },
        }

    return resp, pub_info


# ---------- Subscriber para tópico "servers" ----------
def server_subscriber_thread(pub_socket):
    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.connect("tcp://proxy:5558")
    sub.setsockopt_string(zmq.SUBSCRIBE, "servers")
    
    print("[SERVER] Subscriber conectado ao tópico 'servers'")
    
    while True:
        try:
            frames = sub.recv_multipart()
            if len(frames) < 2:
                continue
            topic = frames[0].decode()
            payload = msgpack.unpackb(frames[1], raw=False)
            
            if topic == "servers" and payload.get("service") == "election":
                new_coord = payload.get("data", {}).get("coordinator")
                received_clock = payload.get("data", {}).get("clock", 0)
                update_clock(received_clock)
                
                with coordinator_lock:
                    coordinator = new_coord
                print(f"[SERVER] Novo coordenador: {new_coord}")
        except Exception as e:
            print(f"[SERVER] Erro no subscriber: {e}")


# ---------- Subscriber para tópico "replication" (Parte 5) ----------
def replication_subscriber_thread():
    """Thread que recebe operações de replicação de outros servidores"""
    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.connect("tcp://proxy:5558")
    sub.setsockopt_string(zmq.SUBSCRIBE, "replication")
    
    print("[REPLICATION] Subscriber conectado ao tópico 'replication'")
    
    while True:
        try:
            frames = sub.recv_multipart()
            if len(frames) < 2:
                continue
            topic = frames[0].decode()
            payload = msgpack.unpackb(frames[1], raw=False)
            
            if topic == "replication":
                # Atualiza relógio lógico
                received_clock = payload.get("data", {}).get("clock", 0)
                if received_clock > 0:
                    update_clock(received_clock)
                
                # Processa operação de replicação
                service = payload.get("service")
                if service and service.startswith("replicate_"):
                    # Aplica a replicação diretamente
                    operation = service.replace("replicate_", "")
                    apply_replication(operation, payload.get("data", {}))
        
        except Exception as e:
            print(f"[REPLICATION] Erro no subscriber: {e}")


# ---------- main ----------
def main():
    global server_rank, coordinator
    
    os.makedirs(DATA_DIR, exist_ok=True)
    ctx = zmq.Context()

    rep = ctx.socket(zmq.REP)
    rep.bind("tcp://*:5555")
    print(f"[SERVER] REP em tcp://*:5555 (nome: {server_name})")

    pub = ctx.socket(zmq.PUB)
    pub.connect("tcp://proxy:5557")
    print("[SERVER] PUB -> proxy tcp://proxy:5557")

    # Obtém rank do serviço de referência
    print("[SERVER] Obtendo rank do serviço de referência...")
    get_rank_from_reference()
    
    # Inicia threads de background
    threading.Thread(target=heartbeat_thread, daemon=True).start()
    threading.Thread(target=sync_thread, daemon=True).start()
    threading.Thread(target=server_subscriber_thread, args=(pub,), daemon=True).start()
    threading.Thread(target=election_thread, daemon=True).start()
    threading.Thread(target=replication_subscriber_thread, daemon=True).start()
    
    # Aguarda um pouco antes de iniciar eleição
    time.sleep(3)
    if server_rank is not None:
        start_election()
    else:
        print("[SERVER] Aguardando rank antes de iniciar eleição...")

    print("[SERVER] Online (MsgPack + Relógios + Replicação).")

    while True:
        req = recv_msgpack(rep)
        resp, pub_info = handle_request(req, is_replication=False, pub_socket=pub)
        send_msgpack(rep, resp)

        if pub_info:
            topic, payload = pub_info
            packed = msgpack.packb(payload, use_bin_type=True)
            pub.send_multipart([topic.encode(), packed])


if __name__ == "__main__":
    main()
