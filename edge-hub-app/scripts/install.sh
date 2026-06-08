#!/usr/bin/env bash
# ==============================================================================
#  EdgeHub  ·  Server Installer (Docker Compose)
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
INSTALL_DIR="/opt/edgehub-server"
ENV_FILE="${INSTALL_DIR}/.env"
COMPOSE_FILE="${INSTALL_DIR}/docker-compose.yml"

# Update these URLs with the exact 'raw' links to your files on GitHub
COMPOSE_URL="https://raw.githubusercontent.com/AndreaProzzo21/edge-hub/main/edge-hub-app/deploy/docker-compose.yml"
ENV_EXAMPLE_URL="https://raw.githubusercontent.com/AndreaProzzo21/edge-hub/main/edge-hub-app/deploy/.env.example"

# --- UI HELPERS ---
_step()   { echo -e "\n ${BCYAN}➜${C0}  $*"; }
_ok()     { echo -e " ${BGREEN}✔${C0}  $*"; }
_info()   { echo -e " ${BCYAN}ℹ${C0}  ${GRAY}$*${C0}"; }
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
echo -e "   ${WHITE}${BOLD}EdgeHub Server${C0}  ${DIM}·${C0}  ${GRAY}Master Node Installer${C0}"
echo -e "   ${DIM}Deploys the Dashboard, Backend API, and Database via Docker${C0}\n"

# --- 1. CHECKS ---
if [[ $EUID -ne 0 ]]; then _err "This installer must be run as root (or via sudo)."; fi

_step "Checking prerequisites..."
if ! command -v docker >/dev/null 2>&1; then _err "Docker is not installed."; fi
if docker compose version >/dev/null 2>&1; then
  DOCKER_CMD="docker compose"
elif docker-compose version >/dev/null 2>&1; then
  DOCKER_CMD="docker-compose"
else
  _err "Docker Compose is not installed."
fi
_ok "Docker and ${DOCKER_CMD} found"

# --- 2. WORKSPACE & DOWNLOADS ---
_step "Setting up workspace..."
mkdir -p "${INSTALL_DIR}"
_ok "Workspace created at ${INSTALL_DIR}"

_step "Downloading files from GitHub..."
curl -# -fSL "${COMPOSE_URL}" -o "${COMPOSE_FILE}" || _err "Download failed for docker-compose.yml. Check the URL."
_ok "docker-compose.yml downloaded successfully"

curl -# -fSL "${ENV_EXAMPLE_URL}" -o "${INSTALL_DIR}/.env.example" || _err "Download failed for .env.example. Check the URL."
_ok ".env.example downloaded successfully"

# --- 3. CONFIGURATION PROMPTS ---
_step "Network & Exposure"
_info "Which domain or IP will you use to access the Dashboard?"
_info "This sets the CORS policy. Examples: https://hub.mydomain.com or http://192.168.1.10"
_prompt "Dashboard URL (CORS Origin)" "*"
CORS_ORIGINS="$REPLY"

_step "Database Configuration"
_info "Settings for the internal PostgreSQL database."
_prompt "Database Name" "edge-hub"
POSTGRES_DB="$REPLY"

_prompt "Database User" "edgehub_user"
POSTGRES_USER="$REPLY"

_prompt "Database Password (leave blank to auto-generate)" ""
POSTGRES_PASSWORD="$REPLY"
if [[ -z "$POSTGRES_PASSWORD" ]]; then
  POSTGRES_PASSWORD=$(openssl rand -hex 16)
  _ok "Database password auto-generated."
fi

_step "Security & Authentication"
_info "The Admin API Key is your master password to access the web Dashboard."
_prompt "Admin API Key (leave blank to auto-generate)" ""
ADMIN_API_KEY="$REPLY"
if [[ -z "$ADMIN_API_KEY" ]]; then
  ADMIN_API_KEY="eh_admin_$(openssl rand -hex 16)"
  _ok "Admin API Key auto-generated."
fi
echo ""
_info "The JWT Secret is used to sign Agent tokens."
_info "If this changes, all agents will need to re-register. Keep it safe!"
_prompt "JWT Secret Key (leave blank to auto-generate)" ""
JWT_SECRET_KEY="$REPLY"
if [[ -z "$JWT_SECRET_KEY" ]]; then
  JWT_SECRET_KEY=$(openssl rand -hex 32)
  _ok "JWT Secret auto-generated."
fi

_step "Monitoring & Heartbeat (Optional)"
_info "How many seconds before a node is considered offline?"
_prompt "Offline Threshold (seconds)" "100"
OFFLINE_THRESHOLD="$REPLY"

# --- 4. GENERATING .ENV FILE ---
_step "Applying configuration..."
DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}"

cat > "${ENV_FILE}" <<EOF
# ==========================================
# EdgeHub Server - Environment Variables
# ==========================================

# --- Network ---
CORS_ORIGINS=${CORS_ORIGINS}

# --- Database ---
DATABASE_URL=${DATABASE_URL}
POSTGRES_DB=${POSTGRES_DB}
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

# --- Security ---
ADMIN_API_KEY=${ADMIN_API_KEY}
JWT_SECRET_KEY=${JWT_SECRET_KEY}
JWT_ALGORITHM=HS256

# --- Monitoring ---
NODE_OFFLINE_THRESHOLD_SECONDS=${OFFLINE_THRESHOLD}
OFFLINE_CHECK_INTERVAL_SECONDS=30
EOF

chmod 600 "${ENV_FILE}"
_ok "Active configuration saved to ${ENV_FILE}"

# --- 5. DEPLOYMENT ---
_step "Starting EdgeHub Server..."
cd "${INSTALL_DIR}"
${DOCKER_CMD} up -d || _err "Failed to start the Docker containers."
_ok "Containers started"

# --- 6. DONE ---
echo -e "\n ${BGREEN}╔══════════════════════════════════════════════════════╗${C0}"
echo -e " ${BGREEN}║${C0}  ${BOLD}EdgeHub Server is now up and running!${C0}               ${BGREEN}║${C0}"
echo -e " ${BGREEN}╚══════════════════════════════════════════════════════╝${C0}\n"
echo -e "  ${BOLD}Web Dashboard :${C0} ${CORS_ORIGINS}"
echo -e "  ${DIM}(Ensure your DNS/Tunnel routes traffic to this server's port 80)${C0}\n"
echo -e "  ${BOLD}Admin API Key :${C0} ${BCYAN}${ADMIN_API_KEY}${C0} ${DIM}(Save this!)${C0}\n"
echo -e "  ${DIM}Install path  :${C0} ${INSTALL_DIR}"
echo -e "  ${DIM}Check status  :${C0} cd ${INSTALL_DIR} && ${DOCKER_CMD} ps"
echo -e "  ${DIM}View logs     :${C0} cd ${INSTALL_DIR} && ${DOCKER_CMD} logs -f\n"