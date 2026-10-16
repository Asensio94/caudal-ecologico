"""«L'atteindra-t-elle en 2027 ?»: the French water bodies, same method as countdown.py.

France reports its SDAGE 2022-2027 to the EEA like Spain reports its basin plans, so the
status, deadline bands and exemptions come from the same WISE tables. There is no French
counterpart of the Spanish BOE appendix read here, so the deadline is the EEA band.
Renders docs/france-2027.html and docs/masas-2027-fr.json.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import DOCS_DIR
from .countdown import CATEGORIES, CSS, DISCODATA_URL, ORDER, bodies, write_json
from .i18n import PAGES_2027, REASONS_FR, VERDICTS_FR, country_nav, long_date, n, p
from .logo import LOGO_SVG, favicon_link
from .web import ACCENT, ACCENT_DARK, COMMON_CSS, REPO, SIBLINGS
from .wfd import RBD_NAMES

LANG = "fr"
COUNTRY = "FR"
JSON_NAME = "masas-2027-fr.json"
CATEGORIES_FR = {"RW": "Cours d'eau", "LW": "Plan d'eau", "TW": "Eau de transition", "CW": "Eau côtière",
                 "GW": "Eau souterraine"}
WISE_FR = "https://water.europa.eu/freshwater/europe-freshwater/water-framework-directive"
EAUFRANCE_SDAGE = "https://www.eaufrance.fr/les-sdage"
assert CATEGORIES.keys() == CATEGORIES_FR.keys()


def _summary_rows(rows: list[dict]) -> tuple[str, Counter]:
    by_rbd: dict[str, Counter] = {}
    for b in rows:
        by_rbd.setdefault(b["rbd"], Counter())[b["outlook"].verdict] += 1
    total = Counter()
    lines = []
    for rbd in sorted(by_rbd, key=lambda r: RBD_NAMES.get(r, r)):
        c = by_rbd[rbd]
        total += c
        k = sum(c.values())
        cells = "".join(f'<td class="num">{n(c[v], LANG)}</td>' for v in ORDER)
        lines.append(f'<tr><td><b>{escape(RBD_NAMES.get(rbd, rbd))}</b><span class="sub">{rbd}</span></td>'
                     f'<td class="num">{n(k, LANG)}</td>{cells}'
                     f'<td class="num">{p(c["good"] / k if k else 0, LANG)}</td></tr>')
    return "\n".join(lines), total


def render() -> Path:
    rows = bodies(COUNTRY)
    write_json(rows, datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%MZ"), JSON_NAME, VERDICTS_FR, REASONS_FR)
    summary, total = _summary_rows(rows)
    k = len(rows)
    short = k - total["good"] - total["unknown"]
    beyond = total["beyond_natural"] + total["beyond_other"]
    reported = sorted({b["reported"] for b in rows if b["reported"]})
    undated = sorted({RBD_NAMES.get(b["rbd"], b["rbd"]) for b in rows if not b["reported"]})
    linked = sum(1 for b in rows if b["station"])
    siblings = "\n".join(
        f'    <li{" aria-current=\"page\"" if slug == "caudal-ecologico" else ""}>'
        f'<a href="https://asensio94.github.io/{slug}/">{name}</a></li>' for slug, name in SIBLINGS)
    heads = "".join(f'<th class="num"><span class="state {v}"></span>{VERDICTS_FR[v]}</th>' for v in ORDER)
    totals = "".join(f'<td class="num">{n(total[v], LANG)}</td>' for v in ORDER)
    options = "\n".join(f'      <option value="{c}">{escape(name)}</option>'
                        for c, name in sorted(RBD_NAMES.items(), key=lambda kv: kv[1]) if c.startswith(COUNTRY))
    verdict_options = "\n".join(f'      <option value="{v}">{VERDICTS_FR[v]}</option>' for v in ORDER)
    period = (f"entre le {long_date(date.fromisoformat(reported[0]), LANG)} et le "
              f"{long_date(date.fromisoformat(reported[-1]), LANG)}" if reported else "")
    undated_note = (f" WISE ne donne pas de date de transmission pour {', '.join(undated)}." if undated else "")

    html = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>L’atteindra-t-elle en 2027 ?</title>
<meta name="description" content="État de chaque masse d’eau de France, son échéance pour le bon état et les exemptions de la directive-cadre sur l’eau qui lui sont appliquées.">
{favicon_link(ACCENT, ACCENT_DARK)}
<style>
{COMMON_CSS}
{CSS}
</style>
</head>
<body>
<header class="site-header">
  {country_nav(COUNTRY, PAGES_2027)}
  <h1>{LOGO_SVG}L’atteindra-t-elle en <span>2027</span> ?</h1>
  <p class="lede">2027 est la dernière échéance de la directive-cadre sur l’eau pour que rivières, lacs, côtes et
  nappes soient en bon état. Après, il ne reste qu’à attendre que la nature se rétablisse ou à abaisser l’objectif.
  Voici ce que la France a transmis à l’Agence européenne pour l’environnement pour chaque masse d’eau.</p>
  <div class="figures">
    <div><b>{n(k, LANG)}</b><span>masses d’eau de surface et souterraines</span></div>
    <div><b>{n(short, LANG)}</b><span>ne sont pas encore en bon état</span></div>
    <div><b>{n(beyond, LANG)}</b><span>avec une échéance après 2027</span></div>
    <div><b>{n(total["less_stringent"], LANG)}</b><span>avec des objectifs moins stricts</span></div>
  </div>
</header>
<main>
  <p class="nav"><a href="france.html">← Débit journalier face au débit de crise</a></p>

  <h2>Par district</h2>
  <div class="wrap"><table class="points">
    <thead><tr><th>District</th><th class="num">Masses</th>{heads}<th class="num">En bon état</th></tr></thead>
    <tbody>
{summary}
    </tbody>
    <tfoot><tr><td>France</td><td class="num">{n(k, LANG)}</td>{totals}<td class="num">{p(total["good"] / k if k else 0, LANG)}</td></tr></tfoot>
  </table></div>

  <h2>Chercher une masse d’eau</h2>
  <div class="search" role="search">
    <input id="q" type="search" placeholder="Nom ou code (p. ex. « Garonne », « FRFR327C »)" aria-label="Nom ou code">
    <select id="rbd" aria-label="District">
      <option value="">Tous les districts</option>
{options}
    </select>
    <select id="verdict" aria-label="Situation">
      <option value="">Toutes les situations</option>
{verdict_options}
    </select>
  </div>
  <p id="count" aria-live="polite">Chargement…</p>
  <div class="wrap"><table class="points" id="results">
    <thead><tr><th>Masse d’eau</th><th>État</th><th>Situation</th><th>Échéance</th><th>Exemptions</th></tr></thead>
    <tbody></tbody>
  </table></div>
  <p class="legend">Données du troisième cycle de gestion (SDAGE 2022-2027), transmises par la France
  {period}.{undated_note} <a href="{JSON_NAME}">Télécharger toutes les masses d’eau (JSON)</a>.</p>

  <section class="method" lang="fr">
    <h2>Comment c’est calculé</h2>
    <ol>
      <li><b>L’état vient de ce que la France a transmis à l’Europe.</b> Chaque SDAGE est rapporté à l’Agence
      européenne pour l’environnement (AEE), qui le publie dans sa base <a href="{WISE_FR}">WISE</a>. On y lit, pour
      chaque masse d’eau, l’état écologique (ou le potentiel, pour les masses fortement modifiées ou artificielles)
      et l’état chimique ; pour les eaux souterraines, l’état quantitatif et l’état chimique. Une masse est en bon
      état si tous ses aspects le sont.</li>
      <li><b>L’échéance, par tranches.</b> L’AEE donne l’échéance du bon état par tranches (« 2021 ou avant »,
      « 2027 ou avant », « après 2027 »). Pour l’Espagne, la page lit en plus l’année exacte publiée au Journal
      officiel ; pour la France, aucun équivalent n’est lu pour l’instant, et c’est la tranche de l’AEE qui compte.
      Les SDAGE donnent cette année masse par masse, mais dans des documents propres à chaque bassin.</li>
      <li><b>Les exemptions.</b> On réunit les articles de la directive appliqués à chaque masse : 4(4), report de
      l’échéance ; 4(5), objectifs moins stricts ; 4(6), détérioration temporaire due à des causes naturelles ou à
      des accidents ; 4(7), nouvelles modifications. Pour les reports, on garde aussi le motif invoqué : faisabilité
      technique, coûts disproportionnés ou conditions naturelles.</li>
      <li><b>On classe chaque masse.</b> Si tout va bien, « {VERDICTS_FR["good"]} ». Si un aspect n’est pas bon et
      que l’échéance est 2027 ou avant, « {VERDICTS_FR["by_2027"]} ». Si elle va au-delà de 2027 et que le seul
      motif invoqué est celui des conditions naturelles, « {VERDICTS_FR["beyond_natural"]} » : c’est le seul que
      la directive admet après 2027. Si l’on invoque aussi, ou seulement, la faisabilité technique ou les coûts, ou
      si aucun motif n’est donné, « {VERDICTS_FR["beyond_other"]} ». Si l’objectif a été abaissé,
      « {VERDICTS_FR["less_stringent"]} ». Avec un aspect non évalué et aucun en mauvais état,
      « {VERDICTS_FR["unknown"]} ».</li>
      <li><b>Le lien vers le débit.</b> {n(linked, LANG)} masses d’eau portent un lien vers la page du débit
      journalier : celles où se trouve une station d’un point nodal du bassin Adour-Garonne, d’après la couche des
      masses d’eau de l’AEE au point de la station.</li>
    </ol>
    <h3>Limites</h3>
    <ul>
      <li>« {VERDICTS_FR["beyond_other"]} » décrit ce qui a été transmis, pas une infraction : la Commission
      européenne évalue les plans, et le SDAGE peut contenir des justifications que la base européenne ne reprend
      pas.</li>
      <li>L’état est celui que le SDAGE a retenu à son adoption, établi à partir de données antérieures (état des
      lieux de 2019 dans la plupart des bassins), pas celui d’aujourd’hui. Il changera avec le prochain rapportage.</li>
      <li>Les noms des masses d’eau sont ceux de WISE, où beaucoup ont perdu leurs accents (« Riviere », « Jetee ») ;
      on ne les corrige pas à la main. Le code européen, lui, est exact.</li>
      <li>Les départements et régions d’outre-mer sont inclus, avec leurs propres districts.</li>
    </ul>
  </section>
</main>
<footer class="site-footer">
  <p class="principle">Données publiques, règles en clair et chaque chiffre relié à sa source. Des indices, pas des verdicts.</p>
  <p>État et exemptions : <a href="{DISCODATA_URL}">WISE WFD</a>, Agence européenne pour l’environnement (CC BY 4.0),
  d’après les <a href="{EAUFRANCE_SDAGE}">SDAGE 2022-2027</a>. Code sur <a href="{REPO}">GitHub</a> (MIT) ;
  données propres CC BY 4.0.</p>
  <nav aria-label="Projets associés"><ul class="siblings" lang="es">
{siblings}
  </ul></nav>
</footer>
<script>
const CAT = {json.dumps(CATEGORIES_FR, ensure_ascii=False)};
const ECO = {{"1":"très bon","2":"bon","3":"moyen","4":"médiocre","5":"mauvais","Unknown":"non évalué"}};
const BIN = {{"2":"bon","3":"médiocre","Unknown":"non évalué"}};
const HOR = {{"":"—",">2027":"après 2027","4(5)":"objectif moins strict","2021":"2021 ou avant"}};
const MAX = 200;
let data = null;
const num = x => x.toLocaleString('fr-FR');
const esc = s => String(s).replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}})[c]);
const fold = s => s.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
function row(b, hit) {{
  const [code, name, rbd, cat, eco, chem, quant, verdict, horizon, source, arts, reasons, station] = b;
  const status = cat === 'GW'
    ? `quantitatif ${{BIN[quant] || '—'}}<span class="sub">chimique ${{BIN[chem] || '—'}}</span>`
    : `écologique ${{ECO[eco] || '—'}}<span class="sub">chimique ${{chem === '3' ? 'n’atteint pas le bon état' : BIN[chem] || '—'}}</span>`;
  const st = station ? `<span class="sub"><a href="france.html#${{esc(station)}}">Débit journalier</a></span>` : '';
  const why = reasons.length ? `<span class="sub">${{esc(reasons.join(', '))}}</span>` : '';
  return `<tr id="${{esc(code)}}"${{hit ? ' class="hit"' : ''}}><td><b>${{esc(name || code)}}</b>` +
    `<span class="sub">${{esc(code)}} · ${{CAT[cat] || cat}} · ${{esc(data.districts[rbd] || rbd)}}</span>${{st}}</td>` +
    `<td>${{status}}</td><td><span class="state ${{verdict}}"></span>${{data.verdicts[verdict]}}</td>` +
    `<td>${{HOR[horizon] ?? horizon}}<span class="sub">AEE</span></td>` +
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
    ? `${{num(found.length)}} masses d’eau ; seules les ${{MAX}} premières sont affichées. Affinez la recherche.`
    : `${{num(found.length)}} ${{found.length === 1 ? 'masse d’eau' : 'masses d’eau'}}.`;
}}
function fromHash() {{
  const hash = decodeURIComponent(location.hash.slice(1));
  if (!hash || !data.bodies.some(b => b[0] === hash)) return;
  document.getElementById('q').value = hash;
  document.getElementById('rbd').value = document.getElementById('verdict').value = '';
  draw();
  document.getElementById(hash)?.scrollIntoView({{block: 'center'}});
}}
fetch('{JSON_NAME}').then(r => r.json()).then(d => {{
  data = d;
  ['q', 'rbd', 'verdict'].forEach(id => document.getElementById(id).addEventListener('input', draw));
  window.addEventListener('hashchange', fromHash);
  draw(); fromHash();
}}).catch(() => {{ document.getElementById('count').textContent = 'Impossible de charger les masses d’eau.'; }});
</script>
</body>
</html>
"""
    out = DOCS_DIR / "france-2027.html"
    out.write_text(html, encoding="utf-8")
    return out
