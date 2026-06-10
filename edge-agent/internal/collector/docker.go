//go:build docker || linux
// (Nota: se usi i build tags, assicurati che siano presenti, altrimenti ignora questa riga)

package collector

import (
	"context"
	"strings"
	"sync"

	"github.com/docker/docker/api/types"
	"github.com/docker/docker/client"
	"github.com/avalab/edgehub-agent/internal/models"
)

var (
	// Variabili globali a livello di pacchetto per mantenere la connessione aperta
	dockerCli  *client.Client
	dockerErr  error
	dockerOnce sync.Once
)

// getDockerClient garantisce che il client venga inizializzato una sola volta (Singleton)
func getDockerClient() (*client.Client, error) {
	dockerOnce.Do(func() {
		dockerCli, dockerErr = client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
	})
	return dockerCli, dockerErr
}

// EnrichWithDocker aggiunge le metriche specifiche dei container al payload.
// Riceve ora il context per supportare il graceful shutdown.
func EnrichWithDocker(ctx context.Context, payload *models.HeartbeatRequest) {
	cli, err := getDockerClient()
	if err != nil {
		payload.ExtraData["docker_error"] = "Impossibile connettersi al demone Docker: " + err.Error()
		return
	}
	// ATTENZIONE: Abbiamo rimosso defer cli.Close()!
	// Il client ora vive finché vive l'agente.

	// Chiede a Docker la lista di TUTTI i container passando il context corretto
	containers, err := cli.ContainerList(ctx, types.ContainerListOptions{All: true})
	if err != nil {
		payload.ExtraData["docker_error"] = "Errore lettura container: " + err.Error()
		return
	}

	running := 0
	stopped := 0
	paused := 0

	var runningNames []string
	var stoppedNames []string

	// Categorizza i container in base al loro stato
	for _, c := range containers {
		// I nomi restituiti da Docker hanno uno slash iniziale (es. "/nginx"), lo puliamo
		name := ""
		if len(c.Names) > 0 {
			name = strings.TrimPrefix(c.Names[0], "/")
		}

		switch c.State {
		case "running":
			running++
			// Limitiamo a 10 per non esplodere il payload
			if name != "" && len(runningNames) < 10 {
				runningNames = append(runningNames, name)
			}
		case "exited", "dead", "created":
			stopped++
			// Limitiamo a 5 per i container fermi
			if name != "" && len(stoppedNames) < 5 {
				stoppedNames = append(stoppedNames, name)
			}
		case "paused":
			paused++
		}
	}

	// Inserisce i dati numerici di base
	payload.ExtraData["docker_total"] = len(containers)
	payload.ExtraData["docker_running"] = running
	payload.ExtraData["docker_stopped"] = stopped
	payload.ExtraData["docker_paused"] = paused

	// Inserisce i dati avanzati di osservabilità
	payload.ExtraData["docker_running_names"] = runningNames
	payload.ExtraData["docker_stopped_names"] = stoppedNames
	payload.ExtraData["docker_has_more"] = len(containers) > 10
}