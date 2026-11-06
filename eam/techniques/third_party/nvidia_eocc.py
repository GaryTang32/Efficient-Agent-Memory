"""End-of-conversation compaction (EoCC) prompts from "You don't need long context" (Belcak et al., NVIDIA,
arXiv 2611.05306v1, 3 Nov 2026), Appendix G ("Agent outlines"). Quoted verbatim; the paper's harnesses are
mini-swe-agent v2.4 (MIT) with compaction added, and mini-agent, its generalisation. No code was released with the
paper.

The paper gives the prompts as outlines with placeholders. Its Table (App. G) describes them:

* ``persistence``: which files and environment state remain available across conversations, and which information
  must be preserved in the compacted state;
* ``handoff_details``: additional instructions specifying evidence, input coverage, calculations or implementation
  state to preserve in the compaction;
* ``submission_reminder``: checks required before task completion and the completion protocol to preserve in the
  compacted state;
* ``recap_section``: instructions for continuing execution, followed by the compacted state from the preceding
  conversation.

The texts that fill these placeholders are not given in the paper; ours are in ``eam/techniques/eocc.py`` and are
marked as this project's.
"""

# G.1, mini-swe-agent: passed as a user message once the compaction threshold is met.
SWE_COMPACTION_PROMPT = """Stop work. Write only a concise handoff recap; do not run commands or call tools.
The conversation will reset to the system prompt, task, and this recap.
{persistence}

Record:
1. Objective - one line describing the required result.
2. Established facts - exact paths, relevant symbols or commands, observed values,
   and important errors/output. Separate observations from unverified ideas.
3. Applied changes - each changed/created file, what changed, and whether verified.
4. Verification - exact checks run, outcomes, failures, obstacles, and workarounds.
5. Dead ends - failed approaches that should not be repeated.
6. Remaining plan - outstanding subgoals, in execution order; the immediate next
   command or edit; and the condition for completion.

{handoff_details}

If needed output was truncated, give a narrow command to retrieve it.
{submission_reminder}"""

# G.2, mini-agent (general tasks).
GENERAL_COMPACTION_PROMPT = """Stop work. Write only a concise handoff recap; do not call tools.
The conversation will reset, and the system prompt, task, and recap will be
provided again. {persistence}

Preserve what your next stretch needs:
1. Current progress and best answer/result, separating verified facts from assumptions.
2. Relevant evidence with exact values and source locations; changes already made,
   if any, with paths and verification status.
3. What was solved, what worked, what remains unresolved, what failed, and useful commands already tried.
4. Remaining plan - outstanding subgoals, in execution order; the immediate next
   command or edit; and the condition for completion.

{handoff_details}

If important output was truncated, name a narrow command to retrieve the missing
part. Do not invent observations or repeat the full task or document manifest.
{submission_reminder}"""

PROMPTS = {"swe": SWE_COMPACTION_PROMPT, "general": GENERAL_COMPACTION_PROMPT}
