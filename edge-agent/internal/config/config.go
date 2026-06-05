package config

import (
	"log"
	"os"
	"runtime"
	"strings"
)

// Define the agent version here (can be injected via CI/CD later)
const AgentVersion = "1.0.0"

// Config contains all settings and node metadata
type Config struct {
	BackendURL  string
	Token       string
	StateFile   string // Where we save the JWT to survive reboots
	
	// Registration metadata (aligned with Pydantic Model)
	Hostname    string
	Description string
	AgentType   string
	AgentVer    string
	OS          string
	Arch        string
}

// Load reads environment variables and auto-detects system data
func Load() *Config {
	// 1. Base connection variables
	url := os.Getenv("EDGEHUB_URL")
	token := os.Getenv("EDGEHUB_TOKEN") // Mandatory only for first registration
	stateFile := getEnvOrDefault("EDGEHUB_STATE_FILE", "edgehub-state.json")

	// 2. Agent Type detection (Mode)
	agentType := strings.ToLower(getEnvOrDefault("EDGEHUB_MODE", "linux"))
	if agentType != "linux" && agentType != "docker" && agentType != "kubernetes" {
		log.Fatalf("FATAL ERROR: EDGEHUB_MODE must be 'linux', 'docker', or 'kubernetes'. Received: %s", agentType)
	}

	// 3. Hostname detection
	hostname := os.Getenv("EDGEHUB_HOSTNAME")
	if hostname == "" {
		sysHost, err := os.Hostname()
		if err != nil {
			hostname = "unknown-node"
		} else {
			hostname = sysHost
		}
	}

	// 4. Optional description
	description := os.Getenv("EDGEHUB_DESCRIPTION")

	// 5. OS and Architecture detection
	osName := runtime.GOOS     // e.g., "linux", "windows", "darwin"
	archName := runtime.GOARCH // e.g., "amd64", "arm64"

	return &Config{
		BackendURL:  url,
		Token:       token,
		StateFile:   stateFile,
		Hostname:    hostname,
		Description: description,
		AgentType:   agentType,
		AgentVer:    AgentVersion,
		OS:          osName,
		Arch:        archName,
	}
}

// Helper to read an env var or fallback to a default value
func getEnvOrDefault(key, defaultVal string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return defaultVal
}