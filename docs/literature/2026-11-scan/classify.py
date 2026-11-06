import json, re, collections
P=json.load(open("selected.json")); A=json.load(open("html_affils.json"))
ORGS={
 # US big labs / companies
 "Anthropic":r"\bAnthropic\b","OpenAI":r"\bOpenAI\b","Google/DeepMind":r"Google|DeepMind","Meta":r"\bMeta\b(?! ?-?learning)|FAIR\b|Meta AI|Meta Superintelligence","Microsoft":r"Microsoft","Amazon/AWS":r"Amazon|\bAWS\b","NVIDIA":r"NVIDIA|Nvidia","Apple":r"\bApple\b","IBM":r"\bIBM\b","Salesforce":r"Salesforce","Intel":r"\bIntel\b",
 # China companies
 "Alibaba/Qwen/Tongyi":r"Alibaba|Qwen|Tongyi|DAMO|Ant Group|inclusionAI|Alipay","ByteDance":r"ByteDance|Bytedance|Seed\b|Doubao","Tencent":r"Tencent|Hunyuan|WeChat","Baidu":r"Baidu","DeepSeek":r"DeepSeek","Moonshot/Kimi":r"Moonshot|Kimi","Zhipu/Z.ai":r"Zhipu|Z\.ai|\bGLM\b","MiniMax":r"MiniMax","Meituan":r"Meituan|LongCat","Huawei":r"Huawei|Noah'?s Ark","Xiaohongshu":r"Xiaohongshu|RedNote","Kuaishou":r"Kuaishou","JD":r"\bJD\b|JD\.com","StepFun":r"StepFun","Xiaomi":r"Xiaomi","iFlytek":r"iFlytek","MemTensor":r"MemTensor","SenseTime":r"SenseTime",
 # China universities / institutes
 "Tsinghua":r"Tsinghua","Peking U":r"Peking University|\bPKU\b","Zhejiang U":r"Zhejiang University","SJTU":r"Shanghai Jiao ?Tong","Fudan":r"Fudan","USTC":r"University of Science and Technology of China|\bUSTC\b","Renmin U":r"Renmin","Nanjing U":r"Nanjing University","HIT":r"Harbin Institute","CAS":r"Chinese Academy of Sciences|\bCAS\b|UCAS","Shanghai AI Lab":r"Shanghai (Artificial Intelligence|AI) Lab","BAAI":r"\bBAAI\b|Beijing Academy of Artificial","BUPT":r"Beijing University of Posts","Wuhan U":r"Wuhan University","SYSU":r"Sun Yat-?sen","Beihang":r"Beihang","HKUST":r"Hong Kong University of Science|HKUST","CUHK":r"Chinese University of Hong Kong|CUHK","HKU":r"(?<!Chinese )University of Hong Kong\b|\bHKU\b","Westlake":r"Westlake","Southern U S&T":r"Southern University of Science","Xiamen U":r"Xiamen University","Tianjin U":r"Tianjin University","Soochow":r"Soochow",
}
CHINA={k for k in ORGS if k in ("Alibaba/Qwen/Tongyi","ByteDance","Tencent","Baidu","DeepSeek","Moonshot/Kimi","Zhipu/Z.ai","MiniMax","Meituan","Huawei","Xiaohongshu","Kuaishou","JD","StepFun","Xiaomi","iFlytek","MemTensor","SenseTime","Tsinghua","Peking U","Zhejiang U","SJTU","Fudan","USTC","Renmin U","Nanjing U","HIT","CAS","Shanghai AI Lab","BAAI","BUPT","Wuhan U","SYSU","Beihang","HKUST","CUHK","HKU","Westlake","Southern U S&T","Xiamen U","Tianjin U","Soochow")}
USBIG={"Anthropic","OpenAI","Google/DeepMind","Meta","Microsoft","Amazon/AWS","NVIDIA","Apple","IBM","Salesforce","Intel"}
for p in P:
    txt=A.get(p["id"],"")+" "+" ".join(p.get("affils",[]))
    p["affil_text"]=txt[:600]
    p["orgs"]=[k for k,rx in ORGS.items() if re.search(rx,txt)]
    p["china"]=bool(set(p["orgs"])&CHINA); p["usbig"]=bool(set(p["orgs"])&USBIG)
json.dump(P,open("classified.json","w"),indent=0)
c=collections.Counter(o for p in P for o in p["orgs"])
print("papers",len(P),"no affiliation text",sum(1 for p in P if not A.get(p["id"]) or A[p["id"]].startswith(("ERR","NO_HTML"))))
print("china-affiliated",sum(p["china"] for p in P),"us-big-lab",sum(p["usbig"] for p in P))
print(c.most_common(40))
