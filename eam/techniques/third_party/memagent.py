"""MemAgent templates, verbatim from the official quickstart.

Source: Yu et al., "MemAgent: Reshaping Long-Context LLM with Multi-Conv RL-based Memory Agent", ICLR 2026 (Oral)
(ByteDance Seed + Tsinghua AIR). Repo: https://github.com/BytedTsinghua-SIA/MemAgent (Apache License 2.0), quickstart.py.
"""

TEMPLATE = ('You are presented with a problem, a section of an article that may contain the answer to the problem, and a previous memory. Please read the provided section carefully and update the memory with the new information that helps to answer the problem. Be sure to retain all relevant details from the previous memory while adding any new, useful information.\n\n<problem> \n{prompt}\n</problem>\n\n<memory>\n{memory}\n</memory>\n\n<section>\n{chunk}\n</section>\n\nUpdated memory:\n')

TEMPLATE_FINAL = ('You are presented with a problem and a previous memory. Please answer the problem based on the previous memory and put the answer in \\\\boxed{{}}.\n\n<problem> \n{prompt}\n</problem>\n\n<memory>\n{memory}\n</memory>\n\nYour answer:\n')

NO_MEMORY = "No previous memory"
CHUNK_TOKENS = 5000   # RECURRENT_CHUNK_SIZE
MAX_NEW_TOKENS = 1024  # RECURRENT_MAX_NEW
