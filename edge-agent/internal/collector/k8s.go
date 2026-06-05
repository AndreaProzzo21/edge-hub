package collector

import (
	"context"

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

	// Legge tutti i Pod nel namespace in cui si trova l'agente (o in tutto il cluster se ha i permessi)
	// Qui usiamo metav1.NamespaceAll (tutti i namespace)
	pods, err := clientset.CoreV1().Pods(metav1.NamespaceAll).List(context.Background(), metav1.ListOptions{})
	podCount := 0
	if err == nil {
		podCount = len(pods.Items)
	}

	// Legge i Deployment
	deployments, err := clientset.AppsV1().Deployments(metav1.NamespaceAll).List(context.Background(), metav1.ListOptions{})
	depCount := 0
	if err == nil {
		depCount = len(deployments.Items)
	}

	payload.ExtraData["k8s_total_pods"] = podCount
	payload.ExtraData["k8s_total_deployments"] = depCount
}