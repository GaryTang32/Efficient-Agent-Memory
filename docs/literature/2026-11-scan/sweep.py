import json, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
NS={"a":"http://www.w3.org/2005/Atom","x":"http://arxiv.org/schemas/atom"}
RANGE="submittedDate:[202609010000 TO 202611042359]"
Q={
 "agent_memory": 'abs:"agent memory" OR abs:"agentic memory" OR abs:"memory-augmented agent" OR abs:"long-term memory"',
 "memory_llm_agent": '(abs:memory AND (abs:"LLM agent" OR abs:"LLM agents" OR abs:"language agent" OR abs:"agentic"))',
 "context_eng": 'abs:"context engineering" OR abs:"context management" OR abs:"context compression" OR abs:"context folding" OR abs:"context window"',
 "token_eff": '(abs:"token efficiency" OR abs:"token-efficient" OR abs:"token cost" OR abs:"token consumption" OR abs:"token usage") AND (abs:agent OR abs:agents OR abs:agentic)',
 "kv_prompt_cache": 'abs:"prompt caching" OR abs:"prefix caching" OR (abs:"KV cache" AND abs:agent)',
 "trajectory": 'abs:"trajectory compression" OR abs:"observation pruning" OR abs:"history compression" OR (abs:summarization AND abs:"long-horizon")',
 "experience": '(abs:"experience" AND abs:"memory" AND abs:"agent" AND abs:"self-evolving")',
}
seen={}
for tag,q in Q.items():
    start=0
    while True:
        url="https://export.arxiv.org/api/query?"+urllib.parse.urlencode({"search_query":f"({q}) AND {RANGE}","start":start,"max_results":200,"sortBy":"submittedDate","sortOrder":"descending"})
        for attempt in range(3):
            try:
                xml=urllib.request.urlopen(url,timeout=90).read(); break
            except Exception as e:
                time.sleep(5)
        root=ET.fromstring(xml)
        entries=root.findall("a:entry",NS)
        for e in entries:
            aid=e.find("a:id",NS).text.rsplit("/",1)[-1]
            d=seen.setdefault(aid,{"id":aid,"tags":[]})
            d.update(title=" ".join(e.find("a:title",NS).text.split()),
                     published=e.find("a:published",NS).text[:10],
                     authors=[a.find("a:name",NS).text for a in e.findall("a:author",NS)],
                     affils=sorted({x.text for a in e.findall("a:author",NS) for x in a.findall("x:affiliation",NS)}),
                     comment=(e.find("x:comment",NS).text if e.find("x:comment",NS) is not None else ""),
                     cats=[c.get("term") for c in e.findall("a:category",NS)],
                     abstract=" ".join(e.find("a:summary",NS).text.split()))
            if tag not in d["tags"]: d["tags"].append(tag)
        total=int(root.find("{http://a9.com/-/spec/opensearch/1.1/}totalResults").text)
        print(tag,"page",start,"got",len(entries),"of",total,flush=True)
        start+=200
        time.sleep(3.5)
        if start>=total or start>=1000 or not entries: break
json.dump(list(seen.values()),open("arxiv_sweep.json","w"),indent=0)
print("unique",len(seen))
