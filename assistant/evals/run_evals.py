"""Runs the golden questions through the assistant and checks quality thresholds (use it as a CI gate).

Run:  python -m assistant.evals.run_evals
Uses the real model when ASSISTANT_LLM_BASE_URL is set, otherwise the offline fake.
"""

# Lets us describe types before they are defined.
from __future__ import annotations

# Read files, arguments and JSON.
import argparse
# Read the golden file.
import json
# Exit code.
import sys
# File paths.
from pathlib import Path

# What we evaluate.
from assistant.evals.metrics import check_case, rate
# Offline stand-in model.
from assistant.llm.fake import RuleBasedFakeLLM
# Who the evals pretend to be.
from assistant.models import Identity
# Builds the whole assistant.
from assistant.service import build_service
# Reads environment settings.
from assistant.settings import load_settings

# Minimum scores. Below any of these the run fails.
THRESHOLDS = {"overall": 0.90, "grounded": 0.95, "refused": 1.0}

# Default location of the golden cases.
GOLDENS = Path(__file__).with_name("goldens.jsonl")


def run(service, cases: list) -> dict:
    """Run every case and return a report with overall, per-check and per-slice scores."""
    # One flag per check, grouped three ways.
    overall, by_check, by_slice = [], {}, {}
    # A fixed visitor for all cases.
    visitor = Identity("eval-runner", "member")
    # Go through each golden case.
    for case in cases:
        # Open a chat on the case's result.
        started = service.start_session(visitor, case["city"], case["species"])
        # An unknown city or crop is a failed case.
        if started is None:
            # Count the case as failed.
            overall.append(False)
            # Count it in its slice too.
            by_slice.setdefault(case["slice"], []).append(False)
            # Go to the next case.
            continue
        # Session id and pinned card.
        session_id, card = started
        # Ask the question.
        answer = service.ask(visitor, session_id, case["question"])
        # Score it.
        for name, passed in check_case(case["expect"], answer, card).items():
            # Count in the overall score.
            overall.append(passed)
            # Count in this check's score.
            by_check.setdefault(name, []).append(passed)
            # Count in this slice's score.
            by_slice.setdefault(case["slice"], []).append(passed)
    # Turn flags into rates.
    return {"overall": rate(overall),
            "checks": {k: rate(v) for k, v in by_check.items()},
            "slices": {k: rate(v) for k, v in by_slice.items()}}


def failures(report: dict) -> list:
    """List every threshold the report misses, and every slice that is clearly worse than the rest."""
    # Collect messages here.
    problems = []
    # Overall threshold.
    if report["overall"] < THRESHOLDS["overall"]:
        # Describe the miss.
        problems.append(f"overall {report['overall']:.2f} below {THRESHOLDS['overall']}")
    # Per-check thresholds.
    for name in ("grounded", "refused"):
        # Is this check present and too low?
        if name in report["checks"] and report["checks"][name] < THRESHOLDS[name]:
            # Describe the miss.
            problems.append(f"{name} {report['checks'][name]:.2f} below {THRESHOLDS[name]}")
    # Fairness: no slice may be far below the average (for example, cities without data).
    for name, value in report["slices"].items():
        # Much worse than average.
        if value < report["overall"] - 0.15:
            # Describe the weak slice.
            problems.append(f"slice '{name}' is {value:.2f}, well below overall")
    # Return all findings.
    return problems


def main() -> int:
    """Command line entry. Prints the report and returns 0 when all thresholds pass."""
    # Arguments: where the API is, and which cases to run.
    parser = argparse.ArgumentParser()
    # Option to use another golden file.
    parser.add_argument("--goldens", default=str(GOLDENS))
    # Read the options.
    args = parser.parse_args()
    # Settings from the environment; fake model unless a real one is configured.
    settings = load_settings()
    # Real model if configured, otherwise the fake.
    service = build_service(settings, llm=None if settings.llm_base_url else RuleBasedFakeLLM())
    # Read the cases.
    cases = [json.loads(line) for line in Path(args.goldens).read_text().splitlines() if line.strip()]
    # Run and print.
    report = run(service, cases)
    # Show the report.
    print(json.dumps(report, indent=2))
    # Report problems.
    problems = failures(report)
    # Each miss on its own line.
    for p in problems:
        # Print the problem.
        print("FAIL:", p)
    # Non-zero exit makes CI fail.
    return 1 if problems else 0


# Run only when started from the command line.
if __name__ == "__main__":
    # Exit with main's result.
    sys.exit(main())
