# Monitoring: Prometheus + Grafana

This folder adds a **dashboard** for the server and the AI assistant. It only *watches*; it never changes the API,
the assistant, Airflow or the database. Everything can be switched off again with one command.

## The three pieces

```
  node_exporter ──┐                                            ┌── dashboard "Server"
  (machine numbers)│   every 15 s     ┌────────────┐  asks     │
                   ├──────────────►   │ Prometheus │ ◄──────── Grafana ──┤
  assistant        │  "what are your  │  (diary)   │  questions │
  /assistant/metrics┘   numbers now?" └────────────┘            └── dashboard "Assistant"
```

| Piece | Plain-English job | Port (server only) |
|---|---|---|
| **node_exporter** | Reports the machine's CPU, memory, disk and network numbers | 9100 |
| **Prometheus** | Visits each reporter every 15 seconds and writes the numbers in a diary (15 days kept) | 9090 |
| **Grafana** | Draws charts from the diary and shows them in your browser | 3000 |

All three listen on `127.0.0.1` only, so **nothing is open to the internet**.

## What is in this folder

| File | What it does |
|---|---|
| `install.sh` | Installs and configures everything (safe to run twice) |
| `uninstall.sh` | Turns it all off (`--purge` also removes packages and history) |
| `prometheus/prometheus.yml` | The list of things Prometheus visits |
| `grafana/provisioning/...` | Tells Grafana where Prometheus is and where the dashboards are |
| `grafana/build_dashboards.py` | Defines each chart in a few commented lines and writes the JSON |
| `grafana/dashboards/*.json` | The two finished dashboards (generated; do not edit by hand) |

## Install (on the server)

```bash
# Use the monitoring branch in its own folder, so the running services (on main) are not touched
cd /root/agritech
git fetch
git worktree add /root/agritech-monitoring feature/grafana-monitoring
# Run the installer; it will ask you to choose a Grafana admin password
bash /root/agritech-monitoring/monitoring/install.sh
```

## Open the dashboards (from your own computer)

```powershell
# Keep this window open. It makes the server's Grafana appear on your own port 3001.
ssh -L 3001:127.0.0.1:3000 root@94.237.15.238
```

Then open <http://localhost:3001>, log in as `admin` with the password you chose, and open the folder
**Planting Intelligence**.

## How to read the charts

**Server**
- *CPU busy*: share of the 2 CPUs working. Flat at 100% means the server could not keep up.
- *Load average*: roughly how many programs wait for a CPU. Above 2 for long = queueing.
- *Memory used*: the real use of the 8 GB (file cache is not counted).
- *Disk used*: the main disk. Prometheus history is capped at 15 days.

**Assistant**
- *Questions*, *Cached or fresh*: how busy it is, and how many answers cost nothing.
- *Sent to human review*, *Thumbs down*: the cases waiting for a person.
- *Tokens used today*: model usage against the daily cap (200,000 by default; see the note below).
- *Stopped or sent for review*: blocked questions, rate limits and the budget stop.

## Good to know

- The dashboards show **No data / 0** until something happens: a counter appears the first time it is used.
- The assistant keeps its counters in memory, so a restart sets them back to 0. The charts handle that.
- The *Tokens used today* dial has its top set to 200,000 in `build_dashboards.py`. If you change the assistant's
  daily token setting, change it there too and run `python monitoring/grafana/build_dashboards.py`.
- **API request graphs are not included yet.** The API does not publish its own numbers yet; that needs a small code
  change in a separate step. Machine load already shows when the API is busy.
- The Grafana password is typed during the install and stored by Grafana itself. It is never written in this repo.

## If something looks wrong

| Symptom | Check |
|---|---|
| "Assistant reachable?" shows DOWN | `systemctl status planting-assistant`; then `sudo cat /etc/prometheus/assistant_key | wc -c` should be above 0 (do not print the key) |
| Assistant charts are empty | Open Prometheus through a tunnel (`-L 9091:127.0.0.1:9090`, then http://localhost:9091/targets) and read the error beside the *assistant* target |
| A server chart is empty | `systemctl status prometheus-node-exporter` |
| Grafana does not load | `systemctl status grafana-server` and `journalctl -u grafana-server -n 30 --no-pager` |
| You want it all off | `bash monitoring/uninstall.sh` |

## Changing a chart

1. Edit `grafana/build_dashboards.py`.
2. Run `python monitoring/grafana/build_dashboards.py`.
3. Run `python -m pytest tests/monitoring -q` (it checks the files agree and every metric really exists).
4. Commit both files, merge, then on the server copy the JSON again: `install -m 644 monitoring/grafana/dashboards/*.json /var/lib/grafana/dashboards/`
   (Grafana notices the change within 30 seconds).
