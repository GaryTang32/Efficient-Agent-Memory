"""AgentDiet — Xiao, Gao, Peng, Xiong, "Reducing Cost of LLM Agents with Trajectory Reduction", FSE 2026
(Peking University + ByteDance). Algorithm 1 of the paper with the official artifact's prompt, prefill,
stop sequence, token counter and acceptance rule (see third_party/agentdiet.py).

After step s, a cheap reflection LLM rewrites step s−a (default a=2) given steps s−a−b … s as context (b=1),
if that step has at least θ=500 tokens. The rewrite replaces the step when it saves ≥400 tokens or shrinks it
below 80% (artifact rule). Only step s−a changes, so cached prefixes before it survive.

Adaptation for Converse (documented deviation): the artifact replaces a step by a single assistant message;
Converse needs user/assistant alternation and paired tool results, so the step's tool-result message is
replaced by a short user note instead of being dropped.
"""

from __future__ import annotations

from eam.techniques.base import Technique
from eam.techniques.steps import completed_steps, count_tokens, serialize_step, stable_prefix_len, step_indices
from eam.techniques.third_party import agentdiet as P

RESULTS_FOLDED = "(Tool results of this step are included in the compressed content above.)"


class AgentDiet(Technique):
    name = "agentdiet"
    source = "Xiao et al., FSE 2026 (PKU + ByteDance)"
    provenance = "official prompt + Algorithm 1 (CC BY 4.0 artifact)"
    cache_safe = False  # edits step s−a only; everything before it stays cached

    def __init__(self, a: int = 2, b: int = 1, theta: int = 500, min_saving: int = 400, max_ratio: float = 0.8):
        self.a, self.b, self.theta = int(a), int(b), int(theta)
        self.min_saving, self.max_ratio = int(min_saving), float(max_ratio)

    def before_call(self, ctx):
        turn = completed_steps(ctx.messages)
        if turn < self.b + self.a:
            return
        idx = turn - 1 - self.a
        ctx.state["stable_upto"] = stable_prefix_len(ctx.messages, idx)  # steps ≤ idx are final after this call
        originals = ctx.state.setdefault("agentdiet_originals", {})
        if idx in originals or idx < 0:
            return
        target = serialize_step(ctx.messages, idx)
        old_tokens = count_tokens(target)
        if old_tokens < self.theta:
            return
        context = "\n".join(serialize_step(ctx.messages, i, originals)
                            for i in range(idx - self.b, idx + self.a + 1))
        out = ctx.call_aux(P.USER_PROMPT.format(trajectory=context, idx=idx), purpose="agentdiet",
                           system=P.SYS_PROMPT, temperature=0.0, max_tokens=max(1024, old_tokens),
                           prefill=P.PREFILL.format(idx=idx), stop=[P.STOP])
        content = out.partition(P.STOP)[0]
        if "<step" in content[:200]:
            content = content.partition("<step")[2]
            if ">" in content[:20]:
                content = content.partition(">")[2]
        new_tokens = count_tokens(content)
        if not (old_tokens - new_tokens >= self.min_saving or new_tokens < self.max_ratio * old_tokens):
            ctx.log("agentdiet_kept", step=idx, old=old_tokens, new=new_tokens)
            return
        a_idx, u_idx = step_indices(ctx.messages)[idx]
        originals[idx] = target
        ctx.messages[a_idx]["content"] = [{"text": P.COMPRESSED_MARKER + content.strip()}]
        if u_idx is not None:
            ctx.messages[u_idx]["content"] = [{"text": RESULTS_FOLDED}]
        ctx.log("agentdiet_reduced", step=idx, old=old_tokens, new=new_tokens)
