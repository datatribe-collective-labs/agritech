"""Tests for the email alert script (no real emails or servers are used)."""

# json writes the fake token file.
import json
# importlib loads the script by its file path (the monitoring folder is not a Python package).
import importlib.util
# Path builds file locations.
from pathlib import Path

# The script's location.
SCRIPT = Path(__file__).resolve().parents[2] / "monitoring" / "alerts" / "alert_check.py"


def load(monkeypatch, tmp_path):
    """Load a fresh copy of the script with its files pointed at a temporary folder."""
    # Point the memory and token files at the temporary folder.
    monkeypatch.setenv("ALERT_STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setenv("ASSISTANT_TOKEN_STATE", str(tmp_path / "tokens.json"))
    # A small budget makes the maths easy.
    monkeypatch.setenv("ASSISTANT_DAILY_TOKEN_BUDGET", "1000")
    # Load the script.
    spec = importlib.util.spec_from_file_location("alert_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_token_levels(monkeypatch, tmp_path):
    """Below 80% is quiet, 80% warns, 100% says full, and yesterday's count is ignored."""
    mod = load(monkeypatch, tmp_path)
    # Helper that writes the token file.
    def put(day, used):
        (tmp_path / "tokens.json").write_text(json.dumps({"day": day, "used": used}))
    # 50% used: nothing to say.
    put("2026-11-18", 500)
    assert mod.check_tokens("2026-11-18") is None
    # 85% used: a warning.
    put("2026-11-18", 850)
    assert mod.check_tokens("2026-11-18")[0] == "warn"
    # All used: full.
    put("2026-11-18", 1000)
    assert mod.check_tokens("2026-11-18")[0] == "full"
    # Counted on another day: ignored.
    assert mod.check_tokens("2026-11-19") is None


def test_down_needs_two_fails_and_cooldown(monkeypatch, tmp_path):
    """One failed check sends nothing, two send one email, a third inside the cooldown sends nothing more."""
    mod = load(monkeypatch, tmp_path)
    # Pretend the API is down and everything else is fine.
    monkeypatch.setattr(mod, "check_api", lambda: "down")
    monkeypatch.setattr(mod, "check_assistant", lambda: None)
    monkeypatch.setattr(mod, "check_errors", lambda: None)
    # Record emails instead of sending them.
    sent = []
    monkeypatch.setattr(mod, "send_email", lambda subject, text: sent.append(subject) or True)
    # First failure: no email yet.
    mod.run()
    assert sent == []
    # Second failure: one email.
    mod.run()
    assert len(sent) == 1
    # Third failure, still in cooldown: still one.
    mod.run()
    assert len(sent) == 1


def test_recovery_email(monkeypatch, tmp_path):
    """After an alert, a healthy check sends one Recovered email."""
    mod = load(monkeypatch, tmp_path)
    # Start with the API down.
    state = {"down": True}
    monkeypatch.setattr(mod, "check_api", lambda: "down" if state["down"] else None)
    monkeypatch.setattr(mod, "check_assistant", lambda: None)
    monkeypatch.setattr(mod, "check_errors", lambda: None)
    sent = []
    monkeypatch.setattr(mod, "send_email", lambda subject, text: sent.append(subject) or True)
    # Two failures cause the alert.
    mod.run(); mod.run()
    # The API comes back.
    state["down"] = False
    mod.run()
    # One alert and one recovery.
    assert len(sent) == 2 and "Recovered" in sent[1]


def test_no_key_means_no_crash(monkeypatch, tmp_path):
    """Without a key the sender reports failure instead of raising."""
    mod = load(monkeypatch, tmp_path)
    monkeypatch.setattr(mod, "RESEND_API_KEY", "")
    assert mod.send_email("x", "y") is False


def test_several_recipients_are_split(monkeypatch, tmp_path):
    """Comma-separated addresses become a clean list, ignoring spaces and empty pieces."""
    # Set two addresses with messy spacing and a trailing comma.
    monkeypatch.setenv("ALERT_TO", " a@x.com , b@y.com,")
    # Load the script fresh so it reads the setting.
    mod = load(monkeypatch, tmp_path)
    # Both addresses survive, cleaned.
    assert mod.RECIPIENTS == ["a@x.com", "b@y.com"]
