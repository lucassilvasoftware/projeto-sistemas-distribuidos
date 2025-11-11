package main

import (
	"fmt"
	"log"
	"sync"
	"time"

	zmq "github.com/pebbe/zmq4"
	"github.com/vmihailenco/msgpack/v5"
)

type ServerInfo struct {
	Name      string    `json:"name"`
	Rank      int       `json:"rank"`
	LastSeen  time.Time `json:"last_seen"`
}

type Request struct {
	Service string                 `msgpack:"service"`
	Data    map[string]interface{} `msgpack:"data"`
}

type Response struct {
	Service string                 `msgpack:"service"`
	Data    map[string]interface{} `msgpack:"data"`
}

type ReferenceService struct {
	servers     map[string]*ServerInfo
	serversLock sync.RWMutex
	nextRank    int
	heartbeatTimeout time.Duration
}

func NewReferenceService() *ReferenceService {
	return &ReferenceService{
		servers:         make(map[string]*ServerInfo),
		nextRank:        1,
		heartbeatTimeout: 30 * time.Second,
	}
}

func (rs *ReferenceService) handleRank(req Request) Response {
	user, ok := req.Data["user"].(string)
	if !ok {
		return Response{
			Service: "rank",
			Data: map[string]interface{}{
				"status":    "erro",
				"timestamp": time.Now().Unix(),
				"description": "Campo 'user' inválido",
			},
		}
	}

	rs.serversLock.Lock()
	defer rs.serversLock.Unlock()

	rank := rs.nextRank
	rs.nextRank++

	rs.servers[user] = &ServerInfo{
		Name:     user,
		Rank:     rank,
		LastSeen: time.Now(),
	}

	log.Printf("[REF] Servidor '%s' registrado com rank %d", user, rank)

	return Response{
		Service: "rank",
		Data: map[string]interface{}{
			"rank":      rank,
			"timestamp": time.Now().Unix(),
			"clock":     0, // relógio lógico do serviço de referência
		},
	}
}

func (rs *ReferenceService) handleList(req Request) Response {
	rs.serversLock.RLock()
	defer rs.serversLock.RUnlock()

	now := time.Now()
	var activeServers []map[string]interface{}

	for name, info := range rs.servers {
		// Remove servidores que não enviaram heartbeat recentemente
		if now.Sub(info.LastSeen) > rs.heartbeatTimeout {
			continue
		}
		activeServers = append(activeServers, map[string]interface{}{
			"name": name,
			"rank": info.Rank,
		})
	}

	log.Printf("[REF] Lista de servidores solicitada: %d ativos", len(activeServers))

	return Response{
		Service: "list",
		Data: map[string]interface{}{
			"list":      activeServers,
			"timestamp": time.Now().Unix(),
			"clock":     0,
		},
	}
}

func (rs *ReferenceService) handleHeartbeat(req Request) Response {
	user, ok := req.Data["user"].(string)
	if !ok {
		return Response{
			Service: "heartbeat",
			Data: map[string]interface{}{
				"status":    "erro",
				"timestamp": time.Now().Unix(),
				"description": "Campo 'user' inválido",
			},
		}
	}

	rs.serversLock.Lock()
	defer rs.serversLock.Unlock()

	if info, exists := rs.servers[user]; exists {
		info.LastSeen = time.Now()
		log.Printf("[REF] Heartbeat recebido de '%s'", user)
	} else {
		log.Printf("[REF] Heartbeat de servidor não registrado: '%s'", user)
	}

	return Response{
		Service: "heartbeat",
		Data: map[string]interface{}{
			"timestamp": time.Now().Unix(),
			"clock":     0,
		},
	}
}

func (rs *ReferenceService) handleRequest(req Request) Response {
	log.Printf("[REF] Requisição recebida: service=%s", req.Service)

	switch req.Service {
	case "rank":
		return rs.handleRank(req)
	case "list":
		return rs.handleList(req)
	case "heartbeat":
		return rs.handleHeartbeat(req)
	default:
		return Response{
			Service: "error",
			Data: map[string]interface{}{
				"status":    "erro",
				"timestamp": time.Now().Unix(),
				"description": fmt.Sprintf("Serviço desconhecido: %s", req.Service),
			},
		}
	}
}

func (rs *ReferenceService) cleanupInactiveServers() {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		rs.serversLock.Lock()
		now := time.Now()
		for name, info := range rs.servers {
			if now.Sub(info.LastSeen) > rs.heartbeatTimeout {
				log.Printf("[REF] Removendo servidor inativo: %s (último visto há %v)", name, now.Sub(info.LastSeen))
				delete(rs.servers, name)
			}
		}
		rs.serversLock.Unlock()
	}
}

func main() {
	service := NewReferenceService()

	// Inicia limpeza de servidores inativos em background
	go service.cleanupInactiveServers()

	// Socket REP para receber requisições
	rep, err := zmq.NewSocket(zmq.REP)
	if err != nil {
		log.Fatal("Erro ao criar socket REP:", err)
	}
	defer rep.Close()

	err = rep.Bind("tcp://*:5559")
	if err != nil {
		log.Fatal("Erro ao fazer bind:", err)
	}

	log.Println("[REF] Serviço de referência iniciado em tcp://*:5559")

	for {
		// Recebe mensagem
		msg, err := rep.RecvBytes(0)
		if err != nil {
			log.Printf("[REF] Erro ao receber mensagem: %v", err)
			continue
		}

		// Decodifica MessagePack
		var req Request
		err = msgpack.Unmarshal(msg, &req)
		if err != nil {
			log.Printf("[REF] Erro ao decodificar MessagePack: %v", err)
			// Envia resposta de erro
			resp := Response{
				Service: "error",
				Data: map[string]interface{}{
					"status":    "erro",
					"timestamp": time.Now().Unix(),
					"description": "Erro ao decodificar mensagem",
				},
			}
			respBytes, _ := msgpack.Marshal(resp)
			_, err = rep.SendBytes(respBytes, 0)
			if err != nil {
				log.Printf("[REF] Erro ao enviar resposta de erro: %v", err)
			}
			continue
		}

		// Processa requisição
		resp := service.handleRequest(req)

		// Codifica e envia resposta
		respBytes, err := msgpack.Marshal(resp)
		if err != nil {
			log.Printf("[REF] Erro ao codificar resposta: %v", err)
			continue
		}

		_, err = rep.SendBytes(respBytes, 0)
		if err != nil {
			log.Printf("[REF] Erro ao enviar resposta: %v", err)
		}
	}
}

