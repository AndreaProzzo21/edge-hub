package collector

import (
	"context"
	"strings"

	"github.com/docker/docker/api/types" // Ripristinato l'import corretto per la tua versione
	"github.com/docker/docker/client"
	"github.com/avalab/edgehub-agent/internal/models"
)

// EnrichWithDocker aggiunge le metriche specifiche dei container al payload
func EnrichWithDocker(payload *models.HeartbeatRequest) {
	// Crea un client Docker leggendo l'ambiente (es. /var/run/docker.sock)
	cli, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
	if err != nil {
		payload.ExtraData["docker_error"] = "Impossibile connettersi al demone Docker: " + err.Error()
		return
	}
	defer cli.Close()

	// Chiede a Docker la lista di TUTTI i container usando types.ContainerListOptions
	containers, err := cli.ContainerList(context.Background(), types.ContainerListOptions{All: true})
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
			// Raccogliamo i nomi dei container attivi (limite 10 per non esplodere il payload)
			if name != "" && len(runningNames) < 10 {
				runningNames = append(runningNames, name)
			}
		case "exited", "dead", "created":
			stopped++
			// Raccogliamo i nomi dei container fermi (fondamentale per il troubleshooting, limite 5)
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