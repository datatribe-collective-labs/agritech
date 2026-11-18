#!/usr/bin/env bash
# install.sh: turns on the email alerts. Run on the server, as root, from the repo folder:  bash monitoring/alerts/install.sh
# Safe to run twice. To undo: systemctl disable --now planting-alerts.timer

# Stop at the first error, treat unset variables as errors, and fail on errors inside pipes.
set -euo pipefail
# The folder this script lives in.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Installing units needs root.
if [ "$(id -u)" -ne 0 ]; then
  # Say why we stop.
  echo "Please run as root." >&2
  exit 1
fi

# The settings file must exist first (it holds the secret key, so we never create it with a key in it).
if [ ! -f /root/alerts.env ]; then
  # Explain exactly what to create.
  echo "Missing /root/alerts.env. Create it first (see monitoring/alerts/README.md)." >&2
  exit 1
fi
# Only root may read it (permissions 600).
chmod 600 /root/alerts.env
# Make sure the memory-file folder exists.
mkdir -p /var/lib/planting

# Copy the two unit files to where systemd looks for them.
install -m 644 "$HERE/planting-alerts.service" /etc/systemd/system/planting-alerts.service
install -m 644 "$HERE/planting-alerts.timer" /etc/systemd/system/planting-alerts.timer
# Tell systemd about the new files.
systemctl daemon-reload
# Start the timer now and on every boot.
systemctl enable --now planting-alerts.timer
# Show it is scheduled.
systemctl list-timers planting-alerts.timer --no-pager
