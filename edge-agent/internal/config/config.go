package config

import (
	"log"
	"os"
	"runtime"
	"strconv"
	"strings"
)

const AgentVersion = "1.0.0"

type Config struct {
	BackendURL  string
	Token       string
	StateFile   string
	Interval    int
	Hostname    string
	Description string
	AgentType   string
	AgentVer    string
	OS          string
	Arch        string
}

func Load() *Config {
	url := os.Getenv("EDGEHUB_URL")
	token := os.Getenv("EDGEHUB_TOKEN")
	stateFile := getEnvOrDefault("EDGEHUB_STATE_FILE", "edgehub-state.json")

	// Validazione URL — deve avere schema http:// o https://, altrimenti
	// il client HTTP va in panic con un errore incomprensibile per chi installa.
	if url == "" {
		log.Fatalf("FATAL: EDGEHUB_URL is required but not set.")
	}
	if !strings.HasPrefix(url, "http://") && !strings.HasPrefix(url, "https://") {
		log.Fatalf("FATAL: EDGEHUB_URL must start with http:// or https://. Got: %q", url)
	}
	// Rimuove lo slash finale se presente — evita double-slash negli endpoint
	// es. "https://backend.example.com/" + "/api/v1/..." → "https://backend.example.com/api/v1/..."
	url = strings.TrimRight(url, "/")

	agentType := strings.ToLower(getEnvOrDefault("EDGEHUB_MODE", "linux"))
	if agentType != "linux" && agentType != "docker" && agentType != "kubernetes" {
		log.Fatalf("FATAL: EDGEHUB_MODE must be 'linux', 'docker', or 'kubernetes'. Got: %q", agentType)
	}

	hostname := os.Getenv("EDGEHUB_HOSTNAME")
	if hostname == "" {
		sysHost, err := os.Hostname()
		if err != nil {
			hostname = "unknown-node"
		} else {
			hostname = sysHost
		}
	}

	description := os.Getenv("EDGEHUB_DESCRIPTION")
	osName := runtime.GOOS
	archName := runtime.GOARCH

	intervalStr := getEnvOrDefault("EDGEHUB_INTERVAL", "30")
	interval, err := strconv.Atoi(intervalStr)
	if err != nil || interval <= 0 {
		log.Printf("WARN: Invalid EDGEHUB_INTERVAL %q, falling back to 30s", intervalStr)
		interval = 30
	}

	return &Config{
		BackendURL:  url,
		Token:       token,
		StateFile:   stateFile,
		Interval:    interval,
		Hostname:    hostname,
		Description: description,
		AgentType:   agentType,
		AgentVer:    AgentVersion,
		OS:          osName,
		Arch:        archName,
	}
}

func getEnvOrDefault(key, defaultVal string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return defaultVal
}