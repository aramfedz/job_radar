#!/usr/bin/env python3
"""Job Radar: baja vacantes de TA / Recruiting / People & Culture / HR desde
paginas de carreras (Greenhouse, Lever, Ashby, SmartRecruiters, Workday)
y genera index.html con filtros. Solo libreria estandar (Python 3.9+)."""
import json, re, time, urllib.request, urllib.error, pathlib, html, socket
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from urllib.parse import urlparse, quote, urljoin, urlunparse

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

# Additional employers with Costa Rica operations or Costa Rica-accessible career sites.
DIRECTORY += [('Adobe', 'https://careers.adobe.com/', 'San Jose'), ('AstraZeneca', 'https://careers.astrazeneca.com/', 'San Jose'), ('Bayer', 'https://career.bayer.com/', 'San Jose'), ('Baxter', 'https://jobs.baxter.com/', 'Heredia'), ('Becton Dickinson (BD)', 'https://jobs.bd.com/', 'Alajuela'), ('Boehringer Ingelheim', 'https://jobs.boehringer-ingelheim.com/', 'San Jose'), ('Bristol Myers Squibb', 'https://careers.bms.com/', 'San Jose'), ('Johnson & Johnson', 'https://careers.jnj.com/', 'San Jose'), ('Pfizer', 'https://www.pfizer.com/about/careers', 'San Jose'), ('GSK', 'https://jobs.gsk.com/', 'San Jose'), ('Novartis', 'https://www.novartis.com/careers', 'San Jose'), ('Sanofi', 'https://jobs.sanofi.com/', 'San Jose'), ('Merck', 'https://jobs.merck.com/', 'San Jose'), ('MSD', 'https://jobs.msd.com/', 'San Jose'), ('Lilly', 'https://careers.lilly.com/', 'San Jose'), ('Align Technology', 'https://jobs.aligntech.com/', 'Heredia'), ('ResMed', 'https://careers.resmed.com/', 'Alajuela'), ('AbbVie', 'https://careers.abbvie.com/', 'San Jose'), ('Amgen', 'https://careers.amgen.com/', 'San Jose'), ('BioMarin', 'https://careers.biomarin.com/', 'San Jose'), ('Oracle', 'https://www.oracle.com/careers/', 'San Jose'), ('SAP', 'https://jobs.sap.com/', 'Heredia'), ('VMware by Broadcom', 'https://careers.broadcom.com/', 'Heredia'), ('Broadcom', 'https://careers.broadcom.com/', 'Heredia'), ('NVIDIA', 'https://www.nvidia.com/en-us/about-nvidia/careers/', 'San Jose'), ('ServiceNow', 'https://careers.servicenow.com/', 'Heredia'), ('Splunk', 'https://www.splunk.com/en_us/careers.html', 'San Jose'), ('Databricks', 'https://www.databricks.com/company/careers', 'San Jose'), ('Snowflake', 'https://careers.snowflake.com/', 'San Jose'), ('Twilio', 'https://www.twilio.com/company/jobs', 'Remoto Costa Rica'), ('GitLab', 'https://about.gitlab.com/jobs/', 'Remoto Costa Rica'), ('Zapier', 'https://zapier.com/jobs', 'Remoto Costa Rica'), ('Automattic', 'https://automattic.com/work-with-us/', 'Remoto Costa Rica'), ('Canonical', 'https://canonical.com/careers', 'Remoto Costa Rica'), ('Cloudflare', 'https://www.cloudflare.com/careers/jobs/', 'Remoto Costa Rica'), ('Okta', 'https://www.okta.com/company/careers/', 'Remoto Costa Rica'), ('Elastic', 'https://www.elastic.co/careers', 'Remoto Costa Rica'), ('Red Hat', 'https://www.redhat.com/en/jobs', 'San Jose'), ('Cloudera', 'https://www.cloudera.com/careers.html', 'San Jose'), ('DXC Technology', 'https://careers.dxc.com/', 'Heredia'), ('Genpact', 'https://www.genpact.com/careers', 'Heredia'), ('Cognizant', 'https://careers.cognizant.com/', 'Heredia'), ('Infosys', 'https://www.infosys.com/careers/', 'San Jose'), ('HCLTech', 'https://www.hcltech.com/careers', 'San Jose'), ('NTT DATA', 'https://careers.nttdata.com/', 'Heredia'), ('Capgemini', 'https://www.capgemini.com/careers/', 'San Jose'), ('Globant', 'https://career.globant.com/', 'San Jose'), ('Encora', 'https://careers.encora.com/', 'San Jose'), ('Publicis Sapient', 'https://careers.publicissapient.com/', 'San Jose'), ('Tek Experts', 'https://www.tek-experts.com/careers/', 'Heredia'), ('TransUnion', 'https://www.transunion.com/careers', 'Heredia'), ('Western Union', 'https://careers.westernunion.com/', 'San Jose'), ('Visa', 'https://corporate.visa.com/en/careers.html', 'San Jose'), ('American Express', 'https://www.americanexpress.com/en-us/careers/', 'San Jose'), ('JPMorgan Chase', 'https://careers.jpmorgan.com/', 'San Jose'), ('Scotiabank', 'https://jobs.scotiabank.com/', 'San Jose'), ('Davivienda', 'https://www.davivienda.com/', 'San Jose'), ('Banco Popular de Costa Rica', 'https://www.bancopopular.fi.cr/', 'San Jose'), ('Banco Promerica', 'https://www.promerica.fi.cr/', 'San Jose'), ('Banco Lafise', 'https://www.lafise.com/', 'San Jose'), ('Coopeservidores', 'https://www.coopeservidores.fi.cr/', 'San Jose'), ('Grupo Mutual', 'https://www.grupomutual.fi.cr/', 'Alajuela'), ('INS Costa Rica', 'https://www.grupoins.com/', 'San Jose'), ('ASSA Compania de Seguros', 'https://www.assanet.com/', 'San Jose'), ('Pan-American Life (PALIG)', 'https://www.palig.com/careers', 'San Jose'), ('Sagicor Costa Rica', 'https://www.sagicor.com/en-CR/', 'San Jose'), ('Uber', 'https://www.uber.com/global/en/careers/', 'Heredia'), ('DiDi', 'https://careers.didiglobal.com/', 'San Jose'), ('PedidosYa', 'https://careers.deliveryhero.com/', 'San Jose'), ('Delivery Hero', 'https://careers.deliveryhero.com/', 'San Jose'), ('Maersk', 'https://www.maersk.com/careers', 'San Jose'), ('FedEx', 'https://careers.fedex.com/', 'San Jose'), ('UPS', 'https://www.jobs-ups.com/', 'San Jose'), ('Expeditors', 'https://careers.expeditors.com/', 'San Jose'), ('Hellmann Worldwide Logistics', 'https://www.hellmann.com/en/career', 'San Jose'), ('Kuehne+Nagel', 'https://jobs.kuehne-nagel.com/', 'Heredia'), ('DP World', 'https://www.dpworld.com/careers', 'Limon'), ('APM Terminals', 'https://www.apmterminals.com/en/careers', 'Limon'), ('CMA CGM', 'https://www.cmacgm-group.com/en/talents/join-us', 'San Jose'), ('Dole', 'https://careers.dole.com/', 'Limon'), ('Unilever', 'https://careers.unilever.com/', 'San Jose'), ('Nestle', 'https://www.nestle.com/jobs', 'San Jose'), ('Mondelēz International', 'https://www.mondelezinternational.com/careers/', 'San Jose'), ('Kraft Heinz', 'https://careers.kraftheinz.com/', 'San Jose'), ('Colgate-Palmolive', 'https://jobs.colgate.com/', 'San Jose'), ('Reckitt', 'https://careers.reckitt.com/', 'San Jose'), ('Henkel', 'https://www.henkel.com/careers', 'San Jose'), ("L'Oreal", 'https://careers.loreal.com/', 'San Jose'), ('BAT', 'https://careers.bat.com/', 'Heredia'), ('Philip Morris International', 'https://www.pmi.com/careers', 'San Jose'), ('Heineken', 'https://careers.theheinekencompany.com/', 'San Jose'), ('Pernod Ricard', 'https://pernod-ricard.com/en/careers', 'San Jose'), ('Diageo', 'https://www.diageo.com/en/careers', 'San Jose'), ('Bimbo', 'https://www.grupobimbo.com/es/bolsa-de-trabajo', 'San Jose'), ('Sigma Alimentos', 'https://www.sigma-alimentos.com/careers/', 'San Jose'), ('Cargill Protein Latin America', 'https://careers.cargill.com/', 'Heredia'), ('Emerson', 'https://www.emerson.com/en-us/careers', 'San Jose'), ('Honeywell', 'https://careers.honeywell.com/', 'San Jose'), ('Siemens', 'https://jobs.siemens.com/', 'San Jose'), ('ABB', 'https://careers.abb/global/en', 'San Jose'), ('Eaton', 'https://jobs.eaton.com/', 'San Jose'), ('Embraer', 'https://embraer.com/global/en/careers', 'San Jose'), ('Gensler', 'https://www.gensler.com/careers', 'San Jose'), ('AECOM', 'https://aecom.com/careers/', 'San Jose'), ('Jacobs', 'https://careers.jacobs.com/', 'San Jose'), ('Arcadis', 'https://careers.arcadis.com/', 'San Jose'), ('Autodesk', 'https://www.autodesk.com/careers', 'San Jose'), ('Motorola Solutions', 'https://www.motorolasolutions.com/en_us/about/careers.html', 'San Jose'), ('Ericsson', 'https://www.ericsson.com/en/careers', 'San Jose'), ('Nokia', 'https://www.nokia.com/about-us/careers/', 'San Jose'), ('Liberty Latin America', 'https://careers.lla.com/', 'San Jose'), ('Millicom Tigo', 'https://www.millicom.com/careers/', 'San Jose'), ('Veeam Software', 'https://careers.veeam.com/', 'San Jose'), ('Smith & Nephew', 'https://careers.smith-nephew.com/', 'Alajuela'), ('Zoetis', 'https://careers.zoetis.com/', 'San Jose'), ('Mastercard', 'https://careers.mastercard.com/', 'San Jose'), ('Kyndryl', 'https://www.kyndryl.com/us/en/careers', 'Heredia'), ('Salesforce', 'https://careers.salesforce.com/', 'San Jose'), ('Dell Technologies', 'https://jobs.dell.com/', 'Heredia'), ('HP Inc.', 'https://jobs.hp.com/', 'Heredia'), ('Schlumberger SLB', 'https://careers.slb.com/', 'San Jose'), ('Baker Hughes', 'https://careers.bakerhughes.com/', 'San Jose'), ('Prysmian Group', 'https://www.prysmiangroup.com/en/people-and-careers', 'Heredia'), ('Huntsman', 'https://www.huntsman.com/careers', 'Heredia'), ('Clorox', 'https://www.thecloroxcompany.com/careers/', 'San Jose'), ('The Walt Disney Company', 'https://www.disneycareers.com/', 'San Jose'), ('Sony', 'https://www.sonyjobs.com/', 'San Jose'), ('Samsung', 'https://www.samsung.com/us/careers/', 'San Jose'), ('LG Electronics', 'https://www.lg.com/global/careers', 'San Jose'), ('Grupo Nación', 'https://www.nacion.com/', 'San Jose'), ('Televisora de Costa Rica', 'https://www.teletica.com/', 'San Jose'), ('Universidad de Costa Rica', 'https://www.ucr.ac.cr/', 'San Jose'), ('Tecnológico de Costa Rica', 'https://www.tec.ac.cr/', 'Cartago'), ('Universidad Nacional', 'https://www.una.ac.cr/', 'Heredia')]
assert len(DIRECTORY) == 200 and len({x[0].casefold() for x in DIRECTORY}) == 200
TITLE_RE = re.compile(
    r"\b(recruit\w*|talent|sourc(er|ing)|hr|hrbp|human resources|human capital|"
    r"people (partner|operations|ops|business|team|experience|analytics|success|and culture|& culture)|"
    r"chief people|head of people|vp,? people|culture|employee (experience|relations)|"
    r"total rewards|compensation|benefits|payroll|workforce|onboarding|internal mobility|"
    r"learning (and|&) development|dei|diversity|inclusion|reclutamiento|recursos humanos|"
    r"gesti[oó]n del talento|capital humano)\b")
WORKDAY_TERMS = ["recruiter", "talent acquisition", "human resources", "people"]
# ---------------------------------------------------------------------------
UA = "job-radar/3.0 (+country-wide Costa Rica HR/TA radar)"
class LinkParser(HTMLParser):
    """Extract links without depending on fragile regular expressions."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self._href, self._text = [], None, []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []
    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href, self._text = None, []


def request(url, data=None, accept="application/json", timeout=30):
    headers = {"User-Agent": UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.8,es;q=0.7"}
    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, body, headers)
    return urllib.request.urlopen(req, timeout=timeout)


def http(url, data=None):
    with request(url, data) as response:
        return json.load(response)


def text(url, timeout=30):
    with request(url, accept="text/html,application/xhtml+xml,application/json;q=0.8,*/*;q=0.5", timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, "ignore"), response.geturl(), response.status


def detect(url, body=""):
    """Detect ATS using final URL plus page fingerprints and embedded links."""
    u = urlparse(url)
    host, parts = u.netloc.lower(), [x for x in u.path.split("/") if x]
    direct = [("myworkdayjobs.com", "workday"), ("taleo.net", "taleo"),
              ("oraclecloud.com", "oracle"), ("successfactors.com", "successfactors"),
              ("jobs2web.com", "successfactors")]
    for key, name in direct:
        if key in host:
            return name, url
    for key, name in [("greenhouse.io", "greenhouse"), ("lever.co", "lever"),
                      ("ashbyhq.com", "ashby"), ("smartrecruiters.com", "smartrecruiters"),
                      ("workable.com", "workable")]:
        if key in host and parts:
            if name == "greenhouse" and parts[0] in ("embed", "boards") and len(parts) > 1:
                return name, parts[1]
            if name == "smartrecruiters" and parts[0] == "company" and len(parts) > 1:
                return name, parts[1]
            return name, parts[0]
    if "icims.com" in host:
        return "icims", url
    if "recruitee.com" in host:
        return "recruitee", host.split(".")[0]
    low = html.unescape(body).lower()
    patterns = [
        (r'https?://[^"\'<> ]+\.myworkdayjobs\.com/[^"\'<> ]+', "workday"),
        (r'https?://[^"\'<> ]+\.taleo\.net/careersection/[^"\'<> ]+', "taleo"),
        (r'https?://[^"\'<> ]+\.oraclecloud\.com/[^"\'<> ]*/sites/[^"\'<> ]+', "oracle"),
        (r'https?://[^"\'<> ]+(?:successfactors\.com|jobs2web\.com)/[^"\'<> ]+', "successfactors"),
        (r'https?://(?:boards|job-boards)\.greenhouse\.io/([^/"\'<>?# ]+)', "greenhouse"),
        (r'https?://jobs\.lever\.co/([^/"\'<>?# ]+)', "lever"),
        (r'https?://jobs\.ashbyhq\.com/([^/"\'<>?# ]+)', "ashby"),
        (r'https?://jobs\.smartrecruiters\.com/([^/"\'<>?# ]+)', "smartrecruiters"),
        (r'https?://apply\.workable\.com/([^/"\'<>?# ]+)', "workable"),
        (r'https?://([^./"\'<> ]+)\.recruitee\.com', "recruitee"),
        (r'https?://[^"\'<> ]+\.icims\.com/jobs/[^"\'<> ]*', "icims")]
    for pattern, name in patterns:
        m = re.search(pattern, low, re.I)
        if m:
            value = m.group(1) if m.lastindex else html.unescape(m.group(0))
            return name, value.rstrip("/.,)")
    return None, url


def locale_variants(url):
    """Return ordered Costa Rica language variants without duplicating requests."""
    u = urlparse(url)
    base_path = u.path.rstrip("/")
    locale_re = re.compile(r"/(?:cr/(?:en|es)|(?:en|es)/cr|cr-(?:en|es)|(?:en|es)-cr)(?=/|$)", re.I)
    stripped = locale_re.sub("", base_path).rstrip("/")
    paths = [base_path, f"{stripped}/cr/en", f"{stripped}/cr/es",
             f"{stripped}/en/cr", f"{stripped}/es/cr",
             f"{stripped}/en-cr", f"{stripped}/es-cr",
             f"{stripped}/cr-en", f"{stripped}/cr-es"]
    out=[]
    for path in paths:
        candidate=urlunparse((u.scheme or "https",u.netloc,path or "/",u.params,u.query,u.fragment))
        if candidate not in out: out.append(candidate)
    return out


def discover_one(url):
    body, final_url, status = text(url, timeout=20)
    ats, token = detect(final_url, body)
    if ats:
        return ats, token, final_url, status
    parser = LinkParser(); parser.feed(body[:1500000])
    candidates=[]
    for href, label in parser.links:
        if not href: continue
        absolute=urljoin(final_url, href)
        a,t=detect(absolute)
        if a: candidates.append((a,t,absolute))
    if candidates:
        candidates.sort(key=lambda x:("/job/" in x[2].lower(),len(x[2])))
        a,t,found_url=candidates[0]
        return a,t,found_url,status
    return None, final_url, final_url, status


def discover(url):
    """Try canonical URL and CR language variants, stopping at first detected ATS."""
    first_accessible=None
    errors=[]
    for candidate in locale_variants(url):
        try:
            result=discover_one(candidate)
            if first_accessible is None: first_accessible=result
            if result[0]:
                return (*result, candidate)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            errors.append(f"{candidate}: {type(exc).__name__}")
    if first_accessible:
        return (*first_accessible, url)
    raise urllib.error.URLError("; ".join(errors[:3]) or "No accessible variant")

def fetch(ats, tok, only_cr):
    if ats == "auto":
        ats, tok = detect(tok)
        if not ats:
            raise ValueError("ATS no soportado o no detectado")
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
    if ats == "successfactors":
        # SuccessFactors has tenant-specific career pages. We paginate the public
        # HTML and parse job links semantically; no private API or credentials.
        base = tok
        found, seen_pages = {}, set()
        for term in terms(only_cr):
            for startrow in range(0, 500, 25):
                sep = "&" if "?" in base else "?"
                url = f"{base}{sep}q={quote(term)}&startrow={startrow}"
                page, final, _ = text(url)
                signature = hash(page)
                if signature in seen_pages:
                    break
                seen_pages.add(signature)
                parser = LinkParser(); parser.feed(page)
                added = 0
                from urllib.parse import urljoin
                for href, label in parser.links:
                    absolute = urljoin(final, href)
                    if not re.search(r"/(?:job|jobdetail|careersection)/", absolute, re.I):
                        continue
                    title = re.sub(r"\s+", " ", label).strip()
                    if not title or len(title) < 4:
                        continue
                    jid = re.search(r"(?:job|jobid|jobId|jobReqId)[=/\-](\d+)", absolute, re.I)
                    key = jid.group(1) if jid else absolute
                    context_at = page.lower().find(href.lower())
                    context = re.sub(r"<[^>]+>", " ", page[max(0, context_at-500):context_at+1200])
                    context = html.unescape(re.sub(r"\s+", " ", context))
                    found[key] = dict(title=title, loc=context[:500], url=absolute, wt="")
                    added += 1
                if added == 0:
                    break
                time.sleep(0.2)
        return list(found.values())
    if ats == "icims":
        base = f"https://{urlparse(tok).netloc}"
        found = {}
        for term in terms(only_cr):
            for pg in range(0, 40):
                page, final, _ = text(f"{base}/jobs/search?ss=1&searchKeyword={quote(term)}&in_iframe=1&pr={pg}")
                parser = LinkParser(); parser.feed(page)
                added = 0
                from urllib.parse import urljoin
                for href, label in parser.links:
                    m = re.search(r"/jobs/(\d+)/", href)
                    if not m:
                        continue
                    title = re.sub(r"\s+", " ", label).strip()
                    if not title:
                        continue
                    at = page.find(href)
                    context = re.sub(r"<[^>]+>", " ", page[at:at + 1800])
                    context = html.unescape(re.sub(r"\s+", " ", context)).strip()
                    found[m.group(1)] = dict(title=title, wt="", url=urljoin(final, href), loc=context[:600])
                    added += 1
                if not added:
                    break
                time.sleep(0.2)
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

CR_RX = re.compile(r"costa\s*rica|\bcri\b|\bcr(?:i)?[-, ]|san\s+jos[eé](?!\s*,\s*(?:california|ca\b))|heredia|bel[eé]n|barreal|lagunilla|ulloa|alajuela|el\s+coyol|grecia|cartago|la\s+uni[oó]n|tres\s+r[ií]os|escaz[uú]|santa\s+ana|lindora|pavas|la\s+uruca|sabana|curridabat|moravia|guadalupe|desamparados|lim[oó]n|puntarenas|guanacaste|liberia|p[eé]rez\s+zeled[oó]n|san\s+carlos|ciudad\s+quesada", re.I)
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
#dirl a{position:relative;padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:var(--sur);color:inherit;text-decoration:none}#dirl a:hover{border-color:var(--remote)} #dirl a.detected:after,#dirl a.accessible:after,#dirl a.unsupported:after,#dirl a.error:after{content:"";position:absolute;right:8px;top:12px;width:7px;height:7px;border-radius:50%;background:var(--remote)}#dirl a.accessible:after{background:#d49b00}#dirl a.unsupported:after{background:#7b8791}#dirl a.error:after{background:var(--red)} .legend{display:flex;flex-wrap:wrap;gap:12px;margin:10px 0;color:var(--mut);font-size:12px}.legend i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px}
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
<details class=dir><summary>Directorio de carreras: __NDIR__ empresas</summary><div class=legend><span><i style="background:#0b7a5a"></i>ATS detectado</span><span><i style="background:#d49b00"></i>Página accesible</span><span><i style="background:#7b8791"></i>Sin conector</span><span><i style="background:#c8102e"></i>Error</span></div><div id=dirl></div></details>
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
$("stl").innerHTML=ST.map(x=>`<div class=st><span>${esc(x[0])}</span><span>${({ok:"Activa",detected:"ATS detectado",accessible:"Página accesible",unsupported:"Sin conector",error:"Con error"}[x[1]]||x[1])}</span><span>${esc(x[2])}</span></div>`).join("");
render();
</script></html>
"""

def build_sources():
    """Join configured connectors with every directory company, deduplicated."""
    sources = {(name.lower(), tok): (ats, tok, name, only_cr, "configured")
               for ats, tok, name, only_cr in COMPANIES}
    directory_state = {}
    explicit_names = {name.lower() for _, _, name, _ in COMPANIES}

    def probe(entry):
        name, url, province = entry
        try:
            ats, token, final, code, tested = discover(url)
            state = "detected" if ats else "accessible"
            detail = f"HTTP {code}" + (f" · {ats} · variante {tested}" if ats else " · accesible, ATS no detectado")
            return entry, ats, token, final, state, detail
        except Exception as exc:
            return entry, None, url, url, "error", type(exc).__name__ + ": " + str(exc)[:70]

    # Concurrent probes keep a country-wide directory practical.
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(probe, entry) for entry in DIRECTORY]
        for future in as_completed(futures):
            entry, ats, token, final, state, detail = future.result()
            name, url, province = entry
            directory_state[name] = [state, detail, final]
            if ats and name.lower() not in explicit_names:
                sources[(name.lower(), token)] = (ats, token, name, True, "directory")
    return list(sources.values()), directory_state


def main():
    root = pathlib.Path(__file__).parent
    sf = root / "seen.json"
    initial = not sf.exists()
    try:
        seen = json.loads(sf.read_text(encoding="utf-8")) if sf.exists() else {}
    except (ValueError, OSError):
        seen = {}
    if isinstance(seen, list):
        seen = {u: date.today().isoformat() for u in seen}

    today, rows, status = date.today(), [], []
    sources, directory_state = build_sources()
    print(f"[info] {len(DIRECTORY)} paginas comprobadas; {len(sources)} fuentes ATS para extraer")

    for ats, tok, name, only_cr, origin in sources:
        try:
            jobs = fetch(ats, tok, only_cr)
        except Exception as exc:
            message = type(exc).__name__ + ": " + str(exc)[:80]
            print(f"[skip] {name}: {message}")
            status.append([name, "error", message])
            continue
        kept = 0
        for j in jobs:
            title = re.sub(r"\s+", " ", str(j.get("title") or "")).strip()
            loc = re.sub(r"\s+", " ", str(j.get("loc") or "")).strip()
            url = str(j.get("url") or "").strip()
            if not title or not url or not TITLE_RE.search(title.lower()):
                continue
            # Use all public signals, not only the location field.
            cr_signal = " ".join((loc, title, url))
            if (ONLY_COSTA_RICA or only_cr) and not is_cr(cr_signal):
                continue
            first = seen.setdefault(url, today.isoformat())
            try:
                age = (today - date.fromisoformat(first)).days
            except ValueError:
                seen[url], age = today.isoformat(), 0
            rows.append(dict(company=name, title=title, loc=loc or "Costa Rica (ubicación no detallada)", url=url,
                             mode=work_mode({"wt": j.get("wt", ""), "loc": loc, "title": title}),
                             region=region(cr_signal), new=(not initial and age <= 2)))
            kept += 1
        print(f"[ok] {name}: {kept} vacantes")
        status.append([name, "ok", f"{kept} vacantes HR/TA en Costa Rica" if kept else "sin vacantes HR/TA detectadas"])

    # Exact URL deduplication, then stable ordering.
    rows = list({r["url"]: r for r in rows}.values())
    rows.sort(key=lambda r: (not r["new"], r["company"].casefold(), r["title"].casefold()))
    sf.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")

    # Add live state to directory records without changing their visible grouping.
    directory_ui = []
    for name, url, province in DIRECTORY:
        state, detail, final = directory_state.get(name, ["error", "No comprobada", url])
        directory_ui.append([name, final or url, province, state, detail])
    template = TEMPLATE.replace('DIR.filter(c=>c[2]==p).map(c=>`<a href="${esc(c[1])}" target=_blank rel=noopener>${esc(c[0])}</a>`)',
        'DIR.filter(c=>c[2]==p).map(c=>`<a class="${esc(c[3]||\'\')}" title="${esc(c[4]||\'\')}" href="${esc(c[1])}" target=_blank rel=noopener>${esc(c[0])}</a>`)')
    page = template.replace("__DATA__", json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")) \
                   .replace("__DIR__", json.dumps(directory_ui, ensure_ascii=False)).replace("__NDIR__", str(len(DIRECTORY))) \
                   .replace("__STATUS__", json.dumps(status, ensure_ascii=False)).replace("__UPDATED__", today.strftime("%d/%m/%Y"))
    (root / "index.html").write_text(page, encoding="utf-8")
    print(f"Total: {len(rows)} -> index.html")

if __name__ == "__main__":
    main()
