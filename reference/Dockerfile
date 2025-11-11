FROM golang:1.21-alpine AS builder

# Habilita CGO explicitamente (necessário para zmq4)
ENV CGO_ENABLED=1

# Instala dependências de desenvolvimento do ZeroMQ
# O repositório community do Alpine já vem habilitado por padrão nas imagens golang
RUN apk update && \
    apk add --no-cache \
    zeromq-dev \
    gcc \
    g++ \
    musl-dev \
    pkgconfig \
    libc-dev \
    linux-headers

WORKDIR /app

# Copia go.mod primeiro (para cache do Docker)
COPY go.mod ./

# Copia código fonte (necessário para go mod tidy)
COPY . .

# Gera go.sum e baixa todas as dependências
# go mod tidy faz tudo: resolve dependências, gera go.sum, baixa pacotes
RUN go mod tidy

# Compila o programa
RUN go build -v -o reference reference.go

FROM alpine:latest

# Instala bibliotecas runtime do ZeroMQ (necessárias para executar o binário)
# zeromq = bibliotecas runtime
# libstdc++ = biblioteca C++ padrão
# ca-certificates = certificados SSL
RUN apk --no-cache add ca-certificates zeromq libstdc++

WORKDIR /app

COPY --from=builder /app/reference .

CMD ["./reference"]

