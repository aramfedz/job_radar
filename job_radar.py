#!/usr/bin/env python3
"""Job Radar: baja vacantes de TA / Recruiting / People & Culture / HR desde
paginas de carreras (Greenhouse, Lever, Ashby, SmartRecruiters, Workday)
y genera index.html con filtros. Solo libreria estandar (Python 3.9+)."""
import json, re, time, urllib.request, pathlib
from datetime import date
from urllib.parse import urlparse

# ---- EDITA AQUI ------------------------------------------------------------
# (ats, token_o_url, nombre, solo_costa_rica)
#  greenhouse/lever/ashby/smartrecruiters -> token de la empresa
#  workday -> pega la URL de su pagina de carreras (termina en .myworkdayjobs.com/...)
#  solo_costa_rica=True descarta todo lo que no mencione Costa Rica
COMPANIES = [
    ("workday", "https://intel.wd1.myworkdayjobs.com/External", "Intel", True),
    ("workday", "https://dell.wd1.myworkdayjobs.com/External", "Dell", True),
    ("workday", "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site", "Salesforce", True),
    ("greenhouse", "anthropic", "Anthropic", False),
    ("greenhouse", "stripe", "Stripe", False),
    ("greenhouse", "gitlab", "GitLab", False),
    ("greenhouse", "databricks", "Databricks", False),
    ("greenhouse", "datadog", "Datadog", False),
    ("greenhouse", "cloudflare", "Cloudflare", False),
    ("ashby", "openai", "OpenAI", False),
    ("ashby", "notion", "Notion", False),
    ("ashby", "ramp", "Ramp", False),
    ("lever", "palantir", "Palantir", False),
]
TITLE_RE = re.compile(
    r"\b(recruit\w*|talent|sourc(er|ing)|hr|hrbp|human resources|human capital|"
    r"people (partner|operations|ops|business|team|experience|analytics|success|and culture|& culture)|"
    r"chief people|head of people|vp,? people|culture|employee (experience|relations)|"
    r"total rewards|compensation|benefits|payroll|workforce|onboarding|internal mobility|"
    r"learning (and|&) development|dei|diversity|inclusion|reclutamiento|recursos humanos|"
    r"gesti[oó]n del talento|capital humano)\b")
WORKDAY_TERMS = ["recruiter", "talent acquisition", "human resources", "people"]
# ---------------------------------------------------------------------------
UA = "job-radar/2.0"
REGIONS = [
    ("Costa Rica", re.compile(r"costa rica|heredia|escaz[uú]|ulloa|alajuela")),
    ("LATAM", re.compile(r"latam|latin america|mexico|m[eé]xico|brazil|brasil|colombia|argentina|"
                         r"chile|peru|per[uú]|panam[aá]|uruguay|guatemala|ecuador|dominican")),
    ("Norteamérica", re.compile(r"united states|\b(us|usa|u\.s\.)\b|canada|north america|new york|"
                                r"california|texas|washington|massachusetts|illinois|georgia")),
    ("Europa / EMEA", re.compile(r"europe|emea|united kingdom|\buk\b|ireland|germany|spain|portugal|"
                                 r"france|netherlands|poland|london|dublin|berlin|madrid|lisbon")),
    ("Asia-Pacífico", re.compile(r"apac|apj|asia|india|japan|singapore|australia|china")),
    ("Global / Remoto", re.compile(r"remote|remoto|anywhere|global|worldwide")),
]

def http(url, data=None):
    h = {"User-Agent": UA, "Accept": "application/json"}
    if data is not None:
        h["Content-Type"] = "application/json"
        data = json.dumps(data).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request(url, data, h), timeout=30))

def fetch(ats, tok, only_cr):
    if ats == "greenhouse":
        d = http(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs")
        return [dict(title=j["title"], loc=(j.get("location") or {}).get("name", ""),
                     url=j["absolute_url"], wt="") for j in d["jobs"]]
    if ats == "lever":
        d = http(f"https://api.lever.co/v0/postings/{tok}?mode=json")
        return [dict(title=j["text"], loc=(j.get("categories") or {}).get("location") or "",
                     url=j["hostedUrl"], wt=j.get("workplaceType") or "") for j in d]
    if ats == "ashby":
        d = http(f"https://api.ashbyhq.com/posting-api/job-board/{tok}")
        return [dict(title=j["title"], loc=j.get("location") or "", url=j["jobUrl"],
                     wt=j.get("workplaceType") or ("remote" if j.get("isRemote") else "")) for j in d["jobs"]]
    if ats == "smartrecruiters":
        out, off = [], 0
        while True:
            q = "&country=cr" if only_cr else ""
            d = http(f"https://api.smartrecruiters.com/v1/companies/{tok}/postings?limit=100&offset={off}{q}")
            for p in d.get("content", []):
                l = p.get("location") or {}
                wt = "remote" if l.get("remote") else "hybrid" if l.get("hybrid") else ""
                out.append(dict(title=p["name"], loc=", ".join(x for x in [l.get("city"), l.get("country")] if x),
                                url=f"https://jobs.smartrecruiters.com/{tok}/{p['id']}", wt=wt))
            off += 100
            if off >= d.get("totalFound", 0):
                return out
    if ats == "workday":
        u = urlparse(tok)
        host, site = u.netloc, u.path.strip("/").split("/")[-1]
        api = f"https://{host}/wday/cxs/{host.split('.')[0]}/{site}/jobs"
        found = {}
        for term in (["Costa Rica"] if only_cr else WORKDAY_TERMS):
            for off in range(0, 300, 20):
                ps = http(api, {"appliedFacets": {}, "limit": 20, "offset": off,
                                "searchText": term}).get("jobPostings", [])
                for p in ps:
                    found[p["externalPath"]] = dict(
                        title=p["title"], loc=p.get("locationsText", ""), wt="",
                        url=f"https://{host}/en-US/{site}{p['externalPath']}")
                if len(ps) < 20:
                    break
                time.sleep(0.3)
        return list(found.values())
    return []

def work_mode(j):
    s = f"{j['wt']} {j['loc']} {j['title']}".lower()
    if "hybrid" in s or "híbrido" in s or "hibrido" in s:
        return "hybrid"
    if "remote" in s or "remoto" in s:
        return "remote"
    if "on-site" in s or "onsite" in s or "on site" in s or "presencial" in s:
        return "onsite"
    return "unknown"

def region(loc):
    l = loc.lower()
    for name, rx in REGIONS:
        if rx.search(l):
            return name
    return "Otros"

TEMPLATE = r"""<!doctype html><html lang=es><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Job Radar</title>
<style>
:root{--bg:#f6f6f3;--card:#fff;--fg:#1c1c1a;--mut:#6b6b66;--line:#e4e4de;--acc:#d97757}
@media(prefers-color-scheme:dark){:root{--bg:#141413;--card:#1f1f1d;--fg:#eeeeea;--mut:#9a9a93;--line:#33332f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.4 system-ui,sans-serif}
.w{max-width:960px;margin:0 auto;padding:20px 16px 60px}
h1{margin:0;font-size:26px}.sub{color:var(--mut);margin:4px 0 16px}
.bar{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin-bottom:12px}
select,input[type=search]{width:100%;padding:10px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--fg);font:inherit}
.row{display:flex;gap:12px;align-items:center;justify-content:space-between;margin:10px 0;color:var(--mut)}
label{display:flex;gap:6px;align-items:center;cursor:pointer}
.j{display:block;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin:8px 0;color:inherit;text-decoration:none}
.j:hover{border-color:var(--acc)}.t{font-weight:600}.m{color:var(--mut);margin:3px 0 8px}
.c{display:inline-block;font-size:12px;padding:2px 9px;border-radius:99px;margin-right:6px;background:var(--line)}
.remote{background:#cfeedb;color:#14532d}.hybrid{background:#ffe7b3;color:#6b4200}.onsite{background:#dbe7ff;color:#1e3a8a}
.new{background:var(--acc);color:#fff}.e{text-align:center;color:var(--mut);padding:40px}
</style><div class=w><h1>Job Radar</h1><div class=sub id=sub></div>
<div class=bar><input type=search id=q placeholder="Buscar puesto o empresa">
<select id=reg></select><select id=mode></select><select id=co></select></div>
<div class=row><span id=n></span><label><input type=checkbox id=nw> Solo nuevas</label></div>
<div id=list></div></div>
<script>
const D=__DATA__,ML={remote:"Remoto",hybrid:"Híbrido",onsite:"Presencial",unknown:"No indicado"};
const $=i=>document.getElementById(i),esc=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function fill(el,all,vals,lab){el.innerHTML=`<option value="">${all}</option>`+vals.map(v=>`<option value="${esc(v)}">${esc(lab?lab[v]||v:v)} (${D.filter(r=>r[el.dataset.k]==v).length})</option>`).join("")}
const u=k=>[...new Set(D.map(r=>r[k]))].sort();
$("reg").dataset.k="region";$("mode").dataset.k="mode";$("co").dataset.k="company";
const ro=["Costa Rica","LATAM","Norteamérica","Europa / EMEA","Asia-Pacífico","Global / Remoto","Otros"].filter(x=>u("region").includes(x));
fill($("reg"),"Todas las ubicaciones",ro);fill($("mode"),"Todos los tipos",["remote","hybrid","onsite","unknown"].filter(x=>u("mode").includes(x)),ML);fill($("co"),"Todas las empresas",u("company"));
$("sub").textContent=D.length+" vacantes · actualizado __UPDATED__";
function go(){const q=$("q").value.toLowerCase(),a=$("reg").value,b=$("mode").value,c=$("co").value,n=$("nw").checked;
const R=D.filter(r=>(!a||r.region==a)&&(!b||r.mode==b)&&(!c||r.company==c)&&(!n||r.new)&&(!q||(r.title+" "+r.company+" "+r.loc).toLowerCase().includes(q)));
$("n").textContent=R.length+" resultados";
$("list").innerHTML=R.length?R.map(r=>`<a class=j href="${esc(r.url)}" target=_blank rel=noopener><div class=t>${esc(r.title)}</div><div class=m>${esc(r.company)} · ${esc(r.loc||"Ubicación no indicada")}</div><span class="c ${r.mode}">${ML[r.mode]}</span><span class=c>${esc(r.region)}</span>${r.new?'<span class="c new">Nueva</span>':""}</a>`).join(""):'<div class=e>Sin resultados con esos filtros</div>'}
["q","reg","mode","co","nw"].forEach(i=>$(i).addEventListener("input",go));go();
</script></html>"""

def main():
    root = pathlib.Path(__file__).parent
    sf = root / "seen.json"
    initial = not sf.exists()
    seen = json.loads(sf.read_text()) if sf.exists() else {}
    if isinstance(seen, list):
        seen = {u: date.today().isoformat() for u in seen}
    today, rows = date.today(), []
    for ats, tok, name, only_cr in COMPANIES:
        try:
            jobs = fetch(ats, tok, only_cr)
        except Exception as e:
            print(f"[skip] {name}: {e}")
            continue
        kept = 0
        for j in jobs:
            if not TITLE_RE.search(j["title"].lower()):
                continue
            if only_cr and "costa rica" not in j["loc"].lower():
                continue
            first = seen.setdefault(j["url"], today.isoformat())
            age = (today - date.fromisoformat(first)).days
            rows.append(dict(company=name, title=j["title"], loc=j["loc"], url=j["url"],
                             mode=work_mode(j), region=region(j["loc"]),
                             new=(not initial and age <= 2)))
            kept += 1
        print(f"[ok] {name}: {kept} vacantes")
    order = {"Costa Rica": 0, "LATAM": 1}
    rows.sort(key=lambda r: (order.get(r["region"], 2), not r["new"], r["company"], r["title"]))
    sf.write_text(json.dumps(seen))
    page = TEMPLATE.replace("__DATA__", json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")) \
                   .replace("__UPDATED__", today.strftime("%d/%m/%Y"))
    (root / "index.html").write_text(page, encoding="utf-8")
    print(f"Total: {len(rows)} -> index.html")

if __name__ == "__main__":
    main()
