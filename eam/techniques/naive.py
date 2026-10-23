from eam.techniques.base import Technique


class NoOptimization(Technique):
    """Baseline B0: no memory management and no cost optimisation at all.

    Compared with `full` (B1: full history, provider prompt caching on, harness offload of oversized tool output),
    `naive` also switches off:
    * prompt caching. On the Claude Code CLI route this sets ``DISABLE_PROMPT_CACHING=1``, so every prompt token
      is billed as fresh input. Converse/OpenAI routes send no cache points unless a technique adds them.
    * the per-step observation budget. Tool output enters the context raw and in full.

    It runs under the same context window as everything else; append ``@native`` to the spec
    (``naive@native``) to drop the emulated window and use the model's own (1M tokens on the CLI route).
    """

    name = "naive"
    source = "baseline (no memory, no caching, no offload)"
    provenance = "baseline"
    disable_prompt_cache = True
    disable_offload = True
