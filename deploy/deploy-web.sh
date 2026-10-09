#!/usr/bin/env bash
# Builds the website and restarts it. Run on the server after `git pull`.
set -euo pipefail
cd "$(dirname "$0")/../frontend"
export NEXT_TELEMETRY_DISABLED=1
npm ci
npm run build
systemctl restart planting-web
echo "Website rebuilt and restarted."
