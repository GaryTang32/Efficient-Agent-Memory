import json, re, time, html, urllib.request
P=json.load(open("selected.json"))
out={}
for i,p in enumerate(P):
    aid=p["id"]
    url=f"https://arxiv.org/html/{aid}"
    txt=""
    for a in range(2):
        try:
            raw=urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"eam-litscan/0.1"}),timeout=40).read(800000).decode("utf-8","ignore")
            i=raw.find("ltx_authors")
            seg=raw[i:i+12000] if i>=0 else ""
            txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",seg)).split())
            txt=txt.split(" Abstract ")[0][:1500] if txt else "NO_HTML_AUTHORS"
            break
        except Exception as e:
            txt=f"ERR {type(e).__name__}"
            time.sleep(2)
    out[aid]=txt
    if i%25==0: print(i,aid,txt[:80],flush=True)
    time.sleep(1.0)
json.dump(out,open("html_affils.json","w"),indent=0)
print("done",len(out),"errors",sum(v.startswith("ERR") for v in out.values()))
