"""AutoMemory v1 — this project's combined memory skill, built from the phase-1 measurements
(docs/results/2026-10-22-*.md, 2026-10-23-long-horizon-cross-model.md). Every component is a switch, so each one
can be ablated against the full skill.

Components and the evidence behind them:

* ``workspace`` — persistent notes across sessions (FS-Researcher's file-system workspace, our minimal port).
  The only model-robust method on the multi-session tasks, in combination with compaction.
* ``recall`` — the notes are put into the first message of every session (and after every compaction), instead
  of trusting the model to call `read_notes`: Haiku re-read old files rather than its notes (0.34 vs Sonnet 0.99).
* ``autosave`` — each session's final answer is saved as a note automatically (no LLM call): what a later
  session most often needs is an earlier session's result.
* ``guard`` — an in-step size guard. While a step's tool results arrive, any result that would push the next
  prompt past ``guard`` × window is offloaded to the artifact store at once (a pointer stays; `read_artifact`
  pages it back). ReSum checks its trigger only between calls, so a step of many parallel calls (Haiku: one step
  added 13–18K tokens) overflowed the window before it could act, whatever the trigger margin.
* ``keep_recent`` — after a compaction the last steps are kept verbatim after the summary (as Claude Code's own
  compaction does): with only the reset message left, Haiku's tool-call replies degenerated.
* ``compact`` — compaction when the window binds: ``resum`` (official ReSum prompts; rare resets keep the prompt
  cache alive), ``mask`` (observation masking: the only single-session method that recovered on Haiku) or
  ``none``. The trigger is a fraction of the actual window (``trigger`` × window) rather than a fixed K. Until
  then the context is kept whole, which on a cached route is the cheapest correct option while it fits.
* cache-awareness — all edits happen at ingestion (guard, offload) or at rare resets (compaction, recall);
  nothing rewrites earlier history every step (masking aside, when chosen), because history rewrites are paid as
  cache writes (2× input price on the Claude Code route).

The summariser is the run's auxiliary model (``--aux-model``), so a cheaper model can summarise for a stronger
agent.
"""

from __future__ import annotations

from eam.techniques.base import Technique
from eam.techniques.obs_mask import ObservationMasking
from eam.techniques.refold import ReFold, prompt_layer
from eam.techniques.resum import ReSum
from eam.techniques.workspace import NoteWorkspace
from eam.tokens import estimate_tokens

GUARDED = ("[Output of {name} moved out of the context to keep it within the window ({tokens:,} tokens). "
           "It is stored at {pointer}; read it with read_artifact (offset/length to page), one item per step.]")
RECALL = ("Your persistent workspace notes (saved in earlier sessions or before the conversation was "
          "compacted):\n\n{notes}\n\nUse them; keep them up to date with write_note.")


class AutoMemory(Technique):
    name = "automem"
    source = "this project: AutoMemory v1 (workspace + recall + autosave + in-step guard + compaction)"
    provenance = "this project (combination of measured methods; ReSum prompts official)"
    cache_safe = False  # compaction rewrites history (rarely)

    def __init__(self, workspace: bool = True, recall: bool = True, autosave: bool = True, guard: float = 0.9,
                 compact: str = "resum", trigger: float = 0.75, default_window: int = 200_000,
                 token_ratio: float = 1.5, keep_recent: int = 2, fold: bool = False, ingest: float = 0.0,
                 ingest_preview: int = 750):
        self.workspace = bool(workspace)
        self.recall = bool(recall) and self.workspace
        self.autosave = bool(autosave) and self.workspace
        self.guard = float(guard)  # 0 disables the guard
        self.compact = str(compact)
        self.trigger = float(trigger)
        self.default_window = int(default_window)
        self.token_ratio = float(token_ratio)  # real tokens per estimated token, conservative for dense text
        self.keep_recent = int(keep_recent)  # complete steps kept verbatim after a compaction
        # v2 switches (docs/new_methods.md): ReFold's dedup + STALE folding as a render layer, and Strands-style
        # head/tail previews at ingestion for outputs above `ingest` × window (0 = off), retrievable by reference
        self.fold = bool(fold)
        self.ingest = float(ingest)
        self.ingest_preview = int(ingest_preview)
        self._refold = ReFold() if self.fold else None
        self._stash: dict[str, str] = {}
        self._ws = NoteWorkspace() if self.workspace else None
        self._compactor = None
        self._sessions = 0

    # ---- helpers -------------------------------------------------------------------------------------------
    def _window(self, ctx) -> int:
        return ctx.context_limit or getattr(ctx.model, "context_window", None) or self.default_window

    def _notes_text(self) -> str:
        if not self._ws or not self._ws.notes:
            return ""
        return "\n\n".join(f"## {k}\n{v}" for k, v in sorted(self._ws.notes.items()))

    def _make_compactor(self, ctx):
        if self.compact == "resum":
            # ReSum's trigger is 0.9·(K·1024 − 1000); choose K so that it fires at `trigger` × window.
            k = (self.trigger * self._window(ctx) / 0.9 + 1000) / 1024
            return ReSum(max_context_k=k)
        if self.compact == "mask":
            return ObservationMasking()
        return None

    # ---- hooks ---------------------------------------------------------------------------------------------
    def tools(self, ctx):
        tools = self._ws.tools(ctx) if self._ws else []
        if self._refold:
            tools += self._refold.tools(ctx)
        if self.ingest:
            from eam.techniques.strands import StrandsHarness

            sh = StrandsHarness(memory=False)
            sh._stash = self._stash
            tools += sh.tools(ctx)
        return tools

    def system_addendum(self):
        parts = []
        if self._ws:
            parts.append(self._ws.system_addendum())
        if self._refold:
            parts.append(self._refold.system_addendum())
        return "\n\n".join(parts) or None

    def render(self, ctx, req):
        return self._refold.render(ctx, req) if self._refold else req

    def after_call(self, ctx, resp):
        if self._refold:
            self._refold.after_call(ctx, resp)

    def on_session_start(self, ctx):
        self._sessions += 1
        self._compactor = self._make_compactor(ctx)
        ctx.state["automem_guard_step"] = (-1, 0)
        self._stash.clear()
        if self._refold:
            self._refold.on_session_start(ctx)  # puts the PROGRESS/STALE protocol into the first message
        if self.recall and self._notes_text():
            ctx.preamble.append(RECALL.format(notes=self._notes_text()))
            ctx.log("automem_recall", chars=len(self._notes_text()))

    def before_call(self, ctx):
        if self._compactor is None:
            return
        if isinstance(self._compactor, ReSum):
            tail = self._recent_tail(ctx)
            # the guard's prediction of the coming prompt (real tokens), if it is larger than the last real size
            predicted = ctx.state.get("automem_predicted", 0)
            if predicted > ctx.last_prompt_tokens:
                saved, ctx.last_prompt_tokens = ctx.last_prompt_tokens, predicted
                n_before = len(ctx.events)
                self._compactor.before_call(ctx)
                compacted = any(e["kind"] == "resum_rebuild" for e in ctx.events[n_before:])
                ctx.last_prompt_tokens = 0 if compacted else saved
            else:
                n_before = len(ctx.events)
                self._compactor.before_call(ctx)
                compacted = any(e["kind"] == "resum_rebuild" for e in ctx.events[n_before:])
            if compacted:
                ctx.state["automem_predicted"] = 0
                if self.recall and self._notes_text():  # the reset message replaced the session's first message
                    ctx.messages[0]["content"].append({"text": RECALL.format(notes=self._notes_text())})
                if self._refold:  # the rebuilt history starts a new step numbering; the protocol stays visible
                    self._refold._reset()
                    ctx.messages[0]["content"].append({"text": prompt_layer(self._refold.k)[1]})
                if tail:  # the model keeps seeing its own latest calls (Haiku's replies degenerated without them)
                    ctx.messages.extend(tail)
                    ctx.log("automem_kept_recent", messages=len(tail))
        else:
            self._compactor.before_call(ctx)

    def _recent_tail(self, ctx) -> list:
        """The last `keep_recent` complete steps (assistant call + its results), within 15% of the window."""
        import copy

        from eam.techniques.steps import step_indices

        if self.keep_recent <= 0:
            return []
        steps = [(a, u) for a, u in step_indices(ctx.messages) if u is not None][-self.keep_recent:]
        tail: list = []
        for a, u in reversed(steps):
            chunk = copy.deepcopy(ctx.messages[a: u + 1])
            size = sum(estimate_tokens(str(b)) for m in chunk for b in m["content"]) * self.token_ratio
            if size + sum(estimate_tokens(str(b)) for m in tail for b in m["content"]) * self.token_ratio \
                    > 0.15 * self._window(ctx):
                break
            tail = chunk + tail
        return tail

    def on_tool_result(self, ctx, outcome):
        window = self._window(ctx)
        if self.ingest and not outcome.is_error and outcome.name != "retrieve_context" \
                and estimate_tokens(outcome.text) > self.ingest * window:
            from eam.techniques.strands import preview

            ref = f"{outcome.tool_use_id}_0"
            self._stash[ref] = outcome.text
            new = preview(outcome.text, self.ingest_preview)
            if new != outcome.text:
                outcome.text = f"{new}\n\n[Stashed] [ref: {ref}] (retrieve_context with pattern or line_range)"
                ctx.log("automem_ingest_preview", ref=ref)
        if not self.guard:
            return outcome
        step, used = ctx.state.get("automem_guard_step", (-1, 0))
        if step != ctx.step:  # first result of this step: start from the last real prompt + the reply just sent
            reply = sum(estimate_tokens(b.get("text", "")) + estimate_tokens(str(b.get("toolUse", "")))
                        for b in ctx.messages[-1]["content"]) if ctx.messages else 0
            step, used = ctx.step, ctx.last_prompt_tokens + int(reply * self.token_ratio)
        n = int(estimate_tokens(outcome.text) * self.token_ratio)
        if used + n > self.guard * window and n > 200:
            aid = ctx.store.put(outcome.text, label=f"{outcome.name} {outcome.input}")
            outcome.text = GUARDED.format(name=outcome.name, tokens=estimate_tokens(outcome.text),
                                          pointer=ctx.store.pointer(aid))
            n = int(estimate_tokens(outcome.text) * self.token_ratio)
            ctx.log("automem_guard_offload", artifact=aid)
        used += n
        ctx.state["automem_guard_step"] = (step, used)
        ctx.state["automem_predicted"] = used
        return outcome

    def on_session_end(self, ctx, answer):
        if self.autosave and answer and self._ws is not None:
            self._ws.notes[f"session {self._sessions} final answer"] = answer[: self._ws.max_note_chars]
            ctx.log("automem_autosave", chars=len(answer))

    def describe(self) -> str:
        return (f"automem(workspace={self.workspace}, recall={self.recall}, autosave={self.autosave}, "
                f"guard={self.guard}, compact={self.compact}, trigger={self.trigger}, keep_recent={self.keep_recent}, "
                f"fold={self.fold}, ingest={self.ingest})")
