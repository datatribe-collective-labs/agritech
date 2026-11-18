"""Safety checks for the monitoring files, so a typo cannot silently give you an empty or broken dashboard."""

# json reads the dashboard files.
import json
# re finds the metric names inside the chart queries.
import re
# Path builds file locations.
from pathlib import Path

# pytest runs the tests.
import pytest

# The repo's monitoring folder.
MON = Path(__file__).resolve().parents[2] / "monitoring"
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


def test_committed_dashboards_match_the_builder(tmp_path):
    # Load the builder and point it at a throwaway folder.
    builder = _load_builder()
    # Write fresh copies there.
    builder.OUT = tmp_path
    # Generate.
    builder.main()
    # Each committed file must be identical to a fresh build, otherwise someone edited one without the other.
    for name in ("server.json", "assistant.json"):
        # Compare text exactly.
        assert (BOARDS / name).read_text() == (tmp_path / name).read_text(), (
            f"{name} is out of date. Run: python monitoring/grafana/build_dashboards.py")


def test_every_assistant_metric_in_the_dashboard_really_exists():
    # All metric names the dashboard asks Prometheus about.
    text = (BOARDS / "assistant.json").read_text()
    # Names look like planting_assistant_questions.
    used = set(re.findall(r"planting_assistant_[a-z_]+", text))
    # The two files that create counters: the service (questions, tokens...) and the gateway (rate limits).
    sources = [(MON.parent / "assistant" / "service.py").read_text(),
               (MON.parent / "assistant" / "gateway" / "app.py").read_text()]
    # Counters written as metrics.inc("name") become planting_assistant_<name>.
    known = {f"planting_assistant_{n}" for text_ in sources for n in re.findall(r'metrics\.inc\("([a-z_]+)"', text_)}
    # The feedback counters are named after the rating, so they are built in code as feedback_up and feedback_down.
    known |= {"planting_assistant_feedback_up", "planting_assistant_feedback_down"}
    # Two live numbers the gateway writes out in full next to the counters.
    known |= set(re.findall(r"planting_assistant_[a-z_]+", sources[1]))
    # Anything a chart asks for that the assistant never publishes would show 'No data' forever.
    assert used <= known, f"dashboard uses metrics the assistant does not publish: {sorted(used - known)}"


def test_dashboards_are_valid_and_panels_do_not_overlap():
    # Check both dashboards.
    for name in ("server.json", "assistant.json"):
        # Parse (fails if the JSON is broken).
        board = json.loads((BOARDS / name).read_text())
        # Every box on the 24-column grid.
        boxes = [(p["gridPos"]["x"], p["gridPos"]["y"], p["gridPos"]["w"], p["gridPos"]["h"]) for p in board["panels"]]
        # Compare every pair of boxes.
        for i, a in enumerate(boxes):
            # No box may run off the right edge.
            assert a[0] + a[2] <= 24
            # Two boxes overlap unless one is fully left/right of, or above/below, the other.
            for b in boxes[i + 1:]:
                assert (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1])
        # Panel ids must be unique, or Grafana mixes the boxes up.
        ids = [p["id"] for p in board["panels"]]
        # No repeats.
        assert len(ids) == len(set(ids))


def test_prometheus_config_has_the_three_jobs_and_no_secret():
    # The YAML reader may not be installed everywhere; skip rather than fail.
    yaml = pytest.importorskip("yaml")
    # Read the config.
    raw = (MON / "prometheus" / "prometheus.yml").read_text()
    # Parse it.
    config = yaml.safe_load(raw)
    # The jobs we expect.
    assert [j["job_name"] for j in config["scrape_configs"]] == ["prometheus", "server", "assistant"]
    # The key must come from a file, never be written in the config (which is committed to git).
    assistant = config["scrape_configs"][2]
    # Only a 'files' entry is allowed for the header.
    assert list(assistant["http_headers"]["X-Assistant-Key"]) == ["files"]
