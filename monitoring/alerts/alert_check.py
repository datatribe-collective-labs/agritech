#!/usr/bin/env python3
"""Email alerts for Planting Intelligence.

Run once a minute by a systemd timer. Each run looks at four things and emails you only when something is wrong:
  1. Is the API answering?            2. Is the assistant answering (and switched on)?
  3. Are there many server errors?    4. Is the assistant's daily token budget nearly used up?
It uses only Python's standard library, so there is nothing to install.

Test the email by hand:  python3 monitoring/alerts/alert_check.py --test
"""

# annotations lets us write type hints without worrying about the order things are defined in.
from __future__ import annotations

# json reads and writes the small memory file and talks to Prometheus and Resend.
import json
# os reads settings from environment variables.
import os
# sys reads the command line (--test) and sets the exit code.
import sys
# time gives the clock for cooldowns.
import time
# datetime gives today's date, to match the token budget's day.
from datetime import datetime
# urllib makes web requests without extra packages.
import urllib.error
import urllib.parse
import urllib.request
# Path builds file locations.
from pathlib import Path

# ---- Settings (all can be changed with environment variables; the defaults suit this server) ----
# Where the API listens (only on this server).
API_HEALTH_URL = os.environ.get("ALERT_API_HEALTH_URL", "http://127.0.0.1:8000/health")
# Where the assistant listens (only on this server).
ASSISTANT_HEALTH_URL = os.environ.get("ALERT_ASSISTANT_HEALTH_URL", "http://127.0.0.1:8001/assistant/health")
# Where Prometheus (the diary keeper) answers questions.
PROMETHEUS_URL = os.environ.get("ALERT_PROMETHEUS_URL", "http://127.0.0.1:9090")
# The file where the assistant saves today's token count.
TOKEN_FILE = Path(os.environ.get("ASSISTANT_TOKEN_STATE", "/var/lib/planting/assistant_tokens.json"))
# The assistant's daily token allowance (same name and default as the assistant itself uses).
TOKEN_BUDGET = int(os.environ.get("ASSISTANT_DAILY_TOKEN_BUDGET", "200000"))
# Warn when this share of the budget is used (0.8 = 80 percent).
TOKEN_WARN_SHARE = float(os.environ.get("ALERT_TOKEN_WARN_SHARE", "0.8"))
# Email when this many server errors (status 500) happen inside the look-back window below.
ERROR_LIMIT = int(os.environ.get("ALERT_ERROR_LIMIT", "5"))
# How far back to count errors, written the way Prometheus does (10m = ten minutes).
ERROR_WINDOW = os.environ.get("ALERT_ERROR_WINDOW", "10m")
# A service must fail this many checks in a row before we email (stops false alarms during a restart).
FAILS_BEFORE_ALERT = int(os.environ.get("ALERT_FAILS_BEFORE", "2"))
# Do not repeat the same alert more often than this many seconds (3600 = one hour).
COOLDOWN_SECONDS = int(os.environ.get("ALERT_COOLDOWN_SECONDS", "3600"))
# The memory file that remembers what we already emailed about.
STATE_FILE = Path(os.environ.get("ALERT_STATE_FILE", "/var/lib/planting/alerts_state.json"))
# The Resend API key (a secret; it lives only in /root/alerts.env, never in git).
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
# The address(es) that receive the alerts. Several addresses are separated by commas.
ALERT_TO = os.environ.get("ALERT_TO", "")
# The same, cleaned into a list: split on commas, trim spaces, drop empty pieces.
RECIPIENTS = [address.strip() for address in ALERT_TO.split(",") if address.strip()]
# The sender. Resend's test sender needs no domain of your own, but can only email the address you signed up with.
ALERT_FROM = os.environ.get("ALERT_FROM", "Planting Alerts <onboarding@resend.dev>")


def fetch_json(url: str, timeout: float = 5.0):
    """Open a web address and return its JSON answer. Raises an error if it cannot."""
    # Build the request, with a plain browser-like name (some services refuse the default Python one).
    request = urllib.request.Request(url, headers={"User-Agent": "planting-alerts/1.0"})
    # Open it, giving up after the timeout so one stuck service cannot freeze the check.
    with urllib.request.urlopen(request, timeout=timeout) as response:
        # Turn the reply text into Python data.
        return json.loads(response.read().decode("utf-8"))


def check_api() -> str | None:
    """Return a problem description if the API is not healthy, else None."""
    try:
        # The API's /health answers {"status": "ok"} when all is well.
        body = fetch_json(API_HEALTH_URL)
        # Anything other than ok is a problem.
        return None if body.get("status") == "ok" else f"The API answered, but said: {body}"
    except Exception as error:  # noqa: BLE001 - any failure at all means "not healthy"
        # Could not reach it, or it replied with an error.
        return f"The API did not answer ({error})."


def check_assistant() -> str | None:
    """Return a problem description if the assistant is down or switched off, else None."""
    try:
        # The assistant's health answers {"status": "on"} or {"status": "off", "reason": ...}.
        body = fetch_json(ASSISTANT_HEALTH_URL)
        # "off" means the kill switch or the daily budget stopped it on purpose; still worth knowing about.
        return None if body.get("status") == "on" else f"The assistant is switched OFF. Reason: {body.get('reason')}"
    except Exception as error:  # noqa: BLE001 - any failure at all means "not healthy"
        # Could not reach it, or it replied with an error.
        return f"The assistant did not answer ({error})."


def check_errors() -> str | None:
    """Return a problem description if there were too many server errors recently, else None."""
    # Ask Prometheus: how many replies with status 500 happened in the look-back window?
    query = f'sum(increase(planting_api_requests_total{{status="500"}}[{ERROR_WINDOW}]))'
    # Put the question in the web address (urllib needs the special characters made safe).
    url = f"{PROMETHEUS_URL}/api/v1/query?query={urllib.parse.quote(query)}"
    try:
        # Ask.
        body = fetch_json(url)
        # The answer is a list of results; an empty list means no errors were ever counted.
        results = body["data"]["result"]
        # Take the number (Prometheus sends it as text), or 0 if there is no result.
        count = float(results[0]["value"][1]) if results else 0.0
    except Exception:  # noqa: BLE001
        # If Prometheus itself is unreachable we skip this check; the down-checks above still work.
        return None
    # Alert only when the count reaches the limit.
    if count >= ERROR_LIMIT:
        return f"The API returned {count:.0f} server errors (status 500) in the last {ERROR_WINDOW}."
    # Otherwise all is fine.
    return None


def check_tokens(today: str) -> tuple[str, str] | None:
    """Return (level, message) if today's token use is high, else None. Level is 'warn' or 'full'."""
    try:
        # The assistant saves {"day": "2026-11-18", "used": 1354}.
        saved = json.loads(TOKEN_FILE.read_text())
    except Exception:  # noqa: BLE001
        # No file yet (nothing used today) or unreadable: nothing to report.
        return None
    # A count saved on an earlier day does not count today.
    if saved.get("day") != today:
        return None
    # How many tokens were used today.
    used = int(saved.get("used", 0))
    # Used / allowed, as a share.
    share = used / TOKEN_BUDGET if TOKEN_BUDGET else 0.0
    # All used up.
    if share >= 1.0:
        return "full", f"The assistant's daily token budget is used up ({used:,} of {TOKEN_BUDGET:,}). It stops answering until tomorrow."
    # Getting close.
    if share >= TOKEN_WARN_SHARE:
        return "warn", f"The assistant has used {share:.0%} of today's token budget ({used:,} of {TOKEN_BUDGET:,})."
    # Plenty left.
    return None


def load_state() -> dict:
    """Read the memory file, or start fresh if it is missing or damaged."""
    try:
        # Read and parse it.
        return json.loads(STATE_FILE.read_text())
    except Exception:  # noqa: BLE001
        # Fresh start: no failures counted, nothing emailed yet.
        return {"fails": {}, "sent": {}, "active": []}


def save_state(state: dict) -> None:
    """Write the memory file safely (write a temp file, then swap it in, so a crash never leaves half a file)."""
    try:
        # Make sure the folder exists.
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temporary name next to the real file.
        temp = STATE_FILE.with_suffix(".tmp")
        # Save the text.
        temp.write_text(json.dumps(state))
        # Swap it in atomically.
        os.replace(temp, STATE_FILE)
    except Exception as error:  # noqa: BLE001
        # A failed save must never stop alerts; it only means a possible repeat email.
        print(f"alerts: could not save state: {error}", flush=True)


def send_email(subject: str, text: str) -> bool:
    """Send one email through Resend. Returns True if Resend accepted it."""
    # Without a key or an address we cannot send; say so in the log.
    if not RESEND_API_KEY or not RECIPIENTS:
        print("alerts: RESEND_API_KEY or ALERT_TO is not set, so no email was sent.", flush=True)
        return False
    # The message in the format Resend expects.
    payload = json.dumps({"from": ALERT_FROM, "to": RECIPIENTS, "subject": subject, "text": text}).encode("utf-8")
    # The request: a POST with the key as a bearer token.
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        method="POST",
        headers={
            # The secret key proves who we are.
            "Authorization": f"Bearer {RESEND_API_KEY}",
            # We are sending JSON.
            "Content-Type": "application/json",
            # A plain name; Resend's firewall refuses requests with no or the default Python name.
            "User-Agent": "planting-alerts/1.0",
        },
    )
    try:
        # Send, waiting at most 10 seconds.
        with urllib.request.urlopen(request, timeout=10) as response:
            # 200 means accepted.
            return response.status == 200
    except urllib.error.HTTPError as error:
        # Resend replied with a refusal; print its reason (never the key).
        print(f"alerts: Resend refused the email: {error.code} {error.read().decode('utf-8', 'replace')[:300]}", flush=True)
    except Exception as error:  # noqa: BLE001
        # Network trouble.
        print(f"alerts: could not reach Resend: {error}", flush=True)
    # Not sent.
    return False


def run() -> int:
    """Do one round of checks and send any emails that are due. Returns the exit code."""
    # The clock now, and today's date in server time (the assistant saves its day the same way).
    now = time.time()
    today = datetime.now().date().isoformat()
    # What we remembered from the last round.
    state = load_state()
    # Counts of failures in a row, when each alert was last emailed, and which alerts are currently active.
    fails, sent, active = state.setdefault("fails", {}), state.setdefault("sent", {}), set(state.setdefault("active", []))

    # Problems found this round: key -> (subject, message, needs_repeat_check).
    found: dict[str, tuple[str, str]] = {}
    # Check the API.
    problem = check_api()
    if problem:
        found["api-down"] = ("API is not answering", problem)
    # Check the assistant.
    problem = check_assistant()
    if problem:
        found["assistant-down"] = ("Assistant is down or off", problem)
    # Check server errors (only if the API itself is up; otherwise the down alert already covers it).
    if "api-down" not in found:
        problem = check_errors()
        if problem:
            found["api-errors"] = ("API is returning errors", problem)
    # Check the token budget. The key includes the day and level, so each level emails once per day.
    tokens = check_tokens(today)
    if tokens:
        level, message = tokens
        found[f"tokens-{level}-{today}"] = ("Assistant token budget " + ("used up" if level == "full" else "running low"), message)

    # Count failures in a row: keys seen now go up by one, keys not seen reset to zero.
    for key in list(fails):
        if key not in found:
            fails.pop(key)
    for key in found:
        fails[key] = fails.get(key, 0) + 1

    # Send emails for problems that have lasted long enough and are not in cooldown.
    for key, (subject, message) in found.items():
        # Token alerts email at once; the others wait for repeated failures.
        needed = 1 if key.startswith("tokens-") else FAILS_BEFORE_ALERT
        if fails[key] < needed:
            continue
        # Skip if we emailed about this recently.
        if now - sent.get(key, 0) < COOLDOWN_SECONDS:
            continue
        # Send; remember the time only if it really went out (otherwise we retry next minute).
        if send_email(f"[Planting] {subject}", f"{message}\n\nTime: {datetime.now():%Y-%m-%d %H:%M:%S} (server time)\n"):
            sent[key] = now
            active.add(key)
            print(f"alerts: emailed {key}", flush=True)

    # Send an "all clear" for problems that were active and have now stopped (not for token alerts, which end at midnight).
    for key in sorted(active):
        if key not in found and not key.startswith("tokens-"):
            if send_email(f"[Planting] Recovered: {key}", f"The problem '{key}' has cleared.\n\nTime: {datetime.now():%Y-%m-%d %H:%M:%S} (server time)\n"):
                active.discard(key)
                # Forget the cooldown so a new problem can email straight away.
                sent.pop(key, None)
                print(f"alerts: recovered {key}", flush=True)
    # Token alerts are not tracked for recovery; drop them from the active list so it stays small.
    active = {key for key in active if not key.startswith("tokens-")}

    # Save what we learned for the next round.
    state["active"] = sorted(active)
    # Forget cooldown entries older than a day, so the file never grows.
    state["sent"] = {key: stamp for key, stamp in sent.items() if now - stamp < 86400}
    save_state(state)
    # Always succeed: a failing exit code would make systemd mark the timer as failed for no useful reason.
    return 0


def main() -> int:
    """Entry point: --test sends a test email, otherwise do the normal checks."""
    # A hand-run test so you can see an email arrive.
    if "--test" in sys.argv:
        # Send one test message and report the result in plain words.
        ok = send_email("[Planting] Test alert", "If you can read this, email alerts work.")
        print("Test email sent." if ok else "Test email FAILED (see the message above).")
        return 0 if ok else 1
    # Normal run.
    return run()


# Run main() only when this file is started directly (not when a test imports it).
if __name__ == "__main__":
    sys.exit(main())
