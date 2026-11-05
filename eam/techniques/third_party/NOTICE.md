# Third-party prompt texts

The modules in this directory reproduce prompt strings **verbatim** from official paper artifacts and repositories,
so that the techniques here follow the authors' own implementations. Each file names its exact source.

| File | Source | Licence |
|---|---|---|
| `agentdiet.py` | AgentDiet (Xiao, Gao, Peng, Xiong; FSE 2026), official artifact https://doi.org/10.6084/m9.figshare.30073654 | CC BY 4.0 — attribution: © the authors; prompt text unchanged |
| `resum.py` | ReSum (Alibaba Tongyi Lab), https://github.com/Alibaba-NLP/DeepResearch `WebAgent/WebResummer/src/` | MIT License, Copyright (c) 2025 Alibaba-NLP |
| `foldagent.py` | Context-Folding / FoldGRPO (ByteDance Seed; ICML 2026), https://github.com/sunnweiwei/FoldAgent `agents/` | Apache License 2.0 |
| `memagent.py` | MemAgent (ByteDance Seed + Tsinghua AIR; ICLR 2026), https://github.com/BytedTsinghua-SIA/MemAgent `quickstart.py` | Apache License 2.0 |
| `refold/` | ReFold (Su, Tian, Zhang [UCSB], Kundu [Intel]; arXiv 2610.07863), https://github.com/YupengSu/ReFold `src/refold/core` at 017328f — dedup.py, fold.py, filters.py, parse.py, prompts.json; import paths changed, nothing else | Apache License 2.0 (`refold/LICENSE`); the README adds a research/non-commercial disclaimer |
| `selfcompact.py` | SelfCompact (Apple + JHU; arXiv 2606.23525), https://github.com/tianjianl/selfcompact `prompts.py` at 1295817 | MIT License, Copyright (c) 2025 Tianjian Li |
| `coral.py` | CORAL (CUHK + Tencent + HKUST; COLM 2026; arXiv 2610.40350), paper App. I.1–I.3 (the linked code repo returned 404) | quoted from the paper for research reproduction, © the authors |

The turn-control reminder strings (Gao & Peng, ICSE 2026) are quoted from the paper (§2.4) and also appear in the
AgentDiet artifact's `expert.py`; they live in `eam/techniques/turn_control.py`.

MIT notice for the ReSum prompts:

> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
> documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
> rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
> persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice
> and this permission notice shall be included in all copies or substantial portions of the Software.
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

Prompt texts quoted in technique modules (not vendored files): the Strands harness prompts in `eam/techniques/strands.py`
(strands-agents 1.63.0 / strands-harness 0.3.3, Apache License 2.0, Copyright Amazon.com, Inc. or its affiliates); the
SJC CONTEXT/QUESTION texts and the OpenClaw safeguard prompts in `eam/techniques/sjc.py` (quoted from arXiv 2610.20927;
the SJC repo has no licence file, so its code is not copied); the AKV policy in `eam/techniques/akv.py` is re-implemented
from https://github.com/thu-nics/AKV (Apache License 2.0).

The EoCC compaction prompts in `eam/techniques/third_party/nvidia_eocc.py` are quoted from "You don't need long
context" (Belcak et al., NVIDIA, arXiv 2611.05306, App. G); no code was released with the paper. The SWE-bench Django
test directives and log parser in `eam/bench/tasks/swe_env.py` are ported from https://github.com/SWE-bench/SWE-bench
(MIT License, Copyright (c) 2023 Carlos E Jimenez, John Yang, Alexander Wettig, Shunyu Yao, Kexin Pei, Ofir Press,
Karthik R Narasimhan).
