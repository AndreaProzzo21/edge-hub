package client

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "log"
    "net/http"
    "os"
    "path/filepath"
    "time"

    "github.com/avalab/edgehub-agent/internal/config"
    "github.com/avalab/edgehub-agent/internal/models"
)

// Structure to save local state on disk
type agentState struct {
    AgentToken string `json:"agent_token"`
}

// EdgeClient handles all HTTP calls to the backend
type EdgeClient struct {
    Config     *config.Config
    HTTPClient *http.Client
    jwtToken   string
}

// NewEdgeClient initializes a new client
func NewEdgeClient(cfg *config.Config) *EdgeClient {
    return &EdgeClient{
        Config: cfg,
        HTTPClient: &http.Client{
            Timeout: 10 * time.Second,
        },
    }
}

// Init checks the state and registers the agent if necessary
func (c *EdgeClient) Init() {
    if c.loadState() {
        log.Println("INFO: Valid local state found. Skipping registration.")
        return
    }

    log.Println("INFO: No valid local state found. Starting node registration...")
    if c.Config.Token == "" {
        log.Fatalf("FATAL: EDGEHUB_TOKEN not provided and no valid state found. Cannot proceed.")
    }

    err := c.Register()
    if err != nil {
        log.Fatalf("FATAL: Error during registration: %v", err)
    }
}

// loadState attempts to read the JWT from the state file
func (c *EdgeClient) loadState() bool {
    data, err := os.ReadFile(c.Config.StateFile)
    if err != nil {
        return false
    }

    var state agentState
    if err := json.Unmarshal(data, &state); err != nil {
        log.Printf("WARN: State file is corrupted, proceeding with a new registration.")
        return false
    }

    if state.AgentToken != "" {
        c.jwtToken = state.AgentToken
        return true
    }
    return false
}

func (c *EdgeClient) saveState(token string) error {
    state := agentState{AgentToken: token}
    data, err := json.MarshalIndent(state, "", "  ")
    if err != nil {
        return err
    }

    dir := filepath.Dir(c.Config.StateFile)
    if err := os.MkdirAll(dir, 0755); err != nil {
        return fmt.Errorf("impossibile creare la directory di stato: %w", err)
    }

    return os.WriteFile(c.Config.StateFile, data, 0644)
}

// Register sends the registration request to the backend
func (c *EdgeClient) Register() error {
    endpoint := fmt.Sprintf("%s/api/v1/agents/register", c.Config.BackendURL)

    reqData := models.AgentRegisterRequest{
        RegistrationToken: c.Config.Token,
        Hostname:          c.Config.Hostname,
        Description:       c.Config.Description,
        AgentType:         c.Config.AgentType,
        AgentVersion:      c.Config.AgentVer,
        OS:                c.Config.OS,
        Arch:              c.Config.Arch,
    }

    body, err := json.Marshal(reqData)
    if err != nil {
        return fmt.Errorf("JSON encoding error: %w", err)
    }

    req, err := http.NewRequest("POST", endpoint, bytes.NewBuffer(body))
    if err != nil {
        return err
    }
    req.Header.Set("Content-Type", "application/json")

    resp, err := c.HTTPClient.Do(req)
    if err != nil {
        return fmt.Errorf("network error: %w", err)
    }
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusCreated {
        respBody, _ := io.ReadAll(resp.Body)
        return fmt.Errorf("server rejected registration (status %d): %s", resp.StatusCode, string(respBody))
    }

    var respData models.AgentRegisterResponse
    if err := json.NewDecoder(resp.Body).Decode(&respData); err != nil {
        return fmt.Errorf("response decoding error: %w", err)
    }

    c.jwtToken = respData.AgentToken
    if err := c.saveState(c.jwtToken); err != nil {
        return fmt.Errorf("failed to save local state: %w", err)
    }

    log.Printf("SUCCESS: Node successfully registered with ID: %s", respData.NodeID)
    return nil
}

// SendHeartbeat sends current metrics. Handles the 401 Unauthorized logic (Revocation).
func (c *EdgeClient) SendHeartbeat(payload *models.HeartbeatRequest) error {
    endpoint := fmt.Sprintf("%s/api/v1/agents/heartbeat", c.Config.BackendURL)

    body, err := json.Marshal(payload)
    if err != nil {
        return err
    }

    req, err := http.NewRequest("POST", endpoint, bytes.NewBuffer(body))
    if err != nil {
        return err
    }

    req.Header.Set("Content-Type", "application/json")
    req.Header.Set("Authorization", "Bearer "+c.jwtToken)

    resp, err := c.HTTPClient.Do(req)
    if err != nil {
        return fmt.Errorf("network error: %w", err)
    }
    defer resp.Body.Close()

    // REVOCATION LOGIC
    if resp.StatusCode == http.StatusUnauthorized {
        log.Fatalf("FATAL: 401 Unauthorized. Node has been revoked or deleted on the server. Agent stopped.")
    }

    if resp.StatusCode != http.StatusOK {
        respBody, _ := io.ReadAll(resp.Body)
        return fmt.Errorf("server error (status %d): %s", resp.StatusCode, string(respBody))
    }

    // --- NUOVA LOGICA: COMMAND & CONTROL ---
    // Decodifichiamo la risposta invece di ignorarla
    var hbResp models.HeartbeatResponse
    if err := json.NewDecoder(resp.Body).Decode(&hbResp); err != nil {
        return fmt.Errorf("failed to decode heartbeat response: %w", err)
    }

    // Controlliamo se c'è un comando pendente da eseguire
    if hbResp.Command != nil {
        log.Printf("INFO: Received command from Hub: %s", hbResp.Command.Action)
        
        switch hbResp.Command.Action {
        case "update_jwt":
            if newToken, ok := hbResp.Command.Payload["new_token"].(string); ok {
                // 1. Aggiorna in RAM per i prossimi heartbeat
                c.jwtToken = newToken
                // 2. Salva su disco per i futuri riavvii
                if err := c.saveState(newToken); err != nil {
                    log.Printf("ERROR: Failed to save new JWT to disk: %v", err)
                } else {
                    log.Println("SUCCESS: JWT successfully updated and saved to state file.")
                }
            } else {
                log.Println("ERROR: Received update_jwt command but payload 'new_token' is missing or invalid.")
            }
        default:
            log.Printf("WARN: Unknown command received: %s. Ignoring.", hbResp.Command.Action)
        }
    }
    return nil
}