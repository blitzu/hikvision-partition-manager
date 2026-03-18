#!/usr/bin/env bash
# =============================================================================
# Hikvision Partition Manager — Auto-installer pentru Ubuntu
# Folosire:
#   curl -fsSL https://raw.githubusercontent.com/blitzu/hikvision-partition-manager/main/install.sh | sudo bash
#   sau:
#   sudo bash install.sh
# =============================================================================
set -euo pipefail

REPO_URL="https://github.com/blitzu/hikvision-partition-manager.git"
INSTALL_DIR="/opt/hikvision-partition-manager"
APP_PORT="${APP_PORT:-8000}"

# ── Culori ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}▶${NC}  $*"; }
success() { echo -e "${GREEN}✓${NC}  $*"; }
warn()    { echo -e "${YELLOW}⚠${NC}  $*"; }
error()   { echo -e "${RED}✗${NC}  $*" >&2; exit 1; }
header()  { echo -e "\n${BOLD}━━━ $* ━━━${NC}"; }

# ── Root check ────────────────────────────────────────────────────────────────
[[ "$(id -u)" -eq 0 ]] || error "Rulează cu sudo: sudo bash install.sh"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   Hikvision Partition Manager — Instalare auto  ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Dependențe de sistem ───────────────────────────────────────────────────
header "1. Dependențe sistem"

apt-get update -qq
apt-get install -y -qq \
    curl \
    git \
    ca-certificates \
    gnupg \
    lsb-release \
    python3 \
    python3-pip \
    rsync \
    openssl \
    2>/dev/null

success "Pachete sistem instalate"

# ── 2. Docker ─────────────────────────────────────────────────────────────────
header "2. Docker"

if command -v docker &>/dev/null && docker compose version &>/dev/null; then
    success "Docker $(docker --version | grep -oP '[\d.]+' | head -1) + Compose deja instalate"
else
    info "Instalez Docker CE..."

    # Elimină versiuni vechi dacă există
    apt-get remove -y -qq docker docker-engine docker.io containerd runc 2>/dev/null || true

    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list

    apt-get update -qq
    apt-get install -y -qq \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin

    systemctl enable --now docker
    success "Docker instalat și pornit"
fi

# ── 3. Descărcare aplicație ───────────────────────────────────────────────────
header "3. Aplicație"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-install.sh}")" 2>/dev/null && pwd || echo "")"
IS_REPO=false
[[ -f "${SCRIPT_DIR}/docker-compose.yml" ]] && IS_REPO=true

if [[ "$IS_REPO" == "true" ]] && [[ "$SCRIPT_DIR" != "$INSTALL_DIR" ]]; then
    info "Copiez fișierele din $SCRIPT_DIR → $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
    rsync -a --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
        --exclude='*.egg-info' --exclude='.env' \
        "$SCRIPT_DIR/" "$INSTALL_DIR/"
    success "Fișiere copiate"
elif [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Actualizez repo din GitHub..."
    git -C "$INSTALL_DIR" pull --ff-only
    success "Actualizat"
else
    info "Clonez repo din GitHub..."
    rm -rf "$INSTALL_DIR"
    git clone "$REPO_URL" "$INSTALL_DIR"
    success "Repo clonat"
fi

cd "$INSTALL_DIR"

# ── 4. Configurare .env ───────────────────────────────────────────────────────
header "4. Configurare"

if [[ -f "$INSTALL_DIR/.env" ]]; then
    warn ".env există deja — îl păstrez neschimbat (configurația nu se suprascrie)"
else
    info "Generez cheia de criptare Fernet..."
    ENCRYPTION_KEY=$(python3 -c \
        "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" \
        2>/dev/null) || {
        # fallback: instalează cryptography și încearcă din nou
        pip3 install -q cryptography
        ENCRYPTION_KEY=$(python3 -c \
            "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    }

    # Detectează IP-ul local pentru BASE_URL
    LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
    BASE_URL="http://${LOCAL_IP}:${APP_PORT}"

    cat > "$INSTALL_DIR/.env" <<EOF
# Generat automat de install.sh — $(date '+%Y-%m-%d %H:%M:%S')

# Baza de date — gestionată de Docker Compose (nu modifica fără a reface volumul)
DATABASE_URL=postgresql+asyncpg://appuser:apppassword@localhost:5432/partitions

# Cheie criptare parole NVR (NU o schimba după ce ai adăugat NVR-uri!)
ENCRYPTION_KEY=${ENCRYPTION_KEY}

# URL public al serviciului (folosit în webhook-uri și link-uri de alertă)
BASE_URL=${BASE_URL}

# Logging: DEBUG / INFO / WARNING / ERROR
LOG_LEVEL=INFO
DB_ECHO=false

# Webhook URL pentru alerte (stick-disarmed, NVR offline, auto-rearm)
# Lasă gol dacă nu folosești
ALERT_WEBHOOK_URL=

# Interval monitor partiții blocate în secunde (default 300 = 5 minute)
POLL_INTERVAL_SECONDS=300
EOF

    # Actualizează portul în docker-compose dacă diferit de 8000
    if [[ "$APP_PORT" != "8000" ]]; then
        sed -i "s/\"8000:8000\"/\"${APP_PORT}:8000\"/" "$INSTALL_DIR/docker-compose.yml"
    fi

    success ".env creat cu cheie de criptare generată automat"
fi

# ── 5. Build & Start ──────────────────────────────────────────────────────────
header "5. Build și pornire"

info "Build imagine Docker (prima dată: 2-4 minute)..."
docker compose build
success "Build complet"

info "Pornesc PostgreSQL și aplicația..."
docker compose up -d
success "Containere pornite"

# ── 6. Health check ───────────────────────────────────────────────────────────
header "6. Verificare"

info "Aștept să fie gata aplicația (max 60s)..."
ATTEMPTS=0
until curl -sf "http://localhost:${APP_PORT}/api/dashboard" &>/dev/null; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [[ $ATTEMPTS -ge 30 ]]; then
        echo ""
        warn "Aplicația nu răspunde încă. Loguri:"
        docker compose logs --tail=20
        error "Verifică logurile de mai sus cu: docker compose -C ${INSTALL_DIR} logs -f"
    fi
    printf "."
    sleep 2
done
echo ""
success "Aplicația răspunde pe portul ${APP_PORT}"

# ── 7. Systemd — autostart la boot ───────────────────────────────────────────
header "7. Autostart la boot"

cat > /etc/systemd/system/hikvision-pm.service <<EOF
[Unit]
Description=Hikvision Partition Manager
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable hikvision-pm
success "Serviciu systemd activat (pornire automată la boot)"

# ── Sumar final ───────────────────────────────────────────────────────────────
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║         Instalare completă cu succes!           ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Dashboard:${NC}  ${CYAN}http://${LOCAL_IP}:${APP_PORT}${NC}"
echo -e "  ${BOLD}API:${NC}        ${CYAN}http://${LOCAL_IP}:${APP_PORT}/api/dashboard${NC}"
echo ""
echo -e "  ${BOLD}Configurație:${NC}  ${INSTALL_DIR}/.env"
echo ""
echo -e "  ${BOLD}Comenzi utile:${NC}"
echo -e "    cd ${INSTALL_DIR}"
echo -e "    docker compose logs -f          # loguri live"
echo -e "    docker compose restart          # restart"
echo -e "    docker compose down             # oprire"
echo -e "    docker compose up -d            # repornire"
echo ""
echo -e "  ${BOLD}Actualizare la versiune nouă:${NC}"
echo -e "    cd ${INSTALL_DIR} && git pull && docker compose up -d --build"
echo ""
