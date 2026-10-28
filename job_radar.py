#!/usr/bin/env python3
"""Job Radar: baja vacantes de APIs publicas (Greenhouse, Lever, Ashby),
filtra remotas / amigables con Costa Rica y genera index.html.
Uso: python job_radar.py   (solo libreria estandar, Python 3.9+)"""
import json, html, os, re, urllib.request, pathlib
from datetime import datetime, timezone

# ---- EDITA AQUI ----------------------------------------------------------
# (ats, token_de_la_empresa). Si un token falla, simplemente se salta.
COMPANIES = [
    ("greenhouse", "anthropic"), ("greenhouse", "stripe"),
    ("greenhouse", "gitlab"), ("greenhouse", "databricks"),
    ("greenhouse", "datadog"), ("greenhouse", "cloudflare"),
    ("ashby", "openai"), ("ashby", "notion"), ("ashby", "ramp"),
    ("lever", "palantir"),
]
TITLE_RE = re.compile(
    r"\b(recruit\w*|talent|sourc(er|ing)|hr|hrbp|human resources|human capital|"
    r"people (partner|operations|ops|business|team|experience|analytics|success|and culture|& culture)|"
    r"chief people|head of people|vp,? people|culture|employee (experience|relations)|"
    r"total rewards|compensation|benefits|payroll|workforce|onboarding|internal mobility|"
    r"learning (and|&) development|dei|diversity|inclusion)\b")
CR_FRIENDLY = ["costa rica", "latam", "latin america", "americas",
               "worldwide", "anywhere", "global"]

# Palabras de tu perfil y cuanto pesan en el puntaje (titulo x2, descripcion x1)
WEIGHTS = {"gtm": 12, "sales": 10, "internal mobility": 15, "talent acquisition": 12,
           "recruit": 10, "sourc": 8, "renewals": 8, "latam": 10, "latin america": 10,
           "spanish": 8, "portuguese": 8, "workday": 6, "greenhouse": 6,
           "operations": 5, "program": 4,
           "human resources": 6, "people operations": 6, "hrbp": 6, "culture": 4}
CV_SUMMARY = """Talent Acquisition Partner GTM/Sales, 5+ anos. Veeam (Mar 2026-hoy): portafolio de 30
requisiciones (Sales Engineering, SDR, Renewals, Advocacy), SME de Internal Mobility para las Americas,
diseno la politica global de movilidad interna (~7,000 empleados), 20 contrataciones internas en Q2 2026,
tiempo de cierre 14.5 dias. Antes: Recruiting Coordinator en Amazon (AWS), reclutamiento de operaciones,
SOPs, programa de mentoria (140+ coordinadores). Herramientas: Workday, Greenhouse, LinkedIn Recruiter,
Boolean, Tableau, Python. Idiomas: espanol nativo, ingles C2, portugues B2. Vive en Costa Rica, busca remoto."""
# ---------------------------------------------------------------------------

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "job-radar/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def fetch(ats, token):
    if ats == "greenhouse":
        d = get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true")
        return [dict(title=j["title"], loc=(j.get("location") or {}).get("name", ""),
                     url=j["absolute_url"], remote=False,
                     desc=re.sub("<[^>]+>", " ", html.unescape(j.get("content", "")))) for j in d["jobs"]]
    if ats == "lever":
        d = get(f"https://api.lever.co/v0/postings/{token}?mode=json")
        return [dict(title=j["text"], loc=(j.get("categories") or {}).get("location", "") or "",
                     url=j["hostedUrl"], remote=j.get("workplaceType") == "remote", wt=j.get("workplaceType") or "",
                     desc=j.get("descriptionPlain", "")) for j in d]
    if ats == "ashby":
        d = get(f"https://api.ashbyhq.com/posting-api/job-board/{token}")
        return [dict(title=j["title"], loc=j.get("location", "") or "",
                     url=j["jobUrl"], remote=bool(j.get("isRemote")), wt=j.get("workplaceType") or "",
                     desc=j.get("descriptionPlain", "")) for j in d["jobs"]]
    return []

def detect_mode(j, loc):
    """remote / hybrid / onsite. Si no hay pista clara, se asume presencial."""
    wt = (j.get("wt") or "").lower()
    txt = loc + " " + j["title"].lower()
    if "hybrid" in wt or "hybrid" in txt or "híbrido" in txt or "hibrido" in txt:
        return "hybrid"
    if wt == "remote" or j.get("remote") or "remote" in txt or "remoto" in txt:
        return "remote"
    return "onsite"

def kw_score(title, desc, cr):
    """Puntaje 0-100 gratis y local, por palabras clave de tu perfil."""
    t, d = title.lower(), desc.lower()
    s = sum(w * 2 for k, w in WEIGHTS.items() if k in t) + sum(w for k, w in WEIGHTS.items() if k in d)
    return min(100, s + (15 if cr else 0))

def claude_score(r):
    """Opcional: si hay ANTHROPIC_API_KEY, Claude afina el puntaje de las 15 mejores."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return
    prompt = (f"Perfil del candidato:\n{CV_SUMMARY}\n\nVacante: {r['title']} en {r['company']} "
              f"({r['loc']})\n{r['desc'][:4000]}\n\nResponde SOLO JSON: "
              '{"score": 0-100, "why": "max 20 palabras en espanol; indica si es viable desde Costa Rica"}')
    body = json.dumps({"model": "claude-sonnet-5-5", "max_tokens": 200,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", body,
                                 {"x-api-key": key, "anthropic-version": "2023-06-01",
                                  "content-type": "application/json"})
    try:
        out = json.load(urllib.request.urlopen(req, timeout=30))
        d = json.loads(out["content"][0]["text"])
        r["score"], r["why"] = int(d["score"]), d["why"]
    except Exception as e:
        print("[claude]", e)

def main():
    root = pathlib.Path(__file__).parent
    seen_f = root / "seen.json"
    seen = set(json.loads(seen_f.read_text())) if seen_f.exists() else set()
    rows = []
    for ats, token in COMPANIES:
        try:
            jobs = fetch(ats, token)
        except Exception as e:
            print(f"[skip] {token}: {e}")
            continue
        for j in jobs:
            t, loc = j["title"].lower(), j["loc"].lower()
            if not TITLE_RE.search(t):
                continue
            mode = detect_mode(j, loc)
            cr = any(k in loc for k in CR_FRIENDLY)
            rows.append(dict(company=token, title=j["title"], loc=j["loc"] or "No indicada", mode=mode,
                             url=j["url"], cr=cr, new=j["url"] not in seen,
                             desc=j["desc"][:6000], score=kw_score(j["title"], j["desc"], cr), why=""))
    rows.sort(key=lambda r: -r["score"])
    for r in rows[:15]:
        claude_score(r)
    rows.sort(key=lambda r: (-r["score"], not r["new"]))
    seen_f.write_text(json.dumps(sorted(seen | {r["url"] for r in rows})))

    def cards_of(rows_):
      return "\n".join(
        f'<a class="c" href="{html.escape(r["url"])}" target="_blank" rel="noopener">'
        f'<b>{html.escape(r["title"])}</b><span>{html.escape(r["company"])} · {html.escape(r["loc"])}</span>'
        f'<i class=s>Afinidad {r["score"]}/100</i>'
        f'{"<span>" + html.escape(r["why"]) + "</span>" if r["why"] else ""}'
        f'{"<i class=g>Apto CR/LATAM</i>" if r["cr"] else "<i>Revisar elegibilidad</i>"}'
        f'{"<i class=n>Nueva</i>" if r["new"] else ""}</a>' for r in rows_)
    LABELS = [("remote", "Remoto"), ("hybrid", "Híbrido"), ("onsite", "Presencial")]
    cards = ""
    for key, lab in LABELS:
        sub = [r for r in rows if r["mode"] == key]
        cards += f'<h2 id={key}>{lab} ({len(sub)})</h2>' + cards_of(sub)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    page = f"""<!doctype html><html lang=es><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Job Radar</title><style>
:root{{--bg:#fff;--fg:#1a1a1a;--card:#f4f4f2;--mut:#666}}
@media(prefers-color-scheme:dark){{:root{{--bg:#161616;--fg:#eee;--card:#242424;--mut:#aaa}}}}
body{{font:16px system-ui;background:var(--bg);color:var(--fg);max-width:720px;margin:0 auto;padding:16px}}
input{{width:100%;padding:10px;margin:8px 0;font-size:16px;box-sizing:border-box}}
.c{{display:block;background:var(--card);padding:12px;border-radius:10px;margin:8px 0;color:inherit;text-decoration:none}}
.c span{{display:block;color:var(--mut);font-size:14px;margin:2px 0 6px}}
i{{font-size:12px;font-style:normal;padding:2px 8px;border-radius:99px;background:#ddd;color:#333;margin-right:6px}}
i.g{{background:#bfe8c9}}i.n{{background:#ffd98a}}
</style><h1>Job Radar</h1>
<p style="color:var(--mut)">{len(rows)} vacantes · actualizado {now}</p>
<p><a href=#remote>Remoto</a> · <a href=#hybrid>Híbrido</a> · <a href=#onsite>Presencial</a></p>
<input id=q placeholder="Filtrar..." oninput="f()">
<div id=l>{cards}</div>
<script>function f(){{var v=q.value.toLowerCase();
document.querySelectorAll('.c').forEach(function(e){{e.style.display=e.textContent.toLowerCase().includes(v)?'':'none'}})}}</script></html>"""
    (root / "index.html").write_text(page, encoding="utf-8")
    print(f"{len(rows)} vacantes -> index.html")

if __name__ == "__main__":
    main()
