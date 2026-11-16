"""AutoMemory's layers (eam/automem): typed notes and their schema, the pure core, and the stores, which must all
behave the same (one conformance suite)."""

import json
import multiprocessing as mp
import os
import stat

import pytest

from eam.automem import core as C
from eam.automem.notes import Note, dump_document, load_document
from eam.automem.storage import JsonStore, MemoryStore, SQLiteStore
from eam.mcp_server import Server
from eam.memory_skill import MemorySkill

POSIX = os.name == "posix"


# ---- notes and schema -----------------------------------------------------------------------------------------------
def test_version_1_notes_are_migrated_on_the_next_write(tmp_path):
    root = tmp_path / "m"
    root.mkdir()
    (root / "notes.json").write_text(json.dumps({"totals": "Acme = 10", "plan": "next: round 3"}))
    skill = MemorySkill(root)
    assert skill.notes() == {"totals": "Acme = 10", "plan": "next: round 3"}
    assert all(n.source == "migrated" for n in skill.records())
    skill.write_note("new", "x")
    doc = json.loads((root / "notes.json").read_text())
    assert doc["version"] == 2 and [n["name"] for n in doc["notes"]] == ["totals", "plan", "new"]


def test_unknown_types_fall_back_and_documents_round_trip():
    notes = [Note("a", "1", type="decision", files=["x.py"]), Note("b", "2", type="nonsense")]
    back = load_document(json.loads(json.dumps(dump_document(notes))))
    assert [n.type for n in back] == ["decision", "note"] and back[0].files == ["x.py"]


# ---- core -----------------------------------------------------------------------------------------------------------
def test_a_superseding_note_retires_the_old_one_from_recall():
    notes: list[Note] = []
    C.upsert(notes, C.make_note("cache plan", "use a dict", max_chars=1000, type="decision"))
    C.upsert(notes, C.make_note("cache plan v2", "use lru_cache: the dict leaked", max_chars=1000, type="decision",
                                supersedes="cache plan"))
    text = C.recall_text(notes, 10_000, wrap=False)
    assert "lru_cache" in text and "use a dict" not in text and len(notes) == 2


def test_recall_shows_type_date_and_files_and_respects_the_budget():
    notes: list[Note] = []
    C.upsert(notes, C.make_note("bug", "timezone offset dropped", max_chars=1000, type="fact", files=["io/dates.py"]))
    text = C.recall_text(notes, 1000)
    assert "## bug (fact, 20" in text and "Files: io/dates.py" in text and text.startswith("<memory")
    for i in range(50):
        C.upsert(notes, C.make_note(f"n{i}", "y" * 400, max_chars=1000))
    kept, rest = C.select_recall(notes, 1000)
    assert 1 <= len(kept) < 51 and kept[-1].name == "n49" and "bug" in rest


def test_notes_are_redacted_by_the_core():
    note = C.make_note("deploy", "token ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789", max_chars=1000)
    assert "ghp_" not in note.text


# ---- stores: one conformance suite ----------------------------------------------------------------------------------
@pytest.fixture(params=["json", "sqlite", "memory"])
def make_store(request, tmp_path):
    def make():
        return {"json": lambda: JsonStore(tmp_path / "j"), "sqlite": lambda: SQLiteStore(tmp_path / "s" / "mem.db"),
                "memory": lambda: shared}[request.param]()
    shared = MemoryStore()
    make.kind = request.param
    return make


def test_store_keeps_notes_across_instances(make_store):
    with make_store().transaction() as notes:
        C.upsert(notes, Note("a", "1", type="fact"))
        C.upsert(notes, Note("b", "2"))
    with make_store().transaction() as notes:
        C.upsert(notes, Note("a", "3", type="fact"))  # replaced: moves to the end
    loaded = make_store().load()
    assert [(n.name, n.text) for n in loaded] == [("b", "2"), ("a", "3")] and loaded[1].type == "fact"


def test_a_failed_transaction_changes_nothing(make_store):
    with make_store().transaction() as notes:
        C.upsert(notes, Note("a", "1"))
    with pytest.raises(RuntimeError):
        with make_store().transaction() as notes:
            C.upsert(notes, Note("b", "2"))
            raise RuntimeError
    assert [n.name for n in make_store().load()] == ["a"]


def test_store_artifacts_round_trip_and_reject_bad_ids(make_store):
    store = make_store()
    a, b = store.put_artifact("first"), store.put_artifact("second", label="x")
    assert a != b and store.get_artifact(f"artifact://{b}") == "second"
    for bad in ("../notes.json", "a1", "a00099"):
        with pytest.raises(ValueError):
            store.get_artifact(bad)


def test_library_works_on_every_store(make_store):
    skill = MemorySkill(store=make_store(), window=20_000)
    skill.write_note("plan", "fix cache.py", type="decision", files=["utils/cache.py"])
    skill.save_session("FINAL ANSWER: fixed", label="session 1")
    pre = MemorySkill(store=make_store(), window=20_000).session_preamble()
    assert "fix cache.py" in pre and "(result," in pre and "(decision," in pre
    ref = skill.offload("z" * 50_000)
    assert skill.read_artifact(ref, length=10).startswith("zzzzzzzzzz")


def _sqlite_writer(path, k):
    skill = MemorySkill(store=SQLiteStore(path), window=50_000)
    for i in range(15):
        skill.write_note(f"w{k}-{i}", "v")


@pytest.mark.skipif(not POSIX, reason="fork start method")
def test_sqlite_store_loses_no_notes_under_concurrent_writers(tmp_path):
    path = tmp_path / "mem.db"
    SQLiteStore(path)
    procs = [mp.get_context("fork").Process(target=_sqlite_writer, args=(path, k)) for k in range(4)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(60)
    assert len(SQLiteStore(path).load()) == 60
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_mcp_write_note_accepts_type_files_and_supersedes(tmp_path):
    srv = Server(MemorySkill(tmp_path / "m"))
    srv.call("write_note", {"name": "plan", "content": "dict cache"})
    out = srv.call("write_note", {"name": "plan v2", "content": "lru_cache", "type": "decision",
                                  "files": ["cache.py"], "supersedes": "plan"})
    assert "superseded" in out
    recall = srv.call("recall", {})
    assert "lru_cache" in recall and "dict cache" not in recall


def test_store_prune_bounds_artifacts_by_size(make_store):
    store = make_store()
    ids = [store.put_artifact("x" * 1000) for _ in range(10)]
    store.prune(0, 3500)
    kept = [a for a in ids if _exists(store, a)]
    assert kept == ids[-len(kept):] and 1 <= len(kept) <= 3


def _exists(store, aid):
    try:
        store.get_artifact(aid)
        return True
    except ValueError:
        return False
