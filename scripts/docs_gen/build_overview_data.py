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
    + sorted(glob.glob("results/seeds_sonnet-*.jsonl")) + sorted(glob.glob("results/handoff-*.jsonl"))


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
    # references on the method's own instances (paired), so a method run on fewer instances is not compared with
    # the ceiling's mean over different ones
    mine = {r["instance"] for r in rs}
    ref = [r for r in g[(m, f, "naive@native")] if r["instance"] in mine] or g[(m, f, "naive@native")]
    fl = [r for r in g[(m, f, "naive")] if r["instance"] in mine] or g[(m, f, "naive")]
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
swe = {}
# 100-issue set (SWE-bench-faithful grading): the 32K grid with own-window references, and the 16K grid (key "@16k")
for m in ("haiku", "sonnet"):
    rs = []
    for f, tag in ((f"results/swe_wide-{m}.jsonl", ""), (f"results/swe_16k-{m}.jsonl", "@16k"),
                   (f"results/swe_16k-{m}-aux.jsonl", "@16k")):
        try:
            lines = open(f).read().splitlines()
        except OSError:
            continue
        for x in lines:
            if x.strip():
                r = json.loads(x)
                if "error" not in r or "overflow" in str(r["error"]):
                    r["spec"] += tag
                    rs.append(r)
    if not rs:
        continue
    by = collections.defaultdict(dict)
    for r in rs:
        by[r["spec"]][r["instance"]] = r
    mk = rs[0]["model"]
    ref = by.get("naive@native", {})
    for spec, runs in by.items():
        common = [i for i in runs if i in ref]
        res = sum(sum(r["round_scores"]) for r in runs.values())
        n = sum(len(r["round_scores"]) for r in runs.values())
        usd = sum(r["cost_usd"] for r in runs.values())
        swe.setdefault(mk, {})[spec] = dict(
            resolved=round(res), n=n, usd=round(usd, 2), per=round(usd / max(res, 1), 3),
            cost=round(100 * sum(runs[i]["cost_usd"] for i in common) / max(sum(ref[i]["cost_usd"] for i in common), 1e-9)),
            peak=round(st.median(r["peak_prompt_tokens"] for r in runs.values())),
            steps=round(st.median(r["steps"] for r in runs.values())),
            compactions=sum(v for r in runs.values() for k, v in r["events"].items() if k.endswith("_rebuild")),
            overflows=sum(r["events"].get("context_overflow", 0) for r in runs.values()))
out["__swe__"] = swe
json.dump(out, open(OUT, "w"), indent=0)
print(OUT, len(out))
