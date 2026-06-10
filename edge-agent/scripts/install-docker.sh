#!/usr/bin/env bash
# ==============================================================================
#  Edge Agent  ·  Docker Compose Installer
# ==============================================================================
#
#  USAGE:
#    EDGEHUB_URL='https://api.edgehub.io' \
#    EDGEHUB_TOKEN='your-token' \
#    bash <(curl -sSL https://raw.githubusercontent.com/AndreaProzzo21/edge-hub/main/edge-agent/scripts/install-docker.sh)
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
INSTALL_DIR="/opt/edgehub"
ENV_FILE="${INSTALL_DIR}/.env"
COMPOSE_FILE="${INSTALL_DIR}/docker-compose.yml"

COMPOSE_URL="https://raw.githubusercontent.com/AndreaProzzo21/edge-hub/main/edge-agent/deploy/docker/docker-compose.yml"

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
echo -e "   ${WHITE}${BOLD}Edge Agent${C0}  ${DIM}·${C0}  ${GRAY}Docker Compose Installer${C0}"
echo -e "   ${DIM}Deploys the EdgeHub monitoring agent as a Docker container${C0}\n"

# --- 1. CHECKS ---
if [[ $EUID -ne 0 ]]; then _err "This installer must be run as root (or via sudo)."; fi

_step "Checking prerequisites..."

if ! command -v docker >/dev/null 2>&1; then
  _err "Docker is not installed. Please install Docker first: https://docs.docker.com/engine/install/"
fi

if docker compose version >/dev/null 2>&1; then
  DOCKER_CMD="docker compose"
elif docker-compose version >/dev/null 2>&1; then
  DOCKER_CMD="docker-compose"
else
  _err "Docker Compose is not installed. Please install it first: https://docs.docker.com/compose/install/"
fi
_ok "Docker and '${DOCKER_CMD}' found"

# Check Docker daemon is actually running
if ! docker info >/dev/null 2>&1; then
  _err "Docker daemon is not running. Start it with: systemctl start docker"
fi
_ok "Docker daemon is running"

# --- 2. CONFIGURATION ---
_step "Configuration"

if [[ -z "${EDGEHUB_URL:-}" ]]; then
  _prompt "Backend URL (e.g. https://api.edgehub.io)" ""
  EDGEHUB_URL="$REPLY"
  [[ -z "$EDGEHUB_URL" ]] && _err "Backend URL is required."
else
  _ok "Backend URL automatically applied: ${EDGEHUB_URL}"
fi

# Validazione schema URL — coerente con config.go e install-linux.sh
if [[ "$EDGEHUB_URL" != http://* && "$EDGEHUB_URL" != https://* ]]; then
  _err "Backend URL must start with http:// or https://. Got: ${EDGEHUB_URL}"
fi
# Rimuove slash finale per evitare double-slash negli endpoint
EDGEHUB_URL="${EDGEHUB_URL%/}"

if [[ -z "${EDGEHUB_TOKEN:-}" ]]; then
  _prompt "Registration Token" ""
  EDGEHUB_TOKEN="$REPLY"
  [[ -z "$EDGEHUB_TOKEN" ]] && _err "Registration Token is required."
else
  _ok "Registration Token automatically applied."
fi

_prompt "Node Name" "$(hostname)"
EDGEHUB_HOSTNAME="$REPLY"

_prompt "Node Description" "Docker Edge Node"
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
mkdir -p "${INSTALL_DIR}/data"
_ok "Workspace created at ${INSTALL_DIR}"

# --- 4. DOWNLOAD COMPOSE FILE ---
_step "Downloading docker-compose.yml..."
curl -# -fSL "${COMPOSE_URL}" -o "${COMPOSE_FILE}" || \
  _err "Download failed. Check your internet connection or the repository URL."
_ok "docker-compose.yml saved to ${COMPOSE_FILE}"

# --- 5. CONFIGURATION FILE ---
_step "Generating configuration..."
cat > "${ENV_FILE}" <<EOF
EDGEHUB_URL=${EDGEHUB_URL}
EDGEHUB_TOKEN=${EDGEHUB_TOKEN}
EDGEHUB_HOSTNAME=${EDGEHUB_HOSTNAME}
EDGEHUB_DESCRIPTION=${EDGEHUB_DESC}
EDGEHUB_INTERVAL=${EDGEHUB_INTERVAL}
EDGEHUB_MODE=docker
EDGEHUB_STATE_FILE=/app/data/edgehub-state.json
EOF
chmod 600 "${ENV_FILE}"
_ok "Config saved to ${ENV_FILE} (permissions: 600)"

# --- 6. DEPLOYMENT ---
_step "Pulling image and starting container..."
cd "${INSTALL_DIR}"
${DOCKER_CMD} pull aprozzo/edgehub-agent:latest 2>&1 | tail -1
${DOCKER_CMD} up -d || _err "Failed to start the container. Run '${DOCKER_CMD} logs' for details."
_ok "Container started"

# Breve attesa e verifica che il container sia ancora in piedi
sleep 3
if ! docker ps --filter "name=edgehub-agent" --filter "status=running" | grep -q edgehub-agent; then
  _warn "Container started but exited immediately. Check logs:"
  echo ""
  ${DOCKER_CMD} logs --tail 20
  echo ""
  _err "Deployment failed. See logs above."
fi
_ok "Container is running"

# --- 7. DONE ---
echo -e "\n ${BGREEN}╔══════════════════════════════════════════════════════╗${C0}"
echo -e " ${BGREEN}║${C0}  ${BOLD}Edge Agent deployed and running successfully!${C0}       ${BGREEN}║${C0}"
echo -e " ${BGREEN}╚══════════════════════════════════════════════════════╝${C0}\n"
echo -e "  ${DIM}Check status :${C0}  cd ${INSTALL_DIR} && ${DOCKER_CMD} ps"
echo -e "  ${DIM}View logs    :${C0}  cd ${INSTALL_DIR} && ${DOCKER_CMD} logs -f edgehub-agent"
echo -e "  ${DIM}Update agent :${C0}  cd ${INSTALL_DIR} && ${DOCKER_CMD} pull && ${DOCKER_CMD} up -d"
echo -e "  ${DIM}Config file  :${C0}  ${ENV_FILE}"
echo -e "  ${DIM}State file   :${C0}  ${INSTALL_DIR}/data/edgehub-state.json\n"