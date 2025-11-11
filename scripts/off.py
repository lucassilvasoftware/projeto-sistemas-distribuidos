# -*- coding: utf-8 -*-
import subprocess
import sys
import time
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

def run_cmd(cmd_list, check=True, realtime=False):
    """Executa comando e retorna resultado"""
    if realtime:
        # Executa em tempo real, mostrando output
        try:
            process = subprocess.Popen(
                cmd_list, 
                shell=False, 
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
                if not check:
                    return type('Result', (), {'returncode': process.returncode, 'stdout': '', 'stderr': ''})()
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
            result = subprocess.run(cmd_list, shell=False, capture_output=True, text=True, encoding='utf-8', errors='replace')
            if check and result.returncode != 0:
                cmd_str = " ".join(cmd_list) if isinstance(cmd_list, list) else cmd_list
                print(f"[ERRO] Erro ao executar: {cmd_str}")
                if result.stdout:
                    print(f"   STDOUT: {result.stdout}")
                if result.stderr:
                    print(f"   STDERR: {result.stderr}")
                if not check:
                    return result
                sys.exit(1)
            return result
        except Exception as e:
            print(f"[ERRO] Falha ao executar comando: {e}")
            if check:
                sys.exit(1)
            return type('Result', (), {'returncode': 1, 'stdout': '', 'stderr': str(e)})()

print("=" * 70)
print("PARANDO TODOS OS CONTAINERS DO DOCKER COMPOSE")
print("=" * 70)

# Mostra containers rodando antes
print("\n[STATUS] Containers rodando antes de parar:")
result = run_cmd(["docker", "compose", "ps"], check=False)
if result.stdout and result.stdout.strip():
    print(result.stdout)
else:
    print("   Nenhum container do projeto esta rodando.")

# Para todos os servicos
print("\n" + "=" * 70)
print("PARANDO CONTAINERS")
print("=" * 70)
print("   Executando: docker compose stop")
result = run_cmd(["docker", "compose", "stop"], check=False, realtime=True)
if result.returncode == 0:
    print("\n[OK] Containers parados com sucesso.")
else:
    print(f"\n[AVISO] Alguns containers podem nao ter sido parados (codigo: {result.returncode})")

time.sleep(2)

# Remove containers (opcional, mas limpa melhor)
print("\n" + "=" * 70)
print("REMOVENDO CONTAINERS")
print("=" * 70)
print("   Executando: docker compose down")
result = run_cmd(["docker", "compose", "down"], check=False, realtime=True)
if result.returncode == 0:
    print("\n[OK] Containers removidos com sucesso.")
else:
    print(f"\n[AVISO] Alguns containers podem nao ter sido removidos (codigo: {result.returncode})")

time.sleep(1)

# Mostra estado atual
print("\n" + "=" * 70)
print("ESTADO ATUAL DOS CONTAINERS")
print("=" * 70)
result = run_cmd(["docker", "compose", "ps"], check=False)
if result.stdout and result.stdout.strip():
    print(result.stdout)
else:
    print("   [OK] Nenhum container do projeto esta rodando.")

# Verifica se ha containers orfaos
print("\n[VERIFICANDO] Verificando containers orfaos do projeto...")
result = run_cmd(["docker", "ps", "-a", "--filter", "name=projeto-sistemas-distribuidos", "--format", "table {{.Names}}\t{{.Status}}\t{{.Image}}"], check=False)
if result.stdout and result.stdout.strip():
    print("   Containers encontrados:")
    print(result.stdout)
else:
    print("   [OK] Nenhum container orfao encontrado.")

print("\n" + "=" * 70)
print("LIMPEZA CONCLUIDA")
print("=" * 70)
print("Para iniciar novamente: python scripts/on.py")
