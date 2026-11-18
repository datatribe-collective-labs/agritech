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
| **Grafana** | Draws charts from the diary and shows them in your browser | 3030 (3000 is the website) |

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
# Keep this window open. It makes the server's Grafana appear on your own port 3300.
ssh -i $HOME\.ssh\KEYNAME -L 3300:127.0.0.1:3030 root@94.237.15.238
```

Then open <http://localhost:3300>, log in as `admin` with the password you chose, and open the folder
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

**Traffic** (needs Caddy's metrics switched on, see "Switching on the traffic numbers")
- *Requests (1 h)*, *Server errors*, *Busy replies (503)*: the hour at a glance. Errors should stay at 0.
- *Slowest 5% take longer than*: the wait most visitors never notice but the unlucky ones do. Under 0.5 s is good.
- *Requests per second by site*, *Replies by status code*: how busy each site is and what the server answered.
- *Response time* and *Share of requests that failed*: speed and failures over time (our load test is the benchmark).

## Switching on the traffic numbers (one time, on the server)

Caddy keeps its own numbers private until you ask it to publish them. Prometheus then reads them from Caddy's admin
address (127.0.0.1:2019, reachable only from the server itself).

1. See which Caddy you have: `caddy version`.
2. Make a safety copy: `cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak`.
3. Open `/etc/caddy/Caddyfile` (`nano /etc/caddy/Caddyfile`) and put this block at the very top, above every site:
   ```
   {
       metrics {
           per_host
       }
   }
   ```
   If your file already starts with a `{ ... }` block, add the `metrics { per_host }` lines inside it instead.
   (Older Caddy versions want `servers { metrics { per_host } }` instead; step 4 tells you if it is wrong.)
4. Check it BEFORE using it: `caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile`.
5. Apply it without dropping connections: `systemctl reload caddy`.
6. Confirm the numbers exist: `curl -s http://127.0.0.1:2019/metrics | grep -c caddy_http_request_duration_seconds`
   (any number above 0 is good; visit the website once first).
7. Tell Prometheus to read them: `cd /root/agritech && git pull && install -m 644 monitoring/prometheus/prometheus.yml /etc/prometheus/prometheus.yml && promtool check config /etc/prometheus/prometheus.yml && systemctl restart prometheus`
8. Load the new dashboard: `install -m 644 monitoring/grafana/dashboards/*.json /var/lib/grafana/dashboards/`.

If something goes wrong, restore the copy: `cp /etc/caddy/Caddyfile.bak /etc/caddy/Caddyfile && systemctl reload caddy`.

## Good to know

- The dashboards show **No data / 0** until something happens: a counter appears the first time it is used.
- The assistant keeps its counters in memory, so a restart sets them back to 0. The charts handle that.
- The *Tokens used today* dial has its top set to 200,000 in `build_dashboards.py`. If you change the assistant's
  daily token setting, change it there too and run `python monitoring/grafana/build_dashboards.py`.
- **Traffic graphs come from Caddy**, the web server in front of the API and the website, so they cover every request
  (including answers served from the API's cache) with no change to the app. They need the one-time switch below.
- The Grafana password is typed during the install and stored by Grafana itself. It is never written in this repo.

## If something looks wrong

| Symptom | Check |
|---|---|
| "Assistant reachable?" shows DOWN | `systemctl status planting-assistant`; then `sudo cat /etc/prometheus/assistant_key | wc -c` should be above 0 (do not print the key) |
| Assistant charts are empty | Open Prometheus through a tunnel (`-L 9091:127.0.0.1:9090`, then http://localhost:9091/targets) and read the error beside the *assistant* target |
| Traffic charts are empty | Check step 6 above; then the *caddy* target on Prometheus's /targets page (tunnel `-L 9091:127.0.0.1:9090`) should be UP |
| A server chart is empty | `systemctl status prometheus-node-exporter` |
| Grafana does not load | `systemctl status grafana-server` and `journalctl -u grafana-server -n 30 --no-pager` |
| You want it all off | `bash monitoring/uninstall.sh` |

## Changing a chart

1. Edit `grafana/build_dashboards.py`.
2. Run `python monitoring/grafana/build_dashboards.py`.
3. Run `python -m pytest tests/monitoring -q` (it checks the files agree and every metric really exists).
4. Commit both files, merge, then on the server copy the JSON again: `install -m 644 monitoring/grafana/dashboards/*.json /var/lib/grafana/dashboards/`
   (Grafana notices the change within 30 seconds).
