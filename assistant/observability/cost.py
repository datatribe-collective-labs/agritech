"""Cost estimate per question. Prices default to zero (free tier); set real prices before using a paid model."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Euros per 1,000 tokens as (input, output). Fill in from your provider's price page.
PRICES_PER_1K = {}


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Return the estimated cost of one call (0.0 when the model has no price set)."""
    # Look up the price pair, defaulting to free.
    price_in, price_out = PRICES_PER_1K.get(model, (0.0, 0.0))
    # Cost is tokens divided by 1000 times the price.
    return tokens_in / 1000 * price_in + tokens_out / 1000 * price_out
