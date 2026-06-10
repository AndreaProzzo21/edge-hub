package collector

import (
	"context"
	"sync"

	v1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"

	"github.com/avalab/edgehub-agent/internal/models"
)

var (
	k8sClient *kubernetes.Clientset
	k8sErr    error
	k8sOnce   sync.Once
)

func getK8sClient() (*kubernetes.Clientset, error) {
	k8sOnce.Do(func() {
		config, err := rest.InClusterConfig()
		if err != nil {
			k8sErr = err
			return
		}
		k8sClient, k8sErr = kubernetes.NewForConfig(config)
	})
	return k8sClient, k8sErr
}

// EnrichWithK8s aggiunge le metriche del cluster al payload.
// Riceve il context per supportare il graceful shutdown.
func EnrichWithK8s(ctx context.Context, payload *models.HeartbeatRequest) {
	clientset, err := getK8sClient()
	if err != nil {
		payload.ExtraData["k8s_error"] = "Impossibile inizializzare il client K8s: " + err.Error()
		return
	}

	// 1. Versione Kubernetes (chiamata leggera, Discovery è cached dal client)
	versionInfo, err := clientset.Discovery().ServerVersion()
	if err == nil {
		payload.ExtraData["k8s_version"] = versionInfo.GitVersion
	}

	// 2. Nodi del Cluster
	nodes, err := clientset.CoreV1().Nodes().List(ctx, metav1.ListOptions{})
	if err == nil {
		payload.ExtraData["k8s_total_nodes"] = len(nodes.Items)
	}

	// 3. Pod — usiamo ResourceVersion="0" per leggere dalla cache dell'API server
	// invece di fare una query "live" al etcd. Fondamentale per cluster grandi.
	pods, err := clientset.CoreV1().Pods(metav1.NamespaceAll).List(ctx, metav1.ListOptions{
		ResourceVersion: "0",
	})
	if err != nil {
		payload.ExtraData["k8s_error"] = "Errore lettura pods: " + err.Error()
		return
	}

	running, failing, pending, succeeded := 0, 0, 0, 0
	var runningNames, failingNames []string

	for _, p := range pods.Items {
		fullName := p.Namespace + "/" + p.Name
		switch p.Status.Phase {
		case v1.PodRunning:
			running++
			if len(runningNames) < 10 {
				runningNames = append(runningNames, fullName)
			}
		case v1.PodPending:
			pending++
			if len(failingNames) < 5 {
				failingNames = append(failingNames, fullName+" (Pending)")
			}
		case v1.PodFailed, v1.PodUnknown:
			failing++
			if len(failingNames) < 5 {
				failingNames = append(failingNames, fullName+" (Failed)")
			}
		case v1.PodSucceeded:
			succeeded++
		}
	}

	// 4. Deployments — anche qui usiamo la cache
	deployments, err := clientset.AppsV1().Deployments(metav1.NamespaceAll).List(ctx, metav1.ListOptions{
		ResourceVersion: "0",
	})
	depCount := 0
	if err == nil {
		depCount = len(deployments.Items)
	}

	payload.ExtraData["k8s_total_pods"] = len(pods.Items)
	payload.ExtraData["k8s_total_deployments"] = depCount
	payload.ExtraData["k8s_pods_running"] = running
	payload.ExtraData["k8s_pods_pending"] = pending
	payload.ExtraData["k8s_pods_failing"] = failing
	payload.ExtraData["k8s_pods_succeeded"] = succeeded
	payload.ExtraData["k8s_running_names"] = runningNames
	payload.ExtraData["k8s_failing_names"] = failingNames
	payload.ExtraData["k8s_has_more_pods"] = len(pods.Items) > 10
}