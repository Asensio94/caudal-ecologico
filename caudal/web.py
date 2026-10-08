"""The published page: one self-contained HTML file, Spanish text, shared sibling style."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from . import store
from .compliance import DayResult, Status, episodes, evaluate
from .config import DOCS_DIR, TOLERANCE
from .logo import LOGO_SVG, favicon_link

ACCENT, ACCENT_DARK = "#007c91", "#4fc7d9"
WINDOW_DAYS = 30
COMMON_CSS = (Path(__file__).parent / "common.css").read_text(encoding="utf-8")
SAIH_JUCAR = "https://saih.chj.es/mapa-aforos"
REPO = "https://github.com/Asensio94/caudal-ecologico"

SIBLINGS = [
    ("observatorio-alegaciones", "Observatorio de alegaciones"), ("vigia-incendios", "Vigía de incendios"),
    ("centinela-natura", "Centinela Natura"), ("vigilancia-humedales", "Vigilancia de humedales"),
    ("sub-nocte", "Sub Nocte"), ("riesgo-tendidos-aves", "Riesgo de tendidos para aves"),
    ("grafo-promotores", "Grafo de promotores"), ("cartera-cotizadas", "Cartera de las cotizadas"),
    ("cuaderno-campo", "Cuaderno de campo"), ("caudal-ecologico", "Caudal ecológico"),
]
MONTHS = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()

CSS = f""":root{{--accent:{ACCENT};--accent-dark:{ACCENT_DARK};--below:#b42318;--ok:#2f7a55;--gap:#9a948d}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--below:#f47067;--ok:#62b88a;--gap:#6f6a64}}}}
:root[data-theme="dark"]{{--below:#f47067;--ok:#62b88a;--gap:#6f6a64}}
main{{max-width:1100px;margin:0 auto;padding:0 16px}}
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
.spark .min{{stroke:var(--ink);stroke-dasharray:3 2;stroke-width:1;fill:none;opacity:.6}}
.spark .q{{stroke:var(--accent);stroke-width:1.6;fill:none}}
.spark .bd{{fill:var(--below);opacity:.25}}
tr[hidden]{{display:none}}
.legend{{color:var(--muted);font-size:.85rem;margin:8px 0 0}}
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
    rows = []
    for s in store.load_stations():
        series = store.flow_series(s["station_id"])
        window = {start + timedelta(days=i): series.get(start + timedelta(days=i)) for i in range(WINDOW_DAYS)}
        results = evaluate(window, reqs.get(s["station_id"], []), tolerance=TOLERANCE)
        latest = next((r for r in reversed(results) if r.flow is not None), None)
        eps = episodes(results)
        ongoing = eps[-1] if eps and latest and latest.status is Status.BELOW and eps[-1].end == latest.day else None
        rows.append({"station": s, "results": results, "latest": latest,
                     "below_days": sum(r.status is Status.BELOW for r in results),
                     "deficit": sum(r.deficit_hm3 for r in results), "ongoing": ongoing})
    order = {Status.BELOW: 0, Status.OK: 2, Status.NO_DATA: 1, Status.NO_RULE: 3}
    rows.sort(key=lambda r: (order[r["latest"].status] if r["latest"] else 1, -(r["below_days"]), r["station"]["name"]))
    return rows, start


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
        f'<tr data-status="{status}"><td><span class="state {status}" title="{label}"></span>'
        f'<b>{escape(s["name"])}</b><span class="sub">Río {escape(s["river"])} · ROEA {s["roea"]}</span></td>'
        f'<td>{escape(s["water_body_name"])}<span class="sub">Masa {s["water_body_code"]}{protected}</span></td>'
        f'<td class="num {status}"><b>{q}</b><span class="sub">{pct}</span></td>'
        f'<td class="num">{qmin}</td>'
        f'<td class="num">{r["below_days"]}{ongoing}</td>'
        f'<td class="num">{_fmt(r["deficit"], 3)}</td>'
        f'<td>{_sparkline(r["results"], start)}</td></tr>'
    )


def render(today: date | None = None) -> Path:
    now = datetime.now(ZoneInfo("Europe/Madrid"))
    today = today or now.date()
    rows, start = build_rows(today)
    last = today - timedelta(days=1)
    n_below_now = sum(1 for r in rows if r["latest"] and r["latest"].status is Status.BELOW)
    n_any = sum(1 for r in rows if r["below_days"])
    deficit = sum(r["deficit"] for r in rows)
    month = MONTHS[last.month - 1]
    siblings = "\n".join(
        f'    <li{" aria-current=\"page\"" if slug == "caudal-ecologico" else ""}>'
        f'<a href="https://asensio94.github.io/{slug}/">{name}</a></li>' for slug, name in SIBLINGS)

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
    <div><b>{len(rows)}</b><span>puntos de control (Júcar)</span></div>
    <div><b>{n_below_now}</b><span>por debajo del mínimo el último día con datos</span></div>
    <div><b>{n_any}</b><span>con algún día por debajo en {WINDOW_DAYS} días</span></div>
    <div><b>{_fmt(deficit, 2)}</b><span>hm³ que faltaron para llegar al mínimo</span></div>
  </div>
</header>
<main>
  <div class="tools" role="group" aria-label="Filtrar">
    <button type="button" data-filter="all" aria-pressed="true">Todos</button>
    <button type="button" data-filter="below" aria-pressed="false">Por debajo ahora</button>
    <button type="button" data-filter="history" aria-pressed="false">Algún día por debajo</button>
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

  <section class="method">
    <h2>Cómo se calcula</h2>
    <ol>
      <li><b>El mínimo sale del BOE.</b> El Real Decreto 35/2023 aprobó los planes hidrológicos 2022–2027.
      Su anexo XI, apéndice 5, fija para cada masa de agua del Júcar un caudal mínimo por mes y nombra la
      estación de aforo que lo controla. El programa lee esas tablas directamente del BOE, sin copiarlas a mano.</li>
      <li><b>El caudal sale del SAIH.</b> El Sistema Automático de Información Hidrológica de la Confederación
      Hidrográfica del Júcar publica el caudal cada cinco minutos. Se juntan las lecturas de cada día (hora
      peninsular) y se calcula la media.</li>
      <li><b>Se comparan.</b> Un día queda «por debajo del mínimo» si su caudal medio es más de un
      {TOLERANCE * 100:.0f} % inferior al mínimo de ese mes. Ese margen absorbe el error de medida, que es mayor
      cuanto menos agua lleva el río.</li>
      <li><b>Se suma lo que faltó.</b> El déficit es la diferencia entre el mínimo y el caudal, multiplicada por
      los segundos del día: el volumen de agua que habría hecho falta, en hectómetros cúbicos.</li>
    </ol>
    <table class="params">
      <tr><th>Parámetro</th><th class="num">Valor</th></tr>
      <tr><td>Lecturas mínimas para dar un día por bueno</td><td class="num">75 %</td></tr>
      <tr><td>Margen por error de medida</td><td class="num">{TOLERANCE * 100:.0f} %</td></tr>
      <tr><td>Días sin datos dentro de un episodio que no lo cortan</td><td class="num">1</td></tr>
      <tr><td>Días que se vuelven a leer cada mañana</td><td class="num">7</td></tr>
    </table>
    <h3>Límites</h3>
    <ul>
      <li>Los datos del SAIH son provisionales: la confederación los revisa y publica los definitivos en el anuario
      de aforos meses después. Un día por debajo aquí es un indicio, no una infracción.</li>
      <li>Se aplica siempre el régimen ordinario. En sequía prolongada declarada, el plan permite un mínimo menor
      fuera de los espacios protegidos; aún no se cruza con las declaraciones de sequía.</li>
      <li>El plan mide el cumplimiento en conjunto por meses y años, no día a día; esta página enseña el detalle diario.</li>
      <li>Tres puntos de control del plan no tienen todavía aforo con datos públicos y no aparecen.</li>
      <li>De momento solo la demarcación del Júcar; el resto de cuencas se irá sumando.</li>
    </ul>
  </section>
</main>
<footer class="site-footer">
  <p class="principle">Datos públicos, reglas a la vista y cada cifra enlazada a su fuente. Indicios, no veredictos.</p>
  <p>Caudales: <a href="{SAIH_JUCAR}">SAIH Júcar</a>, Confederación Hidrográfica del Júcar. Mínimos:
  <a href="https://www.boe.es/buscar/act.php?id=BOE-A-2023-3511">Real Decreto 35/2023</a>, BOE. Código en
  <a href="{REPO}">GitHub</a> (MIT); datos propios CC BY 4.0.</p>
  <nav aria-label="Proyectos hermanos"><ul class="siblings">
{siblings}
  </ul></nav>
</footer>
<script>
document.querySelectorAll('.tools button').forEach(b => b.addEventListener('click', () => {{
  document.querySelectorAll('.tools button').forEach(o => o.setAttribute('aria-pressed', o === b));
  const f = b.dataset.filter;
  document.querySelectorAll('.points tbody tr').forEach(tr => {{
    const below = tr.dataset.status === 'below';
    const history = tr.children[4].textContent.trim()[0] !== '0';
    tr.hidden = f === 'below' ? !below : f === 'history' ? !history : false;
  }});
}}));
</script>
</body>
</html>
"""
    out = DOCS_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    return out
