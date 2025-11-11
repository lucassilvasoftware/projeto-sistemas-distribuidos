import subprocess
import time
import platform
import ctypes

# ---------- Somente Windows ----------
if platform.system().lower() != "windows":
    print("Este script de layout é específico para Windows.")
    raise SystemExit(1)

# ---------- WinAPI ----------
user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

GetSystemMetrics = user32.GetSystemMetrics
FindWindowW = user32.FindWindowW
MoveWindow = user32.MoveWindow
ShowWindow = user32.ShowWindow

SW_RESTORE = 9


def wait_for_window(title, retries=40, delay=0.25):
    """Espera uma janela com o título exato aparecer e retorna o handle."""
    for _ in range(retries):
        hwnd = FindWindowW(None, title)
        if hwnd:
            return hwnd
        time.sleep(delay)
    return None


def move_window(title, x, y, w, h):
    hwnd = wait_for_window(title)
    if not hwnd:
        print(f"[WARN] Não encontrei janela com título: {title!r}")
        return
    ShowWindow(hwnd, SW_RESTORE)
    MoveWindow(hwnd, int(x), int(y), int(w), int(h), True)
    print(f"[OK] Janela '{title}' posicionada em ({x},{y}) {w}x{h}")


# ---------- Build das imagens ----------
print("🔄 Fazendo build das imagens do Docker Compose...")
subprocess.run(["docker", "compose", "build"], check=False)
print("✅ Build concluído (ou já estava em cache).")

# ---------- Sobe serviços ----------
print("🚀 Subindo serviços (proxy, server, bot)...")
subprocess.run(["docker", "compose", "up", "-d", "proxy", "server", "bot"], check=False)
print("✅ Serviços básicos ativos.\n")

time.sleep(2)

# ---------- Abre janelas separadas ----------
windows = [
    {"title": "Logs - proxy", "cmd": "docker compose logs -f proxy"},
    {"title": "Logs - server", "cmd": "docker compose logs -f server"},
    {"title": "Logs - bot", "cmd": "docker compose logs -f bot"},
    {"title": "Client - interactive", "cmd": "docker compose run --rm client"},
]

for win in windows:
    title, cmd = win["title"], win["cmd"]
    print(f"🪟 Abrindo terminal: {title}")
    subprocess.Popen(
        [
            "start",
            "powershell",
            "-NoExit",
            "-Command",
            f"$Host.UI.RawUI.WindowTitle='{title}'; {cmd}",
        ],
        shell=True,
    )
    time.sleep(0.7)

# ---------- Layout de janelas ----------
screen_w = GetSystemMetrics(0)
screen_h = GetSystemMetrics(1)

w2 = screen_w // 2
h2 = screen_h // 2

layout = {
    "Logs - proxy": (0, 0, w2, h2),
    "Logs - server": (w2, 0, w2, h2),
    "Logs - bot": (0, h2, w2, h2),
    "Client - interactive": (w2, h2, w2, h2),
}

print("\n📐 Posicionando janelas...")
for title, (x, y, w, h) in layout.items():
    move_window(title, x, y, w, h)

print("\n✅ Layout de debug aplicado.")
print("   As quatro janelas foram abertas com os serviços principais.")
print("   Feche qualquer uma delas individualmente para parar o log.")
print("   Para encerrar todos os containers: docker compose stop\n")
