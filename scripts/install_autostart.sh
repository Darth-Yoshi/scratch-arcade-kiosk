#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="scratch-arcade-kiosk"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"

if [[ $EUID -ne 0 ]]; then
  echo "This installer must be run as root (sudo)." >&2
  exit 1
fi

cat <<SERVICE > "$SERVICE_FILE"
[Unit]
Description=Scratch Arcade Kiosk
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
ExecStart=${PYTHON_BIN} -m kiosk.app
Restart=always
RestartSec=2
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=graphical.target
SERVICE

systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"

echo "Installed ${SERVICE_NAME}.service. The kiosk will start automatically on boot." >&2
