#!/usr/bin/env bash
# Model Price — VPS deployment script
# Usage: bash deploy.sh
#
# Edit deploy.env before running to set port, domain, paths.
#
# Prerequisites on VPS:
#   - Python 3.12+, uv, Node.js 18+, npm, Caddy, systemctl
#   - Domain pointed to VPS IP

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/deploy.env"

echo "==> Deploying model-price"
echo "    APP_DIR:      ${APP_DIR}"
echo "    DOMAIN:       ${DOMAIN}"
echo "    BACKEND_PORT: ${BACKEND_PORT}"

# ─── 1. Backend dependencies ───
echo "==> Installing backend dependencies..."
cd "${APP_DIR}/backend"
${UV_BIN} sync --frozen 2>/dev/null || ${UV_BIN} sync

# ─── 2. Frontend build ───
echo "==> Building frontend..."
cd "${APP_DIR}/frontend"
npm ci --prefer-offline 2>/dev/null || npm install
VITE_PUBLIC_BASE_URL="https://${DOMAIN}" npm run build

# ─── 3. Generate & install systemd service ───
echo "==> Installing systemd service..."
cat > /tmp/model-price-backend.service <<UNIT
[Unit]
Description=Model Price Backend (FastAPI)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}/backend
Environment=RELOAD=false
Environment=CORS_ORIGINS=["https://${DOMAIN}"]
ExecStart=${UV_BIN} run uvicorn main:app --host 127.0.0.1 --port ${BACKEND_PORT}
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT

sudo mv /tmp/model-price-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable model-price-backend
sudo systemctl restart model-price-backend

sleep 3
if systemctl is-active --quiet model-price-backend; then
    echo "    Backend is running on port ${BACKEND_PORT}."
else
    echo "    WARNING: Backend failed to start."
    echo "    Check: journalctl -u model-price-backend -n 30"
    exit 1
fi

# ─── 4. Generate & install Caddy site config ───
echo "==> Configuring Caddy..."
sudo mkdir -p /etc/caddy/sites

cat > /tmp/model-price-caddy <<CADDY
${DOMAIN} {
	handle /api/* {
		reverse_proxy 127.0.0.1:${BACKEND_PORT}
	}

	handle {
		root * ${APP_DIR}/frontend/dist
		try_files {path} /index.html
		file_server
	}

	encode gzip zstd

	@static path *.js *.css *.png *.jpg *.svg *.ico *.woff2
	header @static Cache-Control "public, max-age=31536000, immutable"
}
CADDY

sudo mv /tmp/model-price-caddy /etc/caddy/sites/model-price

# Check if main Caddyfile imports sites/*
if ! grep -q 'import sites/\*' /etc/caddy/Caddyfile 2>/dev/null; then
    echo ""
    echo "    NOTE: Your /etc/caddy/Caddyfile needs this line:"
    echo "      import sites/*"
    echo "    Add it, then run: sudo systemctl reload caddy"
    echo ""
else
    sudo systemctl reload caddy 2>/dev/null || sudo systemctl restart caddy
    echo "    Caddy reloaded."
fi

echo ""
echo "==> Done!"
echo "    https://${DOMAIN}"
echo ""
echo "    Commands:"
echo "      journalctl -u model-price-backend -f   # backend logs"
echo "      systemctl restart model-price-backend   # restart backend"
echo "      sudo systemctl reload caddy             # reload caddy"
