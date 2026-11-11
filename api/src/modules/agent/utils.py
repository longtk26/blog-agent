from src.configs.config import config


def compute_token_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
    pricing_table: dict[str, dict[str, float]] | None = None,
) -> float:
    """Compute estimated cost in USD based on input, output and cached tokens.
    Labeled as an estimate."""
    table = pricing_table or config.model_pricing
    normalized = model.lower()
    # Local agent CLIs run on the owner's subscription: tokens are recorded, but nothing is billed per call.
    if normalized.split(":", 1)[0] in ("agy", "claude_code"):
        return 0.0
    if ":" in normalized:
        normalized = normalized.split(":", 1)[1]

    # Find matching model key
    matched_pricing = None
    for key, price in table.items():
        if key != "default" and key in normalized:
            matched_pricing = price
            break

    if not matched_pricing:
        matched_pricing = table.get("default", {"input": 2.0, "output": 10.0, "cached": 0.50})

    in_rate = matched_pricing.get("input", 2.0)
    out_rate = matched_pricing.get("output", 10.0)
    cached_rate = matched_pricing.get("cached", 0.50)

    # Cost per 1M tokens
    cost = (
        (input_tokens * in_rate)
        + (output_tokens * out_rate)
        + (cached_tokens * cached_rate)
    ) / 1_000_000.0

    return round(cost, 6)
