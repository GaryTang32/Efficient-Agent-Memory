"""Summarise the result rows used by docs/overview.html into overview_data.json (per method, model and task)."""
import collections
import glob
import json
import re
import statistics as st
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "overview_data.json"
FILES = ("results/real_v4-research_corpus-haiku.jsonl results/real_v4-research_corpus-sonnet.jsonl "
         "results/real_v3-research-sonnet.jsonl results/real_v4-ops_stream-haiku.jsonl results/real_v4-ops_stream-sonnet.jsonl "
         "results/real_v3-ops-sonnet.jsonl results/real_v4-ledger_audit-haiku.jsonl results/real_v4-ledger_audit-sonnet.jsonl "
         "results/real_v2-cli-sonnet.jsonl results/real_v4-repo_debug-haiku.jsonl results/real_v4-repo_debug-sonnet.jsonl "
         "results/extmem-memoryos-haiku.jsonl results/extmem-lightmem-haiku.jsonl results/extmem-nemori-haiku.jsonl").split()
FILES += sorted(glob.glob("results/real_v5-*.jsonl")) + sorted(glob.glob("results/automem_v2-*.jsonl")) \
    + sorted(glob.glob("results/seeds_sonnet-*.jsonl"))


def key(r):
    return re.sub(r":max_context_k=\d+", "", r["spec"]).replace("ext_memory:backend=", "ext:")


g, seen = collections.defaultdict(list), set()
for f in FILES:
    for line in open(f):
        r = json.loads(line)
        k = (r["model"], r["family"], key(r), r["instance"])
        if "error" in r or k in seen:
            continue
        seen.add(k)
        g[k[:3]].append(r)
out = {}
for (m, f, s), rs in g.items():
    ref, fl = g[(m, f, "naive@native")], g[(m, f, "naive")]
    rc = st.median(r["cost_usd"] for r in ref)
    rt = st.median(r["prompt_tokens"] for r in ref)
    rp = st.median(r["peak_prompt_tokens"] for r in ref)
    F, C = st.mean(r["score"] for r in fl), st.mean(r["score"] for r in ref)
    sc = st.mean(r["score"] for r in rs)
    out.setdefault(s, {}).setdefault(m, {})[f] = dict(
        n=len(rs), score=round(sc, 2), rec=round((sc - F) / (C - F), 2) if C - F >= 0.15 else None,
        cost=round(st.median(r["cost_usd"] for r in rs) / rc * 100), tok=round(st.median(r["prompt_tokens"] for r in rs) / rt * 100),
        peak=round(st.median(r["peak_prompt_tokens"] for r in rs) / rp * 100), solved=sum(r["success"] for r in rs),
        usd=round(sum(r["cost_usd"] for r in rs), 2), steps=round(st.median(r["steps"] for r in rs)),
        wall=round(st.median(r["wall_s"] for r in rs) / 60, 1),
        read=sum(r["usage"].get("cache_read_tokens", 0) for r in rs), write=sum(r["usage"].get("cache_write_tokens", 0) for r in rs),
        unc=sum(r["usage"].get("input_tokens", 0) for r in rs), out=sum(r["usage"].get("output_tokens", 0) for r in rs))
json.dump(out, open(OUT, "w"), indent=0)
print(OUT, len(out))
