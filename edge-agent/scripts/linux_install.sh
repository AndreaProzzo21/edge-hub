#!/usr/bin/env bash
# ==============================================================================
#
#   ███████╗██████╗  ██████╗ ███████╗██╗  ██╗██╗   ██╗██████╗
#   ██╔════╝██╔══██╗██╔════╝ ██╔════╝██║  ██║██║   ██║██╔══██╗
#   █████╗  ██║  ██║██║  ███╗█████╗  ███████║██║   ██║██████╔╝
#   ██╔══╝  ██║  ██║██║   ██║██╔══╝  ██╔══██║██║   ██║██╔══██╗
#   ███████╗██████╔╝╚██████╔╝███████╗██║  ██║╚██████╔╝██████╔╝
#   ╚══════╝╚═════╝  ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝
#
#   edge-agent  ·  Linux Native Installer
#   https://github.com/yourorg/edgehub
#
# ==============================================================================
set -Eeuo pipefail

# ── Trap: print a clean error on unexpected exit ──────────────────────────────
trap 'on_error $? $LINENO' ERR
on_error() {
  echo ""
  _box_err "Installer failed (exit $1 at line $2). Check output above for details."
  exit 1
}

# ==============================================================================
#  COLOUR PALETTE
# ==============================================================================
if [[ -t 1 ]]; then
  C0='\033[0m'
  BOLD='\033[1m'
  DIM='\033[2m'
  GREEN='\033[0;32m'   BGREEN='\033[1;32m'
  CYAN='\033[0;36m'    BCYAN='\033[1;36m'
  YELLOW='\033[0;33m'  BYELLOW='\033[1;33m'
  RED='\033[0;31m'     BRED='\033[1;31m'
  WHITE='\033[1;37m'
  GRAY='\033[0;90m'
else
  C0=''; BOLD=''; DIM=''; GREEN=''; BGREEN=''; CYAN=''; BCYAN=''
  YELLOW=''; BYELLOW=''; RED=''; BRED=''; WHITE=''; GRAY=''
fi

# ==============================================================================
#  CONSTANTS
# ==============================================================================
readonly AGENT_NAME="edge-agent"
readonly INSTALL_DIR="/opt/edgehub"
readonly BINARY_PATH="${INSTALL_DIR}/${AGENT_NAME}"
readonly ENV_FILE="${INSTALL_DIR}/.env"
readonly SERVICE_NAME="edgehub-agent"
readonly SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
readonly RELEASES_URL="https://github.com/yourorg/edgehub/releases/latest/download"
readonly LOG_FILE="/tmp/edgehub-install-$(date +%s).log"

# Runtime vars (populated during configuration)
EDGEHUB_URL=""
EDGEHUB_TOKEN=""
EDGEHUB_HOSTNAME=""
EDGEHUB_DESCRIPTION=""
DETECTED_ARCH=""
SELECTED_ARCH=""
BIN_FILENAME=""

# ==============================================================================
#  UI PRIMITIVES
# ==============================================================================

# Terminal width (fallback 80)
_cols() { tput cols 2>/dev/null || echo 80; }

# Print a horizontal rule
_rule() {
  local char="${1:-─}"
  local cols; cols=$(_cols)
  printf "${DIM}%${cols}s${C0}\n" '' | tr ' ' "${char}"
}

# Section header  →  ── Title ───────────────────────────────
_section() {
  local title="$1"
  echo ""
  printf "${CYAN}${BOLD}  %-3s${C0}${DIM} %s${C0}\n" "§" "${title}"
  _rule "─"
}

# Step line  →    ➜  doing something…
_step()    { echo -e "  ${BCYAN}➜${C0}  $*"; }

# Sub-item   →      ·  detail
_item()    { echo -e "  ${DIM}·${C0}  $*"; }

# Success    →    ✔  message
_ok()      { echo -e "  ${BGREEN}✔${C0}  $*"; }

# Warning    →    ⚠  message
_warn()    { echo -e "  ${BYELLOW}⚠${C0}  ${YELLOW}$*${C0}"; }

# Info       →    ℹ  message
_info()    { echo -e "  ${CYAN}ℹ${C0}  ${GRAY}$*${C0}"; }

# Box: success
_box_ok() {
  local cols; cols=$(( $(_cols) - 4 ))
  echo ""
  echo -e "  ${BGREEN}╔$(printf '═%.0s' $(seq 1 $cols))╗${C0}"
  echo -e "  ${BGREEN}║${C0}  ${WHITE}${BOLD}$1$(printf ' %.0s' $(seq ${#1} $cols))${C0}${BGREEN}║${C0}"
  echo -e "  ${BGREEN}╚$(printf '═%.0s' $(seq 1 $cols))╝${C0}"
  echo ""
}

# Box: error
_box_err() {
  local cols; cols=$(( $(_cols) - 4 ))
  echo ""
  echo -e "  ${BRED}╔$(printf '═%.0s' $(seq 1 $cols))╗${C0}"
  echo -e "  ${BRED}║${C0}  ${BOLD}ERROR: $1$(printf ' %.0s' $(seq $(( ${#1} + 7 )) $cols))${C0}${BRED}║${C0}"
  echo -e "  ${BRED}╚$(printf '═%.0s' $(seq 1 $cols))╝${C0}"
  echo ""
}

# Box: warning
_box_warn() {
  local cols; cols=$(( $(_cols) - 4 ))
  echo ""
  echo -e "  ${BYELLOW}╔$(printf '═%.0s' $(seq 1 $cols))╗${C0}"
  echo -e "  ${BYELLOW}║${C0}  ${BOLD}${YELLOW}$1$(printf ' %.0s' $(seq ${#1} $cols))${C0}${BYELLOW}║${C0}"
  echo -e "  ${BYELLOW}╚$(printf '═%.0s' $(seq 1 $cols))╝${C0}"
  echo ""
}

# Spinner: _spin_start "label"; ..work..; _spin_stop [ok|fail]
_SPIN_PID=""
_spin_start() {
  local label="$1"
  local frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
  (
    local i=0
    while true; do
      printf "\r  ${CYAN}%s${C0}  ${DIM}%s${C0}  " "${frames[$i]}" "${label}"
      i=$(( (i+1) % ${#frames[@]} ))
      sleep 0.08
    done
  ) &
  _SPIN_PID=$!
  disown "$_SPIN_PID"
}
_spin_stop() {
  local result="${1:-ok}"
  [[ -n "$_SPIN_PID" ]] && kill "$_SPIN_PID" 2>/dev/null && _SPIN_PID=""
  printf "\r%s\r" "$(printf ' %.0s' $(seq 1 $(_cols)))"   # clear line
  if [[ "$result" == "ok" ]]; then
    _ok "$2"
  else
    echo -e "  ${BRED}✖${C0}  ${RED}$2${C0}"
  fi
}

# Progress bar: _progress <current> <total> <label>
_progress() {
  local current=$1 total=$2 label="${3:-}"
  local cols; cols=$(( $(_cols) - 24 ))
  local filled=$(( current * cols / total ))
  local empty=$(( cols - filled ))
  printf "\r  ${DIM}[${C0}${GREEN}%s${C0}${DIM}%s]${C0}  ${GRAY}%s${C0}  " \
    "$(printf '█%.0s' $(seq 1 "$filled"))" \
    "$(printf '░%.0s' $(seq 1 "$empty"))" \
    "${label}"
}

# Prompt with optional default value
# _prompt "Question" "DEFAULT" → sets $REPLY
_prompt() {
  local question="$1"
  local default="${2:-}"
  if [[ -n "$default" ]]; then
    printf "  ${WHITE}%s${C0} ${GRAY}[%s]${C0}: " "${question}" "${default}"
  else
    printf "  ${WHITE}%s${C0}: " "${question}"
  fi
  read -r REPLY
  [[ -z "$REPLY" && -n "$default" ]] && REPLY="$default"
}

# Secret prompt (no echo)
_prompt_secret() {
  local question="$1"
  printf "  ${WHITE}%s${C0}: " "${question}"
  read -rs REPLY
  echo ""
}

# ==============================================================================
#  HEADER
# ==============================================================================
_print_header() {
  clear
  echo ""
  echo -e "${BGREEN}   ███████╗██████╗  ██████╗ ███████╗██╗  ██╗██╗   ██╗██████╗ ${C0}"
  echo -e "${BGREEN}   ██╔════╝██╔══██╗██╔════╝ ██╔════╝██║  ██║██║   ██║██╔══██╗${C0}"
  echo -e "${BGREEN}   █████╗  ██║  ██║██║  ███╗█████╗  ███████║██║   ██║██████╔╝${C0}"
  echo -e "${BGREEN}   ██╔══╝  ██║  ██║██║   ██║██╔══╝  ██╔══██║██║   ██║██╔══██╗${C0}"
  echo -e "${BGREEN}   ███████╗██████╔╝╚██████╔╝███████╗██║  ██║╚██████╔╝██████╔╝${C0}"
  echo -e "${BGREEN}   ╚══════╝╚═════╝  ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝${C0}"
  echo ""
  echo -e "   ${WHITE}${BOLD}edge-agent${C0}  ${DIM}·${C0}  ${GRAY}Linux Native Installer${C0}"
  echo -e "   ${DIM}Deploys and configures the EdgeHub monitoring agent as a systemd service${C0}"
  echo ""
  _rule "═"
  echo ""
}

# ==============================================================================
#  STEP 0 — Preflight checks
# ==============================================================================
_preflight() {
  _section "Preflight Checks"

  # Root check
  _step "Checking privileges…"
  if [[ $EUID -ne 0 ]]; then
    _box_err "This installer must be run as root (or via sudo)."
    exit 1
  fi
  _ok "Running as root"

  # OS check
  _step "Detecting OS…"
  if [[ -f /etc/os-release ]]; then
    source /etc/os-release
    _ok "OS: ${PRETTY_NAME:-Linux}"
  else
    _warn "Cannot detect OS — continuing anyway"
  fi

  # Required tools
  _step "Checking required tools…"
  local missing=()
  for tool in curl systemctl; do
    if ! command -v "$tool" &>/dev/null; then
      missing+=("$tool")
    else
      _item "${tool}: $(command -v "$tool")"
    fi
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    _box_err "Missing required tools: ${missing[*]}"
    exit 1
  fi
  _ok "All required tools present"

  # Architecture detection
  _step "Detecting system architecture…"
  local raw_arch; raw_arch=$(uname -m)
  case "$raw_arch" in
    x86_64)         DETECTED_ARCH="amd64" ;;
    aarch64|arm64)  DETECTED_ARCH="arm64" ;;
    armv7l|armv6l)  DETECTED_ARCH="arm"   ;;
    *)              DETECTED_ARCH=""       ;;
  esac
  if [[ -n "$DETECTED_ARCH" ]]; then
    _ok "Architecture detected: ${raw_arch} → ${BGREEN}${DETECTED_ARCH}${C0}"
  else
    _warn "Could not auto-detect architecture (raw: ${raw_arch})"
  fi

  # Check if already installed
  if [[ -f "$BINARY_PATH" ]]; then
    echo ""
    _box_warn "edge-agent is already installed at ${BINARY_PATH}"
    _prompt "Overwrite existing installation?" "yes"
    if [[ ! "$REPLY" =~ ^[Yy] ]]; then
      echo ""
      _info "Installation aborted by user."
      exit 0
    fi
  fi
}

# ==============================================================================
#  STEP 1 — Configuration
# ==============================================================================
_configure() {
  _section "Agent Configuration"
  echo -e "  ${DIM}All values will be saved to ${ENV_FILE}${C0}"
  echo ""

  # Backend URL
  local url_default="${EDGEHUB_URL:-}"
  while true; do
    _prompt "EdgeHub backend URL  (e.g. https://hub.example.com)" "$url_default"
    EDGEHUB_URL="${REPLY}"
    # Strip trailing slash
    EDGEHUB_URL="${EDGEHUB_URL%/}"
    if [[ "$EDGEHUB_URL" =~ ^https?://.+ ]]; then
      break
    fi
    _warn "Please enter a valid URL starting with http:// or https://"
  done

  echo ""

  # Registration token
  while true; do
    _prompt_secret "Registration token  (from the EdgeHub dashboard)"
    EDGEHUB_TOKEN="${REPLY}"
    if [[ -n "$EDGEHUB_TOKEN" ]]; then
      break
    fi
    _warn "Token cannot be empty."
  done

  echo ""

  # Hostname (default: system hostname)
  local default_hostname; default_hostname=$(hostname -s 2>/dev/null || echo "edge-node")
  _prompt "Node hostname" "${default_hostname}"
  EDGEHUB_HOSTNAME="${REPLY:-$default_hostname}"

  echo ""

  # Description
  _prompt "Node description  (optional, e.g. 'Factory Floor Rack A')" "Linux edge node"
  EDGEHUB_DESCRIPTION="${REPLY}"

  echo ""

  # Architecture selection
  _step "Select binary architecture:"
  echo ""
  echo -e "    ${BOLD}1)${C0}  x86_64  / amd64  ${DIM}— standard 64-bit Intel/AMD${C0}"
  echo -e "    ${BOLD}2)${C0}  aarch64 / arm64  ${DIM}— 64-bit ARM (Raspberry Pi 4+, AWS Graviton)${C0}"
  echo -e "    ${BOLD}3)${C0}  armv7l  / arm    ${DIM}— 32-bit ARM (Raspberry Pi 2/3, older boards)${C0}"
  echo ""

  local auto_opt=""
  case "$DETECTED_ARCH" in
    amd64) auto_opt="1" ;;
    arm64) auto_opt="2" ;;
    arm)   auto_opt="3" ;;
  esac

  while true; do
    _prompt "Architecture [1-3]" "${auto_opt}"
    case "$REPLY" in
      1) SELECTED_ARCH="amd64"; BIN_FILENAME="${AGENT_NAME}-linux-amd64"; break ;;
      2) SELECTED_ARCH="arm64"; BIN_FILENAME="${AGENT_NAME}-linux-arm64"; break ;;
      3) SELECTED_ARCH="arm";   BIN_FILENAME="${AGENT_NAME}-linux-arm";   break ;;
      *) _warn "Please enter 1, 2 or 3." ;;
    esac
  done

  # Advanced options
  echo ""
  _prompt "Show advanced options?" "no"
  if [[ "$REPLY" =~ ^[Yy] ]]; then
    echo ""
    _prompt "Run agent as system user" "root"
    SERVICE_USER="${REPLY:-root}"

    _prompt "Restart delay on failure (seconds)" "10"
    SERVICE_RESTART_DELAY="${REPLY:-10}"
  else
    SERVICE_USER="root"
    SERVICE_RESTART_DELAY="10"
  fi
}

# ==============================================================================
#  STEP 2 — Confirm summary
# ==============================================================================
_confirm_summary() {
  _section "Installation Summary"
  echo ""
  echo -e "  ${BOLD}Backend URL${C0}        ${CYAN}${EDGEHUB_URL}${C0}"
  echo -e "  ${BOLD}Registration Token${C0} ${GRAY}$(echo "$EDGEHUB_TOKEN" | head -c 8)…$(echo "$EDGEHUB_TOKEN" | tail -c 5) ${DIM}(truncated for display)${C0}"
  echo -e "  ${BOLD}Hostname${C0}           ${WHITE}${EDGEHUB_HOSTNAME}${C0}"
  echo -e "  ${BOLD}Description${C0}        ${WHITE}${EDGEHUB_DESCRIPTION}${C0}"
  echo -e "  ${BOLD}Architecture${C0}       ${BGREEN}${SELECTED_ARCH}${C0}"
  echo -e "  ${BOLD}Binary${C0}             ${GRAY}${BIN_FILENAME}${C0}"
  echo -e "  ${BOLD}Install path${C0}       ${GRAY}${INSTALL_DIR}${C0}"
  echo -e "  ${BOLD}Service${C0}            ${GRAY}${SERVICE_NAME}.service (systemd)${C0}"
  echo -e "  ${BOLD}Service user${C0}       ${GRAY}${SERVICE_USER}${C0}"
  echo ""
  _rule

  echo ""
  _prompt "Proceed with installation?" "yes"
  if [[ ! "$REPLY" =~ ^[Yy] ]]; then
    echo ""
    _info "Installation cancelled."
    exit 0
  fi
}

# ==============================================================================
#  STEP 3 — Workspace setup
# ==============================================================================
_setup_workspace() {
  _section "Setting Up Workspace"

  _step "Creating directory structure…"
  mkdir -p "${INSTALL_DIR}"
  mkdir -p "${INSTALL_DIR}/logs"
  _ok "Created ${INSTALL_DIR}"

  # Stop service if already running
  if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
    _step "Stopping existing service…"
    systemctl stop "${SERVICE_NAME}" >> "${LOG_FILE}" 2>&1
    _ok "Service stopped"
  fi
}

# ==============================================================================
#  STEP 4 — Download binary
# ==============================================================================
_download_binary() {
  _section "Downloading Agent Binary"

  local url="${RELEASES_URL}/${BIN_FILENAME}"
  local tmp_path="/tmp/${BIN_FILENAME}.tmp"
  local checksum_url="${RELEASES_URL}/${BIN_FILENAME}.sha256"

  _item "Source  : ${GRAY}${url}${C0}"
  _item "Target  : ${GRAY}${BINARY_PATH}${C0}"
  echo ""

  # Download with progress
  _step "Downloading ${BIN_FILENAME}…"
  if ! curl -fSL \
      --retry 3 \
      --retry-delay 2 \
      --connect-timeout 15 \
      --progress-bar \
      -o "${tmp_path}" \
      "${url}" 2>&1; then
    _spin_stop "fail" "Download failed"
    _box_err "Could not download binary from ${url}"
    _info "Check the URL and your network connection. Full log: ${LOG_FILE}"
    exit 1
  fi
  _ok "Binary downloaded"

  # Verify file is not empty / is actually an ELF
  _step "Verifying binary integrity…"
  local file_type; file_type=$(file "${tmp_path}" 2>/dev/null || echo "unknown")
  if [[ "$file_type" == *"ELF"* ]]; then
    _ok "Binary verified (ELF executable)"
  else
    _warn "Binary type: ${file_type} — if this is unexpected, abort and check the release URL"
  fi

  # Optional SHA256 checksum
  if curl -fsSL --connect-timeout 5 -o "/tmp/${BIN_FILENAME}.sha256" "${checksum_url}" 2>/dev/null; then
    _step "Verifying SHA256 checksum…"
    local expected; expected=$(awk '{print $1}' "/tmp/${BIN_FILENAME}.sha256")
    local actual;   actual=$(sha256sum "${tmp_path}" | awk '{print $1}')
    if [[ "$expected" == "$actual" ]]; then
      _ok "Checksum verified: ${GRAY}${actual:0:16}…${C0}"
    else
      _box_err "Checksum mismatch! Expected ${expected:0:16}… got ${actual:0:16}…"
      rm -f "${tmp_path}"
      exit 1
    fi
  else
    _info "No checksum file found at release URL — skipping verification"
  fi

  # Move into place
  mv "${tmp_path}" "${BINARY_PATH}"
  chmod +x "${BINARY_PATH}"
  _ok "Binary installed to ${BINARY_PATH}"
}

# ==============================================================================
#  STEP 5 — Write configuration
# ==============================================================================
_write_config() {
  _section "Writing Configuration"

  _step "Generating .env file…"
  cat > "${ENV_FILE}" <<EOF
# EdgeHub Agent Configuration
# Generated by installer on $(date -u '+%Y-%m-%dT%H:%M:%SZ')
# DO NOT share this file — it contains your registration token.

EDGEHUB_URL=${EDGEHUB_URL}
EDGEHUB_TOKEN=${EDGEHUB_TOKEN}
EDGEHUB_HOSTNAME=${EDGEHUB_HOSTNAME}
EDGEHUB_DESCRIPTION=${EDGEHUB_DESCRIPTION}
EDGEHUB_AGENT_TYPE=linux
EOF

  chmod 600 "${ENV_FILE}"
  _ok "Config written to ${ENV_FILE} (mode 600)"

  # README
  _step "Writing README…"
  cat > "${INSTALL_DIR}/README.md" <<EOF
# EdgeHub Agent — Linux Native Deployment

Installed on : $(date -u '+%Y-%m-%dT%H:%M:%SZ')
Agent binary : ${BINARY_PATH}
Architecture : ${SELECTED_ARCH}
Backend URL  : ${EDGEHUB_URL}
Hostname     : ${EDGEHUB_HOSTNAME}

## Managing the service

| Action              | Command                                      |
|---------------------|----------------------------------------------|
| Check status        | \`systemctl status ${SERVICE_NAME}\`          |
| View live logs      | \`journalctl -u ${SERVICE_NAME} -f\`         |
| Stop agent          | \`systemctl stop ${SERVICE_NAME}\`           |
| Start agent         | \`systemctl start ${SERVICE_NAME}\`          |
| Restart agent       | \`systemctl restart ${SERVICE_NAME}\`        |
| Disable autostart   | \`systemctl disable ${SERVICE_NAME}\`        |

## Configuration

Edit \`${ENV_FILE}\` to change settings, then restart the service:

\`\`\`bash
systemctl restart ${SERVICE_NAME}
\`\`\`

## Uninstall

\`\`\`bash
systemctl stop ${SERVICE_NAME}
systemctl disable ${SERVICE_NAME}
rm -rf ${INSTALL_DIR}
rm -f ${SERVICE_FILE}
systemctl daemon-reload
\`\`\`
EOF
  _ok "README written to ${INSTALL_DIR}/README.md"
}

# ==============================================================================
#  STEP 6 — Systemd service
# ==============================================================================
_install_service() {
  _section "Installing Systemd Service"

  _step "Writing service unit file…"
  cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=EdgeHub Agent — edge monitoring daemon
Documentation=https://github.com/yourorg/edgehub
After=network-online.target
Wants=network-online.target
# Restart if network goes down and comes back
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${BINARY_PATH}
Restart=on-failure
RestartSec=${SERVICE_RESTART_DELAY}

# Hardening
PrivateTmp=true
ProtectSystem=full
NoNewPrivileges=true

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
EOF
  _ok "Service unit written to ${SERVICE_FILE}"

  _step "Reloading systemd daemon…"
  systemctl daemon-reload >> "${LOG_FILE}" 2>&1
  _ok "Daemon reloaded"

  _step "Enabling service on boot…"
  systemctl enable "${SERVICE_NAME}" >> "${LOG_FILE}" 2>&1
  _ok "Service enabled"

  _step "Starting ${SERVICE_NAME}…"
  if systemctl start "${SERVICE_NAME}" >> "${LOG_FILE}" 2>&1; then
    sleep 1
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
      _ok "Service is ${BGREEN}running${C0}"
    else
      _spin_stop "fail" "Service started but is not active"
      _warn "The service may have crashed immediately. Check logs:"
      echo ""
      echo -e "    ${GRAY}journalctl -u ${SERVICE_NAME} -n 30 --no-pager${C0}"
      echo ""
    fi
  else
    _box_err "Failed to start service — run: journalctl -u ${SERVICE_NAME} -n 50"
    exit 1
  fi
}

# ==============================================================================
#  STEP 7 — Post-install verification
# ==============================================================================
_verify() {
  _section "Post-Install Verification"

  local all_ok=true

  # Binary executable
  if [[ -x "${BINARY_PATH}" ]]; then
    _ok "Binary present and executable: ${GRAY}${BINARY_PATH}${C0}"
  else
    _warn "Binary not found or not executable at ${BINARY_PATH}"
    all_ok=false
  fi

  # Env file
  if [[ -f "${ENV_FILE}" ]]; then
    _ok "Config file present: ${GRAY}${ENV_FILE}${C0} (mode $(stat -c%a "${ENV_FILE}"))"
  else
    _warn "Config file missing at ${ENV_FILE}"
    all_ok=false
  fi

  # Service enabled
  if systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
    _ok "Service enabled for boot"
  else
    _warn "Service not enabled for boot"
    all_ok=false
  fi

  # Service running
  if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
    _ok "Service is ${BGREEN}active (running)${C0}"
  else
    _warn "Service is NOT running — check: journalctl -u ${SERVICE_NAME} -n 50"
    all_ok=false
  fi

  $all_ok
}

# ==============================================================================
#  DONE — summary
# ==============================================================================
_print_done() {
  echo ""
  _box_ok "  edge-agent installed and running successfully!  "

  echo -e "  ${BOLD}Next steps:${C0}"
  echo ""
  echo -e "    ${CYAN}1.${C0}  Check the dashboard at ${CYAN}${EDGEHUB_URL}${C0}"
  echo -e "       The node ${WHITE}${EDGEHUB_HOSTNAME}${C0} should appear within ~30 seconds."
  echo ""
  echo -e "    ${CYAN}2.${C0}  Monitor the agent locally:"
  echo -e "       ${GRAY}journalctl -u ${SERVICE_NAME} -f${C0}"
  echo ""
  echo -e "    ${CYAN}3.${C0}  Service management:"
  echo -e "       ${GRAY}systemctl {status|stop|restart} ${SERVICE_NAME}${C0}"
  echo ""
  echo -e "    ${CYAN}4.${C0}  Configuration file:"
  echo -e "       ${GRAY}${ENV_FILE}${C0}"
  echo ""
  echo -e "    ${CYAN}5.${C0}  Full README:"
  echo -e "       ${GRAY}cat ${INSTALL_DIR}/README.md${C0}"
  echo ""
  _rule "═"
  echo ""
  echo -e "  ${DIM}Installer log saved to: ${LOG_FILE}${C0}"
  echo ""
}

# ==============================================================================
#  MAIN FLOW
# ==============================================================================
main() {
  _print_header
  _preflight
  _configure
  _confirm_summary
  _setup_workspace
  _download_binary
  _write_config
  _install_service
  _verify && _print_done
}

main "$@"