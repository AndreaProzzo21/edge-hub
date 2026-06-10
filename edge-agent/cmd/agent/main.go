package main

import (
	"context"
	"errors"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/avalab/edgehub-agent/internal/client"
	"github.com/avalab/edgehub-agent/internal/collector"
	"github.com/avalab/edgehub-agent/internal/config"
)

func main() {
	log.Println("INFO: Starting EdgeHub Agent...")

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		sig := <-sigCh
		log.Printf("INFO: Received signal %v. Initiating graceful shutdown...", sig)
		cancel()
	}()

	cfg := config.Load()
	log.Printf("INFO: Agent Mode: %s | Hostname: %s | OS: %s/%s", cfg.AgentType, cfg.Hostname, cfg.OS, cfg.Arch)

	edgeClient := client.NewEdgeClient(cfg)
	edgeClient.Init()

	interval := time.Duration(cfg.Interval) * time.Second
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	log.Printf("INFO: Entering heartbeat loop. Sending telemetry every %v...", interval)

	var heartbeatCount uint64 = 1
	sendTelemetry(ctx, cancel, edgeClient, cfg.AgentType, heartbeatCount)

	for {
		select {
		case <-ctx.Done():
			log.Println("INFO: EdgeHub Agent stopped cleanly.")
			return
		case <-ticker.C:
			heartbeatCount++
			sendTelemetry(ctx, cancel, edgeClient, cfg.AgentType, heartbeatCount)
		}
	}
}

func sendTelemetry(ctx context.Context, cancel context.CancelFunc, c *client.EdgeClient, mode string, count uint64) {
	if ctx.Err() != nil {
		return
	}

	payload := collector.CollectSystemMetrics(mode)

	if mode == "docker" {
		collector.EnrichWithDocker(ctx, payload)
	} else if mode == "kubernetes" || mode == "k8s" {
		collector.EnrichWithK8s(ctx, payload)
	}

	err := c.SendHeartbeat(ctx, payload)
	if err != nil {
		if errors.Is(err, client.ErrRevoked) {
			log.Println("FATAL: Node has been revoked on the server. Shutting down cleanly.")
			cancel()
			return
		}
		log.Printf("ERROR: Failed to send heartbeat (Attempt %d): %v", count, err)
	} else if count == 1 || count%20 == 0 {
		log.Printf("INFO: Agent healthy. Sent %d heartbeats successfully so far. [Next log in 20 cycles]", count)
	}
}