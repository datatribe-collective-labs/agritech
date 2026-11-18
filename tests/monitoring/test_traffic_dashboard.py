"""Safety checks for the API traffic dashboard (the numbers come from the API itself, see api/metrics.py)."""

# json reads the dashboard file.
import json
# re finds metric names inside the chart queries.
import re
# Path builds file locations.
from pathlib import Path

# The repo root and its monitoring folder.
ROOT = Path(__file__).resolve().parents[2]
# The monitoring folder.
MON = ROOT / "monitoring"
# The folder with the finished dashboard JSON files.
BOARDS = MON / "grafana" / "dashboards"


def _load_builder():
    """Import build_dashboards.py by its file path (the monitoring folder is not a Python package)."""
    # importlib lets us load a module from a file path.
    import importlib.util
    # Describe where the module lives.
    spec = importlib.util.spec_from_file_location("build_dashboards", MON / "grafana" / "build_dashboards.py")
    # Create and run the module.
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Hand it back.
    return module


def test_committed_traffic_dashboard_matches_the_builder(tmp_path):
    # Build fresh copies into a throwaway folder.
    builder = _load_builder()
    # Point the builder there.
    builder.OUT = tmp_path
    # Generate.
    builder.main()
    # The committed file must be identical to a fresh build, otherwise someone edited one without the other.
    assert (BOARDS / "traffic.json").read_text() == (tmp_path / "traffic.json").read_text(), (
        "traffic.json is out of date. Run: python monitoring/grafana/build_dashboards.py")


def test_traffic_dashboard_layout_is_valid():
    # Parse (fails if the JSON is broken).
    board = json.loads((BOARDS / "traffic.json").read_text())
    # Every box on the 24-column grid.
    boxes = [(p["gridPos"]["x"], p["gridPos"]["y"], p["gridPos"]["w"], p["gridPos"]["h"]) for p in board["panels"]]
    # Compare every pair of boxes.
    for i, a in enumerate(boxes):
        # No box may run off the right edge.
        assert a[0] + a[2] <= 24
        # Two boxes overlap unless one is fully left/right of, or above/below, the other.
        for b in boxes[i + 1:]:
            assert a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1]
    # Panel ids must be unique, or Grafana mixes the boxes up.
    ids = [p["id"] for p in board["panels"]]
    # No repeats.
    assert len(ids) == len(set(ids))


def test_traffic_dashboard_only_asks_for_metrics_the_api_publishes():
    # Every API metric name the dashboard asks Prometheus about.
    used = set(re.findall(r"planting_api_[a-z_]+", (BOARDS / "traffic.json").read_text()))
    # The names api/metrics.py creates (a histogram also publishes _bucket, _count and _sum parts).
    code = (ROOT / "api" / "metrics.py").read_text()
    # The counter and histogram names written in that file.
    base = set(re.findall(r'"(planting_api_[a-z_]+)"', code))
    # Every name a chart may use.
    known = set(base) | {f"{n}_{part}" for n in base for part in ("bucket", "count", "sum")}
    # A typo here would show 'No data' forever, so catch it now.
    assert used <= known, f"traffic dashboard uses unknown metrics: {sorted(used - known)}"
    # And it must really use them (an empty dashboard would also pass the line above).
    assert used, "traffic dashboard asks for no API metrics at all"


def test_prometheus_reads_the_api_and_the_service_gives_workers_a_shared_folder():
    # The Prometheus settings file, read as plain text.
    config = (MON / "prometheus" / "prometheus.yml").read_text()
    # A job for the API must exist, pointing at the API's own port.
    assert "job_name: api" in config and "127.0.0.1:8000" in config
    # Without a shared folder the two workers would each show only their own half of the requests.
    unit = (ROOT / "deploy" / "planting-api.service").read_text()
    # The folder setting and the systemd line that creates it.
    assert "PROMETHEUS_MULTIPROC_DIR=/run/planting-api" in unit and "RuntimeDirectory=planting-api" in unit
