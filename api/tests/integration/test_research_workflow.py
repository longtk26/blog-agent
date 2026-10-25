import asyncio

import pytest

from src.libs.exceptions import BadRequestException
from src.modules.agent.ports.output import ThreadStatus
from src.modules.shared.domain.entities import SourceStatus, TaskMode
from src.modules.shared.domain.value_objects import TaskStatus
from tests.fakes import FakeExtractor
from tests.integration.workflow_harness import Harness


async def test_research_only_task_completes_with_traceable_brief(checkpointer):
    h = Harness(checkpointer)
    task_id = h.create_task(TaskMode.RESEARCH_ONLY)
    await h.run(task_id)

    task = h.task(task_id)
    assert task.status == TaskStatus.COMPLETED
    assert task.research_plan["questions"][0]["id"] == "Q1"
    assert task.progress.round == 2  # Q2 was a gap after round 1 -> one follow-up round
    assert h.search.queries == ["lora low-rank adaptation paper", "peft lora tutorial", "qlora memory 4-bit"]

    sources = {s.canonical_url: s for s in h.sources(task_id)}
    # utm params stripped -> the LoRA paper found by two queries is stored once
    assert set(sources) == {
        "https://arxiv.org/abs/2106.09685",
        "https://spam.example.com/lora-deal",
        "https://huggingface.co/docs/peft/lora",
        "https://arxiv.org/abs/2305.14314",
    }
    assert sources["https://spam.example.com/lora-deal"].status == SourceStatus.LOW_QUALITY
    assert sources["https://arxiv.org/abs/2305.14314"].round == 2

    claims = h.claims(task_id)
    by_text = {c.text: c for c in claims}
    assert by_text["PEFT trains only adapter weights"].quote_verified is True
    assert by_text["A made-up claim"].quote_verified is False

    brief = h.brief(task_id)
    findings = brief.data["key_findings"]
    assert findings[0]["supported"] and findings[0]["claim_ids"]
    assert findings[2]["supported"] is False  # no evidence -> flagged, not hidden
    assert all(ref.startswith("S") for f in findings for ref in f["source_refs"])
    assert "S99" not in {s["ref"] for s in brief.data["recommended_sources"]}  # hallucinated ref dropped
    assert "](https://arxiv.org/abs/2106.09685)" in brief.markdown

    event_types = [e.type for e in h.events(task_id)]
    for expected in ("plan_ready", "query_issued", "source_found", "source_assessed", "coverage_checked", "brief_ready", "paused"):
        assert expected in event_types
    assert await h.runner.thread_status(str(task_id)) == ThreadStatus.INTERRUPTED


async def test_prompt_injection_page_is_wrapped_and_cannot_close_the_block(checkpointer):
    h = Harness(checkpointer)
    task_id = h.create_task()
    await h.run(task_id)

    prompts = [m[-1].content for m in h.models.calls_for("SourceAssessmentOut")]
    injected = next(p for p in prompts if "IGNORE PREVIOUS INSTRUCTIONS" in p)
    # the page's fake closing tag is neutralised: exactly one real closing tag, at the very end
    assert injected.count("</untrusted_source>") == 1
    assert injected.rstrip().endswith("</untrusted_source>")
    assert "&lt;/untrusted_source>" in injected
    system = h.models.calls_for("SourceAssessmentOut")[0][0].content
    assert "untrusted DATA" in system
    assert h.task(task_id).status == TaskStatus.COMPLETED


async def test_promote_continues_same_thread_without_new_searches(checkpointer):
    from src.libs.database import run_in_session
    from src.modules.shared.domain.entities import EventActor
    from src.modules.tasks.domain.task_transitions import TaskTransitioner
    from src.modules.tasks.infrastructure.persistence import TaskEventRepository, TaskRepository

    h = Harness(checkpointer)
    task_id = h.create_task()
    await h.run(task_id)
    searches = list(h.search.queries)

    run_in_session(
        lambda s: TaskTransitioner(TaskRepository(s), TaskEventRepository(s)).transition(
            task_id, TaskStatus.OUTLINING, actor=EventActor.OWNER, updates={"mode": TaskMode.ARTICLE, "angle": "first principles"}
        )
    )
    await h.runner.resume(str(task_id), {"action": "promote", "angle": "first principles"})
    await h.wait(task_id)

    assert h.task(task_id).status == TaskStatus.AWAITING_REVIEW
    assert h.search.queries == searches
    state = await h.graph.aget_state({"configurable": {"thread_id": str(task_id)}})
    assert state.values["promotion"]["angle"] == "first principles"
    assert state.values["mode"] == "article"
    assert (await h.runner.pending_interrupt(str(task_id)))["type"] == "awaiting_review"


async def test_article_mode_goes_straight_to_writing(checkpointer):
    h = Harness(checkpointer)
    task_id = h.create_task(TaskMode.ARTICLE)
    await h.run(task_id)
    assert h.task(task_id).status == TaskStatus.AWAITING_REVIEW
    statuses = [e.to_status for e in h.events(task_id) if e.type == "status_changed"]
    # one self-revision round: validating -> drafting -> validating
    assert statuses == ["researching", "outlining", "drafting", "generating_diagram", "validating", "drafting", "validating", "awaiting_review"]


async def test_failed_node_retries_from_checkpoint_without_duplicates(checkpointer):
    from src.libs.database import run_in_session
    from src.modules.agent.ports.output import ModelRole
    from src.modules.shared.domain.entities import EventActor
    from src.modules.tasks.domain.task_transitions import TaskTransitioner
    from src.modules.tasks.infrastructure.persistence import TaskEventRepository, TaskRepository

    h = Harness(checkpointer)
    real_get = h.models.get

    def fast_model_down(role):
        if role == ModelRole.FAST:
            raise RuntimeError("LLM down")
        return real_get(role)

    h.models.get = fast_model_down  # plan/search/extract succeed, assess_sources fails as a node
    task_id = h.create_task()
    await h.run(task_id)

    task = h.task(task_id)
    assert task.status == TaskStatus.FAILED
    assert task.failed_stage == TaskStatus.RESEARCHING
    assert task.resumable is True
    assert "LLM down" in task.last_error
    assert await h.runner.thread_status(str(task_id)) == ThreadStatus.PENDING

    h.models.get = real_get
    run_in_session(
        lambda s: TaskTransitioner(TaskRepository(s), TaskEventRepository(s)).transition(
            task_id, TaskStatus.RESEARCHING, actor=EventActor.OWNER, reason="retry"
        )
    )
    await h.runner.resume(str(task_id))
    await h.wait(task_id)

    assert h.task(task_id).status == TaskStatus.COMPLETED
    urls = [s.canonical_url for s in h.sources(task_id)]
    assert len(urls) == len(set(urls)) == 4
    assert max(h.extractor.calls.values()) == 1  # completed nodes (search/extract) were not re-run
    assert h.search.queries.count("lora low-rank adaptation paper") == 1


async def test_per_source_failures_do_not_fail_the_task(checkpointer):
    h = Harness(checkpointer, extractor=FakeExtractor(fail_times=1))
    task_id = h.create_task()
    await h.run(task_id)
    assert h.task(task_id).status == TaskStatus.COMPLETED
    failed = [s for s in h.sources(task_id) if s.status == SourceStatus.FAILED]
    assert len(failed) == 1 and "simulated crash" in failed[0].error


async def test_recover_marks_interrupted_runs_failed_and_keeps_paused_ones(checkpointer):
    from src.libs.database import run_in_session
    from src.modules.tasks.infrastructure.persistence import TaskRepository

    h = Harness(checkpointer)
    paused = h.create_task()
    await h.run(paused)  # completed + paused at interrupt -> not active anyway

    article = h.create_task(TaskMode.ARTICLE)
    await h.run(article)  # awaiting_review, paused at interrupt -> at rest

    crashed = h.create_task()
    def set_researching(session):
        repo = TaskRepository(session)
        task = repo.get(crashed)
        task.status = TaskStatus.RESEARCHING
        repo.update(task)
    run_in_session(set_researching)  # simulates a process that died mid-research with no checkpoint

    queued = h.create_task()

    fresh = Harness(checkpointer)  # new runner after "restart"
    await fresh.runner.recover()
    await fresh.wait(queued)

    assert fresh.task(article).status == TaskStatus.AWAITING_REVIEW
    crashed_task = fresh.task(crashed)
    assert crashed_task.status == TaskStatus.FAILED and crashed_task.resumable
    assert crashed_task.last_error == "Interrupted by API restart"
    assert fresh.task(queued).status == TaskStatus.COMPLETED  # queued tasks are started on recovery


async def test_cancel_stops_a_running_task(checkpointer):
    from src.libs.database import run_in_session
    from src.modules.shared.domain.entities import EventActor
    from src.modules.tasks.domain.task_transitions import TaskTransitioner
    from src.modules.tasks.infrastructure.persistence import TaskEventRepository, TaskRepository

    started = asyncio.Event()
    release = asyncio.Event()
    h = Harness(checkpointer)
    original = h.extractor.extract

    async def slow(url):
        started.set()
        await release.wait()
        return await original(url)

    h.extractor.extract = slow
    task_id = h.create_task()
    await h.runner.start(str(task_id))
    await asyncio.wait_for(started.wait(), 10)

    run_in_session(
        lambda s: TaskTransitioner(TaskRepository(s), TaskEventRepository(s)).transition(
            task_id, TaskStatus.REJECTED, actor=EventActor.OWNER, reason="cancelled"
        )
    )
    running = h.runner._running[str(task_id)]
    await h.runner.cancel(str(task_id))
    await asyncio.gather(running, return_exceptions=True)
    release.set()
    assert h.task(task_id).status == TaskStatus.REJECTED
    assert not h.runner.is_running(str(task_id))
    with pytest.raises(BadRequestException):
        run_in_session(
            lambda s: TaskTransitioner(TaskRepository(s), TaskEventRepository(s)).transition(
                task_id, TaskStatus.RESEARCHING, actor=EventActor.OWNER
            )
        )
