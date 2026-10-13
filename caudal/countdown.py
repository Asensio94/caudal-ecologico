"""«¿Llegará a 2027?»: every water body with its status, deadline and exemptions.

Reads data/wfd/*.csv (written by `python -m caudal.cli wfd`), assesses each body with
outlook.py and renders docs/2027.html, plus docs/masas-2027.json for the search box.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from . import store
from .config import DOCS_DIR
from .logo import LOGO_SVG, favicon_link
from .outlook import VERDICTS, assess, flagged
from .web import ACCENT, ACCENT_DARK, COMMON_CSS, REPO, SIBLINGS
from .wfd import RBD_NAMES, match_code, read_csv

PAGE_URL = "https://asensio94.github.io/caudal-ecologico/2027.html"
DISCODATA_URL = "https://discodata.eea.europa.eu/"
BOE_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2023-3511"
CATEGORIES = {"RW": "Río", "LW": "Lago o embalse", "TW": "Transición", "CW": "Costera", "GW": "Subterránea"}
# Basins of the stations (data/stations.csv) and the districts their water bodies fall in.
STATION_RBD = {"jucar": ("ES080",), "guadiana": ("ES040",), "cantabrico": ("ES017", "ES018")}
ORDER = ["good", "by_2027", "beyond_natural", "beyond_other", "less_stringent", "unknown"]
REASONS = {"natural conditions": "condiciones naturales", "technical feasibility": "viabilidad técnica",
           "disproportionate cost": "coste desproporcionado", "new modification": "nueva modificación",
           "accidents": "accidente"}
JSON_FIELDS = ["code", "name", "rbd", "category", "ecological", "chemical", "quantitative", "verdict",
               "horizon", "source", "articles", "reasons", "station"]


def status_label(aspect: str, value: str) -> str:
    if not value:
        return ""
    if value == "Unknown":
        return "sin evaluar"
    if aspect == "ecological":
        return {"1": "muy bueno", "2": "bueno", "3": "moderado", "4": "deficiente", "5": "malo"}.get(value, value)
    return "bueno" if value == "2" else "no alcanza el bueno" if aspect == "chemical" else "malo"


def horizon_label(h: str) -> str:
    return {"": "—", ">2027": "después de 2027", "4(5)": "objetivo menos riguroso",
            "2015": "2015", "2021": "2021 o antes"}.get(h, h)


def station_links() -> dict[str, str]:
    """EU code of a water body → id of the gauging station that measures it on index.html."""
    out = {}
    known = {b["code"] for b in read_csv("water_bodies.csv")}
    for s in store.load_stations():
        for rbd in STATION_RBD.get(s["basin"], ()):
            code = match_code(s["water_body_code"], rbd, known)
            if code:
                out.setdefault(code, s["station_id"])
                break
    return out


def bodies() -> list[dict]:
    """Every reported water body with its outlook, sorted by district and code."""
    exemptions: dict[str, list[dict]] = {}
    for e in read_csv("exemptions.csv"):
        exemptions.setdefault(e["code"], []).append(e)
    objectives = {o["code"]: o for o in read_csv("objectives.csv")}
    stations = station_links()
    out = []
    for b in read_csv("water_bodies.csv"):
        o = assess(b, exemptions.get(b["code"], []), objectives.get(b["code"]))
        out.append({**b, "outlook": o, "flagged": flagged(o), "station": stations.get(b["code"], ""),
                    "objective": objectives.get(b["code"]), "exemptions": exemptions.get(b["code"], [])})
    return sorted(out, key=lambda r: (r["rbd"], r["code"]))


def _json_row(b: dict) -> list:
    o = b["outlook"]
    return [b["code"], b["name"], b["rbd"], b["category"], b["ecological"], b["chemical"], b["quantitative"],
            o.verdict, o.horizon, o.horizon_source, o.articles, [REASONS.get(r, r) for r in o.reasons], b["station"]]


def write_json(rows: list[dict], generated: str) -> Path:
    doc = {"generated": generated, "cycle": "2022-2027", "fields": JSON_FIELDS,
           "districts": RBD_NAMES, "verdicts": VERDICTS, "bodies": [_json_row(b) for b in rows]}
    out = DOCS_DIR / "masas-2027.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out


CSS = f""":root{{--accent:{ACCENT};--accent-dark:{ACCENT_DARK};--good:#2f7a55;--by2027:#b7791f;
  --natural:#6b7280;--other:#b42318;--ls:#7c3aed;--gap:#9a948d}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--good:#62b88a;--by2027:#e3a64a;
  --natural:#a1a1aa;--other:#f47067;--ls:#b197fc;--gap:#6f6a64}}}}
:root[data-theme="dark"]{{--good:#62b88a;--by2027:#e3a64a;--natural:#a1a1aa;--other:#f47067;--ls:#b197fc;--gap:#6f6a64}}
main{{max-width:1100px;margin:0 auto;padding:0 16px}}
.nav{{margin:20px 0 0;font-size:.92rem}}
.wrap{{overflow-x:auto}}
table.points{{width:100%;border-collapse:collapse;font-size:.92rem}}
.points th{{text-align:left;font-weight:600;color:var(--muted);font-size:.8rem;text-transform:uppercase;
  letter-spacing:.03em;padding:8px 10px;border-bottom:2px solid var(--line)}}
.points td{{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
.points td.num,.points th.num{{text-align:right;font-family:var(--font-data);white-space:nowrap}}
.points .sub{{display:block;color:var(--muted);font-size:.82rem}}
.points tfoot td{{font-weight:600;border-top:2px solid var(--line)}}
.state{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:middle}}
.state.good{{background:var(--good)}}.state.by_2027{{background:var(--by2027)}}
.state.beyond_natural{{background:var(--natural)}}.state.beyond_other{{background:var(--other)}}
.state.less_stringent{{background:var(--ls)}}.state.unknown{{background:var(--gap)}}
.search{{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 12px}}
.search input,.search select{{font:inherit;font-size:.95rem;padding:7px 10px;border:1px solid var(--line);
  border-radius:8px;background:var(--paper);color:var(--ink)}}
.search input{{flex:1 1 260px}}
#count{{color:var(--muted);font-size:.85rem;margin:0 0 8px}}
.points tr:target td,.points tr.hit td{{background:color-mix(in srgb,var(--accent) 10%,transparent)}}
.legend{{color:var(--muted);font-size:.85rem;margin:8px 0 0}}
"""


def _summary_rows(rows: list[dict]) -> tuple[str, Counter]:
    by_rbd: dict[str, Counter] = {}
    for b in rows:
        by_rbd.setdefault(b["rbd"], Counter())[b["outlook"].verdict] += 1
    total = Counter()
    lines = []
    for rbd in sorted(by_rbd, key=lambda r: RBD_NAMES.get(r, r)):
        c = by_rbd[rbd]
        total += c
        n = sum(c.values())
        cells = "".join(f'<td class="num">{c[v]}</td>' for v in ORDER)
        good = c["good"] / n * 100 if n else 0
        lines.append(f'<tr><td><b>{escape(RBD_NAMES.get(rbd, rbd))}</b><span class="sub">{rbd}</span></td>'
                     f'<td class="num">{n}</td>{cells}<td class="num">{good:.0f} %</td></tr>')
    return "\n".join(lines), total


def render() -> Path:
    rows = bodies()
    write_json(rows, datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%MZ"))
    summary, total = _summary_rows(rows)
    n = len(rows)
    short = n - total["good"] - total["unknown"]
    beyond = total["beyond_natural"] + total["beyond_other"]
    reported = sorted({b["reported"] for b in rows if b["reported"]})
    boe = sum(1 for b in rows if b["objective"])
    differ = sum(1 for b in rows if b["outlook"].sources_differ)
    siblings = "\n".join(
        f'    <li{" aria-current=\"page\"" if slug == "caudal-ecologico" else ""}>'
        f'<a href="https://asensio94.github.io/{slug}/">{name}</a></li>' for slug, name in SIBLINGS)
    heads = "".join(f'<th class="num"><span class="state {v}"></span>{VERDICTS[v]}</th>' for v in ORDER)
    totals = "".join(f'<td class="num">{total[v]}</td>' for v in ORDER)
    options = "\n".join(f'      <option value="{k}">{escape(v)}</option>'
                        for k, v in sorted(RBD_NAMES.items(), key=lambda kv: kv[1]))
    verdict_options = "\n".join(f'      <option value="{v}">{VERDICTS[v]}</option>' for v in ORDER)

    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>¿Llegará a 2027?</title>
<meta name="description" content="Estado de cada masa de agua de España, su plazo para el buen estado y las excepciones de la Directiva Marco del Agua que se le aplican.">
{favicon_link(ACCENT, ACCENT_DARK)}
<style>
{COMMON_CSS}
{CSS}
</style>
</head>
<body>
<header class="site-header">
  <h1>{LOGO_SVG}¿Llegará a <span>2027</span>?</h1>
  <p class="lede">2027 es el último plazo de la Directiva Marco del Agua para que ríos, lagos, costas y acuíferos
  estén en buen estado. Después solo cabe esperar a que la naturaleza se recupere o rebajar el objetivo.
  Esto es lo que España comunicó a la Agencia Europea de Medio Ambiente para cada masa de agua.</p>
  <div class="figures">
    <div><b>{n}</b><span>masas de agua superficiales y subterráneas</span></div>
    <div><b>{short}</b><span>aún no están en buen estado</span></div>
    <div><b>{beyond}</b><span>con plazo después de 2027</span></div>
    <div><b>{total["less_stringent"]}</b><span>con objetivos menos rigurosos</span></div>
  </div>
</header>
<main>
  <p class="nav"><a href="./">← Caudal diario frente al mínimo ecológico</a></p>

  <h2>Por demarcación</h2>
  <div class="wrap"><table class="points">
    <thead><tr><th>Demarcación</th><th class="num">Masas</th>{heads}<th class="num">En buen estado</th></tr></thead>
    <tbody>
{summary}
    </tbody>
    <tfoot><tr><td>España</td><td class="num">{n}</td>{totals}<td class="num">{total["good"] / n * 100 if n else 0:.0f} %</td></tr></tfoot>
  </table></div>

  <h2>Buscar una masa de agua</h2>
  <div class="search" role="search">
    <input id="q" type="search" placeholder="Nombre o código (p. ej. «Tajo», «ES080MSPF18-33»)" aria-label="Nombre o código">
    <select id="rbd" aria-label="Demarcación">
      <option value="">Todas las demarcaciones</option>
{options}
    </select>
    <select id="verdict" aria-label="Situación">
      <option value="">Todas las situaciones</option>
{verdict_options}
    </select>
  </div>
  <p id="count" aria-live="polite">Cargando…</p>
  <div class="wrap"><table class="points" id="results">
    <thead><tr><th>Masa de agua</th><th>Estado</th><th>Situación</th><th>Plazo</th><th>Excepciones</th></tr></thead>
    <tbody></tbody>
  </table></div>
  <p class="legend">Datos del tercer ciclo de planificación (2022–2027), entregados por España entre
  {_date_es(reported[0]) if reported else "—"} y {_date_es(reported[-1]) if reported else "—"}.
  <a href="masas-2027.json">Descargar todas las masas (JSON)</a>.</p>

  <section class="method">
    <h2>Cómo se calcula</h2>
    <ol>
      <li><b>El estado sale de lo que España comunicó a Europa.</b> Cada plan hidrológico se notifica a la
      Agencia Europea de Medio Ambiente (AEMA), que lo publica en su base WISE. De ahí salen, para cada masa, el
      estado ecológico (o el potencial, en masas muy modificadas o artificiales) y el químico. En las
      subterráneas, el cuantitativo y el químico. Una masa está en buen estado si todos sus aspectos lo están.</li>
      <li><b>El plazo, del BOE cuando lo hay.</b> La AEMA da el plazo por tramos («2021 o antes», «2027 o antes»,
      «después de 2027»). Para el Júcar, el Guadiana y los dos planes del Cantábrico se usa el año que fija el
      Real Decreto 35/2023 en el apéndice de objetivos medioambientales de cada plan ({boe} masas). Si los dos no
      coinciden, manda el BOE ({differ} masas con tramos distintos).</li>
      <li><b>Las excepciones, de las dos fuentes.</b> Se reúnen los artículos de la Directiva que se aplican a cada masa:
      4(4), prórroga del plazo; 4(5), objetivos menos rigurosos; 4(6), deterioro temporal por causas
      naturales o accidentes; y 4(7), nuevas modificaciones. En las prórrogas se guarda también el motivo
      alegado: viabilidad técnica, coste desproporcionado o condiciones naturales.</li>
      <li><b>Se clasifica cada masa.</b> Si todo está bien, «{VERDICTS["good"]}». Si algo falla y el plazo es 2027
      o antes, «{VERDICTS["by_2027"]}». Si va más allá de 2027 y el único motivo alegado son las condiciones
      naturales, «{VERDICTS["beyond_natural"]}», lo único que la Directiva admite tras 2027. Si se alega además, o
      solo, la viabilidad técnica o el coste, o no consta motivo, «{VERDICTS["beyond_other"]}». Si se ha
      rebajado el objetivo, «{VERDICTS["less_stringent"]}». Con algún aspecto sin evaluar y ninguno en mal estado,
      «{VERDICTS["unknown"]}».</li>
    </ol>
    <h3>Límites</h3>
    <ul>
      <li>«{VERDICTS["beyond_other"]}» describe lo que se comunicó, no es una infracción: la Comisión Europea evalúa
      los planes y puede haber justificaciones en la memoria del plan que la base europea no recoge.</li>
      <li>El estado es el que el plan dio por bueno al aprobarse (datos de 2019–2021 en la mayoría de cuencas),
      no el de hoy. Se actualizará con el próximo informe a Europa.</li>
      <li>Las fichas de masas que publica el Ministerio (MITECO) están tras una protección anti-robots y no se leen.</li>
      <li>De momento el año exacto del BOE se lee para Júcar, Guadiana y Cantábrico; en el resto de cuencas
      intercomunitarias se irá sumando. Las cuencas internas (Cataluña, Baleares, Canarias, Andalucía, Galicia)
      no están en ese real decreto y se quedan con los tramos de la AEMA.</li>
    </ul>
  </section>
</main>
<footer class="site-footer">
  <p class="principle">Datos públicos, reglas a la vista y cada cifra enlazada a su fuente. Indicios, no veredictos.</p>
  <p>Estado y excepciones: <a href="{DISCODATA_URL}">WISE WFD</a>, Agencia Europea de Medio Ambiente (CC BY 4.0).
  Plazos: <a href="{BOE_URL}">Real Decreto 35/2023</a>, BOE. Código en <a href="{REPO}">GitHub</a> (MIT);
  datos propios CC BY 4.0.</p>
  <nav aria-label="Proyectos hermanos"><ul class="siblings">
{siblings}
  </ul></nav>
</footer>
<script>
const CAT = {json.dumps(CATEGORIES, ensure_ascii=False)};
const ECO = {{"1":"muy bueno","2":"bueno","3":"moderado","4":"deficiente","5":"malo","Unknown":"sin evaluar"}};
const BIN = {{"2":"bueno","3":"malo","Unknown":"sin evaluar"}};
const HOR = {{"":"—",">2027":"después de 2027","4(5)":"objetivo menos riguroso","2021":"2021 o antes"}};
const MAX = 200;
let data = null;
const esc = s => String(s).replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}})[c]);
const fold = s => s.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
function row(b, hit) {{
  const [code, name, rbd, cat, eco, chem, quant, verdict, horizon, source, arts, reasons, station] = b;
  const status = cat === 'GW'
    ? `cuantitativo ${{BIN[quant] || '—'}}<span class="sub">químico ${{BIN[chem] || '—'}}</span>`
    : `ecológico ${{ECO[eco] || '—'}}<span class="sub">químico ${{chem === '3' ? 'no alcanza el bueno' : BIN[chem] || '—'}}</span>`;
  const st = station ? `<span class="sub"><a href="./#${{esc(station)}}">Caudal diario</a></span>` : '';
  const why = reasons.length ? `<span class="sub">${{esc(reasons.join(', '))}}</span>` : '';
  return `<tr id="${{esc(code)}}"${{hit ? ' class="hit"' : ''}}><td><b>${{esc(name || code)}}</b>` +
    `<span class="sub">${{esc(code)}} · ${{CAT[cat] || cat}} · ${{esc(data.districts[rbd] || rbd)}}</span>${{st}}</td>` +
    `<td>${{status}}</td><td><span class="state ${{verdict}}"></span>${{data.verdicts[verdict]}}</td>` +
    `<td>${{HOR[horizon] ?? horizon}}<span class="sub">${{source === 'boe' ? 'BOE' : 'AEMA'}}</span></td>` +
    `<td>${{arts.length ? arts.map(a => 'art. ' + a).join(', ') : '—'}}${{why}}</td></tr>`;
}}
function draw() {{
  const q = fold(document.getElementById('q').value.trim());
  const rbd = document.getElementById('rbd').value, verdict = document.getElementById('verdict').value;
  const hash = decodeURIComponent(location.hash.slice(1));
  const found = data.bodies.filter(b => (!rbd || b[2] === rbd) && (!verdict || b[7] === verdict) &&
    (!q || fold(b[0]).includes(q) || fold(b[1]).includes(q)));
  document.querySelector('#results tbody').innerHTML = found.slice(0, MAX).map(b => row(b, b[0] === hash)).join('');
  document.getElementById('count').textContent = found.length > MAX
    ? `${{found.length}} masas; se muestran las ${{MAX}} primeras. Afina la búsqueda.`
    : `${{found.length}} ${{found.length === 1 ? 'masa' : 'masas'}}.`;
}}
function fromHash() {{
  const hash = decodeURIComponent(location.hash.slice(1));
  if (!hash || !data.bodies.some(b => b[0] === hash)) return;
  document.getElementById('q').value = hash;
  document.getElementById('rbd').value = document.getElementById('verdict').value = '';
  draw();
  document.getElementById(hash)?.scrollIntoView({{block: 'center'}});
}}
fetch('masas-2027.json').then(r => r.json()).then(d => {{
  data = d;
  ['q', 'rbd', 'verdict'].forEach(id => document.getElementById(id).addEventListener('input', draw));
  window.addEventListener('hashchange', fromHash);
  draw(); fromHash();
}}).catch(() => {{ document.getElementById('count').textContent = 'No se han podido cargar las masas.'; }});
</script>
</body>
</html>
"""
    out = DOCS_DIR / "2027.html"
    out.write_text(html, encoding="utf-8")
    return out


MONTHS = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()


def _date_es(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"el {int(d)} de {MONTHS[int(m) - 1]} de {y}"
