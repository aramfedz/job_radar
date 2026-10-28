#!/usr/bin/env python3
"""Job Radar: baja vacantes de TA / Recruiting / People & Culture / HR desde
paginas de carreras (Greenhouse, Lever, Ashby, SmartRecruiters, Workday)
y genera index.html con filtros. Solo libreria estandar (Python 3.9+)."""
import json, re, time, urllib.request, pathlib
from datetime import date
from urllib.parse import urlparse, quote

# ---- EDITA AQUI ------------------------------------------------------------
# (ats, token_o_url, nombre, solo_costa_rica)
#  "auto" -> pega la URL de carreras y el script detecta el ATS (Workday, Taleo, Oracle,
#           Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Recruitee)
#  taleo/oracle -> pega la URL de carreras (xxx.taleo.net/careersection/... o ...oraclecloud.com/.../sites/...)
#  greenhouse/lever/ashby/smartrecruiters/workable/recruitee -> token de la empresa
#  workday -> pega la URL de su pagina de carreras (termina en .myworkdayjobs.com/...)
#  solo_costa_rica=True descarta todo lo que no mencione Costa Rica
# Solo Costa Rica. Ponelo en False para ver tambien otros paises (LATAM separado por pais).
ONLY_COSTA_RICA = True

# (ats, token_o_url, nombre, solo_costa_rica). Las URLs de Workday NO estan verificadas:
# si una falla, el log dice [skip] y las demas siguen. Agrega mas pegando la URL de carreras.
COMPANIES = [
    ("workday", "https://intel.wd1.myworkdayjobs.com/External", "Intel", True),
    ("workday", "https://dell.wd1.myworkdayjobs.com/External", "Dell", True),
    ("workday", "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site", "Salesforce", True),
    ("workday", "https://hp.wd5.myworkdayjobs.com/ExternalCareerSite", "HP", True),
    ("workday", "https://medtronic.wd1.myworkdayjobs.com/MedtronicCareers", "Medtronic", True),
    ("workday", "https://abbott.wd5.myworkdayjobs.com/abbottcareers", "Abbott", True),
    ("workday", "https://edwards.wd5.myworkdayjobs.com/edwardscareers", "Edwards Lifesciences", True),
    ("workday", "https://stryker.wd1.myworkdayjobs.com/StrykerCareers", "Stryker", True),
    ("workday", "https://equifax.wd5.myworkdayjobs.com/External", "Equifax", True),
    ("workday", "https://zoetis.wd5.myworkdayjobs.com/zoetis", "Zoetis", True),
    ("workday", "https://mastercard.wd1.myworkdayjobs.com/CorporateCareers", "Mastercard", True),
    ("workday", "https://philips.wd3.myworkdayjobs.com/jobs-and-careers", "Philips", True),
    ("workday", "https://kyndryl.wd5.myworkdayjobs.com/KyndrylProfessionalCareers", "Kyndryl", True),
    ("workday", "https://concentrix.wd1.myworkdayjobs.com/Concentrix_Careers", "Concentrix", True),
    ("taleo", "https://schneider.taleo.net/careersection/7/default.ftl?lang=en", "Schneider Electric", True),
    ("taleo", "https://teletech.taleo.net/careersection/2/jobsearch.ftl", "TTEC", True),
    ("taleo", "https://wsp.taleo.net/careersection/globalcareersection/jobsearch.ftl", "WSP", True),
    ("icims", "https://jobs-auxis.icims.com/jobs/search", "Auxis", True),
    ("greenhouse", "anthropic", "Anthropic", True),
    ("greenhouse", "stripe", "Stripe", True),
    ("greenhouse", "datadog", "Datadog", True),
    ("greenhouse", "cloudfire", "Cloudfire", True),
    ("ashby", "openai", "OpenAI", True),
    ("lever", "palantir", "Palantir", True),
]

# Directorio de empresas con sus paginas de empleo, por provincia.
DIRECTORY = [
 ('Roche', 'https://careers.roche.com/', 'Heredia'),
 ('Intel', 'https://jobs.intel.com/', 'Heredia'),
 ('Amazon', 'https://www.amazon.jobs/', 'Heredia'),
 ('IBM', 'https://www.ibm.com/careers', 'Heredia'),
 ('Hewlett Packard Enterprise', 'https://careers.hpe.com/', 'Heredia'),
 ('Cisco', 'https://careers.cisco.com/', 'Heredia'),
 ('Accenture', 'https://www.accenture.com/cr-es/careers', 'Heredia'),
 ('Equifax', 'https://careers.equifax.com/', 'Heredia'),
 ('Boston Consulting Group (BCG)', 'https://careers.bcg.com/', 'Heredia'),
 ('3M', 'https://www.3m.com/3M/en_US/careers-us/', 'Heredia'),
 ('DHL', 'https://careers.dhl.com/', 'Heredia'),
 ('Citi', 'https://jobs.citi.com/', 'Heredia'),
 ('Cargill', 'https://careers.cargill.com/', 'Heredia'),
 ('Bridgestone', 'https://www.bridgestone.com/corporate/careers/', 'Heredia'),
 ('Thermo Fisher Scientific', 'https://jobs.thermofisher.com/', 'Heredia'),
 ('Boston Scientific', 'https://jobs.bostonscientific.com/', 'Alajuela'),
 ('Smith+Nephew', 'https://careers.smith-nephew.com/', 'Alajuela'),
 ('Stryker', 'https://careers.stryker.com/', 'Alajuela'),
 ('Freudenberg Medical', 'https://jobs.freudenberg.com/', 'Alajuela'),
 ('Panduit', 'https://careers.panduit.com/', 'Alajuela'),
 ('Samtec', 'https://careers.samtec.com/', 'Alajuela'),
 ('Abbott', 'https://www.jobs.abbott/', 'Alajuela'),
 ('Philips', 'https://www.careers.philips.com/', 'Alajuela'),
 ('Medtronic', 'https://www.medtronic.com/us-en/our-company/careers.html', 'Alajuela'),
 ('MicroVention / Terumo', 'https://www.terumomedical.com/careers/', 'Alajuela'),
 ('Viant Medical', 'https://viantmedical.com/careers/', 'Alajuela'),
 ('CooperCompanies', 'https://www.coopercos.com/careers/', 'Alajuela'),
 ('Coloplast', 'https://www.coloplast.com/careers/', 'Alajuela'),
 ('Cardinal Health', 'https://jobs.cardinalhealth.com/', 'Alajuela'),
 ('Coca-Cola FEMSA', 'https://coca-colafemsa.com/en/join-coca-cola-femsa/apply-here/costa-rica.html', 'Alajuela'),
 ('Microsoft', 'https://careers.microsoft.com/', 'San José'),
 ('Deloitte', 'https://www.deloitte.com/cr/es/careers.html', 'San José'),
 ('PwC', 'https://www.pwc.com/ia/es/carreras.html', 'San José'),
 ('EY', 'https://www.ey.com/es_cr/careers', 'San José'),
 ('KPMG', 'https://kpmg.com/cr/es/home/carreras.html', 'San José'),
 ('Procter & Gamble (P&G)', 'https://www.pgcareers.com/', 'San José'),
 ('Coca-Cola Company', 'https://careers.coca-colacompany.com/', 'San José'),
 ('Walmart', 'https://careers.walmart.com/', 'San José'),
 ('PepsiCo', 'https://www.pepsicojobs.com/', 'San José'),
 ('GFT', 'https://www.gft.com/int/en/careers', 'San José'),
 ('Akamai Technologies', 'https://www.akamai.com/careers', 'San José'),
 ('Concentrix', 'https://jobs.concentrix.com/', 'San José'),
 ('Foundever', 'https://jobs.foundever.com/', 'San José'),
 ('Experian', 'https://www.experianplc.com/careers', 'San José'),
 ('Marriott International', 'https://careers.marriott.com/', 'San José'),
 ('Edwards Lifesciences', 'https://www.edwards.com/careers', 'Cartago'),
 ('Hologic', 'https://careers.hologic.com/', 'Cartago'),
 ('ICU Medical', 'https://www.icumed.com/careers/', 'Cartago'),
 ('Terumo', 'https://www.terumo.com/careers', 'Cartago'),
 ('Zollner Elektronik', 'https://www.zollner-electronics.com/career', 'Cartago'),
 ('Kimberly-Clark', 'https://careers.kimberly-clark.com/', 'Cartago'),
 ('Holcim', 'https://careers.holcim.com/', 'Cartago'),
 ('Dos Pinos', 'https://www.dospinos.com/', 'Cartago'),
 ('Florida Ice and Farm Company (FIFCO)', 'https://www.fifco.com/', 'Cartago'),
 ('Grupo Purdy', 'https://www.grupopurdy.com/', 'Cartago'),
 ('Banco Nacional de Costa Rica', 'https://www.bncr.fi.cr/', 'Cartago'),
 ('BAC Credomatic', 'https://www.baccredomatic.com/es-cr', 'Cartago'),
 ('Banco de Costa Rica', 'https://www.bancobcr.com/', 'Cartago'),
 ('Sysco / Mayca', 'https://www.syscocareers.cr/es/buscar-trabajo', 'Cartago'),
 ('Grupo Monge', 'https://www.grupomonge.com/', 'Cartago'),
 ("Moody's", 'https://careers.moodys.com/', 'Heredia'),
 ('Auxis', 'https://jobs-auxis.icims.com/jobs/search', 'Heredia'),
 ('Teradyne', 'https://careers.teradyne.com/', 'Heredia'),
 ('Schneider Electric', 'https://schneider.taleo.net/careersection/7/default.ftl?lang=en', 'San José'),
 ('TTEC', 'https://teletech.taleo.net/careersection/2/jobsearch.ftl', 'San José'),
 ('WSP', 'https://wsp.taleo.net/careersection/globalcareersection/jobsearch.ftl', 'San José'),
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
def http(url, data=None):
    h = {"User-Agent": UA, "Accept": "application/json"}
    if data is not None:
        h["Content-Type"] = "application/json"
        data = json.dumps(data).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request(url, data, h), timeout=30))

def text(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30).read().decode("utf-8", "ignore")

def detect(url):
    u = urlparse(url)
    h, parts = u.netloc.lower(), [x for x in u.path.split("/") if x]
    for key, name in [("myworkdayjobs.com", "workday"), ("taleo.net", "taleo"), ("oraclecloud.com", "oracle")]:
        if key in h:
            return name, url
    for key, name in [("greenhouse.io", "greenhouse"), ("lever.co", "lever"), ("ashbyhq.com", "ashby"),
                      ("smartrecruiters.com", "smartrecruiters"), ("workable.com", "workable")]:
        if key in h and parts:
            return name, parts[0]
    if "icims.com" in h:
        return "icims", url
    if "recruitee.com" in h:
        return "recruitee", h.split(".")[0]
    return None, url

def fetch(ats, tok, only_cr):
    if ats == "auto":
        ats, tok = detect(tok)
        if not ats:
            raise ValueError("ATS no soportado (iCIMS, SuccessFactors y Phenom no tienen API publica)")
    return fetch_ats(ats, tok, only_cr)

def terms(only_cr):
    return ["Costa Rica"] if only_cr else WORKDAY_TERMS

def fetch_ats(ats, tok, only_cr):
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
    if ats == "taleo":
        u = urlparse(tok)
        m = re.search(r"/careersection/([^/]+)/", u.path + "/")
        base = f"https://{u.netloc}/careersection/{m.group(1) if m else 'ex'}"
        pm = re.search(r"portal[=:\"' ]+(\d{6,})", text(base + "/jobsearch.ftl?lang=en"))
        api = f"https://{u.netloc}/careersection/rest/jobboard/searchjobs?lang=en&portal={pm.group(1) if pm else ''}"
        ids = lambda *n: [{"id": i, "selectedValues": []} for i in n]
        found = {}
        for term in terms(only_cr):
            for page in range(1, 21):
                d = http(api, {"multilineEnabled": False,
                               "sortingSelection": {"sortBySelectionParam": "3", "ascendingSortingOrder": "false"},
                               "fieldData": {"fields": {"KEYWORD": term, "LOCATION": ""}, "valid": True},
                               "filterSelectionParam": {"searchFilterSelections": ids("POSTING_DATE", "LOCATION", "JOB_FIELD", "JOB_TYPE", "JOB_SCHEDULE", "JOB_LEVEL")},
                               "advancedSearchFiltersSelectionParam": {"searchFilterSelections": ids("ORGANIZATION", "LOCATION", "JOB_FIELD", "JOB_NUMBER", "URGENT_JOB", "EMPLOYEE_STATUS", "STUDY_LEVEL", "WILL_TRAVEL", "JOB_SHIFT")},
                               "pageNo": page})
                items = d.get("requisitionList", [])
                for it in items:
                    c = it.get("column", [])
                    jid = it.get("contestNo") or it.get("jobId")
                    found[jid] = dict(title=str(c[0]) if c else "", wt="", url=f"{base}/jobdetail.ftl?job={jid}",
                                      loc=re.sub(r'[\[\]"]', "", str(c[1])) if len(c) > 1 else "")
                pg = d.get("pagingData", {})
                if not items or page * pg.get("pageSize", 25) >= pg.get("totalCount", 0):
                    break
                time.sleep(0.3)
        return list(found.values())
    if ats == "oracle":
        u = urlparse(tok)
        m = re.search(r"/sites/([^/]+)", u.path)
        site = m.group(1) if m else "CX"
        found = {}
        for term in terms(only_cr):
            for off in range(0, 500, 25):
                fin = f'findReqs;siteNumber={site},keyword="{term}",limit=25,offset={off},sortBy=POSTING_DATES_DESC'
                d = http(f"https://{u.netloc}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
                         f"?onlyData=true&expand=requisitionList&finder={quote(fin, safe='')}")
                reqs = (d.get("items") or [{}])[0].get("requisitionList", [])
                for r in reqs:
                    found[r["Id"]] = dict(title=r["Title"], loc=r.get("PrimaryLocation") or "",
                                          wt=(r.get("WorkplaceType") or "").replace("_", "-"),
                                          url=f"https://{u.netloc}/hcmUI/CandidateExperience/en/sites/{site}/job/{r['Id']}")
                if len(reqs) < 25:
                    break
                time.sleep(0.3)
        return list(found.values())
    if ats == "workable":
        out, body = [], {"query": "", "location": [], "department": [], "worktype": [], "remote": []}
        for _ in range(20):
            d = http(f"https://apply.workable.com/api/v3/accounts/{tok}/jobs", body)
            for r in d.get("results", []):
                l = r.get("location") or {}
                out.append(dict(title=r["title"], wt=(r.get("workplace") or "").replace("_", "-"),
                                loc=", ".join(x for x in [l.get("city"), l.get("region"), l.get("country")] if x),
                                url=f"https://apply.workable.com/{tok}/j/{r['shortcode']}/"))
            if not d.get("nextPage"):
                break
            body = {**body, "token": d["nextPage"]}
        return out
    if ats == "recruitee":
        d = http(f"https://{tok}.recruitee.com/api/offers/")
        return [dict(title=o["title"], url=o["careers_url"], wt="remote" if o.get("remote") else "",
                     loc=", ".join(x for x in [o.get("city"), o.get("country")] if x) or o.get("location") or "")
                for o in d.get("offers", [])]
    if ats == "icims":
        base = f"https://{urlparse(tok).netloc}"
        found = {}
        for term in terms(only_cr):
            for pg in range(0, 20):
                h = text(f"{base}/jobs/search?ss=1&searchKeyword={quote(term)}&in_iframe=1&pr={pg}")
                links = list(re.finditer(r'<a[^>]+href="([^"]*?/jobs/(\d+)/[^"]*?/job[^"]*)"[^>]*>(.*?)</a>', h, re.S))
                for m in links:
                    url, jid, inner = m.groups()
                    title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", inner)).strip()
                    lm = re.search(r"[^<>\n]*(?:Costa Rica|CR-|CRI)[^<>\n]*", h[m.end():m.end() + 1200])
                    if title and jid not in found:
                        found[jid] = dict(title=title, wt="", url=url if url.startswith("http") else base + url,
                                          loc=(lm.group(0).strip() if lm else ""))
                if not links:
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

CR_RX = re.compile(r"costa rica|\bcri\b|\bcr\b|heredia|escaz[uú]|ulloa|bel[eé]n|alajuela|coyol|cartago|pavas|la uruca|santa ana|san jos[eé]\s*[,-]\s*(cr|costa)")
def is_cr(loc):
    return bool(CR_RX.search(loc.lower()))

CR_PLACES = [("Remoto desde Costa Rica", r"remote|remoto|teletrabajo|home office"),
             ("Heredia y Belén", r"heredia|ulloa|bel[eé]n"),
             ("Alajuela y Coyol", r"alajuela|coyol"),
             ("San José y Escazú", r"san jos[eé]|escaz[uú]|pavas|uruca|santa ana"),
             ("Cartago", r"cartago")]
COUNTRIES = [("México", r"mexico|méxico"), ("Brasil", r"brazil|brasil"), ("Colombia", r"colombia"),
             ("Argentina", r"argentina"), ("Chile", r"\bchile\b"), ("Perú", r"\bperu\b|perú"),
             ("Panamá", r"panam"), ("Uruguay", r"uruguay"), ("Guatemala", r"guatemala"),
             ("Ecuador", r"ecuador"), ("República Dominicana", r"dominican"),
             ("LATAM (regional)", r"latam|latin america"),
             ("Estados Unidos", r"united states|\b(us|usa|u\.s\.)\b|new york|california|texas|washington"),
             ("Canadá", r"canada"), ("Europa / EMEA", r"europe|emea|\buk\b|united kingdom|ireland|germany|spain|portugal|france"),
             ("Asia-Pacífico", r"apac|apj|asia|india|japan|singapore|australia"),
             ("Global / Remoto", r"remote|remoto|anywhere|global|worldwide")]

def region(loc):
    l = loc.lower()
    if is_cr(l):
        for name, rx in CR_PLACES:
            if re.search(rx, l):
                return name
        return "Costa Rica (sin ciudad)"
    for name, rx in COUNTRIES:
        if re.search(rx, l):
            return name
    return "Otros"

TEMPLATE = r"""<!doctype html><html lang=es><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Job Radar</title>
<link rel=preconnect href="https://fonts.googleapis.com"><link rel=preconnect href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700&family=Instrument+Sans:wght@400;500;600&display=swap" rel=stylesheet>
<style>
:root{--bg:#eef1ec;--sur:#fff;--ink:#12211b;--mut:#5d6c63;--line:#d9dfd6;--pri:#1b4332;--onpri:#fff;--red:#c8102e;
--remote:#0b7a5a;--remote-bg:#d8f1e6;--hybrid:#8a5a00;--hybrid-bg:#fbebc4;--onsite:#2b4a8a;--onsite-bg:#dde6fa;--unknown:#5d6c63;--unknown-bg:#e6eae4}
@media(prefers-color-scheme:dark){:root{--bg:#0f1914;--sur:#16231c;--ink:#e8efe9;--mut:#92a399;--line:#26382e;--pri:#10261b;--onpri:#e8efe9;--red:#ff6b81;
--remote:#7fe0b6;--remote-bg:#12382a;--hybrid:#f2c867;--hybrid-bg:#3a2d0c;--onsite:#9db8f5;--onsite-bg:#18284a;--unknown:#92a399;--unknown-bg:#1f2d25}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 "Instrument Sans",system-ui,sans-serif}
button,input,select{font:inherit;color:inherit}:focus-visible{outline:2px solid var(--remote);outline-offset:2px}
header{background:var(--pri);color:var(--onpri);padding:34px 16px 30px}
.in{max-width:1040px;margin:0 auto}
h1{font:700 clamp(30px,5vw,44px)/1.05 "Bricolage Grotesque",system-ui,sans-serif;margin:0;letter-spacing:-.02em}
header p{margin:8px 0 0;opacity:.8;max-width:56ch}
.wrap{max-width:1040px;margin:0 auto;padding:20px 16px 60px;display:grid;grid-template-columns:250px 1fr;gap:24px;align-items:start}
aside{position:sticky;top:16px;display:grid;gap:18px}
h2{font-size:13px;font-weight:600;color:var(--mut);margin:0 0 6px}
input[type=search],select{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--sur)}
.opts{display:grid;gap:2px}
.opt{display:flex;align-items:center;gap:8px;width:100%;text-align:left;background:none;border:0;border-radius:8px;padding:7px 10px;cursor:pointer}
.opt b{margin-left:auto;font-weight:500;color:var(--mut);font-variant-numeric:tabular-nums}
.opt:hover{background:var(--line)}.opt[aria-pressed=true]{background:var(--pri);color:var(--onpri)}.opt[aria-pressed=true] b{color:inherit;opacity:.8}
.dot{width:9px;height:9px;border-radius:50%;background:var(--c)}
.remote{--c:var(--remote);--cb:var(--remote-bg)}.hybrid{--c:var(--hybrid);--cb:var(--hybrid-bg)}
.onsite{--c:var(--onsite);--cb:var(--onsite-bg)}.unknown{--c:var(--unknown);--cb:var(--unknown-bg)}
.chk{display:flex;gap:8px;align-items:center;cursor:pointer}
.bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;min-height:32px}
.bar span{font-weight:600}.clr{background:none;border:1px solid var(--line);border-radius:8px;padding:5px 12px;cursor:pointer}
.job{display:grid;grid-template-columns:1fr auto;gap:4px 14px;background:var(--sur);border:1px solid var(--line);border-left:5px solid var(--c);
border-radius:6px;padding:13px 16px;margin-bottom:8px;color:inherit;text-decoration:none}
.job:hover{border-color:var(--c)}
.jt{font-weight:600;font-size:16px}.jm{color:var(--mut);display:flex;flex-wrap:wrap;gap:2px 16px;grid-column:1}
.tags{grid-column:2;grid-row:1/3;display:flex;flex-direction:column;align-items:flex-end;gap:5px}
.tag{font-size:12px;font-weight:600;padding:2px 10px;border-radius:99px;background:var(--cb);color:var(--c)}
.tag.new{background:var(--red);color:#fff}
.dir{margin-top:28px;border-top:1px solid var(--line);padding-top:14px}.dir summary{cursor:pointer;font-weight:600}
#dirl h3{font-size:13px;font-weight:600;color:var(--mut);margin:16px 0 6px}
#dirl .g{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:6px}
#dirl a{padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:var(--sur);color:inherit;text-decoration:none}#dirl a:hover{border-color:var(--remote)}
.st{display:grid;grid-template-columns:1.2fr .7fr 2fr;gap:8px;padding:7px 0;border-bottom:1px solid var(--line);font-size:14px}
.empty{padding:48px 16px;text-align:center;color:var(--mut)}
@media(max-width:800px){.wrap{grid-template-columns:1fr}aside{position:static}.opts{display:flex;flex-wrap:wrap;gap:6px}
.opt{width:auto;border:1px solid var(--line)}.opt[aria-pressed=true]{border-color:var(--pri)}
.job{grid-template-columns:1fr}.tags{grid-column:1;grid-row:auto;flex-direction:row;flex-wrap:wrap;align-items:center}}
</style>
<header><div class=in><h1>Job Radar</h1><p id=sub></p></div></header>
<div class=wrap>
<aside>
<div><h2>Buscar</h2><input type=search id=q placeholder="Puesto, empresa o ciudad"></div>
<div><h2>Ubicación</h2><div class=opts id=reg></div></div>
<div><h2>Tipo de trabajo</h2><div class=opts id=mode></div></div>
<div><h2>Empresa</h2><select id=co></select></div>
<label class=chk><input type=checkbox id=nw> Solo vacantes nuevas</label>
</aside>
<main><div class=bar><span id=n></span><button class=clr id=clr hidden>Limpiar filtros</button></div><div id=list></div>
<details class=dir><summary>Directorio de carreras: __NDIR__ empresas</summary><div id=dirl></div></details>
<details class=dir><summary>Estado de las fuentes</summary><div id=stl></div></details></main>
</div>
<script>
const D=__DATA__,DIR=__DIR__,ST=__STATUS__,ML={remote:"Remoto",hybrid:"Híbrido",onsite:"Presencial",unknown:"No indicado"};
const REG=["Costa Rica","LATAM","Norteamérica","Europa / EMEA","Asia-Pacífico","Global / Remoto","Otros"];
const S={q:"",region:"",mode:"",company:"",nw:false},$=i=>document.getElementById(i);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const ok=(r,k)=>(k=="region"||!S.region||r.region==S.region)&&(k=="mode"||!S.mode||r.mode==S.mode)&&(k=="company"||!S.company||r.company==S.company)&&(!S.nw||r.new)&&(!S.q||(r.title+" "+r.company+" "+r.loc).toLowerCase().includes(S.q));
const has=k=>[...new Set(D.map(r=>r[k]))];
function opts(id,key,vals,all){const base=D.filter(r=>ok(r,key));
$(id).innerHTML=`<button class=opt data-k=${key} data-v="" aria-pressed=${!S[key]}>${all}<b>${base.length}</b></button>`+
vals.map(v=>({v,n:base.filter(r=>r[key]==v).length})).filter(o=>o.n||S[key]==o.v).map(o=>
`<button class="opt ${key=="mode"?o.v:""}" data-k=${key} data-v="${esc(o.v)}" aria-pressed=${S[key]==o.v}>${key=="mode"?"<i class=dot></i>":""}${esc(ML[o.v]||o.v)}<b>${o.n}</b></button>`).join("")}
function render(){const R=D.filter(r=>ok(r));
opts("reg","region",has("region").sort((a,b)=>D.filter(r=>r.region==b).length-D.filter(r=>r.region==a).length),"Todas");
opts("mode","mode",["remote","hybrid","onsite","unknown"].filter(x=>has("mode").includes(x)),"Todos");
const base=D.filter(r=>ok(r,"company"));
$("co").innerHTML='<option value="">Todas las empresas</option>'+has("company").sort().map(c=>`<option ${S.company==c?"selected":""} value="${esc(c)}">${esc(c)} (${base.filter(r=>r.company==c).length})</option>`).join("");
$("n").textContent=R.length+(R.length==1?" vacante":" vacantes");
$("clr").hidden=!(S.q||S.region||S.mode||S.company||S.nw);
$("list").innerHTML=R.length?R.map(r=>`<a class="job ${r.mode}" href="${esc(r.url)}" target=_blank rel=noopener><div class=jt>${esc(r.title)}</div><div class=jm><span>${esc(r.company)}</span><span>${esc(r.loc||"Ubicación no indicada")}</span></div><div class=tags><span class=tag>${ML[r.mode]}</span>${r.new?'<span class="tag new">Nueva</span>':""}</div></a>`).join("")
:'<div class=empty>Ninguna vacante coincide con estos filtros. Probá quitar alguno.</div>'}
$("sub").textContent="Talent Acquisition, Recruiting, People y HR en Costa Rica. Actualizado el __UPDATED__.";
document.querySelector("aside").addEventListener("click",e=>{const b=e.target.closest(".opt");if(!b)return;const k=b.dataset.k,v=b.dataset.v;S[k]=S[k]==v?"":v;render()});
$("q").addEventListener("input",e=>{S.q=e.target.value.toLowerCase().trim();render()});
$("co").addEventListener("change",e=>{S.company=e.target.value;render()});
$("nw").addEventListener("change",e=>{S.nw=e.target.checked;render()});
$("clr").addEventListener("click",()=>{Object.assign(S,{q:"",region:"",mode:"",company:"",nw:false});$("q").value="";$("nw").checked=false;render()});
$("dirl").innerHTML=[...new Set(DIR.map(c=>c[2]))].map(p=>`<h3>${esc(p)}</h3><div class=g>`+DIR.filter(c=>c[2]==p).map(c=>`<a href="${esc(c[1])}" target=_blank rel=noopener>${esc(c[0])}</a>`).join("")+"</div>").join("");
$("stl").innerHTML=ST.map(x=>`<div class=st><span>${esc(x[0])}</span><span>${x[1]=="ok"?"Activa":"Con error"}</span><span>${esc(x[2])}</span></div>`).join("");
render();
</script></html>
"""

def main():
    root = pathlib.Path(__file__).parent
    sf = root / "seen.json"
    initial = not sf.exists()
    seen = json.loads(sf.read_text()) if sf.exists() else {}
    if isinstance(seen, list):
        seen = {u: date.today().isoformat() for u in seen}
    today, rows, status = date.today(), [], []
    for ats, tok, name, only_cr in COMPANIES:
        try:
            jobs = fetch(ats, tok, only_cr)
        except Exception as e:
            print(f"[skip] {name}: {e}")
            status.append([name, "error", str(e)[:90]])
            continue
        kept = 0
        for j in jobs:
            if not TITLE_RE.search(j["title"].lower()):
                continue
            if (ONLY_COSTA_RICA or only_cr) and not is_cr(j["loc"]):
                continue
            first = seen.setdefault(j["url"], today.isoformat())
            age = (today - date.fromisoformat(first)).days
            rows.append(dict(company=name, title=j["title"], loc=j["loc"], url=j["url"],
                             mode=work_mode(j), region=region(j["loc"]),
                             new=(not initial and age <= 2)))
            kept += 1
        print(f"[ok] {name}: {kept} vacantes")
        status.append([name, "ok", f"{kept} vacantes de Costa Rica" if kept else "sin vacantes de HR/TA ahora"])
    order = {"Costa Rica": 0, "LATAM": 1}
    rows.sort(key=lambda r: (order.get(r["region"], 2), not r["new"], r["company"], r["title"]))
    sf.write_text(json.dumps(seen))
    page = TEMPLATE.replace("__DATA__", json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")) \
                   .replace("__DIR__", json.dumps(DIRECTORY, ensure_ascii=False)).replace("__NDIR__", str(len(DIRECTORY))) \
                   .replace("__STATUS__", json.dumps(status, ensure_ascii=False)).replace("__UPDATED__", today.strftime("%d/%m/%Y"))
    (root / "index.html").write_text(page, encoding="utf-8")
    print(f"Total: {len(rows)} -> index.html")

if __name__ == "__main__":
    main()
