"""The French page: same layout and rules as the Spanish one, French text, French sources.

Three basins are compared: Adour-Garonne, which publishes its crisis flows (DCR) in an open
file with the gauge of each nodal point, and Loire-Bretagne and Rhône-Méditerranée, whose
tables are transcribed from the SDAGE (plan_fr.py). Everything else that stays out, and why,
is listed on the page itself (explain_fr.py).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from . import context, store
from .compliance import Status
from .config import DOCS_DIR
from .explain_fr import BASIN_NAMES, method_html, sources_html
from .i18n import FLOW_PRESSURES_FR, country_nav, d, long_date, n, p, t
from .logo import LOGO_SVG, favicon_link
from .sources import vigieau
from .web import ACCENT, ACCENT_DARK, COMMON_CSS, CSS, REPO, SIBLINGS, WINDOW_DAYS, _sparkline, build_rows

LANG = "fr"
PARIS = ZoneInfo("Europe/Paris")
CSS_FR = """.basins{margin:8px 0 0;color:var(--muted);font-size:.9rem}
.level{display:inline-block;font-size:.78rem;padding:1px 8px;border-radius:999px;border:1px solid var(--line)}
.level.crise,.level.alerte_renforcee{border-color:var(--below);color:var(--below)}
"""


def _latest_restriction(levels: dict[date, dict], today: date) -> dict | None:
    """The last level stored on or before today."""
    days = [x for x in levels if x <= today]
    return levels[max(days)] if days else None


def _restriction_html(r: dict | None) -> str:
    if r is None:
        return '<span class="sub">—</span>'
    if not r["level"]:
        return f'<span class="sub">{t(LANG, "no_order")}</span>'
    since = (f'<span class="sub">{t(LANG, "order_since", date=long_date(date.fromisoformat(r["order_from"]), LANG))}</span>'
             if r.get("order_from") else "")
    zone = f'<span class="note">{escape(r["zone_name"])}</span>' if r.get("zone_name") else ""
    label = t(LANG, f'level_{r["level"]}')
    link = f'<a href="{escape(r["order_url"])}">{label}</a>' if r.get("order_url") else label
    return f'<span class="level {r["level"]}">{link}</span>{since}{zone}'


def _context_html(c: context.Context | None) -> str:
    if c is None:
        return ""
    lines = []
    if c.river_body_code:
        ps = [FLOW_PRESSURES_FR[x] for x in c.flow_pressures]
        lines.append(t(LANG, "pressures", list=", ".join(ps)) if ps else t(LANG, "no_pressures"))
    # French groundwater bodies are stacked in layers (up to eight under one gauge): only those
    # in poor quantitative status are named, the others counted.
    for a in c.aquifers:
        if a["aquifer_status"] != "poor":
            continue
        risk = t(LANG, "aq_risk") if a["aquifer_at_risk"] == "1" else ""
        lines.append(t(LANG, "aquifer", name=escape(a["aquifer_name"]), state=t(LANG, "aq_poor"), risk=risk))
    others = sum(1 for a in c.aquifers if a["aquifer_status"] != "poor")
    if others:
        lines.append(t(LANG, "aq_others_1" if others == 1 else "aq_others_n", n=others))
    return "".join(f'<span class="ctx">{x}</span>' for x in lines)


def _row_html(r: dict, start: date, doe: str, alert: str, restriction: dict | None) -> str:
    s, latest = r["station"], r["latest"]
    status = latest.status.value if latest else "no_data"
    key = "st_below_validated" if status == "below" and not latest.provisional else f"st_{status}"
    label = t(LANG, key)
    ongoing = ""
    if r["ongoing"]:
        k = r["ongoing"].length
        ongoing = f'<span class="sub">{t(LANG, "consecutive_1" if k == 1 else "consecutive_n", n=k)}</span>'
    q = d(latest.flow, LANG, 3) if latest else "—"
    pct = p(latest.ratio, LANG) if latest and latest.ratio is not None else ""
    state = t(LANG, "provisional" if latest is None or latest.provisional else "validated")
    dcr = d(latest.minimum, LANG, 3) if latest and latest.minimum is not None else "—"
    level = (restriction or {}).get("level") or ""
    doe_line = (f'<span class="sub" title="{t(LANG, "doe_note")}">{t(LANG, "doe", doe=escape(doe.replace(".", ",")))}</span>'
                if doe else "")
    if alert:
        doe_line += (f'<span class="sub" title="{t(LANG, "dsa_note")}">'
                     f'{t(LANG, "dsa", dsa=escape(alert.replace(".", ",")))}</span>')
    return (
        f'<tr id="{s["station_id"]}" data-status="{status}" data-level="{level}" data-basin="{s["basin"]}">'
        f'<td><span class="state {status}" title="{label}"></span><b>{escape(s["name"])}</b>'
        f'<span class="sub">{escape(s["river"])} · {t(LANG, "station", code=escape(s["source_id"]))}</span></td>'
        f'<td>{escape(s["water_body_name"])}{doe_line}'
        f'<span class="sub"><a href="{escape(r["ref"][1])}">{escape(r["ref"][0])}</a></span>'
        f'<span class="note">{escape(s.get("note") or "")}</span>{_context_html(r["context"])}</td>'
        f'<td class="num {status}"><b>{q}</b><span class="sub">{pct}</span><span class="sub">{state}</span></td>'
        f'<td class="num">{dcr}</td>'
        f'<td class="num">{r["below_days"]}{ongoing}</td>'
        f'<td>{_restriction_html(restriction)}</td>'
        f'<td>{_sparkline(r["results"], start, t(LANG, "spark_label", days=WINDOW_DAYS))}</td></tr>'
    )


def render(today: date | None = None) -> Path:
    now = datetime.now(PARIS)
    today = today or now.date()
    rows, start = build_rows(today, "FR")
    last = today - timedelta(days=1)
    objectives, alerts, levels = store.objectives(), store.objectives("alert"), vigieau.load()
    restriction = {r["station"]["station_id"]: _latest_restriction(levels.get(r["station"]["station_id"], {}), today)
                   for r in rows}
    n_below_now = sum(1 for r in rows if r["latest"] and r["latest"].status is Status.BELOW)
    n_any = sum(1 for r in rows if r["below_days"])
    n_crisis = sum(1 for x in restriction.values() if x and x["level"] == "crise")
    first_level = min((day for lv in levels.values() for day in lv), default=None)
    compared = {b: sum(1 for r in rows if r["station"]["basin"] == b) for b in BASIN_NAMES}
    excluded = {b: [x["reason"] for x in store.load_excluded("FR") if x["basin"] == b] for b in BASIN_NAMES}
    method = method_html(compared, excluded, first_level)
    per_basin = " · ".join(f"{BASIN_NAMES[b]} {n(k, LANG)}" for b, k in compared.items())
    basin_buttons = "\n".join(
        f'    <button type="button" data-basin="{b}" aria-pressed="false">{name}</button>'
        for b, name in BASIN_NAMES.items())
    siblings = "\n".join(
        f'    <li{" aria-current=\"page\"" if slug == "caudal-ecologico" else ""}>'
        f'<a href="https://asensio94.github.io/{slug}/">{name}</a></li>' for slug, name in SIBLINGS)
    body = "\n".join(_row_html(r, start, objectives.get(r["station"]["station_id"], ""),
                               alerts.get(r["station"]["station_id"], ""),
                               restriction[r["station"]["station_id"]]) for r in rows)

    html = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{t(LANG, "title")}</title>
<meta name="description" content="{t(LANG, "description")}">
{favicon_link(ACCENT, ACCENT_DARK)}
<style>
{COMMON_CSS}
{CSS}
{CSS_FR}
</style>
</head>
<body>
<header class="site-header">
  {country_nav("FR")}
  <h1>{LOGO_SVG}{t(LANG, "h1")}</h1>
  <p class="lede">{t(LANG, "lede")}</p>
  <div class="figures">
    <div><b>{n(len(rows), LANG)}</b><span>{t(LANG, "fig_points")}</span></div>
    <div><b>{n(n_below_now, LANG)}</b><span>{t(LANG, "fig_below_now")}</span></div>
    <div><b>{n(n_any, LANG)}</b><span>{t(LANG, "fig_below_any", days=WINDOW_DAYS)}</span></div>
    <div><b>{n(n_crisis, LANG)}</b><span>{t(LANG, "fig_crisis")}</span></div>
  </div>
  <p class="basins">{t(LANG, "fig_per_basin", list=per_basin)}</p>
</header>
<main>
  <p class="nav"><a href="france-2027.html">{t(LANG, "nav_2027")}</a></p>
  <div class="tools" role="group" aria-label="{t(LANG, "filter")}">
    <button type="button" data-filter="all" aria-pressed="true">{t(LANG, "f_all")}</button>
    <button type="button" data-filter="below" aria-pressed="false">{t(LANG, "f_below")}</button>
    <button type="button" data-filter="history" aria-pressed="false">{t(LANG, "f_history")}</button>
    <button type="button" data-filter="crisis" aria-pressed="false">{t(LANG, "f_crisis")}</button>
  </div>
  <div class="tools" role="group" aria-label="{t(LANG, "f_basin")}">
    <button type="button" data-basin="all" aria-pressed="true">{t(LANG, "basin_all")}</button>
{basin_buttons}
  </div>
  <div class="wrap"><table class="points">
    <thead><tr><th>{t(LANG, "th_point")}</th><th>{t(LANG, "th_thresholds")}</th><th class="num">{t(LANG, "th_flow")}</th>
    <th class="num">{t(LANG, "th_dcr")}</th><th class="num">{t(LANG, "th_days", days=WINDOW_DAYS)}</th>
    <th>{t(LANG, "th_restriction")}</th><th>{t(LANG, "th_spark", days=WINDOW_DAYS)}</th></tr></thead>
    <tbody>
{body}
    </tbody>
  </table></div>
  <p class="legend">{t(LANG, "legend", start=long_date(start, LANG), end=long_date(last, LANG),
                         updated=f"{now:%d/%m/%Y à %H:%M}")}</p>

{method}
</main>
<footer class="site-footer">
  <p class="principle">{t(LANG, "principle")}</p>
  {sources_html()}
  <p>{t(LANG, "code", repo=REPO)}</p>
  <nav aria-label="{t(LANG, "siblings")}"><ul class="siblings" lang="es">
{siblings}
  </ul></nav>
</footer>
<script>
// Two groups of buttons: what the flow did, and which basin. A row shows when it passes both.
const chosen = {{filter: 'all', basin: 'all'}};
document.querySelectorAll('.tools button').forEach(b => b.addEventListener('click', () => {{
  b.parentElement.querySelectorAll('button').forEach(o => o.setAttribute('aria-pressed', o === b));
  if (b.dataset.filter) chosen.filter = b.dataset.filter; else chosen.basin = b.dataset.basin;
  const f = chosen.filter;
  document.querySelectorAll('.points tbody tr').forEach(tr => {{
    const below = tr.dataset.status === 'below';
    const history = tr.children[4].textContent.trim()[0] !== '0';
    const crisis = tr.dataset.level === 'crise';
    const shown = f === 'below' ? below : f === 'history' ? history : f === 'crisis' ? crisis : true;
    tr.hidden = !(shown && (chosen.basin === 'all' || tr.dataset.basin === chosen.basin));
  }});
}}));
</script>
</body>
</html>
"""
    out = DOCS_DIR / "france.html"
    out.write_text(html, encoding="utf-8")
    return out
