"""CADOC — Cache-Aware Dynamic Object Context (Yao, Zhou, Xu; SJTU; arXiv 2609.37012). No public code: this is a
re-implementation from the paper (§2–3, App. B–E).

Large structured spans (here: tool results) are registered as immutable, versioned *objects*; the bytes go to an
external store and, once an object leaves the raw hot tail, it is replaced *in place* by a deterministic Card
(``<OBJECT_CARD>{sorted JSON: contains, object_ref, origin, type, version}</OBJECT_CARD>``, no LLM synopsis).
``retrieve_object(object_ref, reason)`` returns the exact bytes as a new tool result at the end.

The cache-aware part is *when* to replace. Every replacement rewrites the prompt from the earliest edit on, so the
cached tokens after it must be re-processed. Objects that left the hot tail (≤ h steps and ≤ 12,800 tokens) wait as
*pending*; a waiting ledger W accumulates the read cost of carrying them raw (w_r · G per request, G = raw − card
tokens of the pending set) and the whole pending set is committed at once when

    W + w_r · G ≥ Q,   Q = F_0 + (w_m − w_r) · H_shared

where H_shared is the already-cached part of the prompt after the newest pending block. The paper prices a miss at
1 (w_m = 1, ``mode="paper"``, w_r = 0.1); on a route that bills prompt rewrites as cache *writes* the same derivation
gives w_m = write/input price (``mode="route"``, the default: 2× on the Claude Code route, 1.25× on Bedrock).
Forced commits: pending > 2h steps, pending > 25,600 raw tokens, or the window about to overflow.

Deviations: objects are whole tool results (the paper also registers code spans and artifacts inside messages);
Card ``contains`` fields beyond the paper's example (line/char counts, first line) and the retrieval-receipt text
are ours; F_0 = 0 as in all the paper's runs.
"""

from __future__ import annotations

import json
import uuid

from eam.agent.context import Tool
from eam.llm.types import ToolSpec
from eam.techniques.base import Technique
from eam.techniques.steps import count_tokens, step_indices

ADDENDUM = ("Large earlier tool results may be shown as <OBJECT_CARD> entries; the exact content is kept outside "
            "the context. Call retrieve_object with the card's object_ref (and a short reason) when you need the "
            "content again.")
RECEIPT = "[retrieval receipt: the content of {ref} was returned here earlier; call retrieve_object again if needed]"


class CADOC(Technique):
    name = "cadoc"
    source = "CADOC (SJTU), arXiv 2609.37012"
    provenance = "re-implementation from the paper (no public code); commit rule and defaults as published"
    cache_safe = False  # commits rewrite the rendered prefix by design (rarely, in batches)

    def __init__(self, h: int = 4, t_hot: int = 12_800, mode: str = "route", w_r: float = 0.1, f0: float = 0.0,
                 max_pending_tokens: int = 25_600, guard: float = 0.9):
        self.h = int(h)
        self.t_hot = int(t_hot)
        self.mode = str(mode)
        self.w_r_paper = float(w_r)
        self.f0 = float(f0)
        self.max_pending_tokens = int(max_pending_tokens)
        self.guard = float(guard)

    def describe(self):
        return f"cadoc(h={self.h}, t_hot={self.t_hot}, mode={self.mode})"

    # ---- prices ---------------------------------------------------------------------------------------------
    def _weights(self, ctx) -> tuple[float, float]:
        m = ctx.model
        if self.mode == "route":
            if m.price_cache_read is not None and m.price_in:
                return (m.price_cache_write or m.price_in) / m.price_in, m.price_cache_read / m.price_in
            from eam.bench.analyze import CLI_INPUT_RATES  # Claude Code profiles carry no prices (CLI reports cost)

            if m.key in CLI_INPUT_RATES:
                p_in, p_read, p_write = CLI_INPUT_RATES[m.key]
                return p_write / p_in, p_read / p_in
        return 1.0, self.w_r_paper

    # ---- objects --------------------------------------------------------------------------------------------
    def on_session_start(self, ctx):
        ctx.state["cadoc"] = {"objects": {}, "occ": {}, "W": 0.0, "committing": set(), "versions": {},
                              "commits": 0}

    def tools(self, ctx):
        def handler(args, ctx):
            ref = str(args.get("object_ref", "")).strip()
            obj = ctx.state["cadoc"]["objects"].get(ref)
            if obj is None:
                raise ValueError(f"no object '{ref}'")
            return json.dumps({"retrieved_object": {"object_ref": ref, "version": obj["version"],
                                                    "content": obj["bytes"]}}, ensure_ascii=False)

        return [Tool(ToolSpec("retrieve_object", "Return the exact content of an object shown as an <OBJECT_CARD>.",
                              {"type": "object", "properties": {
                                  "object_ref": {"type": "string", "description": "e.g. object://obj_…@v1"},
                                  "reason": {"type": "string", "description": "why the content is needed"}},
                               "required": ["object_ref", "reason"]}), handler)]

    def system_addendum(self):
        return ADDENDUM

    @staticmethod
    def _card(ref: str, version: int, name: str, args: dict, step: int, text: str) -> str:
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            contains, kind = {"top_level_keys": sorted(parsed)[:20]}, "structured_data"
        else:
            lines = text.split("\n")
            contains = {"chars": len(text), "first_line": lines[0][:120], "lines": len(lines)}
            kind = "text"
        card = {"contains": contains, "object_ref": ref, "origin": {"input": args, "step": step, "tool": name},
                "type": kind, "version": version}
        return "<OBJECT_CARD>\n" + json.dumps(card, sort_keys=True, ensure_ascii=False) + "\n</OBJECT_CARD>"

    def on_tool_result(self, ctx, outcome):
        st = ctx.state["cadoc"]
        if outcome.is_error:
            return outcome
        raw_tok = count_tokens(outcome.text)
        if outcome.name == "retrieve_object":
            ref = str(outcome.input.get("object_ref", ""))
            card = RECEIPT.format(ref=ref)
        else:
            source = f"{outcome.name}:{json.dumps(outcome.input, sort_keys=True)}"
            prev = st["versions"].get(source)
            version = 1 if prev is None else prev[1] + (prev[0] != outcome.text)
            st["versions"][source] = (outcome.text, version)
            ref = f"object://obj_{uuid.uuid4().hex[:24]}@v{version}"
            card = self._card(ref, version, outcome.name, outcome.input, ctx.step, outcome.text)
            st["objects"][ref] = {"bytes": outcome.text, "version": version}
            ctx.store.put(outcome.text, label=ref)
        card_tok = count_tokens(card)
        if card_tok < raw_tok:
            st["occ"][outcome.tool_use_id] = {"ref": ref, "card": card, "raw": raw_tok, "card_tok": card_tok,
                                              "status": "hot", "exposed": False}
        return outcome

    # ---- render: the commit decision ------------------------------------------------------------------------
    def _locate(self, ctx) -> dict[str, tuple[int, int, int]]:
        """toolUseId -> (step k, message index, block index)."""
        out = {}
        for k, (_, u) in enumerate(step_indices(ctx.messages)):
            if u is None:
                continue
            for j, b in enumerate(ctx.messages[u]["content"]):
                if "toolResult" in b:
                    out[b["toolResult"]["toolUseId"]] = (k, u, j)
        return out

    def render(self, ctx, req):
        st = ctx.state["cadoc"]
        if req.messages is not ctx.messages or not st["occ"]:
            return req
        loc = self._locate(ctx)
        steps = step_indices(ctx.messages)
        # hot tail: the newest step always, then older steps while ≤ h steps and ≤ t_hot tokens
        hot, tokens = set(), 0
        for k in range(len(steps) - 1, -1, -1):
            a, u = steps[k]
            size = sum(count_tokens(json.dumps(b, ensure_ascii=False)) for i in (a, u) if i is not None
                       for b in ctx.messages[i]["content"])
            if hot and (len(hot) >= self.h or tokens + size > self.t_hot):
                break
            hot.add(k)
            tokens += size
        pending = [tid for tid, o in st["occ"].items() if o["status"] == "hot" and o["exposed"] and tid in loc
                   and loc[tid][0] not in hot]
        st["pending_now"] = pending
        st["committing"] = set()
        if pending:
            w_m, w_r = self._weights(ctx)
            g = sum(st["occ"][t]["raw"] - st["occ"][t]["card_tok"] for t in pending)
            newest = max(loc[t][1] for t in pending)
            # cached tokens after the newest pending block (the newest message was not sent before: not cached)
            h_shared = sum(count_tokens(json.dumps(b, ensure_ascii=False)) for m in ctx.messages[newest + 1:-1]
                           for b in m["content"])
            q = self.f0 + (w_m - w_r) * h_shared
            pend_steps = {loc[t][0] for t in pending}
            raw_pending = sum(st["occ"][t]["raw"] for t in pending)
            window = ctx.context_limit or getattr(ctx.model, "context_window", 200_000)
            capacity = ctx.last_prompt_tokens + count_tokens(json.dumps(ctx.messages[-1]["content"])) \
                > self.guard * window
            forced = len(pend_steps) > 2 * self.h or raw_pending > self.max_pending_tokens or capacity
            decision = "commit" if (st["W"] + w_r * g >= q or forced) else "wait"
            ctx.log("cadoc_decision", W=round(st["W"], 1), G=g, Q=round(q, 1), decision=decision,
                    batch=len(pending), forced=bool(forced))
            st["G_now"] = w_r * g
            if decision == "commit":
                st["committing"] = set(pending)
        replace = {t for t, o in st["occ"].items() if o["status"] == "committed"} | st["committing"]
        if not replace:
            return req
        by_msg: dict[int, dict[int, str]] = {}
        for t in replace:
            if t in loc:
                _, u, j = loc[t]
                by_msg.setdefault(u, {})[j] = st["occ"][t]["card"]
        out = []
        for i, msg in enumerate(ctx.messages):
            if i not in by_msg:
                out.append(msg)
                continue
            content = list(msg["content"])
            for j, card in by_msg[i].items():
                tr = content[j]["toolResult"]
                content[j] = {"toolResult": {**tr, "content": [{"text": card}]}}
            out.append({**msg, "content": content})
        req.messages = out
        return req

    def after_call(self, ctx, resp):
        st = ctx.state["cadoc"]
        if st.get("committing"):
            for t in st["committing"]:
                st["occ"][t]["status"] = "committed"
            st["W"] = 0.0
            st["commits"] += 1
            st["committing"] = set()
        elif st.get("pending_now"):
            st["W"] += st.get("G_now", 0.0)
        st["pending_now"] = []
        for o in st["occ"].values():  # every registered occurrence sent in this request has had its raw exposure
            o["exposed"] = True

    def on_session_end(self, ctx, answer):
        st = ctx.state["cadoc"]
        ctx.log("cadoc_record", objects=len(st["objects"]), commits=st["commits"],
                committed=sum(o["status"] == "committed" for o in st["occ"].values()))
