# Serviço de Referência (Go)

Serviço de referência implementado em Go para gerenciar ranks e heartbeats dos servidores.

## Problemas Comuns de Build

### Erro: "missing go.sum entry"

Isso é normal na primeira vez. O `go mod tidy` no Dockerfile gera o `go.sum` automaticamente.

### Erro: "failed to solve" ou erro de compilação

Se o build falhar com Alpine, tente usar a versão Debian:

1. Edite `docker-compose.yml`
2. Na seção `reference`, descomente a linha:
   ```yaml
   dockerfile: Dockerfile.debian
   ```
3. Execute `docker compose build reference` novamente

### Alpine vs Debian

- **Alpine**: Imagem menor, mas pode ter problemas com pacotes C
- **Debian**: Mais compatível, imagem maior, mas geralmente mais confiável para CGO

## Testando Localmente

Para testar o build localmente:

```bash
cd reference
docker build -t reference-test .
```

Se falhar, tente:

```bash
docker build -f Dockerfile.debian -t reference-test .
```

