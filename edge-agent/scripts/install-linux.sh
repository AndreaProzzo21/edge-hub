#!/usr/bin/env bash
# ==============================================================================
#  Edge Agent  ·  Linux Native Installer
# ==============================================================================
#
#  USAGE:
#    EDGEHUB_URL='https://api.edgehub.io' \
#    EDGEHUB_TOKEN='your-token' \
#    bash <(curl -sSL https://raw.githubusercontent.com/AndreaProzzo21/edge-hub/main/edge-agent/scripts/install-linux.sh)
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
BINARY_PATH="${INSTALL_DIR}/edgehub-agent"
ENV_FILE="${INSTALL_DIR}/.env"
SERVICE_NAME="edgehub"

RELEASES_URL="https://raw.githubusercontent.com/AndreaProzzo21/edge-hub/main/edge-agent/deploy/linux"

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
echo -e "   ${WHITE}${BOLD}Edge Agent${C0}  ${DIM}·${C0}  ${GRAY}Linux Native Installer${C0}"
echo -e "   ${DIM}Deploys the EdgeHub monitoring agent as a systemd service${C0}\n"

# --- 1. CHECKS ---
if [[ $EUID -ne 0 ]]; then _err "This installer must be run as root (or via sudo)."; fi

_step "Checking prerequisites..."
if ! command -v curl >/dev/null 2>&1; then
  _err "curl is not installed. Please install curl first."
fi
if ! command -v systemctl >/dev/null 2>&1; then
  _err "systemd is not available. This installer requires a systemd-based Linux distribution."
fi

raw_arch=$(uname -m)
if [[ "$raw_arch" == "x86_64" ]]; then
  DETECTED_ARCH="amd64"
elif [[ "$raw_arch" == "aarch64" || "$raw_arch" == "arm64" ]]; then
  DETECTED_ARCH="arm64"
else
  DETECTED_ARCH="amd64"
fi
_ok "Prerequisites OK — detected architecture: ${DETECTED_ARCH}"

# --- 2. CONFIGURATION ---
_step "Configuration"

if [[ -z "${EDGEHUB_URL:-}" ]]; then
  _prompt "Backend URL (e.g. https://api.edgehub.io)" ""
  EDGEHUB_URL="$REPLY"
  [[ -z "$EDGEHUB_URL" ]] && _err "Backend URL is required."
else
  _ok "Backend URL automatically applied: ${EDGEHUB_URL}"
fi

if [[ -z "${EDGEHUB_TOKEN:-}" ]]; then
  _prompt "Registration Token" ""
  EDGEHUB_TOKEN="$REPLY"
  [[ -z "$EDGEHUB_TOKEN" ]] && _err "Registration Token is required."
else
  _ok "Registration Token automatically applied."
fi

_prompt "Node Name" "$(hostname)"
EDGEHUB_HOSTNAME="$REPLY"

_prompt "Node Description" "Linux Edge Node"
EDGEHUB_DESC="$REPLY"

_prompt "Heartbeat Interval (seconds: max 90)" "30"
EDGEHUB_INTERVAL="$REPLY"

_prompt "Architecture [1: amd64, 2: arm64]" "$([[ "$DETECTED_ARCH" == "amd64" ]] && echo "1" || echo "2")"
case "$REPLY" in
  2) BIN_FILENAME="edgehub-agent-linux-arm64" ;;
  *) BIN_FILENAME="edgehub-agent-linux-amd64" ;;
esac

# --- 3. WORKSPACE & DOWNLOAD ---
_step "Setting up workspace..."
mkdir -p "${INSTALL_DIR}/data"
_ok "Workspace created at ${INSTALL_DIR}"

_step "Downloading binary (${BIN_FILENAME})..."
curl -# -fSL "${RELEASES_URL}/${BIN_FILENAME}" -o "${BINARY_PATH}" || _err "Download failed. Check the URL or GitHub Releases."
chmod +x "${BINARY_PATH}"
_ok "Binary installed to ${BINARY_PATH}"

# --- 4. CONFIGURATION FILE ---
_step "Generating configuration..."
cat > "${ENV_FILE}" <<EOF
EDGEHUB_URL=${EDGEHUB_URL}
EDGEHUB_TOKEN=${EDGEHUB_TOKEN}
EDGEHUB_HOSTNAME=${EDGEHUB_HOSTNAME}
EDGEHUB_DESCRIPTION=${EDGEHUB_DESC}
EDGEHUB_INTERVAL=${EDGEHUB_INTERVAL}
EDGEHUB_MODE=linux
EDGEHUB_STATE_FILE=${INSTALL_DIR}/data/edgehub-state.json
EOF
chmod 600 "${ENV_FILE}"
_ok "Config saved to ${ENV_FILE}"

# --- 5. SYSTEMD SERVICE ---
_step "Configuring Systemd..."
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=EdgeHub Agent
After=network.target

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${BINARY_PATH}
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}.service" >/dev/null 2>&1
_ok "Service ${SERVICE_NAME} started and enabled on boot"

# --- 6. DONE ---
echo -e "\n ${BGREEN}╔══════════════════════════════════════════════════════╗${C0}"
echo -e " ${BGREEN}║${C0}  ${BOLD}Edge Agent installed and running successfully!${C0}      ${BGREEN}║${C0}"
echo -e " ${BGREEN}╚══════════════════════════════════════════════════════╝${C0}\n"
echo -e "  ${DIM}Check status :${C0} systemctl status ${SERVICE_NAME}.service"
echo -e "  ${DIM}View logs    :${C0} journalctl -u ${SERVICE_NAME}.service -f"
echo -e "  ${DIM}Config file  :${C0} ${ENV_FILE}\n"