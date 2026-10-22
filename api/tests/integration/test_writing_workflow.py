import re

import psycopg
import pytest

from src.modules.agent.infrastructure.adapters import workflow_runner as runner_module
from src.modules.articles.domain.content_hash import compute_content_hash
from src.modules.shared.domain.entities import TaskMode
from src.modules.shared.domain.value_objects import TaskStatus
from tests.conftest import TEST_DB_URL
from tests.fakes import WritingScript
from tests.integration.workflow_harness import Harness


async def test_article_run_produces_validated_immutable_revision(checkpointer):
    h = Harness(checkpointer)
    task_id = h.create_task(TaskMode.ARTICLE, audience="engineers new to fine-tuning")
    await h.run(task_id)

    assert h.task(task_id).status == TaskStatus.AWAITING_REVIEW
    [revision] = h.revisions(task_id)
    assert revision.revision_number == 1 and revision.created_by == "ai"
    assert revision.title == "LoRA Fine-Tuning Explained"
    assert revision.slug == "lora-fine-tuning-explained"
    assert revision.tags == ["llm", "lora", "finetuning"]
    assert revision.content_hash == compute_content_hash(
        title=revision.title, slug=revision.slug, description=revision.description, tags=revision.tags, markdown=revision.markdown
    )

    md = revision.markdown
    assert md.startswith("# LoRA Fine-Tuning Explained\n\nFine-tuning large models is expensive.")
    assert "## Table of Contents" in md and "1. [How LoRA Works](#1-how-lora-works)" in md
    assert "## 1. How LoRA Works" in md and "## 1. 1. How" not in md  # LLM numbering stripped, heading not duplicated
    assert "## 3. Summary & What's Next" in md
    assert "### Summary & What's Next" not in md  # repeated section heading removed
    body, references = md.split("## References")
    cited = set(re.findall(r"\]\((https://[^)]+)\)", body)) - {u for u in re.findall(r"\]\((#[^)]+)\)", body)}
    listed = re.findall(r"^\d+\. \[[^\]]+\]\((https://[^)]+)\)", references, re.MULTILINE)
    assert listed and set(listed) <= cited  # references = exactly the stored sources the text cites

    # bounded self-revision touched only the section the judge flagged
    assert md.count("(revised)") == 1
    assert len(h.script.section_prompts["How LoRA Works"]) == 2
    assert len(h.script.section_prompts["QLoRA Memory Savings"]) == 1
    assert revision.metadata["history"][0]["revised_sections"] == ["s1"]
    assert revision.metadata["self_revisions"] == 1
    assert revision.metadata["claim_map"]["s1"][0]["claim_ids"]
    assert revision.metadata["style_guide_version"] == "style-v2"

    evaluations = {e.kind: e for e in h.evaluations(revision.id)}
    assert evaluations["deterministic"].passed is True
    assert evaluations["judge"].passed is True and evaluations["judge"].scores["factual_support"] == 4

    with psycopg.connect(TEST_DB_URL) as conn, pytest.raises(psycopg.errors.RaiseException, match="immutable"):
        conn.execute("UPDATE article_revisions SET title = 'tampered' WHERE id = %s", (revision.id,))

    assert (await h.runner.pending_interrupt(str(task_id)))["type"] == "awaiting_review"


async def test_self_revision_is_bounded(checkpointer):
    class AlwaysBlocking(WritingScript):
        def __call__(self, schema, messages):
            self.judge_calls = 0  # every judge call behaves like the first (blocking)
            return super().__call__(schema, messages)

    h = Harness(checkpointer, responder=AlwaysBlocking())
    task_id = h.create_task(TaskMode.ARTICLE)
    await h.run(task_id)

    [revision] = h.revisions(task_id)
    assert revision.metadata["self_revisions"] == 2  # DRAFT_MAX_SELF_REVISIONS
    judge = {e.kind: e for e in h.evaluations(revision.id)}["judge"]
    assert judge.passed is False and any(i.severity == "blocker" for i in judge.issues)
    assert revision.metadata["unsupported_statements"] == ["LoRA is always better"]
    assert h.task(task_id).status == TaskStatus.AWAITING_REVIEW  # issues are surfaced for review, not hidden


async def test_outline_review_pauses_and_accepts_owner_edits(checkpointer):
    h = Harness(checkpointer)
    task_id = h.create_task(TaskMode.ARTICLE, review_outline=True)
    await h.run(task_id)

    assert h.task(task_id).status == TaskStatus.OUTLINING
    assert (await h.runner.pending_interrupt(str(task_id)))["type"] == "outline_review"
    outline = h.task(task_id).outline
    assert [s["heading"] for s in outline["sections"]] == ["How LoRA Works", "QLoRA Memory Savings", "Summary & What's Next"]

    edited = [dict(s) for s in outline["sections"]]
    edited[1]["heading"] = "QLoRA: 4-bit Memory Savings"
    await h.runner.resume(str(task_id), {"action": "approve_outline", "outline": {"sections": edited}})
    await h.wait(task_id)

    assert h.task(task_id).status == TaskStatus.AWAITING_REVIEW
    assert "## 2. QLoRA: 4-bit Memory Savings" in h.revisions(task_id)[0].markdown


async def test_placeholder_interrupts_are_resumed_on_recovery(checkpointer, monkeypatch):
    from src.libs.database import run_in_session
    from src.modules.tasks.infrastructure.persistence import TaskRepository

    h = Harness(checkpointer)
    task_id = h.create_task(TaskMode.RESEARCH_ONLY)
    await h.run(task_id)  # paused at await_promotion

    def mark_outlining(session):  # what a promote did while the outline node was still a placeholder
        repo = TaskRepository(session)
        task = repo.get(task_id)
        task.status, task.mode = TaskStatus.OUTLINING, TaskMode.ARTICLE
        repo.update(task)

    run_in_session(mark_outlining)
    monkeypatch.setattr(runner_module, "PLACEHOLDER_INTERRUPTS", {"awaiting_promotion"})
    fresh = Harness(checkpointer)
    await fresh.runner.recover()
    await fresh.wait(task_id)
    assert fresh.task(task_id).status == TaskStatus.AWAITING_REVIEW
    assert fresh.revisions(task_id)


async def test_draft_uses_owner_style_guide(checkpointer):
    from src.libs.database import run_in_session
    from src.modules.shared.domain.entities import StyleGuideEntity
    from src.modules.styles.infrastructure.persistence import StyleGuideRepository

    run_in_session(lambda s: StyleGuideRepository(s).create(StyleGuideEntity(version="owner-1", content="ALWAYS USE PIRATE METAPHORS " * 5)))
    try:
        h = Harness(checkpointer)
        task_id = h.create_task(TaskMode.ARTICLE)
        await h.run(task_id)
        assert "ALWAYS USE PIRATE METAPHORS" in h.script.section_prompts["How LoRA Works"][0]
        assert h.revisions(task_id)[0].metadata["style_guide_version"] == "owner-1"
    finally:
        with psycopg.connect(TEST_DB_URL, autocommit=True) as conn:
            conn.execute("TRUNCATE style_guides")
