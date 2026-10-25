from src.modules.agent.utils import compute_token_cost


def test_compute_token_cost_default_rates():
    # 1,000,000 input tokens at default $2.0, 1,000,000 output tokens at default $10.0
    cost = compute_token_cost(
        model="custom-unknown-model",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cached_tokens=0,
    )
    assert cost == 12.0


def test_compute_token_cost_custom_pricing_and_prefix():
    pricing = {
        "claude-3-5-sonnet": {"input": 3.0, "output": 15.0, "cached": 0.30},
        "default": {"input": 1.0, "output": 2.0, "cached": 0.10},
    }
    # Test model with provider prefix like 'anthropic:claude-3-5-sonnet-20241022'
    cost = compute_token_cost(
        model="anthropic:claude-3-5-sonnet-20241022",
        input_tokens=100_000,
        output_tokens=20_000,
        cached_tokens=50_000,
        pricing_table=pricing,
    )
    # (100k * 3.0 + 20k * 15.0 + 50k * 0.30) / 1,000,000 = (300,000 + 300,000 + 15,000) / 1,000,000 = 0.615
    assert cost == 0.615


def test_compute_token_cost_gemini_models():
    # Test google_genai:gemini-3.1-flash-lite
    # Rates: input $0.25, output $1.50, cached $0.025 per 1M tokens
    cost_31 = compute_token_cost(
        model="google_genai:gemini-3.1-flash-lite",
        input_tokens=100_000,
        output_tokens=10_000,
        cached_tokens=40_000,
    )
    # (100k * 0.25 + 10k * 1.50 + 40k * 0.025) / 1M = (25,000 + 15,000 + 1,000) / 1M = 0.041
    assert cost_31 == 0.041

    # Test google_genai:gemini-3.8-flash
    # Rates: input $0.75, output $3.75, cached $0.075 per 1M tokens
    cost_38 = compute_token_cost(
        model="google_genai:gemini-3.8-flash",
        input_tokens=100_000,
        output_tokens=10_000,
        cached_tokens=40_000,
    )
    # (100k * 0.75 + 10k * 3.75 + 40k * 0.075) / 1M = (75,000 + 37,500 + 3,000) / 1M = 0.1155
    assert cost_38 == 0.1155
