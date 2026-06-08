#!/usr/bin/env bash
# ==============================================================================
#  Edge Agent  ·  Kubernetes Installer
# ==============================================================================
set -euo pipefail

# --- COLOUR PALETTE ---
C0='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'
BGREEN='\033[1;32m'
BCYAN='\033[1;36m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
GRAY='\033[0;90m'
BRED='\033[1;31m'
YELLOW='\033[0;33m'

# --- CONSTANTS ---
INSTALL_DIR="${HOME}/.edgehub-k8s"
SECRET_FILE="${INSTALL_DIR}/edgehub-secret.yaml"
MANIFEST_FILE="${INSTALL_DIR}/edgehub-agent.yaml"

# Update this URL with the exact 'raw' link to your agent Kubernetes manifest on GitHub
# The remote manifest should contain: ServiceAccount, ClusterRole, ClusterRoleBinding, Deployment, PVC
MANIFEST_URL="https://raw.githubusercontent.com/AndreaProzzo21/edge-hub/main/edge-agent/deploy/k8s/edgehub-agent.yaml"

# --- UI HELPERS ---
_step()   { echo -e "\n ${BCYAN}➜${C0}  $*"; }
_ok()     { echo -e " ${BGREEN}✔${C0}  $*"; }
_info()   { echo -e " ${CYAN}ℹ${C0}  ${GRAY}$*${C0}"; }
_warn()   { echo -e " ${YELLOW}⚠${C0}  ${YELLOW}$*${C0}"; }
_err()    { echo -e "\n ${BRED}✖${C0}  ${BRED}ERROR:${C0} $*\n"; exit 1; }

_prompt() {
  local prompt_text="$1"
  local default_val="${2:-}"
  if [[ -n "$default_val" ]]; then
    printf "  ${WHITE}%s${C0} ${GRAY}[%s]${C0}: " "$prompt_text" "$default_val"
  else
    printf "  ${WHITE}%s${C0}: " "$prompt_text"
  fi
  
  REPLY=""
  read -r REPLY < /dev/tty || true

  if [[ -z "$REPLY" && -n "$default_val" ]]; then
    REPLY="$default_val"
  fi
}

# --- HEADER ---
clear
echo -e "${BGREEN}"
echo "   ███████╗██████╗  ██████╗ ███████╗██╗  ██╗██╗   ██╗██████╗ "
echo "   ██╔════╝██╔══██╗██╔════╝ ██╔════╝██║  ██║██║   ██║██╔══██╗"
echo "   █████╗  ██║  ██║██║  ███╗█████╗  ███████║██║   ██║██████╔╝"
echo "   ██╔══╝  ██║  ██║██║   ██║██╔══╝  ██╔══██║██║   ██║██╔══██╗"
echo "   ███████╗██████╔╝╚██████╔╝███████╗██║  ██║╚██████╔╝██████╔╝"
echo "   ╚══════╝╚═════╝  ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝"
echo -e "${C0}"
echo -e "   ${WHITE}${BOLD}Edge Agent${C0}  ${DIM}·${C0}  ${GRAY}Kubernetes Installer${C0}"
echo -e "   ${DIM}Deploys the EdgeHub monitoring agent to a Kubernetes cluster${C0}\n"

# --- 1. CHECKS ---
_step "Checking prerequisites..."
if ! command -v kubectl >/dev/null 2>&1; then
  _err "kubectl is not installed or not in PATH."
fi
_ok "kubectl found"

if ! kubectl get nodes >/dev/null 2>&1; then
  _err "Unable to connect to the Kubernetes cluster. Check your kubeconfig."
fi
_ok "Connected to Kubernetes cluster"

# --- 2. CONFIGURATION ---
_step "Configuration"
_prompt "Namespace to deploy into" "edgehub-system"
EDGEHUB_NAMESPACE="$REPLY"

# Controllo dinamico per EDGEHUB_URL
if [[ -z "${EDGEHUB_URL:-}" ]]; then
  _prompt "Backend URL (e.g. https://api.edgehub.io)" ""
  EDGEHUB_URL="$REPLY"
else
  _ok "Backend URL automatically applied: ${EDGEHUB_URL}"
fi

# Controllo dinamico per EDGEHUB_TOKEN
if [[ -z "${EDGEHUB_TOKEN:-}" ]]; then
  _prompt "Registration Token" ""
  EDGEHUB_TOKEN="$REPLY"
else
  _ok "Registration Token automatically applied."
fi

_prompt "Node Name (Identifier for the Cluster)" "k8s-cluster-01"
EDGEHUB_HOSTNAME="$REPLY"

_prompt "Node Description" "Kubernetes Main Cluster"
EDGEHUB_DESC="$REPLY"

_prompt "Heartbeat Interval (seconds: max 90)" "30"
EDGEHUB_INTERVAL="$REPLY"

# --- 3. WORKSPACE & DOWNLOAD ---
_step "Setting up workspace..."
mkdir -p "${INSTALL_DIR}"
_ok "Workspace created at ${INSTALL_DIR}"

_step "Downloading Kubernetes manifest..."
curl -# -fSL "${MANIFEST_URL}" -o "${MANIFEST_FILE}" || _err "Download failed. Check the MANIFEST_URL."
_ok "edgehub-agent.yaml saved successfully"

# --- 4. CONFIGURATION FILE (K8S SECRET) ---
_step "Generating Kubernetes Secret..."
# Base64 encode values safely (tr -d '\n' prevents line break issues)
B64_URL=$(echo -n "$EDGEHUB_URL" | base64 | tr -d '\n')
B64_TOKEN=$(echo -n "$EDGEHUB_TOKEN" | base64 | tr -d '\n')
B64_HOSTNAME=$(echo -n "$EDGEHUB_HOSTNAME" | base64 | tr -d '\n')
B64_DESC=$(echo -n "$EDGEHUB_DESC" | base64 | tr -d '\n')
B64_INTERVAL=$(echo -n "$EDGEHUB_INTERVAL" | base64 | tr -d '\n')
B64_MODE=$(echo -n "kubernetes" | base64 | tr -d '\n')
B64_STATE=$(echo -n "/data/edgehub-state.json" | base64 | tr -d '\n')

cat > "${SECRET_FILE}" <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: edgehub-agent-config
  namespace: ${EDGEHUB_NAMESPACE}
type: Opaque
data:
  EDGEHUB_URL: ${B64_URL}
  EDGEHUB_TOKEN: ${B64_TOKEN}
  EDGEHUB_HOSTNAME: ${B64_HOSTNAME}
  EDGEHUB_DESCRIPTION: ${B64_DESC}
  EDGEHUB_INTERVAL: ${B64_INTERVAL}
  EDGEHUB_MODE: ${B64_MODE}
  EDGEHUB_STATE_FILE: ${B64_STATE}
EOF
_ok "Secret manifest generated"

# --- 5. DEPLOYMENT ---
_step "Deploying to Kubernetes..."

# Create namespace if it doesn't exist
kubectl create namespace "${EDGEHUB_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
_ok "Namespace '${EDGEHUB_NAMESPACE}' ensured"

# Apply Secret
kubectl apply -f "${SECRET_FILE}" >/dev/null || _err "Failed to apply Secret."
_ok "Configuration Secret applied"

# Apply Manifest
kubectl apply -f "${MANIFEST_FILE}" -n "${EDGEHUB_NAMESPACE}" >/dev/null || _err "Failed to apply Deployment."
_ok "Agent Deployment applied"

# --- 6. DONE ---
echo -e "\n ${BGREEN}╔══════════════════════════════════════════════════════╗${C0}"
echo -e " ${BGREEN}║${C0}  ${BOLD}Edge Agent deployed to K8s successfully!${C0}            ${BGREEN}║${C0}"
echo -e " ${BGREEN}╚══════════════════════════════════════════════════════╝${C0}\n"
echo -e "  ${DIM}Check Pods   :${C0} kubectl get pods -n ${EDGEHUB_NAMESPACE}"
echo -e "  ${DIM}View logs    :${C0} kubectl logs -f deployment/edgehub-agent -n ${EDGEHUB_NAMESPACE}"
echo -e "  ${DIM}Local files  :${C0} ${INSTALL_DIR}\n"