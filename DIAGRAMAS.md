# Diagramas da Arquitetura do Sistema Distribuído

## 1. Arquitetura Geral do Sistema

```mermaid
graph TB
    subgraph "Cliente Web"
        UI[UI - Node.js<br/>Porta 8080]
        Browser[Navegador Web]
    end
    
    subgraph "Clientes"
        Bot1[Bot 1 - Python]
        Bot2[Bot 2 - Python]
        Client[Client - Python]
    end
    
    subgraph "Servidores de Aplicação"
        S1[Server 1 - Python<br/>Porta 5555<br/>Rank: 1]
        S2[Server 2 - Python<br/>Porta 5555<br/>Rank: 2]
        S3[Server 3 - Python<br/>Porta 5555<br/>Rank: 3]
    end
    
    subgraph "Infraestrutura"
        Proxy[Proxy Pub/Sub - Node.js<br/>5557 PUB / 5558 SUB]
        Ref[Reference Service - Go<br/>Porta 5559]
    end
    
    subgraph "Persistência"
        D1[Data Server 1<br/>./server/data/server_1]
        D2[Data Server 2<br/>./server/data/server_2]
        D3[Data Server 3<br/>./server/data/server_3]
    end
    
    Browser -->|HTTP| UI
    UI -->|REQ/REP ZMQ<br/>MsgPack| S1
    UI -->|SUB ZMQ<br/>MsgPack| Proxy
    
    Bot1 -->|REQ/REP ZMQ<br/>MsgPack| S1
    Bot1 -->|SUB ZMQ<br/>MsgPack| Proxy
    Bot2 -->|REQ/REP ZMQ<br/>MsgPack| S1
    Bot2 -->|SUB ZMQ<br/>MsgPack| Proxy
    Client -->|REQ/REP ZMQ<br/>MsgPack| S1
    Client -->|SUB ZMQ<br/>MsgPack| Proxy
    
    S1 -->|REQ/REP ZMQ<br/>MsgPack| Ref
    S2 -->|REQ/REP ZMQ<br/>MsgPack| Ref
    S3 -->|REQ/REP ZMQ<br/>MsgPack| Ref
    
    S1 -->|PUB ZMQ<br/>MsgPack| Proxy
    S2 -->|PUB ZMQ<br/>MsgPack| Proxy
    S3 -->|PUB ZMQ<br/>MsgPack| Proxy
    
    S1 -->|Persistência| D1
    S2 -->|Persistência| D2
    S3 -->|Persistência| D3
    
    S1 -.->|Replicação<br/>Pub/Sub| S2
    S1 -.->|Replicação<br/>Pub/Sub| S3
    S2 -.->|Replicação<br/>Pub/Sub| S1
    S2 -.->|Replicação<br/>Pub/Sub| S3
    S3 -.->|Replicação<br/>Pub/Sub| S1
    S3 -.->|Replicação<br/>Pub/Sub| S2
    
    style S1 fill:#4f46e5,color:#fff
    style S2 fill:#6366f1,color:#fff
    style S3 fill:#818cf8,color:#fff
    style Ref fill:#10b981,color:#fff
    style Proxy fill:#f59e0b,color:#fff
    style UI fill:#ec4899,color:#fff
```

## 2. Fluxo de Comunicação Request-Reply

```mermaid
sequenceDiagram
    participant C as Cliente/UI
    participant S as Server
    participant R as Reference Service
    
    Note over C,R: Parte 1: Request-Reply (REQ/REP)
    
    C->>S: REQ: login, users, channels
    S->>S: Processa (MsgPack)
    S->>S: Atualiza relógio lógico
    S->>S: Persiste dados (JSON)
    S->>C: REP: resposta (MsgPack)
    
    Note over S,R: Servidor obtém rank
    S->>R: REQ: rank
    R->>S: REP: rank único
    S->>R: REQ: heartbeat (periódico)
    R->>S: REP: OK
```

## 3. Fluxo de Comunicação Publisher-Subscriber

```mermaid
sequenceDiagram
    participant C as Cliente/Bot
    participant S as Server
    participant P as Proxy
    participant O as Outros Clientes
    
    Note over C,O: Parte 2: Pub/Sub
    
    C->>S: REQ: publish (canal, mensagem)
    S->>S: Processa e salva
    S->>S: Atualiza relógio lógico
    S->>P: PUB: tópico "canal" + payload (MsgPack)
    P->>O: PUB: repassa mensagem
    O->>O: Recebe via SUB
    O->>O: Atualiza relógio lógico
```

## 4. Fluxo de Eleição de Coordenador

```mermaid
sequenceDiagram
    participant S1 as Server 1 (Rank 1)
    participant S2 as Server 2 (Rank 2)
    participant S3 as Server 3 (Rank 3)
    participant R as Reference Service
    participant P as Proxy
    
    Note over S1,S3: Eleição de Coordenador
    
    S1->>R: REQ: rank
    R->>S1: REP: rank = 1
    S2->>R: REQ: rank
    R->>S2: REP: rank = 2
    S3->>R: REQ: rank
    R->>S3: REP: rank = 3
    
    S1->>S1: Inicia eleição
    S1->>P: PUB: election (rank=1)
    P->>S2: PUB: election
    P->>S3: PUB: election
    
    S2->>S2: Compara rank (2 > 1)
    S3->>S3: Compara rank (3 > 1)
    
    S1->>S1: Eleito coordenador (menor rank)
    S1->>P: PUB: coordinator (server_1)
    P->>S2: PUB: coordinator
    P->>S3: PUB: coordinator
    P->>UI: PUB: coordinator
    
    Note over S1,S3: Sincronização de Relógio Físico (Berkeley)
    S2->>S1: REQ: clock sync
    S3->>S1: REQ: clock sync
    S1->>S1: Calcula média
    S1->>S2: REP: clock ajustado
    S1->>S3: REP: clock ajustado
```

## 5. Fluxo de Replicação de Dados

```mermaid
sequenceDiagram
    participant C as Cliente
    participant S1 as Server 1
    participant P as Proxy
    participant S2 as Server 2
    participant S3 as Server 3
    
    Note over C,S3: Parte 5: Replicação Event-Driven
    
    C->>S1: REQ: publish (mensagem)
    S1->>S1: Salva localmente
    S1->>S1: Atualiza relógio lógico
    S1->>P: PUB: tópico "canal" (para clientes)
    S1->>P: PUB: tópico "replication" (para servidores)
    
    Note over P,S3: Replicação para outros servidores
    P->>S2: PUB: replication (operacao)
    P->>S3: PUB: replication (operacao)
    
    S2->>S2: Verifica se é self-replication
    S2->>S2: Aplica replicação (apply_replication)
    S2->>S2: Verifica duplicatas
    S2->>S2: Salva localmente
    S2->>S2: Atualiza relógio lógico
    
    S3->>S3: Verifica se é self-replication
    S3->>S3: Aplica replicação (apply_replication)
    S3->>S3: Verifica duplicatas
    S3->>S3: Salva localmente
    S3->>S3: Atualiza relógio lógico
    
    Note over S1,S3: Eventual Consistency
```

## 6. Estrutura de Arquivos do Projeto

```
projeto-sistemas-distribuidos/
├── server/                    # Servidor Python
│   ├── server.py             # Servidor principal (REQ/REP + PUB/SUB)
│   ├── requirements.txt      # pyzmq, msgpack
│   ├── Dockerfile
│   └── data/                 # Dados persistidos
│       ├── server_1/
│       │   ├── data.json     # Usuários, canais, mensagens
│       │   └── login.json    # Sessões de login
│       ├── server_2/
│       │   ├── data.json
│       │   └── login.json
│       └── server_3/
│           ├── data.json
│           └── login.json
│
├── client/                    # Cliente Python (terminal)
│   ├── client.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── bot/                       # Bot Python (automático)
│   ├── bot.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── proxy/                     # Proxy Pub/Sub (Node.js)
│   ├── proxy.js              # Proxy XSUB/XPUB
│   ├── package.json
│   └── Dockerfile
│
├── ui/                        # Interface Web (Node.js)
│   ├── server.js             # Servidor Express + ZMQ
│   ├── package.json
│   ├── Dockerfile
│   └── public/
│       ├── index.html        # Interface HTML
│       ├── app.js            # JavaScript cliente
│       └── styles.css        # Estilos CSS
│
├── reference/                 # Serviço de Referência (Go)
│   ├── reference.go          # Gerenciamento de ranks
│   ├── go.mod
│   ├── Dockerfile
│   └── Dockerfile.debian
│
├── scripts/                   # Scripts auxiliares
│   ├── on.py                 # Inicia sistema
│   ├── off.py                # Para sistema
│   ├── test.py               # Testes automatizados
│   └── requirements.txt      # pyzmq, msgpack
│
├── docker-compose.yml         # Orquestração Docker
└── readme.md                  # Documentação
```

## 7. Componentes e Tecnologias

```mermaid
graph LR
    subgraph "Linguagens"
        Py[Python 3.11<br/>Server, Client, Bot]
        JS[Node.js 18<br/>UI, Proxy]
        Go[Go<br/>Reference Service]
    end
    
    subgraph "Bibliotecas"
        ZMQ[ZeroMQ<br/>REQ/REP, PUB/SUB]
        MP[MessagePack<br/>Serialização]
        Exp[Express<br/>HTTP Server]
    end
    
    subgraph "Infraestrutura"
        Docker[Docker<br/>Containerização]
        DC[Docker Compose<br/>Orquestração]
    end
    
    subgraph "Persistência"
        JSON[JSON Files<br/>Data Storage]
    end
    
    Py --> ZMQ
    Py --> MP
    JS --> ZMQ
    JS --> MP
    JS --> Exp
    Go --> ZMQ
    Go --> MP
    Py --> JSON
    Py --> Docker
    JS --> Docker
    Go --> Docker
    Docker --> DC
```

## 8. Portas e Protocolos

| Componente | Porta | Protocolo | Descrição |
|------------|-------|-----------|-----------|
| reference | 5559 | ZMQ REQ/REP | Serviço de referência (ranks) |
| proxy | 5557 | ZMQ PUB | Entrada de publicações |
| proxy | 5558 | ZMQ SUB | Saída para subscritores |
| server_1/2/3 | 5555 | ZMQ REQ/REP | Servidores de aplicação |
| ui | 8080 | HTTP | Interface web |
| ui | - | ZMQ REQ/REP | Comunicação com servidor |
| ui | - | ZMQ SUB | Recebe publicações |

## Resumo das Partes Implementadas

### Parte 1: Request-Reply
- ✅ Comunicação REQ/REP via ZeroMQ
- ✅ Serviços: login, users, channel, channels
- ✅ Persistência em arquivos JSON
- ✅ Serialização MessagePack

### Parte 2: Publisher-Subscriber
- ✅ Comunicação PUB/SUB via ZeroMQ
- ✅ Proxy Pub/Sub (XSUB/XPUB)
- ✅ Serviços: publish, message
- ✅ Bots automatizados

### Parte 3: MessagePack
- ✅ Serialização binária em todos os componentes
- ✅ Python: msgpack
- ✅ JavaScript: @msgpack/msgpack
- ✅ Go: github.com/vmihailenco/msgpack/v5

### Parte 4: Relógios
- ✅ Relógio lógico (Lamport) em todos os processos
- ✅ Serviço de referência (Go) para gerenciar ranks
- ✅ Sincronização de relógio físico (Algoritmo de Berkeley)
- ✅ Eleição de coordenador (menor rank)
- ✅ Heartbeat de servidores

### Parte 5: Consistência e Replicação
- ✅ Replicação de dados entre servidores
- ✅ Cada servidor possui sua própria cópia dos dados
- ✅ Replicação baseada em eventos via Pub/Sub
- ✅ Tópico "replication" para sincronização
- ✅ Prevenção de duplicatas e loops
- ✅ Eventual consistency

## Testes Automatizados

- ✅ Serviço de referência
- ✅ Status dos servidores
- ✅ Conexão do servidor
- ✅ Eleição de coordenador
- ✅ Bots em execução
- ✅ Mensagens dos bots
- ✅ Canais
- ✅ Relógio lógico
- ✅ Replicação de dados

## UI de Testes

- ✅ Interface visual para testes
- ✅ Execução via UI
- ✅ Resultados em tempo real
- ✅ Estatísticas e resumo
- ✅ Design moderno e profissional

