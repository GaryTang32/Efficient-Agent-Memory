"""Observation masking baseline — Lindenbauer et al., "The Complexity Trap" (NeurIPS 2025 DL4Code workshop),
with the settings AgentDiet (FSE'26) and AttnCompress (ISSTA'26) use as their baseline: observations of steps
older than the last `window`=2 are replaced by the placeholder "Environment Observation Ommited" (sic, as in the
artifact) when the step has at least 300 tokens. Not a Chinese-lab method; it is the cheapest strong baseline.
"""

from __future__ import annotations

from eam.techniques.base import Technique
from eam.techniques.steps import completed_steps, count_tokens, serialize_step, stable_prefix_len, step_indices

PLACEHOLDER = "Environment Observation Ommited"


class ObservationMasking(Technique):
    name = "obs_mask"
    source = "Lindenbauer et al. 2025; baseline settings from AgentDiet / AttnCompress"
    provenance = "baseline (published settings)"
    cache_safe = False

    def __init__(self, window: int = 2, min_tokens: int = 300, placeholder: str = PLACEHOLDER):
        self.window = int(window)
        self.min_tokens = int(min_tokens)
        self.placeholder = placeholder

    def before_call(self, ctx):
        done = completed_steps(ctx.messages)
        masked = ctx.state.setdefault("obs_masked", set())
        for k, (_, u_idx) in enumerate(step_indices(ctx.messages)[: max(0, done - self.window)]):
            if k in masked or u_idx is None:
                continue
            if count_tokens(serialize_step(ctx.messages, k)) < self.min_tokens:
                continue
            for b in ctx.messages[u_idx]["content"]:
                if "toolResult" in b:
                    b["toolResult"]["content"] = [{"text": self.placeholder}]
            masked.add(k)
            ctx.log("obs_masked", step=k)
        # steps older than the window are final (masked, or too short to mask): publish the stable boundary so a
        # cache point can sit there (cache_layout:edit_boundary=true on Bedrock)
        ctx.state["stable_upto"] = stable_prefix_len(ctx.messages, done - self.window - 1)
