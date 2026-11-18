"""The daily token count must survive an assistant restart, or a restart would give the budget back."""

# Write and read the saved note.
import json
# Today's date.
from datetime import date, timedelta

# The class under test.
from assistant.governance.kill_switch import KillSwitch


def test_count_survives_a_restart(tmp_path):
    """Tokens spent before a restart are still counted after it."""
    # Where the count is kept.
    state = str(tmp_path / "tokens.json")
    # First run of the service.
    first = KillSwitch("", daily_token_budget=100, state_file=state)
    # It spends 60 tokens.
    first.add_tokens(60)
    # The service restarts: a brand new object reads the same file.
    second = KillSwitch("", daily_token_budget=100, state_file=state)
    # The 60 tokens are remembered.
    assert second.tokens_used_today() == 60
    # Spending 40 more uses up the budget, even though the service restarted in between.
    second.add_tokens(40)
    # So the assistant switches itself off.
    assert "budget" in second.reason_off()


def test_yesterdays_count_is_ignored(tmp_path):
    """A note saved yesterday does not count against today's budget."""
    # A note from yesterday.
    state = tmp_path / "tokens.json"
    # Save it by hand.
    state.write_text(json.dumps({"day": (date.today() - timedelta(days=1)).isoformat(), "used": 999}))
    # A restart today.
    switch = KillSwitch("", daily_token_budget=100, state_file=str(state))
    # Fresh budget.
    assert switch.tokens_used_today() == 0


def test_damaged_or_unwritable_state_never_breaks_the_assistant(tmp_path):
    """A garbled file or an unwritable folder only means the count is not saved."""
    # A file with nonsense inside.
    state = tmp_path / "tokens.json"
    # Garbage.
    state.write_text("not json at all")
    # Starting still works and the count is zero.
    switch = KillSwitch("", daily_token_budget=100, state_file=str(state))
    # Zero.
    assert switch.tokens_used_today() == 0
    # A "folder" that is really a file cannot be written to.
    blocker = tmp_path / "blocker"
    # Make it a file.
    blocker.write_text("x")
    # Saving inside it fails.
    broken = KillSwitch("", daily_token_budget=100, state_file=str(blocker / "tokens.json"))
    # Recording tokens still works in memory.
    broken.add_tokens(5)
    # The count is right.
    assert broken.tokens_used_today() == 5


def test_no_state_file_means_memory_only(tmp_path, monkeypatch):
    """Without a state file nothing is written (this is how the tests and old setups behave)."""
    # Work inside an empty folder.
    monkeypatch.chdir(tmp_path)
    # No state file given.
    switch = KillSwitch("", daily_token_budget=100)
    # Spend some tokens.
    switch.add_tokens(10)
    # The count is kept in memory.
    assert switch.tokens_used_today() == 10
    # No file was created.
    assert list(tmp_path.iterdir()) == []
