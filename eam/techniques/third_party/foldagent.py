"""Context-Folding (FoldGRPO) branch/return protocol, verbatim from the official FoldAgent repo.

Source: Sun et al., "Scaling Long-Horizon LLM Agent via Context-Folding", ICML 2026 (ByteDance Seed).
Repo: https://github.com/sunnweiwei/FoldAgent (Apache License 2.0), agents/prompts.py (BRANCH_MESSAGE),
agents/tool_spec.py (branch/return tools) and agents/fold_agent.py (observations, max_session=5).
"""

BRANCH_MESSAGE = ('ROLE CHANGE: `MODE: BRANCH`\n\nYou are now a branch. You have been assigned a specific task by MAIN as shown above and inherit their full context and understanding of the problem.\n\nYour role is to focus exclusively on the assigned task. Return immediately after completing it, and never perform actions beyond the specified task. Focus exclusively on the assigned task.\n\nYour final response must be clear and compact, while faithfully and comprehensively capture:\n* Outcome of your assigned task.\n* Any files modified, created, or deleted; any environment changes or commands that affected the system.\n* Key insight: Important discoveries about the codebase, problem patterns, architecture understanding, or technical details that future phases need to know\n* What you assumed from previous context, what future phases should know, any unresolved questions or potential issues\n* Any additional notes you would like to inform MAIN about.\n\nWhen you have completed your assigned task, use the return tool to formally return control to MAIN:\n\n<function=return>\n<parameter=message>\nYour message to MAIN here — include branch results, state changes, key insights, dependencies, and notes.\n</parameter>\n</function>')

BRANCH_DESCRIPTION = "Create a sub-branch to execute a sub-task."
BRANCH_PARAM_DESCRIPTION = ('A concise 3-5 word identifier for the sub-task  (e.g., "Narrow down last 7 overs stats", '
                            '"Code Exploration", "Test Creation").')
BRANCH_PARAM_PROMPT = "Clear, compact task prompt: state objectives and critical info to preserve in the response. Be brief and informative."
RETURN_DESCRIPTION = "Finish the interaction when the sub task is complete OR if the assistant cannot proceed further with the task."
RETURN_PARAM_MESSAGE = "A comprehensive message describing sub task outcome."

RETURNED = "Branch has finished its task, the returned message is:\n\n{message}"
RETURNED_NO_MESSAGE = "Branch has finished its task. The last message was:\n\n{last}"
LIMIT_REACHED = "You've already reached the limit of {n} branch calls. Continue working independently."
NO_NESTING = "You are in branch mode and cannot branch task or finish the task. Use the `return` tool to go back to the main agent."
BRANCH_OBSERVATION = ("* You are now in branch mode: {description}. Conduct the sub task based on instruction, and when you "
                      "complete the assigned sub task, use return tool to return, do not perform action beyond the assigned sub task.")
MAX_SESSION = 5
