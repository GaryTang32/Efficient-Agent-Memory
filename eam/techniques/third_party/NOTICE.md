# Third-party prompt texts

The modules in this directory reproduce prompt strings **verbatim** from official paper artifacts and repositories,
so that the techniques here follow the authors' own implementations. Each file names its exact source.

| File | Source | Licence |
|---|---|---|
| `agentdiet.py` | AgentDiet (Xiao, Gao, Peng, Xiong; FSE 2026), official artifact https://doi.org/10.6084/m9.figshare.30073654 | CC BY 4.0 — attribution: © the authors; prompt text unchanged |
| `resum.py` | ReSum (Alibaba Tongyi Lab), https://github.com/Alibaba-NLP/DeepResearch `WebAgent/WebResummer/src/` | MIT License, Copyright (c) 2025 Alibaba-NLP |
| `foldagent.py` | Context-Folding / FoldGRPO (ByteDance Seed; ICML 2026), https://github.com/sunnweiwei/FoldAgent `agents/` | Apache License 2.0 |
| `memagent.py` | MemAgent (ByteDance Seed + Tsinghua AIR; ICLR 2026), https://github.com/BytedTsinghua-SIA/MemAgent `quickstart.py` | Apache License 2.0 |

The turn-control reminder strings (Gao & Peng, ICSE 2026) are quoted from the paper (§2.4) and also appear in the
AgentDiet artifact's `expert.py`; they live in `eam/techniques/turn_control.py`.

MIT notice for the ReSum prompts:

> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
> documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
> rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
> persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice
> and this permission notice shall be included in all copies or substantial portions of the Software.
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
