import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from src.modules.evaluation.domain.deterministic_evaluators import (
    ALL_DETERMINISTIC_EVALUATORS,
    eval_citation_coverage,
    eval_cost_usd,
    eval_diagram_valid,
    eval_latency_s,
    eval_markdown_valid,
    eval_min_sources_met,
    eval_render_contract_violations,
    eval_required_sections_present,
    eval_source_quality_mix,
    eval_tool_error_rate,
)
from src.modules.evaluation.domain.judge_evaluators import (
    eval_audience_depth_fit,
    eval_factual_support,
    eval_must_cover_coverage,
    eval_pairwise_preference,
    eval_style_consistency,
)

GOOD_MARKDOWN = """# Understanding LoRA Fine-Tuning

Low-Rank Adaptation (LoRA) reduces trainable parameters by decomposing weight updates.

## Table of Contents
- [Architecture](#architecture)
- [Summary](#summary)
- [References](#references)

## Architecture

We decompose the weight matrix update:

```python
import torch
print("LoRA weights initialized")
```

The adapter matrix merges into base weights at inference time.
See [HuggingFace Documentation](https://huggingface.co/docs) for setup.

```mermaid
flowchart LR
    Input --> W0[Base Model W0]
    Input --> A[Matrix A] --> B[Matrix B]
    W0 --> Output
    B --> Output
```

## Summary

LoRA achieves full fine-tuning performance with 90% less VRAM.

## References
- [HuggingFace Documentation](https://huggingface.co/docs)
"""

BAD_MARKDOWN = """
Intro line without heading first.

# First Title

# Second Title

### Skipped Level directly to H3

```
code without language tag
```
"""


def test_eval_markdown_valid():
    res_good = eval_markdown_valid(inputs={}, outputs={"markdown": GOOD_MARKDOWN}, reference={"format": "concept"})
    assert res_good["score"] == 1
    assert "valid" in res_good["comment"].lower()

    res_bad = eval_markdown_valid(inputs={}, outputs={"markdown": BAD_MARKDOWN}, reference={"format": "concept"})
    assert res_bad["score"] == 0
    assert "blocker" in res_bad["comment"].lower()


def test_eval_render_contract_violations():
    res_good = eval_render_contract_violations(inputs={}, outputs={"markdown": GOOD_MARKDOWN}, reference={"format": "concept"})
    assert res_good["score"] == 0.0

    res_bad = eval_render_contract_violations(inputs={}, outputs={"markdown": BAD_MARKDOWN}, reference={"format": "concept"})
    assert res_bad["score"] >= 2.0


def test_eval_citation_coverage():
    outputs_with_claim_map = {
        "markdown": GOOD_MARKDOWN,
        "claim_map": [
            {"sentence": "LoRA reduces trainable parameters", "claim_ids": ["c1"]},
            {"sentence": "Adapter merges at inference time", "claim_ids": ["c2"]},
            {"sentence": "Uncited statement", "claim_ids": []},
        ],
    }
    res = eval_citation_coverage(inputs={}, outputs=outputs_with_claim_map, reference={})
    assert res["score"] == pytest.approx(2 / 3, 0.01)

    # Empty claim map fallback to links
    res_fallback = eval_citation_coverage(inputs={}, outputs={"markdown": GOOD_MARKDOWN}, reference={})
    assert res_fallback["score"] > 0.0


def test_eval_source_quality_mix():
    outputs = {
        "sources": [
            {"source_type": "paper", "quality_score": 0.9},
            {"source_type": "official_docs", "quality_score": 0.85},
            {"source_type": "blog", "quality_score": 0.4},
        ]
    }
    res = eval_source_quality_mix(inputs={}, outputs=outputs, reference={})
    assert res["score"] == pytest.approx(2 / 3, 0.01)


def test_eval_min_sources_met():
    outputs = {"sources": [{"id": "s1"}, {"id": "s2"}, {"id": "s3"}]}
    assert eval_min_sources_met(inputs={}, outputs=outputs, reference={"min_sources": 3})["score"] == 1
    assert eval_min_sources_met(inputs={}, outputs=outputs, reference={"min_sources": 5})["score"] == 0


def test_eval_required_sections_present():
    reference = {"expected_sections": ["Architecture", "Summary", "Deployment"]}
    res = eval_required_sections_present(inputs={}, outputs={"markdown": GOOD_MARKDOWN}, reference=reference)
    # Architecture and Summary are in GOOD_MARKDOWN, Deployment is missing -> 2/3
    assert res["score"] == pytest.approx(2 / 3, 0.01)


def test_eval_diagram_valid():
    res_expected_present = eval_diagram_valid(
        inputs={}, outputs={"markdown": GOOD_MARKDOWN}, reference={"diagram_expected": True}
    )
    assert res_expected_present["score"] == 1

    res_expected_missing = eval_diagram_valid(
        inputs={}, outputs={"markdown": BAD_MARKDOWN}, reference={"diagram_expected": True}
    )
    assert res_expected_missing["score"] == 0

    res_not_expected = eval_diagram_valid(
        inputs={}, outputs={"markdown": BAD_MARKDOWN}, reference={"diagram_expected": False}
    )
    assert res_not_expected["score"] == 1


def test_eval_tool_error_rate():
    outputs = {
        "tool_calls": [
            {"name": "web_search", "error": None},
            {"name": "extract_page", "error": "HTTP 500"},
            {"name": "web_search", "error": None},
            {"name": "extract_page", "error": None},
        ]
    }
    res = eval_tool_error_rate(inputs={}, outputs=outputs, reference={})
    assert res["score"] == 0.25


def test_eval_cost_and_latency():
    outputs = {"total_cost_usd": 0.045123, "total_latency_ms": 15400}
    assert eval_cost_usd(inputs={}, outputs=outputs, reference={})["score"] == 0.045123
    assert eval_latency_s(inputs={}, outputs=outputs, reference={})["score"] == 15.4


class FakeStructuredModel:
    def __init__(self, response_obj):
        self.response_obj = response_obj

    def with_structured_output(self, schema):
        fake_self = self

        class Runnable:
            async def ainvoke(self, messages, config=None):
                return fake_self.response_obj

        return Runnable()


@pytest.mark.asyncio
async def test_llm_judge_evaluators_with_fake_model():
    from src.modules.evaluation.domain.judge_evaluators import (
        JudgeEvaluationOut,
        PairwiseEvaluationOut,
    )

    fake_judge = FakeStructuredModel(JudgeEvaluationOut(score=0.92, reasoning="Excellent technical rigor"))

    res_factual = await eval_factual_support(
        inputs={},
        outputs={"markdown": GOOD_MARKDOWN, "claims": []},
        reference={"known_facts": ["LoRA decomposes matrix updates."]},
        model=fake_judge,
    )
    assert res_factual["score"] == 0.92
    assert "rigor" in res_factual["comment"]

    res_must_cover = await eval_must_cover_coverage(
        inputs={},
        outputs={"markdown": GOOD_MARKDOWN},
        reference={"must_cover": ["Matrix decomposition"]},
        model=fake_judge,
    )
    assert res_must_cover["score"] == 0.92

    res_style = await eval_style_consistency(
        inputs={}, outputs={"markdown": GOOD_MARKDOWN}, reference={}, model=fake_judge
    )
    assert res_style["score"] == 0.92

    res_depth = await eval_audience_depth_fit(
        inputs={"audience": "ML engineers", "depth": "deep_dive"},
        outputs={"markdown": GOOD_MARKDOWN},
        reference={},
        model=fake_judge,
    )
    assert res_depth["score"] == 0.92

    # Pairwise preference evaluator
    fake_pairwise = FakeStructuredModel(
        PairwiseEvaluationOut(preference="A", score=1.0, reasoning="Candidate A is cleaner and has code examples")
    )
    res_pair = await eval_pairwise_preference(
        inputs={"topic": "LoRA fine tuning"},
        candidate_a={"markdown": GOOD_MARKDOWN},
        candidate_b={"markdown": BAD_MARKDOWN},
        model=fake_pairwise,
    )
    assert res_pair["preference"] == "A"
    assert res_pair["score"] == 1.0
    assert "cleaner" in res_pair["comment"]
