"""Step 5 fixes: stale autosaved answers leave recall, ids in notes, and a final answer sent back once while the last
test run still fails."""

from eam.bench.runner import run_instance
from eam.bench.tasks import FAMILIES
from eam.memory_skill import MemorySkill
from eam.models import MOCK_MODELS
from eam.techniques.auto_memory import NOTE_IDS, TEST_FAIL, AutoMemory

M = MOCK_MODELS["mock-strong"]


def test_library_autosave_supersedes_the_previous_answer(tmp_path):
    s = MemorySkill(tmp_path, window=16_000)
    s.write_note("plan", "fix the cache")
    s.save_session("day 1: apples=5", label="session 1 final answer")
    s.save_session("day 2: apples=7", label="session 2 final answer")
    pre = s.session_preamble()
    assert "apples=7" in pre and "apples=5" not in pre and "fix the cache" in pre
    assert "superseded" in s.read_notes("session 1 final answer")  # still readable by name
    s.save_session("day 2 again: apples=8", label="session 2 final answer")  # same name: replaced, not superseded
    assert "apples=8" in s.session_preamble()


def test_bench_recall_shows_only_the_latest_autosave():
    am = AutoMemory(recall_results="latest")
    am._ws.notes.update({"stock": "a=1", "session 1 final answer": "old", "session 2 final answer": "new"})
    text = am._notes_text()
    assert "new" in text and "## session 1 final answer" not in text and "session 1 final answer" in text
    default = AutoMemory()
    default._ws.notes.update(am._ws.notes)
    assert "## session 1 final answer" in default._notes_text()  # the default recalls every note, as measured


def test_note_ids_adds_the_instruction():
    assert NOTE_IDS in (AutoMemory(note_ids=True).system_addendum() or "")
    assert NOTE_IDS not in (AutoMemory().system_addendum() or "")


def test_failing_test_output_is_recognised():
    assert TEST_FAIL.search("Ran 12 tests in 0.1s\n\nFAILED (failures=2)")
    assert TEST_FAIL.search("=== 3 failed, 10 passed in 1.2s ===")
    assert not TEST_FAIL.search("Ran 162 tests in 0.120s\n\nOK")
    assert not TEST_FAIL.search("=== 10 passed in 1.2s ===")


def test_verify_sends_a_final_answer_back_once():
    class Ctx:
        state, events = {}, []

        def log(self, kind, **kw):
            self.events.append(kind)

    am, ctx = AutoMemory(verify=True), Ctx()
    ctx.state["automem_tests"] = "FAILED (failures=1)"
    assert "still reports failures" in am.on_final(ctx, "FINAL ANSWER: done")
    ctx.state["automem_tests"] = None
    assert am.on_final(ctx, "FINAL ANSWER: done") is None


def test_runs_with_the_new_switches_finish():
    for fam in ("ledger_audit", "repo_debug"):
        row = run_instance(FAMILIES[fam](0), "automem:ingest=0.1,recall_results=latest,note_ids=true,verify=true",
                           backend="mock", model=M, aux_model=M, models=MOCK_MODELS)
        assert not row.get("error") and row["sessions"] >= 1
