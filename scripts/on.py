import subprocess
import time
import platform
import webbrowser

# ---------- Build ----------
print("🔄 Fazendo build das imagens do Docker Compose...")
subprocess.run(["docker", "compose", "build"], check=False)
print("✅ Build concluído (ou já estava em cache).")

# ---------- Subir serviços ----------
print("🚀 Subindo serviços principais (proxy, server, bot, ui)...")
subprocess.run(
    ["docker", "compose", "up", "-d", "proxy", "server", "bot", "ui"],
    check=False,
)
print("✅ Serviços ativos.")

# ---------- Aguardar estabilização ----------
time.sleep(3)

# ---------- Abrir UI no navegador ----------
url = "http://localhost:8080"
print(f"🌐 Abrindo UI em {url}")
if platform.system().lower() == "windows":
    subprocess.Popen(["start", url], shell=True)
else:
    webbrowser.open(url)

print("\n✅ Sistema iniciado.")
print(
    "💡 Dica: use 'docker compose logs -f <serviço>' para ver logs manuais, ou veja tudo na aba 'Logs' da UI."
)