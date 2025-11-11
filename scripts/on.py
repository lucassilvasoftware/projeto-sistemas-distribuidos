# -*- coding: utf-8 -*-
import subprocess
import time
import platform
import webbrowser
import sys
import urllib.request
import os

# Configura encoding para evitar problemas no Windows
if sys.platform == 'win32':
    try:
        # Tenta configurar UTF-8
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except:
        # Se falhar, usa encoding padrão com replace
        pass
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    # Força UTF-8 no console do Windows
    if hasattr(sys, 'stdout') and hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except:
            pass

def run_cmd(cmd_list, check=True, shell=False, realtime=False):
    """Executa comando e retorna resultado"""
    if realtime:
        # Executa em tempo real, mostrando output
        try:
            process = subprocess.Popen(
                cmd_list, 
                shell=shell, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',
                errors='replace'
            )
            # Mostra output em tempo real
            try:
                for line in process.stdout:
                    try:
                        print(line, end='', flush=True)
                    except UnicodeEncodeError:
                        # Se falhar, tenta com ASCII apenas
                        print(line.encode('ascii', errors='replace').decode('ascii'), end='', flush=True)
            except Exception as e:
                print(f"[AVISO] Erro ao mostrar output: {e}")
            
            process.wait()
            if check and process.returncode != 0:
                cmd_str = " ".join(cmd_list) if isinstance(cmd_list, list) else cmd_list
                print(f"\n[ERRO] Erro ao executar: {cmd_str} (codigo: {process.returncode})")
                sys.exit(1)
            return type('Result', (), {'returncode': process.returncode, 'stdout': '', 'stderr': ''})()
        except Exception as e:
            print(f"[ERRO] Falha ao executar comando: {e}")
            if check:
                sys.exit(1)
            return type('Result', (), {'returncode': 1, 'stdout': '', 'stderr': str(e)})()
    else:
        # Executa normalmente com capture
        try:
            result = subprocess.run(cmd_list, shell=shell, capture_output=True, text=True, encoding='utf-8', errors='replace')
            if check and result.returncode != 0:
                cmd_str = " ".join(cmd_list) if isinstance(cmd_list, list) else cmd_list
                print(f"[ERRO] Erro ao executar: {cmd_str}")
                if result.stdout:
                    print(f"   STDOUT: {result.stdout}")
                if result.stderr:
                    print(f"   STDERR: {result.stderr}")
                sys.exit(1)
            return result
        except Exception as e:
            print(f"[ERRO] Falha ao executar comando: {e}")
            if check:
                sys.exit(1)
            return type('Result', (), {'returncode': 1, 'stdout': '', 'stderr': str(e)})()

def show_logs_tail(service_name, lines=20):
    """Mostra ultimas linhas de log de um servico"""
    print(f"\n[LOGS] Logs recentes de {service_name}:")
    print("-" * 60)
    result = run_cmd(["docker", "compose", "logs", "--tail", str(lines), service_name], check=False)
    if result.stdout:
        print(result.stdout)
    else:
        print("   (Nenhum log disponivel ainda)")
    print("-" * 60)

def wait_for_service(service_name, max_wait=60, show_logs=True):
    """Aguarda servico estar rodando"""
    print(f"\n[AGUARDANDO] Aguardando {service_name} estar pronto (timeout: {max_wait}s)...")
    start_time = time.time()
    
    for i in range(max_wait):
        # Verifica status
        result = run_cmd(["docker", "compose", "ps", service_name], check=False)
        
        if result.stdout:
            # Verifica se esta rodando
            if "Up" in result.stdout or "running" in result.stdout.lower():
                elapsed = time.time() - start_time
                print(f"[OK] {service_name} esta rodando (tempo: {elapsed:.1f}s)")
                
                # Mostra logs iniciais
                if show_logs:
                    time.sleep(1)  # Aguarda um pouco para logs aparecerem
                    show_logs_tail(service_name, lines=10)
                return True
            
            # Verifica se esta com erro
            if "Exited" in result.stdout or "Error" in result.stdout:
                print(f"[ERRO] {service_name} parou com erro!")
                show_logs_tail(service_name, lines=30)
                return False
        
        # Mostra progresso a cada 5 segundos
        if i > 0 and i % 5 == 0:
            elapsed = time.time() - start_time
            print(f"   [AGUARDANDO] Ainda aguardando... ({elapsed:.1f}s/{max_wait}s)")
        
        time.sleep(1)
    
    elapsed = time.time() - start_time
    print(f"[AVISO] {service_name} pode nao estar pronto ainda (aguardado {elapsed:.1f}s)")
    show_logs_tail(service_name, lines=30)
    return False

# ---------- Criar diretórios de dados para replicação (Parte 5) ----------
print("=" * 70)
print("CRIANDO DIRETÓRIOS DE DADOS PARA REPLICAÇÃO")
print("=" * 70)
import os
data_dirs = [
    "server/data/server_1",
    "server/data/server_2",
    "server/data/server_3",
]
for dir_path in data_dirs:
    os.makedirs(dir_path, exist_ok=True)
    print(f"   [OK] Diretorio criado: {dir_path}")

# ---------- Limpar containers antigos (opcional) ----------
print("\n" + "=" * 70)
print("LIMPANDO CONTAINERS ANTIGOS")
print("=" * 70)
run_cmd(["docker", "compose", "down"], check=False)
time.sleep(2)

# ---------- Build ----------
print("\n" + "=" * 70)
print("FAZENDO BUILD DAS IMAGENS DO DOCKER COMPOSE")
print("=" * 70)
print("   (Isso pode levar alguns minutos na primeira vez)")
print("   Mostrando output do build em tempo real...\n")

print("   Executando: docker compose build --progress=plain\n")
process = subprocess.Popen(
    ["docker", "compose", "build", "--progress=plain"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
    universal_newlines=True,
    encoding='utf-8',
    errors='replace'
)

build_success = True
for line in process.stdout:
    print(line, end='')
    # Detecta erros comuns no build
    if "ERROR" in line.upper() or "FAILED" in line.upper() or "exit code: 1" in line.lower():
        build_success = False

process.wait()

if process.returncode != 0:
    build_success = False

if build_success and process.returncode == 0:
    print("\n[OK] Build concluido com sucesso!")
else:
    print("\n[AVISO] Build teve problemas! Verifique os erros acima.")
    print("   Erros comuns:")
    print("   - Dependencias faltando (verifique Dockerfiles)")
    print("   - Arquivos nao encontrados (verifique COPY no Dockerfile)")
    print("   - Erros de compilacao (verifique codigo fonte)")
    print("\n   [AVISO] Continuando mesmo assim...")
    print("   Se servicos criticos falharem, o script vai parar automaticamente.")

# Verifica se as imagens foram criadas
print("\n[VERIFICANDO] Verificando imagens criadas...")
result = run_cmd(["docker", "images", "--format", "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"], check=False)
if result.stdout:
    print(result.stdout)

# ---------- Subir servico de referencia primeiro ----------
print("\n" + "=" * 70)
print("INICIANDO SERVICO DE REFERENCIA")
print("=" * 70)
run_cmd(["docker", "compose", "up", "-d", "reference"], check=False)
time.sleep(2)
if not wait_for_service("reference", max_wait=30, show_logs=True):
    print("[ERRO] Servico de referencia nao iniciou corretamente!")
    print("   Verifique os logs: docker compose logs reference")
    sys.exit(1)

# ---------- Subir proxy ----------
print("\n" + "=" * 70)
print("INICIANDO PROXY")
print("=" * 70)
run_cmd(["docker", "compose", "up", "-d", "proxy"], check=False)
time.sleep(2)
if not wait_for_service("proxy", max_wait=20, show_logs=True):
    print("[AVISO] Proxy pode nao estar funcionando corretamente")

# ---------- Subir servidores ----------
print("\n" + "=" * 70)
print("INICIANDO SERVIDORES (server_1, server_2, server_3)")
print("=" * 70)
run_cmd(["docker", "compose", "up", "-d", "server_1", "server_2", "server_3"], check=False)
print("[AGUARDANDO] Aguardando servidores iniciarem e se registrarem no servico de referencia...")
time.sleep(3)

# Verifica cada servidor individualmente
servers_ready = []
for server in ["server_1", "server_2", "server_3"]:
    if wait_for_service(server, max_wait=40, show_logs=True):
        servers_ready.append(server)
    else:
        print(f"[AVISO] {server} pode nao estar funcionando corretamente")

if len(servers_ready) == 0:
    print("[ERRO] Nenhum servidor iniciou corretamente!")
    sys.exit(1)
elif len(servers_ready) < 3:
    print(f"[AVISO] Apenas {len(servers_ready)} de 3 servidores iniciaram: {servers_ready}")

# ---------- Subir bots ----------
print("\n" + "=" * 70)
print("INICIANDO BOTS (bot_1, bot_2)")
print("=" * 70)
run_cmd(["docker", "compose", "up", "-d", "bot_1", "bot_2"], check=False)
time.sleep(3)

# Verifica bots
for bot in ["bot_1", "bot_2"]:
    wait_for_service(bot, max_wait=20, show_logs=False)

# ---------- Subir UI ----------
print("\n" + "=" * 70)
print("INICIANDO UI")
print("=" * 70)
run_cmd(["docker", "compose", "up", "-d", "ui"], check=False)
time.sleep(3)
if not wait_for_service("ui", max_wait=30, show_logs=True):
    print("[AVISO] UI pode nao estar acessivel")

# ---------- Aguardar estabilizacao completa ----------
print("\n" + "=" * 70)
print("AGUARDANDO ESTABILIZACAO DO SISTEMA")
print("=" * 70)
print("   - Servidores se registrando no servico de referencia")
print("   - Eleicao de coordenador")
print("   - Sincronizacao de relogios")
print("\n   Aguardando 10 segundos para estabilizacao...")

for i in range(10, 0, -1):
    print(f"   [AGUARDANDO] {i} segundo(s) restante(s)...", end='\r')
    time.sleep(1)
print("   [OK] Estabilizacao completa!      ")

# ---------- Mostrar status completo dos servicos ----------
print("\n" + "=" * 70)
print("STATUS COMPLETO DOS SERVICOS")
print("=" * 70)
result = run_cmd(["docker", "compose", "ps"], check=False)
if result.stdout:
    print(result.stdout)
else:
    print("   (Nenhum output)")

# ---------- Verificar servicos criticos ----------
print("\n" + "=" * 70)
print("VERIFICACAO DETALHADA DOS SERVICOS")
print("=" * 70)

# Verifica referencia
print("\n[LOGS] Servico de Referencia:")
show_logs_tail("reference", lines=15)

# Verifica servidores
print("\n[LOGS] Servidores (eleicao de coordenador):")
for server in servers_ready:
    print(f"\n   {server}:")
    show_logs_tail(server, lines=10)

# Verifica se ha coordenador eleito
print("\n[VERIFICANDO] Buscando anuncios de coordenador nos logs...")
result = run_cmd(["docker", "compose", "logs", "server_1", "server_2", "server_3"], check=False)
if result.stdout:
    coord_lines = [line for line in result.stdout.split('\n') if 'coordenador' in line.lower() or 'coordinator' in line.lower()]
    if coord_lines:
        print("   [OK] Coordenador encontrado:")
        for line in coord_lines[-5:]:  # Ultimas 5 mencoes
            print(f"      {line.strip()}")
    else:
        print("   [AVISO] Nenhum anuncio de coordenador encontrado ainda")

# ---------- Verificar UI ----------
print("\n" + "=" * 70)
print("VERIFICANDO UI")
print("=" * 70)
url = "http://localhost:8080"
print(f"   URL: {url}")

# Tenta verificar se a UI esta respondendo
try:
    response = urllib.request.urlopen(url, timeout=5)
    if response.getcode() == 200:
        print("   [OK] UI esta respondendo!")
    else:
        print(f"   [AVISO] UI retornou codigo {response.getcode()}")
except Exception as e:
    print(f"   [AVISO] UI pode nao estar acessivel: {e}")
    print("   Aguarde alguns segundos e tente acessar manualmente")

print("\n   Na aba 'Relogios' voce pode ver:")
print("   - Relogio logico do cliente")
print("   - Servidores registrados e seus ranks")
print("   - Coordenador eleito")
print("   - Relogios logicos nas mensagens")

# Aguarda um pouco antes de abrir
time.sleep(2)
if platform.system().lower() == "windows":
    subprocess.Popen(["start", url], shell=True)
elif platform.system().lower() == "darwin":
    subprocess.Popen(["open", url])
else:
    webbrowser.open(url)

# ---------- Informacoes uteis ----------
print("\n" + "="*60)
print("Sistema iniciado com sucesso!")
print("="*60)
print("\nServicos ativos:")
print("   - reference: Servico de referencia (porta 5559)")
print("   - proxy: Proxy Pub/Sub (portas 5557, 5558)")
print("   - server_1, server_2, server_3: Servidores (porta 5555)")
print("   - bot_1, bot_2: Bots automaticos")
print("   - ui: Interface web (porta 8080)")
print("\nComandos uteis:")
print("   - Ver logs: docker compose logs -f <servico>")
print("   - Ver todos os logs: docker compose logs -f")
print("   - Ver status: docker compose ps")
print("   - Parar tudo: python scripts/off.py")
print("\nTestes da Parte 4:")
print("   1. Abra a UI e va para a aba 'Relogios'")
print("   2. Observe o relogio logico incrementando")
print("   3. Verifique os servidores registrados e seus ranks")
print("   4. Observe qual servidor foi eleito como coordenador")
print("   5. Envie mensagens e veja os relogios logicos nas mensagens")
print("   6. Os bots enviarao mensagens automaticamente")
print("="*60)
