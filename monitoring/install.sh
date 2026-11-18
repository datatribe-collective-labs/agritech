#!/usr/bin/env bash
# install.sh: sets up Prometheus (the diary keeper), node_exporter (the machine reporter) and Grafana (the dashboards).
#
# HOW TO RUN (on the server, as root, from the repo folder):
#     bash monitoring/install.sh
# It is safe to run twice: each step checks what is already done and only changes what is needed.
# It does NOT touch the API, the assistant, Airflow or the database. To undo everything: bash monitoring/uninstall.sh

# "set -e" stops the script at the first error, "-u" treats a missing variable as an error,
# and "pipefail" makes a failure inside a pipe (a | b) count as a failure. Together they prevent half-finished installs.
set -euo pipefail

# The folder this script lives in, so we can find the config files next to it no matter where we run it from.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# A tiny helper that prints a clearly visible heading before each step.
step() { printf '\n==> %s\n' "$1"; }

# --------------------------------------------------------------------------------------------------------------
step "0. Checking we are root (installing software needs it)"
# "id -u" prints the user number; root is 0.
if [ "$(id -u)" -ne 0 ]; then
  # Print the problem on the error stream and stop with a failure code.
  echo "Please run as root: sudo bash monitoring/install.sh" >&2
  exit 1
fi

# --------------------------------------------------------------------------------------------------------------
step "1. Installing Prometheus and node_exporter from Ubuntu's own package list"
# Refresh the list of available packages.
apt-get update -y
# Install: prometheus (the diary keeper, with its promtool checker), prometheus-node-exporter (machine numbers),
# plus gpg and wget which step 2 needs to add Grafana's package list safely.
apt-get install -y prometheus prometheus-node-exporter gpg wget

# --------------------------------------------------------------------------------------------------------------
step "2. Installing Grafana from Grafana's official package list"
# Grafana is not in Ubuntu's own list, so we add Grafana's. First a folder for the signing key.
mkdir -p /etc/apt/keyrings
# Download Grafana's public signing key and convert it to the format apt uses. apt will refuse packages
# that are not signed with this key, which protects us from tampered downloads.
wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor --yes -o /etc/apt/keyrings/grafana.gpg
# Tell apt about Grafana's package list and that its packages must be signed by that key.
echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" > /etc/apt/sources.list.d/grafana.list
# Refresh again so apt sees Grafana's packages, then install Grafana.
apt-get update -y
apt-get install -y grafana

# --------------------------------------------------------------------------------------------------------------
step "3. Making all three services listen ONLY on this server (127.0.0.1), not on the internet"
# Prometheus: listen on localhost only, and keep 15 days of history so the disk never fills up.
# /etc/default/prometheus is where Ubuntu's service reads its command-line options (ARGS).
echo 'ARGS="--web.listen-address=127.0.0.1:9090 --storage.tsdb.retention.time=15d"' > /etc/default/prometheus
# node_exporter: same idea, localhost only (by default it would listen on every network address).
echo 'ARGS="--web.listen-address=127.0.0.1:9100"' > /etc/default/prometheus-node-exporter
# Grafana reads settings from environment variables that start with GF_. They are kept in this file.
GF=/etc/default/grafana-server
# Make sure the file exists before we search it.
touch "$GF"
# Add each setting only if it is not there yet (so running the script twice does not duplicate lines).
for line in "GF_SERVER_HTTP_ADDR=127.0.0.1" "GF_USERS_ALLOW_SIGN_UP=false" "GF_ANALYTICS_REPORTING_ENABLED=false"; do
  # -q means "search quietly", -x means "match the whole line", -F means "treat the text as plain text".
  grep -qxF "$line" "$GF" || echo "$line" >> "$GF"
done

# --------------------------------------------------------------------------------------------------------------
step "4. Giving Prometheus the assistant's admin key (read from the assistant's own settings file)"
# The assistant file has a line like ASSISTANT_API_KEYS=key1:admin,key2:member
# We take that line, cut off the name, split on commas, keep the entry marked ':admin' and print only the key part.
ADMIN_KEY="$(grep '^ASSISTANT_API_KEYS=' /root/assistant.env | cut -d= -f2- | tr ',' '\n' | grep ':admin' | head -n1 | cut -d: -f1 || true)"
# If no admin key was found, say so, because the assistant job would be refused (403) without it.
if [ -z "$ADMIN_KEY" ]; then
  # Warn, but carry on so the server dashboard still works.
  echo "WARNING: no admin key found in /root/assistant.env. The assistant dashboard will be empty until you create" >&2
  echo "         /etc/prometheus/assistant_key by hand (see monitoring/README.md)." >&2
else
  # printf (not echo) avoids adding anything extra; the key goes in the file and is never shown on screen.
  printf '%s' "$ADMIN_KEY" > /etc/prometheus/assistant_key
  # Only the prometheus user may read it: owner prometheus, permissions 600 (owner read and write only).
  chown prometheus:prometheus /etc/prometheus/assistant_key
  # Lock the permissions down.
  chmod 600 /etc/prometheus/assistant_key
fi
# Forget the key in this script's memory as soon as we are done with it.
unset ADMIN_KEY

# --------------------------------------------------------------------------------------------------------------
step "5. Copying our configuration and dashboards into place"
# Prometheus: which things to visit and how often.
install -m 644 "$HERE/prometheus/prometheus.yml" /etc/prometheus/prometheus.yml
# Before using the new file, ask Prometheus's own checker whether it is valid. "set -e" stops the script if it is not.
promtool check config /etc/prometheus/prometheus.yml
# Grafana: where its numbers come from, and where to load dashboards from.
install -m 644 "$HERE/grafana/provisioning/datasources/prometheus.yml" /etc/grafana/provisioning/datasources/prometheus.yml
# Grafana: the rule "load dashboards from a folder".
install -m 644 "$HERE/grafana/provisioning/dashboards/dashboards.yml" /etc/grafana/provisioning/dashboards/dashboards.yml
# The folder the dashboard files live in (matches the path inside dashboards.yml).
mkdir -p /var/lib/grafana/dashboards
# Copy the two dashboard files.
install -m 644 "$HERE"/grafana/dashboards/*.json /var/lib/grafana/dashboards/
# Make sure Grafana owns the folder, so it can read it.
chown -R grafana:grafana /var/lib/grafana/dashboards

# --------------------------------------------------------------------------------------------------------------
step "6. Starting the three services and making them start again after a reboot"
# Tell systemd (the program that manages services) that the unit files may have changed.
systemctl daemon-reload
# "enable" = start at boot; "--now" = also start right now. restart makes the new settings apply on a second run.
systemctl enable --now prometheus prometheus-node-exporter grafana-server
# Restart so the settings from step 3 and 5 are definitely in use.
systemctl restart prometheus prometheus-node-exporter grafana-server

# --------------------------------------------------------------------------------------------------------------
step "7. Setting the Grafana admin password (typed here, never saved in any file of ours)"
# Wait a few seconds so Grafana has created its database.
sleep 8
# Only ask when somebody is at the keyboard (-t 0 means "input is a terminal").
if [ -t 0 ]; then
  # -s hides what you type, -r keeps backslashes literal, -p shows the question.
  read -r -s -p "Choose a strong Grafana admin password: " GRAFANA_PASSWORD
  # read -s does not print a newline, so print one.
  echo
  # Ask Grafana's own tool to set the password for the user "admin".
  grafana-cli admin reset-admin-password "$GRAFANA_PASSWORD"
  # Forget the password.
  unset GRAFANA_PASSWORD
else
  # Not interactive (for example run from automation): leave the default and warn.
  echo "Skipped: not a terminal. Set it later with: grafana-cli admin reset-admin-password '<new password>'"
fi

# --------------------------------------------------------------------------------------------------------------
step "8. Checking: every service should be listening on 127.0.0.1 only"
# ss lists open ports; -t TCP, -l listening, -n numbers instead of names, -p which program.
# We look for our three ports. Each line should show 127.0.0.1:PORT (not 0.0.0.0 or [::]).
ss -tlnp | grep -E ':(9090|9100|3000)\b' || true
# A last summary of whether the services are running.
systemctl is-active prometheus prometheus-node-exporter grafana-server

# Finish with the next steps, written for a human.
cat <<'MSG'

Done. To open the dashboards from your own computer, run this in PowerShell (keep it open):

    ssh -L 3001:127.0.0.1:3000 root@94.237.15.238

then open http://localhost:3001 in your browser. Log in as user "admin" with the password you just chose.
Look in the folder "Planting Intelligence". More help: monitoring/README.md
MSG
