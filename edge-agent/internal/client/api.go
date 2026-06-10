package client

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
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

var ErrRevoked = errors.New("agent revoked: 401 Unauthorized from server")

// Soglia: dopo questo numero di 401 consecutivi l'agente si arrende davvero.
// I tentativi intermedi usano backoff esponenziale prima di riprovare.
const max401Attempts = 3

type agentState struct {
	AgentToken string `json:"agent_token"`
}

type EdgeClient struct {
	Config          *config.Config
	HTTPClient      *http.Client
	jwtToken        string
	consecutive401s int // contatore 401 consecutivi, resettato ad ogni risposta OK
}

func NewEdgeClient(cfg *config.Config) *EdgeClient {
	return &EdgeClient{
		Config: cfg,
		HTTPClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

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

	req, err := http.NewRequestWithContext(context.Background(), "POST", endpoint, bytes.NewBuffer(body))
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

// SendHeartbeat invia le metriche al backend con logica di backoff esponenziale
// sui 401. Solo dopo max401Attempts 401 consecutivi restituisce ErrRevoked.
// Su qualsiasi risposta OK il contatore viene azzerato.
func (c *EdgeClient) SendHeartbeat(ctx context.Context, payload *models.HeartbeatRequest) error {
	endpoint := fmt.Sprintf("%s/api/v1/agents/heartbeat", c.Config.BackendURL)

	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	req, err := http.NewRequestWithContext(ctx, "POST", endpoint, bytes.NewBuffer(body))
	if err != nil {
		return err
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.jwtToken)

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		if ctx.Err() != nil {
			return fmt.Errorf("request cancelled during shutdown: %w", ctx.Err())
		}
		return fmt.Errorf("network error: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusUnauthorized {
		c.consecutive401s++
		attempt := c.consecutive401s

		if attempt >= max401Attempts {
			// Tentativi esauriti: revoca confermata, segnaliamo al main di spegnersi.
			log.Printf("ERROR: 401 Unauthorized for %d consecutive attempts. Treating as revocation.", attempt)
			c.consecutive401s = 0
			return ErrRevoked
		}

		// Backoff esponenziale: 10s, 20s, 40s, ... (cap a 5 minuti)
		backoff := time.Duration(10*(1<<(attempt-1))) * time.Second
		if backoff > 5*time.Minute {
			backoff = 5 * time.Minute
		}

		log.Printf("WARN: 401 Unauthorized (attempt %d/%d). Possible transient error. Retrying in %v...",
			attempt, max401Attempts, backoff)

		// Aspettiamo il backoff rispettando il context: se arriva SIGTERM
		// durante l'attesa usciamo immediatamente senza loggare un falso errore.
		select {
		case <-time.After(backoff):
			// backoff completato, ritorniamo l'errore al ticker che ritenterà
			return fmt.Errorf("401 Unauthorized (attempt %d/%d, retrying after backoff)", attempt, max401Attempts)
		case <-ctx.Done():
			return fmt.Errorf("request cancelled during backoff: %w", ctx.Err())
		}
	}

	// Qualsiasi risposta non-401: azzeriamo il contatore.
	// Questo include anche i 5xx — un server in crash non è una revoca.
	c.consecutive401s = 0

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("server error (status %d): %s", resp.StatusCode, string(respBody))
	}

	// --- COMMAND & CONTROL (invariato) ---
	var hbResp models.HeartbeatResponse
	if err := json.NewDecoder(resp.Body).Decode(&hbResp); err != nil {
		return fmt.Errorf("failed to decode heartbeat response: %w", err)
	}

	if hbResp.Command != nil {
		log.Printf("INFO: Received command from Hub: %s", hbResp.Command.Action)

		switch hbResp.Command.Action {
		case "update_jwt":
			if newToken, ok := hbResp.Command.Payload["new_token"].(string); ok {
				c.jwtToken = newToken
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