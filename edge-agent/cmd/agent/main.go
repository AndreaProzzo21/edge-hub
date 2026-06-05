package main

import (
	"log"
	"time"

	"github.com/avalab/edgehub-agent/internal/client"
	"github.com/avalab/edgehub-agent/internal/collector"
	"github.com/avalab/edgehub-agent/internal/config"
)

func main() {
	log.Println("INFO: Starting EdgeHub Agent...")

	// 1. Carica la configurazione (Env Vars + Auto-rilevamento OS/Arch)
	cfg := config.Load()
	log.Printf("INFO: Agent Mode: %s | Hostname: %s | OS: %s/%s", cfg.AgentType, cfg.Hostname, cfg.OS, cfg.Arch)

	// 2. Inizializza il Client HTTP (Gestisce Registrazione & Stato Locale)
	edgeClient := client.NewEdgeClient(cfg)
	edgeClient.Init() // Se la registrazione fallisce o manca il token, l'app si ferma qui

	// 3. Imposta il Loop dell'Heartbeat (es. ogni 30 secondi)
	interval := 30 * time.Second
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	log.Printf("INFO: Entering heartbeat loop. Sending telemetry every %v...", interval)

	// Invia il primissimo heartbeat immediatamente (senza aspettare i primi 30 secondi)
	sendTelemetry(edgeClient, cfg.AgentType)

	// Aspetta i "tick" del timer e invia i dati all'infinito
	for range ticker.C {
		sendTelemetry(edgeClient, cfg.AgentType)
	}
}

// sendTelemetry orchestra la raccolta delle metriche e l'invio al server
func sendTelemetry(c *client.EdgeClient, mode string) {
	// A. Raccoglie i dati hardware aggiornati in questo esatto momento (Base Universale)
	payload := collector.CollectSystemMetrics(mode)

	// B. Arricchisce i dati in base al tipo di deploy
	if mode == "docker" {
		collector.EnrichWithDocker(payload)
	} else if mode == "kubernetes" || mode == "k8s" {
		collector.EnrichWithK8s(payload)
	}

	// C. Invia al backend (con il JWT)
	err := c.SendHeartbeat(payload)
	if err != nil {
		log.Printf("ERROR: Failed to send heartbeat: %v", err)
	}
}