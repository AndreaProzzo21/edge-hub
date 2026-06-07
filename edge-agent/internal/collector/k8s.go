package collector

import (
	"context"

	v1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"github.com/avalab/edgehub-agent/internal/models"
)

// EnrichWithK8s aggiunge le metriche del cluster al payload
func EnrichWithK8s(payload *models.HeartbeatRequest) {
	// InClusterConfig funziona "magicamente" quando l'agente gira dentro un Pod K8s
	config, err := rest.InClusterConfig()
	if err != nil {
		payload.ExtraData["k8s_error"] = "Non in esecuzione dentro un cluster K8s: " + err.Error()
		return
	}

	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		payload.ExtraData["k8s_error"] = "Errore creazione client K8s: " + err.Error()
		return
	}

	// 1. Lettura Versione Kubernetes
	versionInfo, err := clientset.Discovery().ServerVersion()
	if err == nil {
		payload.ExtraData["k8s_version"] = versionInfo.GitVersion
	}

	// 2. Lettura Nodi del Cluster
	nodes, err := clientset.CoreV1().Nodes().List(context.Background(), metav1.ListOptions{})
	if err == nil {
		payload.ExtraData["k8s_total_nodes"] = len(nodes.Items)
	}

	// 3. Analisi dei Pods (Tutti i Namespace)
	pods, err := clientset.CoreV1().Pods(metav1.NamespaceAll).List(context.Background(), metav1.ListOptions{})
	if err != nil {
		payload.ExtraData["k8s_error"] = "Errore lettura pods: " + err.Error()
		return
	}

	running := 0
	failing := 0
	pending := 0
	succeeded := 0

	var runningNames []string
	var failingNames []string

	// Categorizza i Pod in base al loro stato (Phase)
	for _, p := range pods.Items {
		// In K8s il namespace è fondamentale per identificare un Pod
		fullName := p.Namespace + "/" + p.Name

		switch p.Status.Phase {
		case v1.PodRunning:
			running++
			// Limitiamo a 10 per non esplodere il payload
			if len(runningNames) < 10 {
				runningNames = append(runningNames, fullName)
			}
		case v1.PodPending:
			pending++
			// Limitiamo a 5 per i Pods bloccati in pending (es. mancanza risorse/nodi)
			if len(failingNames) < 5 {
				failingNames = append(failingNames, fullName+" (Pending)")
			}
		case v1.PodFailed, v1.PodUnknown:
			failing++
			// Limitiamo a 5 per i Pods crashati/falliti
			if len(failingNames) < 5 {
				failingNames = append(failingNames, fullName+" (Failed)")
			}
		case v1.PodSucceeded:
			// Pods terminati con successo (es. Jobs completati)
			succeeded++
		}
	}

	// 4. Lettura Deployments
	deployments, err := clientset.AppsV1().Deployments(metav1.NamespaceAll).List(context.Background(), metav1.ListOptions{})
	depCount := 0
	if err == nil {
		depCount = len(deployments.Items)
	}

	// Compilazione Payload Extra
	payload.ExtraData["k8s_total_pods"] = len(pods.Items)
	payload.ExtraData["k8s_total_deployments"] = depCount
	
	// Metriche di Stato
	payload.ExtraData["k8s_pods_running"] = running
	payload.ExtraData["k8s_pods_pending"] = pending
	payload.ExtraData["k8s_pods_failing"] = failing
	payload.ExtraData["k8s_pods_succeeded"] = succeeded
	
	// Osservabilità Nomi (Troncata per sicurezza)
	payload.ExtraData["k8s_running_names"] = runningNames
	payload.ExtraData["k8s_failing_names"] = failingNames
	payload.ExtraData["k8s_has_more_pods"] = len(pods.Items) > 10
}