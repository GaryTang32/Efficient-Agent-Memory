"""The fixed texts AutoMemory adds to a conversation, shared by the bench technique, the library and the adapters."""

WORKSPACE = ("Workspace: you have a persistent note workspace that survives beyond this conversation and across "
             "sessions (tools write_note, read_notes). Save every intermediate result you may need later — "
             "running totals, findings, which files are done — and at the start of a session read your notes "
             "before doing anything else.")

RECALL = ("Your persistent workspace notes (saved in earlier sessions or before the conversation was "
          "compacted):\n\n{notes}\n\nUse them; keep them up to date with write_note.")

GUARDED = ("[Output of {name} moved out of the context to keep it within the window ({tokens:,} tokens). "
           "It is stored at {pointer}; read it with read_artifact (offset/length to page), one item per step.]")


# ---- NVIDIA EoCC handoff recap (arXiv 2611.05306): the paper's prompts are in eam/techniques/third_party/nvidia_eocc
# this project's texts for the paper's placeholders
PERSISTENCE = ("Files you changed and outputs stored outside the context (pointers such as artifact://… or "
               "[ref: …]) stay available after the reset; everything else in this conversation is gone unless it is "
               "in the recap.")
HANDOFF_DETAILS = "Copy exact identifiers, numbers, file paths and line numbers as they appear; do not paraphrase them."
SUBMISSION_REMINDER = ("Completion: when the task is done, finish exactly as the task statement instructs (for "
                       "example with a line starting with 'FINAL ANSWER:').")
RECAP_SECTION = ("You are continuing this task from the compacted state of the preceding conversation (written by "
                 "you before the reset). Resume from the immediate next step it names; do not redo verified work.\n\n"
                 "<recap>\n{recap}\n</recap>")


# This project's brief variant: the paper's six fields, asked for as terse bullets with pointers instead of copied code
# or output, and capped. The full recap cost 1,200-1,800 output tokens per reset on Sonnet and stayed in every later
# prompt (docs/results/2026-11-06-handoff-and-swe-100.md).
BRIEF_PROMPT = """Stop work. Write only a brief handoff recap, at most 150 words; do not call tools.
The conversation will reset to the system prompt, the task and this recap. {persistence}

Use terse bullets under six headings:
1. Objective - one line.
2. Facts - paths, symbols, values, errors (observed, not guessed).
3. Changes - file: what changed; verified or not.
4. Checks - command: result.
5. Dead ends - what failed and should not be repeated.
6. Next - the immediate next command or edit, and when the task is done.

Name files, line numbers and commands instead of copying code or output. {handoff_details}
{submission_reminder}"""

def compaction_prompt(variant: str = "general") -> str:
    template = BRIEF_PROMPT if variant == "brief" else _eocc().PROMPTS[variant]
    return template.format(persistence=PERSISTENCE, handoff_details=HANDOFF_DETAILS,
                           submission_reminder=SUBMISSION_REMINDER)



def _eocc():
    from eam.techniques.third_party import nvidia_eocc

    return nvidia_eocc


# Instructions for a host's own compaction (the Agent SDK's PreCompact): keep NVIDIA's six-field handoff recap
# (App. G). The Claude Code plugin has its own variant, which points to saved files instead of artifact:// pointers.
HANDOFF = """When summarising this conversation, write a concise handoff recap; the conversation will continue from \
the system prompt, the task and this recap. Record:
1. Objective - one line describing the required result.
2. Established facts - exact paths, relevant symbols or commands, observed values, and important errors/output. \
Separate observations from unverified ideas.
3. Applied changes - each changed/created file, what changed, and whether verified.
4. Verification - exact checks run, outcomes, failures, obstacles, and workarounds.
5. Dead ends - failed approaches that should not be repeated.
6. Remaining plan - outstanding subgoals, in execution order; the immediate next command or edit; and the condition \
for completion.
Copy exact identifiers, numbers, file paths and line numbers as they appear. If needed output was truncated or saved \
by AutoMemory (artifact://...), give the pointer so it can be read back with read_artifact."""
