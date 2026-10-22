"""The published page: one self-contained HTML file, Spanish text, shared sibling style."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from . import context, store
from .explain import method_html, sources_html
from .compliance import DayResult, Status, episodes, evaluate
from .config import DOCS_DIR, TOLERANCE
from .logo import LOGO_SVG, favicon_link
from .sources.wise import FLOW_PRESSURES

ACCENT, ACCENT_DARK = "#007c91", "#4fc7d9"
WINDOW_DAYS = 30
COMMON_CSS = (Path(__file__).parent / "common.css").read_text(encoding="utf-8")
SAIH_JUCAR = "https://saih.chj.es/mapa-aforos"
SIRA_GUADIANA = "https://siraguadiana.com/"
SAIH_CANTABRICO = "https://visor.saichcantabrico.es/"
SAIH_GUADALQUIVIR = "https://www.chguadalquivir.es/saih/"
BASINS = {"jucar": "Júcar", "guadiana": "Guadiana", "cantabrico": "Cantábrico", "guadalquivir": "Guadalquivir"}
REPO = "https://github.com/Asensio94/caudal-ecologico"

# Common footer of the Terra Aperta projects: a link back to the hub, then the twelve projects in
# the hub's menu order. This project's own entry is plain text marked with aria-current.
HUB = "https://asensio94.github.io/terra-aperta/"
SIBLINGS = [
    ("sub-nocte", "Sub Nocte"), ("vigia-incendios", "Vigía de incendios"),
    ("centinela-natura", "Centinela Natura"), ("estado-iba", "Estado de las IBA"),
    ("riesgo-tendidos-aves", "Riesgo de tendidos para aves"),
    ("observatorio-alegaciones", "Observatorio de alegaciones"), ("grafo-promotores", "Grafo de promotores"),
    ("vigilancia-humedales", "Vigilancia de humedales"), ("caudal-ecologico", "Caudal ecológico"),
    ("acuiferos-francia", "Acuíferos de Francia"), ("depuracion-y-bano", "Depuración y baño"),
    ("zona-inundable", "Construir en zona inundable"),
]
MONTHS = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()

CSS = f""":root{{--accent:{ACCENT};--accent-dark:{ACCENT_DARK};--below:#b42318;--ok:#2f7a55;--gap:#9a948d}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--below:#f47067;--ok:#62b88a;--gap:#6f6a64}}}}
:root[data-theme="dark"]{{--below:#f47067;--ok:#62b88a;--gap:#6f6a64}}
main{{max-width:1100px;margin:0 auto;padding:0 16px}}
.site-header .note{{margin:0;max-width:72ch}}
.nav{{margin:20px 0 0;font-size:.92rem}}
tr:target td{{background:color-mix(in srgb,var(--accent) 10%,transparent)}}
.tools{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:24px 0 12px}}
.tools button{{font:inherit;font-size:.9rem;padding:6px 12px;border:1px solid var(--line);border-radius:999px;
  background:var(--paper);color:var(--ink);cursor:pointer}}
.tools button[aria-pressed="true"]{{background:var(--accent);border-color:var(--accent);color:var(--paper)}}
.wrap{{overflow-x:auto}}
table.points{{width:100%;border-collapse:collapse;font-size:.92rem}}
.points th{{text-align:left;font-weight:600;color:var(--muted);font-size:.8rem;text-transform:uppercase;
  letter-spacing:.03em;padding:8px 10px;border-bottom:2px solid var(--line)}}
.points td{{padding:10px;border-bottom:1px solid var(--line);vertical-align:middle}}
.points td.num,.points th.num{{text-align:right;font-family:var(--font-data);white-space:nowrap}}
.points .sub{{display:block;color:var(--muted);font-size:.82rem}}
.state{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:middle}}
.state.below{{background:var(--below)}}.state.ok{{background:var(--ok)}}.state.no_data,.state.no_rule{{background:var(--gap)}}
td.below b{{color:var(--below)}}
svg.spark{{width:180px;max-width:none;height:36px;display:block}}
.points td:last-child{{min-width:190px}}
.siblings li[aria-current]{{color:var(--ink);font-weight:600}}
.site-footer .hub{{margin:0;font-weight:600}}
.spark .min{{stroke:var(--ink);stroke-dasharray:3 2;stroke-width:1;fill:none;opacity:.6}}
.spark .q{{stroke:var(--accent);stroke-width:1.6;fill:none}}
.spark .bd{{fill:var(--below);opacity:.25}}
tr[hidden]{{display:none}}
.legend{{color:var(--muted);font-size:.85rem;margin:8px 0 0}}
.points .note{{display:block;color:var(--muted);font-size:.78rem;max-width:42ch;margin-top:2px}}
.points .sub a,.points .note a{{color:inherit}}
.points .ctx{{display:block;font-size:.78rem;max-width:42ch;margin-top:4px}}
.points .ctx b{{color:var(--below);font-weight:600}}
.method details{{margin:6px 0;max-width:72ch}}
.method summary{{cursor:pointer;font-weight:600}}
.method details ul{{font-size:.9rem;margin:6px 0 12px}}
"""


def _fmt(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "—"
    s = f"{x:,.{digits}f}"
    return s.replace(",", " ").replace(".", ",").replace(" ", ".")


def _sparkline(results: list[DayResult], start: date) -> str:
    """Daily flow (line) against the minimum (dashed), days below shaded. Log-free: clipped at 3× the minimum."""
    w, h = 180, 36
    mins = [r.minimum for r in results if r.minimum]
    top = max([*(r.flow for r in results if r.flow is not None), *mins, 0.001])
    top = min(top, 3 * max(mins)) if mins else top
    x = lambda d: (d - start).days * w / (WINDOW_DAYS - 1)      # noqa: E731
    y = lambda v: h - 2 - min(v, top) / top * (h - 4)          # noqa: E731
    shade = "".join(f'<rect class="bd" x="{x(r.day) - 3:.1f}" y="0" width="6" height="{h}"/>'
                    for r in results if r.status is Status.BELOW)

    def path(key):
        d, pen = [], "M"
        for r in results:
            v = getattr(r, key)
            if v is None:
                pen = "M"
                continue
            d.append(f"{pen}{x(r.day):.1f} {y(v):.1f}")
            pen = "L"
        return " ".join(d)
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" role="img" aria-label="Caudal de los últimos {WINDOW_DAYS} días">'
            f'{shade}<path class="min" d="{path("minimum")}"/><path class="q" d="{path("flow")}"/></svg>')


def build_rows(today: date) -> tuple[list[dict], date]:
    last = today - timedelta(days=1)
    start = last - timedelta(days=WINDOW_DAYS - 1)
    reqs = store.load_requirements()
    rows, refs, ctx = [], store.legal_refs(), context.load()
    for s in store.load_stations():
        series = store.flow_series(s["station_id"])
        window = {start + timedelta(days=i): series.get(start + timedelta(days=i)) for i in range(WINDOW_DAYS)}
        results = evaluate(window, reqs.get(s["station_id"], []), tolerance=TOLERANCE)
        latest = next((r for r in reversed(results) if r.flow is not None), None)
        eps = episodes(results)
        ongoing = eps[-1] if eps and latest and latest.status is Status.BELOW and eps[-1].end == latest.day else None
        rows.append({"station": s, "results": results, "latest": latest,
                     "below_days": sum(r.status is Status.BELOW for r in results),
                     "deficit": sum(r.deficit_hm3 for r in results), "ongoing": ongoing,
                     "ref": refs.get(s["station_id"], ("", "")), "context": ctx.get(s["station_id"])})
    order = {Status.BELOW: 0, Status.OK: 2, Status.NO_DATA: 1, Status.NO_RULE: 3}
    rows.sort(key=lambda r: (order[r["latest"].status] if r["latest"] else 1, -(r["below_days"]), r["station"]["name"]))
    return rows, start


SMALL_WORDS = {"de", "del", "la", "las", "los", "el", "y", "en"}


def _title(name: str) -> str:
    """'BAILÉN - GUARROMÁN - LINARES' → 'Bailén - Guarromán - Linares'; "L'ALCORA" → "l'Alcora"."""
    def word(w: str, first: bool) -> str:
        w = w.lower()
        if "'" in w:
            head, tail = w.split("'", 1)
            return f"{head}'{tail.capitalize()}"
        return w if w in SMALL_WORDS and not first else w.capitalize()
    return " ".join("-".join(word(p, i == 0 and j == 0) for j, p in enumerate(w.split("-")))
                    for i, w in enumerate(name.split()))


def _context_html(c: context.Context | None) -> str:
    """What the plan reports around the point: pressures on the river, the aquifer under it."""
    if c is None:
        return ""
    lines = []
    if c.river_body_code:
        p = [FLOW_PRESSURES[x] for x in c.flow_pressures]
        lines.append(f"Presiones sobre el caudal que señala el plan: {', '.join(p)}." if p
                     else "El plan no señala en esta masa presiones que resten caudal.")
    for a in c.aquifers:
        state = {"poor": "<b>mal estado cuantitativo</b>", "good": "buen estado cuantitativo"}.get(
            a["aquifer_status"], "estado cuantitativo desconocido")
        risk = ", en riesgo de no alcanzar el bueno" if a["aquifer_at_risk"] == "1" and a["aquifer_status"] != "good" else ""
        line = f"Acuífero {escape(_title(a['aquifer_name']))}: {state}{risk}."
        if a["level_trend_m_year"]:
            slope = float(a["level_trend_m_year"])
            move = "baja" if slope < 0 else "sube"
            n, falling = int(a["trend_piezometers"]), int(a["trend_falling"])
            years = a["trend_years"].replace("-", "–")
            who = (f"un solo piezómetro" if n == 1 else
                   f"mediana de {n} piezómetros; {falling} {'baja' if falling == 1 else 'bajan'} más de 10 cm al año")
            line += f" Nivel {move} {_fmt(abs(slope))} m al año ({years}, {who})."
        lines.append(line)
    return "".join(f'<span class="ctx">{x}</span>' for x in lines)


ROEA = ('<abbr title="Red Oficial de Estaciones de Aforo: el número que el Estado da a cada estación '
        'que mide el caudal de un río">ROEA</abbr>')


def _gauge_label(s: dict) -> str:
    basin = BASINS.get(s["basin"], s["basin"])
    return f'{basin} · {ROEA} {s["roea"]}' if s["roea"] else f'{basin} · {"señal SAIH" if s["source"] == "saih-guadalquivir" else "estación"} {escape(s["source_id"])}'


def _row_html(r: dict, start: date) -> str:
    s, latest = r["station"], r["latest"]
    status = latest.status.value if latest else "no_data"
    label = {"below": "Por debajo del mínimo", "ok": "Por encima del mínimo",
             "no_data": "Sin datos suficientes", "no_rule": "Sin mínimo ese mes"}[status]
    protected = ' <span class="badge">Espacio protegido</span>' if s["protected"] == "1" else ""
    ongoing = (f'<span class="sub">{r["ongoing"].length} {"día seguido" if r["ongoing"].length == 1 else "días seguidos"}</span>' if r["ongoing"] else "")
    q = _fmt(latest.flow) if latest else "—"
    qmin = _fmt(latest.minimum) if latest and latest.minimum is not None else "—"
    pct = f'{latest.ratio * 100:.0f} %' if latest and latest.ratio is not None else ""
    return (
        f'<tr id="{s["station_id"]}" data-status="{status}" data-basin="{s["basin"]}"><td><span class="state {status}" title="{label}"></span>'
        f'<b>{escape(s["name"])}</b><span class="sub">Río {escape(s["river"])} · {_gauge_label(s)}</span></td>'
        f'<td>{escape(s["water_body_name"])}<span class="sub">{"Masa " + s["water_body_code"] if s["water_body_code"] else "Punto de control del plan"}{protected}</span>'
        f'<span class="sub"><a href="{escape(r["ref"][1])}">{escape(r["ref"][0])}</a></span>'
        f'<span class="note">{escape(s.get("note") or "")}</span>{_context_html(r["context"])}</td>'
        f'<td class="num {status}"><b>{q}</b><span class="sub">{pct}</span></td>'
        f'<td class="num">{qmin}</td>'
        f'<td class="num">{r["below_days"]}{ongoing}</td>'
        f'<td class="num">{_fmt(r["deficit"], 3)}</td>'
        f'<td>{_sparkline(r["results"], start)}</td></tr>'
    )


def _context_counts(rows: list[dict]) -> dict[str, int]:
    cs = [r["context"] for r in rows if r["context"]]
    below = [r["context"] for r in rows if r["context"] and r["below_days"]]
    poor = lambda c: any(a["aquifer_status"] == "poor" for a in c.aquifers)          # noqa: E731
    pressured = lambda c: bool(c.flow_pressures)                                      # noqa: E731
    return {"stations": len(cs), "rivers": sum(bool(c.river_body_code) for c in cs),
            "pressured": sum(map(pressured, cs)), "poor": sum(map(poor, cs)),
            "trend": sum(any(a["level_trend_m_year"] for a in c.aquifers) for c in cs),
            "below": len(below), "below_pressured": sum(map(pressured, below)), "below_poor": sum(map(poor, below)),
            "below_either": sum(pressured(c) or poor(c) for c in below)}


def render(today: date | None = None) -> Path:
    now = datetime.now(ZoneInfo("Europe/Madrid"))
    today = today or now.date()
    rows, start = build_rows(today)
    last = today - timedelta(days=1)
    n_below_now = sum(1 for r in rows if r["latest"] and r["latest"].status is Status.BELOW)
    n_any = sum(1 for r in rows if r["below_days"])
    deficit = sum(r["deficit"] for r in rows)
    month = MONTHS[last.month - 1]
    links = {"jucar": SAIH_JUCAR, "guadiana": SIRA_GUADIANA, "cantabrico": SAIH_CANTABRICO,
             "guadalquivir": SAIH_GUADALQUIVIR}
    compared = {b: sum(r["station"]["basin"] == b for r in rows) for b in BASINS}
    excluded: dict[str, list[str]] = {}
    for x in store.load_excluded():
        excluded.setdefault(x["basin"], []).append(x["reason"])
    method, sources = method_html(compared, excluded, links, _context_counts(rows)), sources_html(links)
    siblings = "\n".join(
        f'    <li aria-current="page">{name}</li>' if slug == "caudal-ecologico"
        else f'    <li><a href="https://asensio94.github.io/{slug}/">{name}</a></li>' for slug, name in SIBLINGS)

    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Caudal ecológico</title>
<meta name="description" content="Caudal diario de los ríos frente al mínimo ecológico que fijan los planes hidrológicos.">
{favicon_link(ACCENT, ACCENT_DARK)}
<style>
{COMMON_CSS}
{CSS}
</style>
</head>
<body>
<header class="site-header">
  <h1>{LOGO_SVG}Caudal <span>ecológico</span></h1>
  <p class="lede">Cada día, el caudal medio de los puntos de control frente al caudal mínimo que fija el plan
  hidrológico para ese río y ese mes. Datos del SAIH; mínimos leídos del BOE.</p>
  <div class="figures">
    <div><b>{len(rows)}</b><span>puntos de control ({", ".join(list(BASINS.values())[:-1])} y {list(BASINS.values())[-1]})</span></div>
    <div><b>{n_below_now}</b><span>por debajo del mínimo el último día con datos</span></div>
    <div><b>{n_any}</b><span>con algún día por debajo en {WINDOW_DAYS} días</span></div>
    <div><b>{_fmt(deficit, 2)}</b><span>hm³ que faltaron para llegar al mínimo</span></div>
  </div>
  <p class="note">Cubre {len(BASINS)} demarcaciones hidrográficas: {", ".join(list(BASINS.values())[:-1])} y
  {list(BASINS.values())[-1]}. Las otras de los planes estatales (Ebro, Segura, Tajo, Duero y Miño-Sil) todavía
  no dejan leer o reutilizar sus datos (<a href="#que-falta">qué falta</a>); las cuencas que gestionan las
  comunidades autónomas tienen planes propios y no entran. La tabla tiene los {len(rows)} puntos de control
  comparados. Solo los {n_any} que han estado por debajo del mínimo algún día de los últimos {WINDOW_DAYS} pasan
  como señal a <a href="https://asensio94.github.io/terra-aperta/">Terra Aperta</a> y Estado de las IBA.</p>
  <p class="note"><b>Caudal ecológico</b>: el caudal mínimo que el plan hidrológico obliga a dejar en cada
  río para que sigan vivos sus peces, sus plantas y sus riberas. <b>Datos provisionales</b>: las lecturas
  automáticas del SAIH (Sistema Automático de Información Hidrológica de cada confederación) tal como llegan;
  la confederación las revisa y publica las definitivas meses después, así que una cifra de aquí puede
  cambiar. <b>ROEA</b>: Red Oficial de Estaciones de Aforo, el número que el
  Estado da a cada estación que mide el caudal; en la tabla, cada punto va primero por su sitio y su río.</p>
</header>
<main>
  <p class="nav"><a href="2027.html">¿Llegará a 2027? Estado y plazo de cada masa de agua →</a></p>
  <div class="tools" role="group" aria-label="Filtrar">
    <button type="button" data-filter="all" aria-pressed="true">Todos</button>
    <button type="button" data-filter="below" aria-pressed="false">Por debajo ahora</button>
    <button type="button" data-filter="history" aria-pressed="false">Algún día por debajo</button>
  </div>
  <div class="tools" role="group" aria-label="Demarcación">
    <button type="button" data-basin="" aria-pressed="true">Todas</button>
{chr(10).join(f'    <button type="button" data-basin="{k}" aria-pressed="false">{v}</button>' for k, v in BASINS.items())}
  </div>
  <div class="wrap"><table class="points">
    <thead><tr><th>Punto de control</th><th>Masa de agua</th><th class="num">Caudal último día<br>m³/s</th>
    <th class="num">Mínimo de {month}<br>m³/s</th><th class="num">Días por debajo<br>({WINDOW_DAYS} d)</th>
    <th class="num">Déficit<br>hm³</th><th>Últimos {WINDOW_DAYS} días</th></tr></thead>
    <tbody>
{chr(10).join(_row_html(r, start) for r in rows)}
    </tbody>
  </table></div>
  <p class="legend">Del {start.day} de {MONTHS[start.month - 1]} al {last.day} de {month} de {last.year}.
  Línea continua: caudal medio diario; discontinua: mínimo; sombreado: día por debajo. Datos provisionales del SAIH,
  actualizados {now:%d/%m/%Y a las %H:%M} (hora peninsular).</p>

{method}
</main>
<footer class="site-footer">
  <p class="principle">Datos públicos, reglas a la vista y cada cifra enlazada a su fuente. Indicios, no veredictos.</p>
  {sources}
  <p>Código en
  <a href="{REPO}">GitHub</a> (MIT); datos propios CC BY 4.0.</p>
  <p class="hub"><a href="{HUB}">← Terra Aperta: todos los proyectos</a></p>
  <nav aria-label="Proyectos hermanos"><ul class="siblings">
{siblings}
  </ul></nav>
</footer>
<script>
const state = {{ filter: 'all', basin: '' }};
document.querySelectorAll('.tools button').forEach(b => b.addEventListener('click', () => {{
  b.parentElement.querySelectorAll('button').forEach(o => o.setAttribute('aria-pressed', o === b));
  if ('filter' in b.dataset) state.filter = b.dataset.filter; else state.basin = b.dataset.basin;
  document.querySelectorAll('.points tbody tr').forEach(tr => {{
    const below = tr.dataset.status === 'below';
    const history = tr.children[4].textContent.trim()[0] !== '0';
    const shown = state.filter === 'below' ? below : state.filter === 'history' ? history : true;
    tr.hidden = !shown || (state.basin !== '' && tr.dataset.basin !== state.basin);
  }});
}}));
</script>
</body>
</html>
"""
    out = DOCS_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    return out
