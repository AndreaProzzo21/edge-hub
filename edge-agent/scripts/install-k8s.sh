#!/usr/bin/env bash
# ==============================================================================
#  Edge Agent  ·  Kubernetes Installer
# ==============================================================================
#
#  USAGE:
#    EDGEHUB_URL='https://api.edgehub.io' \
#    EDGEHUB_TOKEN='your-token' \
#    bash <(curl -sSL https://raw.githubusercontent.com/AndreaProzzo21/edge-hub/main/edge-agent/scripts/install-k8s.sh)
#
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

K8S_VERSION=$(kubectl version --short 2>/dev/null | grep "Server" | awk '{print $3}' || echo "unknown")
_ok "Connected to Kubernetes cluster (server: ${K8S_VERSION})"

# --- 2. CONFIGURATION ---
_step "Configuration"

_prompt "Namespace to deploy into" "edgehub-system"
EDGEHUB_NAMESPACE="$REPLY"

if [[ -z "${EDGEHUB_URL:-}" ]]; then
  _prompt "Backend URL (e.g. https://api.edgehub.io)" ""
  EDGEHUB_URL="$REPLY"
  [[ -z "$EDGEHUB_URL" ]] && _err "Backend URL is required."
else
  _ok "Backend URL automatically applied: ${EDGEHUB_URL}"
fi

# Validazione schema URL — coerente con config.go e gli altri installer
if [[ "$EDGEHUB_URL" != http://* && "$EDGEHUB_URL" != https://* ]]; then
  _err "Backend URL must start with http:// or https://. Got: ${EDGEHUB_URL}"
fi
EDGEHUB_URL="${EDGEHUB_URL%/}"

if [[ -z "${EDGEHUB_TOKEN:-}" ]]; then
  _prompt "Registration Token" ""
  EDGEHUB_TOKEN="$REPLY"
  [[ -z "$EDGEHUB_TOKEN" ]] && _err "Registration Token is required."
else
  _ok "Registration Token automatically applied."
fi

_prompt "Node Name (identifier for this cluster)" "k8s-cluster-01"
EDGEHUB_HOSTNAME="$REPLY"

_prompt "Node Description" "Kubernetes Main Cluster"
EDGEHUB_DESC="$REPLY"

_prompt "Heartbeat Interval in seconds (10–90)" "30"
EDGEHUB_INTERVAL="$REPLY"
if ! [[ "$EDGEHUB_INTERVAL" =~ ^[0-9]+$ ]] || \
   [[ "$EDGEHUB_INTERVAL" -lt 10 ]] || \
   [[ "$EDGEHUB_INTERVAL" -gt 90 ]]; then
  _warn "Invalid interval '${EDGEHUB_INTERVAL}', falling back to 30s."
  EDGEHUB_INTERVAL="30"
fi

# --- 3. WORKSPACE ---
_step "Setting up workspace..."
mkdir -p "${INSTALL_DIR}"
_ok "Workspace created at ${INSTALL_DIR}"

# --- 4. DOWNLOAD & PATCH MANIFEST ---
_step "Downloading Kubernetes manifest..."
curl -# -fSL "${MANIFEST_URL}" -o "${MANIFEST_FILE}" || \
  _err "Download failed. Check your internet connection or the repository URL."

# Sostituisce il placeholder del namespace nel manifest scaricato
sed -i "s/EDGEHUB_NAMESPACE_PLACEHOLDER/${EDGEHUB_NAMESPACE}/g" "${MANIFEST_FILE}"
_ok "Manifest saved to ${MANIFEST_FILE}"

# --- 5. GENERATE SECRET ---
_step "Generating Kubernetes Secret..."

B64_URL=$(echo -n "$EDGEHUB_URL"      | base64 | tr -d '\n')
B64_TOKEN=$(echo -n "$EDGEHUB_TOKEN"  | base64 | tr -d '\n')
B64_HOST=$(echo -n "$EDGEHUB_HOSTNAME"| base64 | tr -d '\n')
B64_DESC=$(echo -n "$EDGEHUB_DESC"    | base64 | tr -d '\n')
B64_INT=$(echo -n "$EDGEHUB_INTERVAL" | base64 | tr -d '\n')
B64_MODE=$(echo -n "kubernetes"       | base64 | tr -d '\n')
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
  EDGEHUB_HOSTNAME: ${B64_HOST}
  EDGEHUB_DESCRIPTION: ${B64_DESC}
  EDGEHUB_INTERVAL: ${B64_INT}
  EDGEHUB_MODE: ${B64_MODE}
  EDGEHUB_STATE_FILE: ${B64_STATE}
EOF
_ok "Secret manifest generated at ${SECRET_FILE}"

# --- 6. APPLY NAMESPACE + SECRET ---
_step "Applying namespace and configuration secret..."

kubectl create namespace "${EDGEHUB_NAMESPACE}" --dry-run=client -o yaml \
  | kubectl apply -f - >/dev/null
_ok "Namespace '${EDGEHUB_NAMESPACE}' ensured"

kubectl apply -f "${SECRET_FILE}" >/dev/null
_ok "Configuration Secret applied (token stored securely in cluster)"

# --- 7. REVIEW & CONFIRM ---
echo -e "\n ${BCYAN}➜${C0}  Manifest ready for review\n"
echo -e "  ${GRAY}The manifest has been downloaded and configured but${C0} ${WHITE}not yet applied${C0}${GRAY}.${C0}"
echo -e "  ${GRAY}Review it before deploying:${C0}\n"
echo -e "    ${WHITE}cat ${MANIFEST_FILE}${C0}\n"

_prompt "Apply the manifest now and start the agent? [y/N]" "N"
if [[ "${REPLY,,}" != "y" ]]; then
  echo ""
  echo -e "  ${CYAN}ℹ${C0}  ${GRAY}No problem — apply it manually when ready:${C0}"
  echo ""
  echo -e "    ${WHITE}kubectl apply -f ${MANIFEST_FILE} -n ${EDGEHUB_NAMESPACE}${C0}"
  echo ""
  exit 0
fi

# --- 8. APPLY DEPLOYMENT ---
_step "Applying agent deployment..."
kubectl apply -f "${MANIFEST_FILE}" -n "${EDGEHUB_NAMESPACE}" >/dev/null
_ok "Agent Deployment applied"

_step "Waiting for Pod to become ready..."
kubectl rollout status deployment/edgehub-agent \
  -n "${EDGEHUB_NAMESPACE}" --timeout=60s || \
  _warn "Pod not ready within 60s — check with: kubectl get pods -n ${EDGEHUB_NAMESPACE}"

# --- 9. DONE ---
echo -e "\n ${BGREEN}╔══════════════════════════════════════════════════════╗${C0}"
echo -e " ${BGREEN}║${C0}  ${BOLD}Edge Agent deployed to Kubernetes successfully!${C0}     ${BGREEN}║${C0}"
echo -e " ${BGREEN}║${C0}  ${DIM}Review the manifest anytime — it's yours to own.${C0}   ${BGREEN}║${C0}"
echo -e " ${BGREEN}╚══════════════════════════════════════════════════════╝${C0}\n"
echo -e "  ${DIM}Check Pods   :${C0}  kubectl get pods -n ${EDGEHUB_NAMESPACE}"
echo -e "  ${DIM}View logs    :${C0}  kubectl logs -f deployment/edgehub-agent -n ${EDGEHUB_NAMESPACE}"
echo -e "  ${DIM}Update agent :${C0}  kubectl rollout restart deployment/edgehub-agent -n ${EDGEHUB_NAMESPACE}"
echo -e "  ${DIM}Remove agent :${C0}  kubectl delete -f ${MANIFEST_FILE} -n ${EDGEHUB_NAMESPACE}"
echo -e "  ${DIM}Local files  :${C0}  ${INSTALL_DIR}\n"