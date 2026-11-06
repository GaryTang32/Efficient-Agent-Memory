"""SelfCompact prompts, verbatim.

Source: "Self-Compacting Language Model Agents" (Li, Zhang, Jurayj, Wang, Jin, Farajtabar, Nalisnick, Khashabi;
Apple + JHU; arXiv 2606.23525). Repo: https://github.com/tianjianl/selfcompact, prompts.py at commit 1295817
(MIT License, Copyright (c) 2025 Tianjian Li).
"""

CONTINUE_AFTER_SUMMARY = (
    "Continue your research. Use your tools to find the answer, or provide your final "
    "answer if you have enough information."
)

SUMMARIZE_PROMPT = """\
You are an expert at analyzing conversation history and extracting relevant information. Your task is to thoroughly evaluate the conversation history above and the user's original question to provide a summary that will REPLACE the full conversation history when you continue.

Task Guidelines

1. Information Analysis:
   - Carefully analyze the conversation history to identify truly useful information.
   - Focus on information that directly contributes to answering the question.
   - Do NOT make assumptions, guesses, or inferences beyond what is explicitly stated in the conversation.
   - If information is missing or unclear, do NOT include it in your summary.

2. Summary Requirements:
   - Extract only the most relevant information that is explicitly present in the conversation.
   - Synthesize information from multiple exchanges when relevant.
   - Only include information that is certain and clearly stated in the conversation.
   - Do NOT output or mention any information that is uncertain, insufficient, or cannot be confirmed from the conversation.

3. Output Format: Your response should be structured as follows:
<summary>
- Essential Information: [Organize the relevant and certain information from the conversation history that helps address the question.]
</summary>

Strictly avoid fabricating, inferring, or exaggerating any information not present in the conversation. Only output information that is certain and explicitly stated."""

# ---------------------------------------------------------------------------
# Self-check rubric (first principles)
# ---------------------------------------------------------------------------
# The agent answers this about its own trajectory. Compression is safe only when
# C1 & C2 & C3 hold AND N1 does NOT (stuck means diagnose, not summarize).

SELFCHECK_PROMPT = """\
You are about to decide whether to compress your conversation history into a summary that REPLACES the full history above. After compression, you continue research from only [system, original_question, assistant_summary, user_continue]. Compression is irreversible: anything not preserved in the summary is gone.

Compression is safe ONLY when ALL FOUR of the following hold:
(C1) the trajectory has reached a closed unit (not mid-thought),
(C2) the essential information is reducible to 3-5 cite-able facts without loss,
(C3) something has progressed since the last compression,
AND
(N1) you are NOT currently stuck in a way summarization would mask.

Answer C1, C2, C3, N1 honestly. Each Y answer requires verbatim evidence quoted from the trajectory above; answers without evidence default to N.

C1 CLOSED-UNIT: The most recent assistant message is a closed unit -- a completed tool call whose result is now visible, or a completed sub-analysis with a clear stopping point. It is NOT mid-sentence reasoning ("Let me now check...", "I should next look at..."), and not a half-formulated query.
  If Y, quote the closing fragment of the last assistant message.
  If N, quote the open fragment that shows the trajectory is mid-thought.

C2 SUMMARIZABLE: You can write 3-5 essential facts (with verbatim citations from the trajectory) that future-you needs to continue research after compression. Each fact must be a single concrete statement: a name, date, URL, quoted claim, or resolved sub-question. Answer N if the trajectory's value is dispersed across many small inferences (e.g., a list of dead-end queries needed to avoid retries, negative results that constrain hypothesis space) that would be lost without the dispersal.
  If Y, list the 3-5 facts numbered, each with a verbatim citation in quotes, separated by " | ".
  If N, name in one sentence the class of information that would be lost.

C3 PROGRESS: Since the most recent compression (or since the start of the conversation if none), you have either obtained a new concrete fact (name, date, URL, or quoted claim) OR refined the sub-question being pursued.
  If Y, name the new fact or refined sub-question.
  If N, state that you are returning the same state you compressed from.

N1 STUCK: At least 3 of your last 4 search queries returned no new URL or fact (i.e., were duplicates or returned already-known content). If you have made fewer than 4 searches total, answer N.
  If Y, name 1 distinct strategy you have NOT yet tried (different tool, different query type, different angle on the question).
  If N, name one new URL or fact obtained recently.

Output: exactly 4 lines, no preamble or trailing text.
C1: Y/N -- <evidence>
C2: Y/N -- <if Y: 1. fact "citation" | 2. fact "citation" | 3. fact "citation"; if N: <class of info that would be lost>>
C3: Y/N -- <evidence>
N1: Y/N -- <evidence>"""

# The four rubric fields, in order.
SELFCHECK_FIELDS = ("C1", "C2", "C3", "N1")

SELFCHECK_PROMPT = """\
You are about to decide whether to compress your conversation history into a summary that REPLACES the full history above. After compression, you continue research from only [system, original_question, assistant_summary, user_continue]. Compression is irreversible: anything not preserved in the summary is gone.

Compression is safe ONLY when ALL FOUR of the following hold:
(C1) the trajectory has reached a closed unit (not mid-thought),
(C2) the essential information is reducible to 3-5 cite-able facts without loss,
(C3) something has progressed since the last compression,
AND
(N1) you are NOT currently stuck in a way summarization would mask.

Answer C1, C2, C3, N1 honestly. Each Y answer requires verbatim evidence quoted from the trajectory above; answers without evidence default to N.

C1 CLOSED-UNIT: The most recent assistant message is a closed unit -- a completed tool call whose result is now visible, or a completed sub-analysis with a clear stopping point. It is NOT mid-sentence reasoning ("Let me now check...", "I should next look at..."), and not a half-formulated query.
  If Y, quote the closing fragment of the last assistant message.
  If N, quote the open fragment that shows the trajectory is mid-thought.

C2 SUMMARIZABLE: You can write 3-5 essential facts (with verbatim citations from the trajectory) that future-you needs to continue research after compression. Each fact must be a single concrete statement: a name, date, URL, quoted claim, or resolved sub-question. Answer N if the trajectory's value is dispersed across many small inferences (e.g., a list of dead-end queries needed to avoid retries, negative results that constrain hypothesis space) that would be lost without the dispersal.
  If Y, list the 3-5 facts numbered, each with a verbatim citation in quotes, separated by " | ".
  If N, name in one sentence the class of information that would be lost.

C3 PROGRESS: Since the most recent compression (or since the start of the conversation if none), you have either obtained a new concrete fact (name, date, URL, or quoted claim) OR refined the sub-question being pursued.
  If Y, name the new fact or refined sub-question.
  If N, state that you are returning the same state you compressed from.

N1 STUCK: At least 3 of your last 4 search queries returned no new URL or fact (i.e., were duplicates or returned already-known content). If you have made fewer than 4 searches total, answer N.
  If Y, name 1 distinct strategy you have NOT yet tried (different tool, different query type, different angle on the question).
  If N, name one new URL or fact obtained recently.

Output: exactly 4 lines, no preamble or trailing text.
C1: Y/N -- <evidence>
C2: Y/N -- <if Y: 1. fact "citation" | 2. fact "citation" | 3. fact "citation"; if N: <class of info that would be lost>>
C3: Y/N -- <evidence>
N1: Y/N -- <evidence>"""

# The four rubric fields, in order.
SELFCHECK_FIELDS = ("C1", "C2", "C3", "N1")
