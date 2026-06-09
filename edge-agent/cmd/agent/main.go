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

    // 1. Carica la configurazione
    cfg := config.Load()
    log.Printf("INFO: Agent Mode: %s | Hostname: %s | OS: %s/%s", cfg.AgentType, cfg.Hostname, cfg.OS, cfg.Arch)

    // 2. Inizializza il Client HTTP
    edgeClient := client.NewEdgeClient(cfg)
    edgeClient.Init() // Se fallisce, si ferma qui

    // 3. Imposta il Loop dell'Heartbeat
    interval := time.Duration(cfg.Interval) * time.Second
    ticker := time.NewTicker(interval)
    defer ticker.Stop()

    log.Printf("INFO: Entering heartbeat loop. Sending telemetry every %v...", interval)

    // Contatore in RAM (nessun I/O su disco)
    var heartbeatCount uint64 = 1

    // Invia il primissimo heartbeat immediatamente
    sendTelemetry(edgeClient, cfg.AgentType, heartbeatCount)

    // Loop infinito
    for range ticker.C {
        heartbeatCount++
        sendTelemetry(edgeClient, cfg.AgentType, heartbeatCount)
    }
}

// sendTelemetry orchestra la raccolta delle metriche e l'invio
// sendTelemetry orchestra la raccolta delle metriche e l'invio
func sendTelemetry(c *client.EdgeClient, mode string, count uint64) {
    payload := collector.CollectSystemMetrics(mode)

    if mode == "docker" {
        collector.EnrichWithDocker(payload)
    } else if mode == "kubernetes" || mode == "k8s" {
        collector.EnrichWithK8s(payload)
    }

    err := c.SendHeartbeat(payload)
    if err != nil {
        log.Printf("ERROR: Failed to send heartbeat (Attempt %d): %v", count, err)
    } else if count == 1 || count%20 == 0 {
        // Log di salute: stampato al primo avvio e poi ogni 20 cicli
        log.Printf("INFO: Agent healthy. Sent %d heartbeats successfully so far. [Next log in 20 cycles]", count)
    }
}