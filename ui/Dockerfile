FROM node:18-alpine

# Instala Docker CLI para executar testes via docker exec
RUN apk add --no-cache docker-cli

WORKDIR /app

COPY package.json .
RUN npm install

COPY public ./public
COPY server.js .

EXPOSE 8080
CMD ["node", "server.js"]