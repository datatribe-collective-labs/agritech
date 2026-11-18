#!/usr/bin/env bash
# uninstall.sh: switches the monitoring off again. It leaves the API, the assistant and the database untouched.
#
# USE:  bash monitoring/uninstall.sh          (stops and disables the services, keeps data and packages)
#       bash monitoring/uninstall.sh --purge  (also removes the packages and the stored history)

# Stop at the first error, treat unset variables as errors, and fail on errors inside pipes.
set -euo pipefail

# Stop the three services now, and stop them starting at boot. "|| true" ignores "not installed" errors.
systemctl disable --now grafana-server prometheus prometheus-node-exporter 2>/dev/null || true

# Only when asked with --purge do we delete things (it cannot be undone).
if [ "${1:-}" = "--purge" ]; then
  # Remove the packages together with their settings.
  apt-get purge -y grafana prometheus prometheus-node-exporter
  # Remove the Grafana package source and its key, which we added in install.sh.
  rm -f /etc/apt/sources.list.d/grafana.list /etc/apt/keyrings/grafana.gpg
  # Remove the secret key file and the dashboard copies.
  rm -f /etc/prometheus/assistant_key
  rm -rf /var/lib/grafana/dashboards
fi

# Confirm what happened.
echo "Monitoring is off. The API and the assistant were not touched."
