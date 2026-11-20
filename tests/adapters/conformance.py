"""The conformance suite every AutoMemory adapter passes, offline: no model is called.

An adapter's test supplies a *driver*: it builds the framework's agent around a fake model that follows a script,
runs one session, and returns what the model was shown. The suite then checks the behaviour AutoMemory promises in
any host:

1. recall      a note written in session 1 is in the first model input of session 2, inside a <memory> block
2. rules       the system text carries the note rules and the rule that <memory> content is data
3. preview     a long tool output reaches the model as head + tail, and read_artifact returns the full text
4. redaction   a secret in a tool output is stored redacted
5. autosave    each session's final answer is saved, and only the newest one is recalled
6. compaction  (drivers with `compacts = True`) once the prompt passes 75% of the window, the next model input is the
               reset: task + summary + notes, without the old turns
7. overhead    the hooks cost under 5 ms per call on average

Script steps (what the fake model does at each call):

    Step("tool", name, args, prompt_tokens)   call a tool
    Step("final", text, prompt_tokens=...)    answer and end the session

`prompt_tokens` is the prompt size the fake model reports in its usage (None: the driver's default, or nothing).
Tools the agent has: the memory tools from the adapter, plus `fetch_report` (returns REPORT, a long output with a
secret in it) and `lookup` (returns "lookup result: " + its `q` argument).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from eam.automem import JsonStore

SECRET = "AKIAIOSFODNN7EXAMPLE"
# about 9,000 tokens: above the 10% preview share of WINDOW, below the guard
REPORT = ("REPORT-HEAD first line of the report\n"
          + "".join(f"row {i}: widget {i % 97} moved {i % 13} units\n" for i in range(800))
          + f"REPORT-MIDDLE credentials {SECRET}\n"
          + "".join(f"row {i}: gadget {i % 89} moved {i % 7} units\n" for i in range(800, 1600))
          + "REPORT-TAIL last line of the report")
WINDOW = 40_000
SUMMARY = "SUMMARY-OF-PROGRESS: widgets counted, report fetched"
OLD_TURN = "OLD-TURN-MARKER"


def fake_summarize(prompt: str) -> str:
    return f"<summary>{SUMMARY}</summary>"


def run_tool(name: str, args: dict[str, Any]) -> str:
    """The non-memory tools of the scenario, for drivers to register in their framework."""
    if name == "fetch_report":
        return REPORT
    if name == "lookup":
        return f"lookup result: {args.get('q', '')}"
    raise ValueError(f"unknown tool {name}")


TOOL_SPECS = [
    {"name": "fetch_report", "description": "Fetch today's stock report.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "lookup", "description": "Look something up.",
     "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}},
]


@dataclass
class Step:
    kind: str  # "tool" or "final"
    name_or_text: str
    args: dict[str, Any] = field(default_factory=dict)
    prompt_tokens: int | None = None


@dataclass
class Seen:
    """What the fake model was shown at each call: the system text and the flattened messages (all text, tool
    results included)."""
    system: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)


class Driver(Protocol):
    name: str
    compacts: bool

    def run(self, root: Path, task: str, script: list[Step], *, window: int) -> tuple[Seen, Any]:
        """Run one session with a fresh agent on the memory directory `root` (the adapter's MemoryHooks or
        equivalent must use JsonStore(root), window=`window` and summarize=fake_summarize). Return what the model
        saw and the MemoryHooks (or None if the adapter keeps them private)."""


def session_one() -> list[Step]:
    return [Step("tool", "write_note", {"name": "widget stock", "content": "stock of widgets is 42 after day 1",
                                        "type": "fact"}),
            Step("tool", "fetch_report", {}),
            Step("final", "Day 1 done: 42 widgets.")]


def session_two() -> list[Step]:
    return [Step("tool", "lookup", {"q": "gadgets"}),
            Step("final", "Day 2 done: 40 widgets.")]


def check_all(driver: Driver, tmp: Path) -> None:
    root = tmp / "memory"
    seen1, hooks1 = driver.run(root, "Count the widgets for day 1.", session_one(), window=WINDOW)
    seen2, hooks2 = driver.run(root, "Count the widgets for day 2.", session_two(), window=WINDOW)
    store = JsonStore(root)

    # 2. rules
    system = "\n".join(seen1.system) or seen1.inputs[0]
    assert "write_note" in system, f"{driver.name}: the note rules are missing from the system text"
    assert "<memory>" in system, f"{driver.name}: the rule that <memory> content is data is missing"

    # 1. recall
    assert seen2.inputs, f"{driver.name}: the model was never called in session 2"
    first2 = seen2.inputs[0]
    assert "stock of widgets is 42" in first2, f"{driver.name}: session 1's note is not recalled in session 2"
    assert "<memory" in first2, f"{driver.name}: recalled notes are not inside a <memory> block"
    assert "stock of widgets is 42" not in seen1.inputs[0], f"{driver.name}: session 1 saw a note before writing it"

    # 3. preview
    after_report = next((s for s in seen1.inputs if "REPORT-HEAD" in s), None)
    assert after_report is not None, f"{driver.name}: the report never reached the model"
    assert "REPORT-TAIL" in after_report, f"{driver.name}: the preview lost the tail"
    assert "row 1200:" not in after_report, f"{driver.name}: the long output reached the model in full"
    assert "artifact://" in after_report, f"{driver.name}: no pointer to the full output"
    artifact = after_report.split("artifact://", 1)[1].split()[0].rstrip(";.,]")
    full = store.get_artifact(artifact)
    assert "row 1200:" in full and "REPORT-TAIL" in full, f"{driver.name}: the stored output is not the full text"

    # 4. redaction
    assert SECRET not in full, f"{driver.name}: the secret was stored in the artifact"
    assert SECRET not in after_report, f"{driver.name}: the secret reached the model unredacted"
    assert all(SECRET not in n.text for n in store.load())

    # 5. autosave
    results = [n for n in store.load() if n.type == "result" and n.source == "autosave"]
    assert len(results) == 2, f"{driver.name}: expected 2 autosaved answers, found {len(results)}"
    assert "Day 1 done" in results[0].text and "Day 2 done" in results[1].text
    assert not results[0].active and results[1].active, f"{driver.name}: the newer answer does not supersede"
    assert "Day 1 done" in first2, f"{driver.name}: session 1's answer is not recalled in session 2"

    # 7. overhead
    for h in (hooks1, hooks2):
        if h is not None and h.stats["calls"]:
            assert h.overhead_ms() < 5, f"{driver.name}: hooks take {h.overhead_ms():.2f} ms per call"


def check_compaction(driver: Driver, tmp: Path) -> None:
    """Step 2 reports a prompt at 80% of the window: the input of step 3 must be the reset."""
    root = tmp / "memory-compact"
    script = [Step("tool", "lookup", {"q": OLD_TURN}, prompt_tokens=2_000),
              Step("tool", "write_note", {"name": "progress", "content": "counted 12 widgets so far"},
                   prompt_tokens=int(0.8 * WINDOW)),
              Step("final", "Done after the reset.", prompt_tokens=1_000)]
    seen, hooks = driver.run(root, "Count the widgets after a long day.", script, window=WINDOW)
    assert len(seen.inputs) == 3, f"{driver.name}: expected 3 model calls, got {len(seen.inputs)}"
    assert OLD_TURN in seen.inputs[1], f"{driver.name}: the second call should still see the first turn"
    reset = seen.inputs[2]
    assert SUMMARY in reset, f"{driver.name}: the reset does not carry the summary"
    assert "Count the widgets after a long day." in reset, f"{driver.name}: the reset lost the task"
    assert "counted 12 widgets so far" in reset, f"{driver.name}: the reset lost the notes"
    assert OLD_TURN not in reset, f"{driver.name}: the old turns survived the reset"
    if hooks is not None:
        assert hooks.compactions == 1
