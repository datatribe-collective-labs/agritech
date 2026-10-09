"""
The quality gate: decides whether a freshly trained model may replace the one in use.

THE RULE IN ONE LINE
  A new model is published only if it is still better than the simple baselines on cities
  it has never seen, and not clearly worse than the model it would replace.
  Otherwise the previous scores stay live and the run is recorded as "rejected".

Each rule below is a plain sentence, so a rejection explains itself.
"""

# How much worse than the model in use is tolerated, in AUC points (0.5 = guessing, 1.0 = perfect).
# Small ups and downs between runs are normal when the data changes a little.
MAX_DROP_VS_CURRENT_MODEL = 0.03

ACCEPTED = "accepted"
REJECTED = "rejected"


def reasons_to_reject(results: dict, current_model_results: dict = None) -> list:
    """
    results               the test results of the new model (from train_suitability.evaluate)
    current_model_results the test results of the model now in use, or None for the first run
    Returns plain sentences. An empty list means the new model may be published.
    """
    reasons = []

    gain = results["model_beats_best_baseline_by_auc"]
    if gain <= 0:
        reasons.append(
            f"The model does not beat the best simple baseline ({results['best_baseline']}): "
            f"gain is {gain:+.3f} AUC."
        )

    if current_model_results is not None:
        new_auc = results["model"]["roc_auc"]
        current_auc = current_model_results["model"]["roc_auc"]
        if new_auc < current_auc - MAX_DROP_VS_CURRENT_MODEL:
            reasons.append(
                f"The new model is clearly worse than the one in use: AUC {new_auc:.3f} "
                f"versus {current_auc:.3f} (more than {MAX_DROP_VS_CURRENT_MODEL} lower)."
            )

    return reasons


def warnings(results: dict) -> list:
    """Things worth a human look that do not block publishing."""
    low, high = results["gain_95_percent_range"]
    if low <= 0 < results["model_beats_best_baseline_by_auc"]:
        return [f"The gain over the baseline could be chance: its 95% range is {low:.3f} to {high:.3f}."]
    return []
