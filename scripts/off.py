import subprocess

print("🛑 Parando todos os containers do docker compose...\n")

try:
    subprocess.run(["docker", "compose", "stop"], check=True)
    print("\n✅ Containers parados. Estado atual:\n")
    subprocess.run(["docker", "compose", "ps"])
except subprocess.CalledProcessError:
    print("\n⚠️  Erro ao parar containers.")