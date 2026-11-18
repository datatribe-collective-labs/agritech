"""Builds the three Grafana dashboards (server, assistant and traffic) as JSON files.

WHY A SCRIPT? A Grafana dashboard is a big JSON file that is hard to read. Here each chart is one short, commented
call, and the script writes the JSON for us. To change a chart: edit this file, run it, commit both files.

RUN (from the repo root, no extra packages needed):
    python monitoring/grafana/build_dashboards.py
"""

# json writes Python data out as JSON text.
import json
# Path builds file locations safely on any operating system.
from pathlib import Path

# The folder next to this script where the finished JSON files go.
OUT = Path(__file__).parent / "dashboards"

# Grafana finds Prometheus by this fixed id (it matches provisioning/datasources/prometheus.yml).
SOURCE = {"type": "prometheus", "uid": "prometheus"}


def query(expr, legend="", ref="A"):
    """One question we ask Prometheus, written in its query language (PromQL).

    expr   : the PromQL text, for example rate(some_counter[5m]).
    legend : the label shown next to the line on the chart.
    ref    : a letter naming this query when a chart has several (A, B, C...).
    """
    # Grafana expects exactly these field names for a Prometheus question.
    return {"refId": ref, "expr": expr, "legendFormat": legend, "datasource": SOURCE}


def colours(*steps):
    """Colour rules: pairs of (starts-at-value, colour). The first value must be None (meaning 'from the bottom')."""
    # Each step says: from this number upward, use this colour.
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for v, c in steps]}


def panel(pid, kind, title, queries, x, y, w, h, unit="short", note="", low=None, high=None, steps=None, extra=None, decimals=None):
    """One box on the dashboard.

    pid   : a unique number for this box.
    kind  : "timeseries" (a line chart), "stat" (one big number) or "gauge" (a dial).
    title : the heading shown on the box.
    queries : the list of query(...) calls that feed it.
    x, y  : where the box starts on a grid that is 24 columns wide (x across, y down).
    w, h  : the box width (in those 24 columns) and height.
    unit  : how to print numbers: "percent", "bytes", "Bps", "short" (plain), "s" (seconds)...
    note  : a sentence shown when you hover over the small "i" next to the title. Use it to explain the chart.
    low, high : fixed bottom and top of the scale (for example 0 and 100 for a percentage).
    steps : colour rules made with colours(...).
    extra : any extra Grafana options to merge in (value mappings and similar).
    decimals : how many digits after the decimal point to show. 0 for whole numbers such as counts of questions.
    """
    # The numbers' formatting and colouring rules.
    defaults = {"unit": unit, "thresholds": steps or colours((None, "green"))}
    # Pin the scale only when asked, otherwise Grafana picks a scale to fit the data.
    if low is not None:
        defaults["min"] = low
    # Same for the top of the scale.
    if high is not None:
        defaults["max"] = high
    # Whole-number counts: show 3 instead of 3.03 (increase() stretches counts over the window, adding a tiny fraction).
    if decimals is not None:
        defaults["decimals"] = decimals
    # Merge any extra field options such as value mappings.
    defaults.update(extra or {})
    # Options that control how a stat or gauge picks its number: use the latest value.
    options = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}} if kind != "timeseries" else {}
    # Assemble the box in Grafana's format.
    return {"id": pid, "type": kind, "title": title, "description": note, "datasource": SOURCE,
            "gridPos": {"x": x, "y": y, "w": w, "h": h}, "targets": queries,
            "fieldConfig": {"defaults": defaults, "overrides": []}, "options": options}


def dashboard(uid, title, panels, tags):
    """Wrap the boxes in a dashboard with a title, a time range and auto-refresh."""
    # These are the standard top-level fields Grafana needs.
    return {"uid": uid, "title": title, "tags": tags, "timezone": "browser", "schemaVersion": 39, "version": 1,
            # Reload the numbers every 30 seconds and show the last 6 hours by default.
            "refresh": "30s", "time": {"from": "now-6h", "to": "now"}, "editable": False, "panels": panels}


# ---------------------------------------------------------------------------------------------------------------
# DASHBOARD 1: THE SERVER. Numbers come from node_exporter (job "server"), so they work without touching the app.
# ---------------------------------------------------------------------------------------------------------------

# 1 means "up" and 0 means "down" for Prometheus's built-in `up` number; show those as words with colours.
UP_DOWN = {"mappings": [{"type": "value", "options": {"0": {"text": "DOWN", "color": "red"},
                                                      "1": {"text": "UP", "color": "green"}}}]}
# Green until 70, yellow until 90, red above: good for CPU, memory and disk percentages.
PERCENT_COLOURS = colours((None, "green"), (70, "yellow"), (90, "red"))

server_panels = [
    # Top row: four big numbers answering "is everything healthy right now?"
    panel(1, "stat", "Assistant reachable?", [query('up{job="assistant"}', "assistant")], 0, 0, 6, 4,
          note="Prometheus visited the assistant and got an answer. DOWN means the assistant service is stopped, "
               "or the admin key file is wrong.", steps=colours((None, "red"), (1, "green")), extra=UP_DOWN),
    # CPU busy: 100 minus the share of time the CPUs were idle.
    panel(2, "stat", "CPU busy now",
          [query('100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[2m])) * 100)', "cpu")], 6, 0, 6, 4,
          unit="percent", low=0, high=100, steps=PERCENT_COLOURS,
          note="Share of the 2 CPUs doing work. Above 90% for a long time means the server is the bottleneck."),
    # Memory used: 100 minus the share that is still available (Linux counts cache as available).
    panel(3, "stat", "Memory used",
          [query("100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)", "memory")], 12, 0, 6, 4,
          unit="percent", low=0, high=100, steps=PERCENT_COLOURS,
          note="How much of the 8 GB is really in use. File cache does not count, because Linux gives it back "
               "when a program needs it."),
    # Disk used on the main disk "/".
    panel(4, "stat", "Disk used (/)",
          [query('100 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} * 100)',
                 "disk")], 18, 0, 6, 4, unit="percent", low=0, high=100, steps=PERCENT_COLOURS,
          note="How full the main disk is. Prometheus stores its diary here, capped at 15 days."),
    # Middle row: how busy over time.
    panel(5, "timeseries", "CPU busy over time",
          [query('100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[2m])) * 100)', "CPU busy %")], 0, 4, 12, 8,
          unit="percent", low=0, high=100,
          note="Look for flat tops at 100%: that is the time the server could not keep up (like our 500-user load test)."),
    # Load average: roughly how many programs wanted a CPU at once.
    panel(6, "timeseries", "Load average",
          [query("node_load1", "1 minute", "A"), query("node_load5", "5 minutes", "B"),
           query("node_load15", "15 minutes", "C")], 12, 4, 12, 8,
          note="Roughly how many programs were waiting for a CPU. This server has 2 CPUs, so a steady value above 2 "
               "means work is queueing."),
    # Bottom row: memory and network.
    panel(7, "timeseries", "Memory used over time",
          [query("node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes", "used"),
           query("node_memory_MemTotal_bytes", "total", "B")], 0, 12, 12, 8, unit="bytes", low=0,
          note="The line should stay well below 'total'. A steady climb that never comes down can mean a memory leak."),
    # Network traffic in and out, ignoring the internal loopback "lo".
    panel(8, "timeseries", "Network traffic",
          [query('sum(rate(node_network_receive_bytes_total{device!="lo"}[2m]))', "received"),
           query('sum(rate(node_network_transmit_bytes_total{device!="lo"}[2m]))', "sent", "B")], 12, 12, 12, 8,
          unit="Bps", low=0, note="Bytes per second arriving at and leaving the server (visitors, database, model calls)."),
]

# ---------------------------------------------------------------------------------------------------------------
# DASHBOARD 2: THE AI ASSISTANT. Numbers come from /assistant/metrics (job "assistant").
# "or vector(0)" shows 0 instead of "No data" when nothing has happened yet (a counter appears at its first use).
# sum(...) is wrapped around the counter first: it drops the labels (job, instance), so the real number and the
# fallback 0 have the same (empty) label set and Prometheus picks ONE of them instead of showing both.
# increase(x[24h]) means "how much did counter x grow in the last 24 hours" and copes with restarts resetting it.
# rate(x[5m]) * 60 means "how many per minute, averaged over the last 5 minutes".
# ---------------------------------------------------------------------------------------------------------------

assistant_panels = [
    # Top row: the day at a glance.
    panel(1, "stat", "Questions (24 h)", [query("sum(increase(planting_assistant_questions_total[24h])) or vector(0)", "questions")],
          0, 0, 4, 4, unit="short", decimals=0, note="Questions farmers asked in the last 24 hours."),
    panel(2, "stat", "Sent to human review (24 h)",
          [query("sum(increase(planting_assistant_sent_to_review_total[24h])) or vector(0)", "review")], 4, 0, 4, 4, decimals=0,
          steps=colours((None, "green"), (1, "yellow"), (10, "red")),
          note="Answers that failed our checks or got a thumbs down. They wait in the review queue for a person."),
    panel(3, "stat", "Thumbs up (24 h)", [query("sum(increase(planting_assistant_feedback_up_total[24h])) or vector(0)", "up")],
          8, 0, 4, 4, decimals=0, note="Farmers who rated an answer helpful."),
    panel(4, "stat", "Thumbs down (24 h)", [query("sum(increase(planting_assistant_feedback_down_total[24h])) or vector(0)", "down")],
          12, 0, 4, 4, decimals=0, steps=colours((None, "green"), (1, "yellow"), (5, "red")),
          note="Farmers who rated an answer not helpful. Each one is queued for review with its reason."),
    # The daily token budget: tokens_today comes straight from the assistant's kill switch.
    panel(5, "gauge", "Tokens used today (budget 200,000)", [query("planting_assistant_tokens_today", "tokens")],
          16, 0, 8, 4, low=0, high=200000, steps=colours((None, "green"), (150000, "yellow"), (190000, "red")),
          note="Model usage so far today against the daily cap. At the cap the assistant stops answering until tomorrow. "
               "The 200,000 comes from the assistant's settings; change it here too if you change the setting."),
    # Middle row: usage over time.
    panel(6, "timeseries", "Questions per minute", [query("rate(planting_assistant_questions_total[5m]) * 60", "questions/min")],
          0, 4, 12, 8, low=0, note="How busy the assistant is through the day."),
    panel(7, "timeseries", "Cached or fresh answers",
          [query("rate(planting_assistant_cache_hits_total[5m]) * 60", "answered from cache", "A"),
           query("(rate(planting_assistant_questions_total[5m]) - rate(planting_assistant_cache_hits_total[5m])) * 60",
                 "needed the model", "B")], 12, 4, 12, 8, low=0,
          note="Repeated questions are answered from memory for free. A high 'cache' line means lower cost."),
    # Bottom row: things that went wrong or got stopped, and what it costs.
    panel(8, "timeseries", "Questions stopped or sent for review (per hour)",
          [query("increase(planting_assistant_blocked_input_total[1h])", "blocked by input rules", "A"),
           query("increase(planting_assistant_blocked_kill_switch_total[1h])", "blocked: daily budget used up", "B"),
           query("increase(planting_assistant_rate_limited_total[1h])", "too many questions (rate limit)", "C"),
           query("increase(planting_assistant_sent_to_review_total[1h])", "sent to review", "D")], 0, 12, 12, 8, low=0,
          note="Anything other than 'sent to review' rising fast can mean someone is probing the assistant."),
    panel(9, "timeseries", "Model tokens per hour", [query("increase(planting_assistant_tokens_total[1h])", "tokens/hour")],
          12, 12, 12, 8, low=0, note="Tokens are what the model provider bills for. Watch this line to predict cost."),
]


# ---------------------------------------------------------------------------------------------------------------
# DASHBOARD 3: TRAFFIC. Numbers come from Caddy (job "caddy"), the web server every visitor passes through first.
# Because Caddy sees EVERY request (the website and the API, answered fresh or from the API's cache), these charts
# show what visitors really experience. Caddy publishes one number per request, kept in a "histogram":
#   caddy_http_request_duration_seconds_count  = how many requests there have been (we use it to count requests)
#   caddy_http_request_duration_seconds_bucket = how many finished within 5 ms, 10 ms, 25 ms... (we use it for speed)
# Each request also carries a "code" label (the reply: 200 = fine, 404 = not found, 503 = too busy) and, with
# per_host switched on in the Caddyfile, a "host" label (which site: the API or the website).
# histogram_quantile(0.95, ...) answers: "95 out of 100 requests were faster than this".
# ---------------------------------------------------------------------------------------------------------------

# The metric every traffic chart is built from (one name, so a typo is easy to spot).
REQ = "caddy_http_request_duration_seconds"

traffic_panels = [
    # Top row: the hour at a glance.
    panel(1, "stat", "Requests (1 h)", [query(f"sum(increase({REQ}_count[1h])) or vector(0)", "requests")],
          0, 0, 6, 4, decimals=0, note="Every request that reached the server in the last hour: the website, the API and the assistant."),
    # 5xx means OUR side failed (a 4xx would be the visitor asking for something wrong).
    panel(2, "stat", "Server errors (1 h)", [query(f'sum(increase({REQ}_count{{code=~"5.."}}[1h])) or vector(0)', "errors")],
          6, 0, 6, 4, decimals=0, steps=colours((None, "green"), (1, "yellow"), (20, "red")),
          note="Replies starting with 5 (500, 502, 503...). These mean the server failed, not the visitor. Should stay at 0."),
    # 503 is the polite 'busy, retry in 5 seconds' reply our API gives when the database connections run out.
    panel(3, "stat", "Busy replies (503, 1 h)", [query(f'sum(increase({REQ}_count{{code="503"}}[1h])) or vector(0)', "busy")],
          12, 0, 6, 4, decimals=0, steps=colours((None, "green"), (1, "yellow"), (50, "red")),
          note="The API said 'busy, try again in a few seconds' (no free database connection). A few during a spike is "
               "the safety net working; many means we need more capacity."),
    # The slowest 5% of requests: far more honest than the average.
    panel(4, "stat", "Slowest 5% take longer than",
          [query(f"histogram_quantile(0.95, sum by (le) (rate({REQ}_bucket[5m])))", "p95")],
          18, 0, 6, 4, unit="s", steps=colours((None, "green"), (0.5, "yellow"), (2, "red")),
          note="95 out of 100 requests were faster than this over the last 5 minutes. Under half a second is good."),
    # Middle row: how busy, and what kind of replies.
    panel(5, "timeseries", "Requests per second, by site",
          [query(f"sum by (host) (rate({REQ}_count[2m]))", "{{host}}")], 0, 4, 12, 8, low=0,
          note="One line per site (the API and the website). If you see a single line called 'No data' or no host name, "
               "switch on per_host in the Caddyfile (see monitoring/README.md)."),
    panel(6, "timeseries", "Replies by status code",
          [query(f"sum by (code) (rate({REQ}_count[2m]))", "{{code}}")], 12, 4, 12, 8, low=0,
          note="200 = fine, 304 = unchanged, 404 = not found, 429 = too many requests, 503 = busy. Watch for any 5xx line."),
    # Bottom row: speed and errors over time.
    panel(7, "timeseries", "Response time (typical, slow, slowest)",
          [query(f"histogram_quantile(0.50, sum by (le) (rate({REQ}_bucket[5m])))", "typical (50%)", "A"),
           query(f"histogram_quantile(0.95, sum by (le) (rate({REQ}_bucket[5m])))", "slow (95%)", "B"),
           query(f"histogram_quantile(0.99, sum by (le) (rate({REQ}_bucket[5m])))", "slowest (99%)", "C")],
          0, 12, 12, 8, unit="s", low=0,
          note="How long visitors wait. During our 500-user test the slow line was about half a second; "
               "a line climbing for minutes means the server is struggling."),
    panel(8, "timeseries", "Share of requests that failed",
          [query(f'(100 * sum(rate({REQ}_count{{code=~"5.."}}[5m])) / sum(rate({REQ}_count[5m]))) or vector(0)', "failed %")],
          12, 12, 12, 8, unit="percent", low=0, high=100,
          note="Failed (5xx) requests as a percentage of all requests. Anything above 1% for long deserves a look."),
]


def main():
    """Write all three dashboards to the dashboards folder."""
    # Make sure the folder exists.
    OUT.mkdir(parents=True, exist_ok=True)
    # The three dashboards to write: file name, dashboard object.
    for name, board in (("server.json", dashboard("planting-server", "Planting Intelligence: Server", server_panels,
                                                   ["planting", "server"])),
                        ("assistant.json", dashboard("planting-assistant", "Planting Intelligence: Assistant",
                                                     assistant_panels, ["planting", "assistant"])),
                        ("traffic.json", dashboard("planting-traffic", "Planting Intelligence: Traffic", traffic_panels,
                                                   ["planting", "traffic"]))):
        # indent=2 makes the JSON readable; sort_keys makes reruns produce identical files (clean git diffs).
        (OUT / name).write_text(json.dumps(board, indent=2, sort_keys=True) + "\n")
        # Say what was written.
        print("wrote", OUT / name)


# Run main() only when this file is executed, not when it is imported.
if __name__ == "__main__":
    main()
