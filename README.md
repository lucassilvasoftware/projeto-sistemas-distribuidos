# Sistemas distribuídos — mensageria instantânea

Sistema de troca de mensagens estilo **BBS** com **ZeroMQ** (request-reply e publish-subscribe), **MessagePack** para serialização binária e **Docker** para orquestração. Há componentes em **Python** (servidor, cliente, bots), **Node.js** (proxy Pub/Sub e UI web) e **Go** (serviço de referência para rank, lista e heartbeat).

## Visão rápida

- Vários servidores Python com persistência local e replicação entre nós.
- Relógio lógico de Lamport, sincronização física (Berkeley) e eleição de coordenador apoiadas pelo serviço de referência em Go.
- Proxy e interface web consomem eventos Pub/Sub; clientes e bots falam REQ/REP com os servidores.

Documentação de arquitetura com **diagramas detalhados**, fluxos e troubleshooting estendido: [**DIAGRAMAS.md**](./DIAGRAMAS.md).

## Pré-requisitos

- Docker e Docker Compose
- Python 3 (para os scripts em `scripts/`)

## Como executar

Subir todo o stack e abrir a UI (porta 8080):

```bash
python scripts/on.py
```

Aguarde a mensagem de sistema pronto antes de usar a interface ou testes.

Encerrar:

```bash
python scripts/off.py
```

Testes automatizados (com o sistema **já em execução**):

```bash
python scripts/test.py
```

Na UI: login, abas de testes/debug conforme implementação.

## Portas principais

| Serviço | Porta(s) |
|---------|-----------|
| UI web | 8080 |
| Servidores Python (REQ/REP) | 5555 |
| Proxy (PUB/SUB) | 5557 / 5558 |
| Serviço de referência (Go) | 5559 |

Estrutura de pastas (`server/`, `client/`, `bot/`, `proxy/`, `ui/`, `reference/`, `scripts/`) está resumida em **DIAGRAMAS.md** e na árvore documentada lá.
