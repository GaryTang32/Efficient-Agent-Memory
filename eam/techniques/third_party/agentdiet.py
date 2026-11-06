"""AgentDiet reflection prompt, verbatim from the official FSE 2026 artifact.

Source: Xiao, Gao, Peng, Xiong, "Reducing Cost of LLM Agents with Trajectory Reduction", FSE 2026.
Artifact: https://doi.org/10.6084/m9.figshare.30073654 (CC BY 4.0),
file code/trae_agent/agents/traj_analyzer.py (SYS_PROMPT, user prompt, prefill, acceptance rule)
and code/trae_agent/agents/expert.py (step serialisation, erase markers).
"""

SYS_PROMPT = ('You will analyze and compress a given step in a trajectory of an AI agent solving a software bug.\n\nIn the trajectory, each step is marked in <step id="..."></step>.\nThe agent will think in <think>, call external tools as marked in <call tool="..."></call>. Its result is marked in <result></result> within the <step> tag.\n\nYour job is to compress the text within the given id to avoid harming efficiency, typically shortening it to 20%-50% of the original length.\nMeanwhile, keep the compressed text useful such that you are able to continue the trajectory as close as the original path.\n\n- You should ONLY remove redundant texts, which are either irrelevant to future steps or duplicated by other texts in the trajectory.\n- Replace the text to remove to "..." and a short takeaway, e.g. "... (same as the content below)".\n- You should keep the original structure unchanged, e.g., XML tags, Python indentation and line numbers.\n- Again, keep useful details in the original content unchanged, e.g., XML tags, Python indentation and line numbers.\n\nTypical examples:\n- If the step opens a huge file but only one part is necessary for future steps, replace other parts to "... (unrelated function XXX, YYY)".\n- If the step runs a verbose test script and everything goes fine, replace the verbose part to "... (expected output)".\n- If the step uses str_replace_editor to modify a file and the content can be inferred by the content after it, replace the tool call argument to "... (see results below)".\n\nYou should only process the text within the <step> tag with the given id. STOP OUTPUT IMMEDIATELY AFTER </step>.')

USER_PROMPT = "{trajectory}\n\nNow, compress the step {idx}."
PREFILL = 'Sure. Here is the compressed content of step {idx}: <step id="{idx}">'
STOP = "</step>"
COMPRESSED_MARKER = "(System reminder: compressed for better efficiency) "
DELETED_MARKER = "(System reminder: long content deleted for better efficiency)"
