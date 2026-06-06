#!/usr/bin/env bash
# ==============================================================================
#  edge-agent  ·  Docker Compose Installer
# ==============================================================================
set -euo pipefail

# --- COLOUR PALETTE ---
C0='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'
BGREEN='\033[1;32m'
BCYAN='\033[1;36m'
WHITE='\033[1;37m'
GRAY='\033[0;90m'
BRED='\033[1;31m'

# --- CONSTANTS ---
INSTALL_DIR="/opt/edgehub"
ENV_FILE="${INSTALL_DIR}/.env"
COMPOSE_FILE="${INSTALL_DIR}/docker-compose.yml"
# Modifica questo URL con il link 'raw' esatto del tuo docker-compose.yml su GitHub
COMPOSE_URL="https://raw.githubusercontent.com/AndreaProzzo21/edge-hub/main/edge-agent/deploy/docker/docker-compose.yml"

# --- UI HELPERS ---
_step()   { echo -e "\n ${BCYAN}➜${C0}  $*"; }
_ok()     { echo -e " ${BGREEN}✔${C0}  $*"; }
_err()    { echo -e "\n ${BRED}✖${C0}  ${BRED}ERROR:${C0} $*\n"; exit 1; }

_prompt() {
  local prompt_text="$1"
  local default_val="${2:-}"
  if [[ -n "$default_val" ]]; then
    printf "  ${WHITE}%s${C0} ${GRAY}[%s]${C0}: " "$prompt_text" "$default_val"
  else
    printf "  ${WHITE}%s${C0}: " "$prompt_text"
  fi
  read -r REPLY
  [[ -z "$REPLY" && -n "$default_val" ]] && REPLY="$default_val"
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
echo -e "   ${WHITE}${BOLD}edge-agent${C0}  ${DIM}·${C0}  ${GRAY}Docker Compose Installer${C0}"
echo -e "   ${DIM}Deploys the EdgeHub monitoring agent as a Docker container${C0}\n"

# --- 1. CHECKS ---
if [[ $EUID -ne 0 ]]; then _err "This installer must be run as root (or via sudo)."; fi

_step "Checking prerequisites..."
if ! command -v docker >/dev/null 2>&1; then
  _err "Docker is not installed. Please install Docker first."
fi

if docker compose version >/dev/null 2>&1; then
  DOCKER_CMD="docker compose"
elif docker-compose version >/dev/null 2>&1; then
  DOCKER_CMD="docker-compose"
else
  _err "Docker Compose is not installed. Please install it first."
fi
_ok "Docker and ${DOCKER_CMD} found"

# --- 2. CONFIGURATION ---
_step "Configuration"
_prompt "Backend URL (e.g. https://api.edgehub.io)" ""
EDGEHUB_URL="$REPLY"

_prompt "Registration Token" ""
EDGEHUB_TOKEN="$REPLY"

_prompt "Node Name" ""
EDGEHUB_HOSTNAME="$REPLY"

_prompt "Node Description" "Docker Edge Node"
EDGEHUB_DESC="$REPLY"

# --- 3. WORKSPACE & DOWNLOAD ---
_step "Setting up workspace..."
mkdir -p "${INSTALL_DIR}/data"  # Cartella per montare il volume di stato
_ok "Workspace created at ${INSTALL_DIR}"

_step "Downloading docker-compose.yml..."
curl -# -fSL "${COMPOSE_URL}" -o "${COMPOSE_FILE}" || _err "Download failed. Check the COMPOSE_URL."
_ok "docker-compose.yml saved successfully"

# --- 4. CONFIGURATION FILE ---
_step "Generating configuration..."
cat > "${ENV_FILE}" <<EOF
EDGEHUB_URL=${EDGEHUB_URL}
EDGEHUB_TOKEN=${EDGEHUB_TOKEN}
EDGEHUB_HOSTNAME=${EDGEHUB_HOSTNAME}
EDGEHUB_DESCRIPTION=${EDGEHUB_DESC}
EDGEHUB_MODE=docker
EDGEHUB_STATE_FILE=/app/data/edgehub-state.json
EOF
chmod 600 "${ENV_FILE}"
_ok "Config saved to ${ENV_FILE}"

# --- 5. DEPLOYMENT ---
_step "Starting container..."
cd "${INSTALL_DIR}"
${DOCKER_CMD} up -d || _err "Failed to start the Docker container."
_ok "Container started"

# --- 6. DONE ---
echo -e "\n ${BGREEN}╔══════════════════════════════════════════════════════╗${C0}"
echo -e " ${BGREEN}║${C0}  ${BOLD}edge-agent deployed and running successfully!${C0}       ${BGREEN}║${C0}"
echo -e " ${BGREEN}╚══════════════════════════════════════════════════════╝${C0}\n"
echo -e "  ${DIM}Check status :${C0} cd ${INSTALL_DIR} && ${DOCKER_CMD} ps"
echo -e "  ${DIM}View logs    :${C0} cd ${INSTALL_DIR} && ${DOCKER_CMD} logs -f edge-agent"
echo -e "  ${DIM}Config file  :${C0} ${ENV_FILE}\n"