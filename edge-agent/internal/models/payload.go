package models

// Dati per la registrazione iniziale
type AgentRegisterRequest struct {
	RegistrationToken string `json:"registration_token"`
	Hostname          string `json:"hostname"`
	Description       string `json:"description,omitempty"`
	AgentType         string `json:"agent_type"`
	AgentVersion      string `json:"agent_version"`
	OS                string `json:"os"`
	Arch              string `json:"arch"`
}

// Risposta dal backend alla registrazione
type AgentRegisterResponse struct {
	NodeID     string `json:"node_id"`
	AgentToken string `json:"agent_token"`
}

// Il payload per l'Heartbeat periodico (esatta copia di HeartbeatRequest in Pydantic)
type HeartbeatRequest struct {
	CPUUsage      float64                `json:"cpu_usage"`
	MemoryUsage   float64                `json:"memory_usage"`
	DiskUsage     float64                `json:"disk_usage"`
	UptimeSeconds float64                `json:"uptime_seconds"` // Corretto in float64 per matchare Python
	IPAddress     string                 `json:"ip_address,omitempty"`
	ExtraData     map[string]interface{} `json:"extra_data,omitempty"`
}