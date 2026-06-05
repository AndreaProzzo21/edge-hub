package collector

import (
	"context"

	"github.com/docker/docker/api/types" // Modificato da api/types/container a api/types
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

	// Chiede a Docker la lista di TUTTI i container (anche quelli spenti) usando types.ContainerListOptions
	containers, err := cli.ContainerList(context.Background(), types.ContainerListOptions{All: true})
	if err != nil {
		payload.ExtraData["docker_error"] = "Errore lettura container: " + err.Error()
		return
	}

	running := 0
	stopped := 0
	paused := 0

	// Categorizza i container in base al loro stato
	for _, c := range containers {
		switch c.State {
		case "running":
			running++
		case "exited", "dead", "created":
			stopped++
		case "paused":
			paused++
		}
	}

	// Inserisce i dati puliti negli Extra Data
	payload.ExtraData["docker_total"] = len(containers)
	payload.ExtraData["docker_running"] = running
	payload.ExtraData["docker_stopped"] = stopped
	payload.ExtraData["docker_paused"] = paused
}