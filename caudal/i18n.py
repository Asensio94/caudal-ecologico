"""Interface strings and number formats, one dictionary per language.

Each country's page is written in that country's language: the Spanish one in Spanish,
the French one in French. Data files (flows, signals.json, masas-2027.json) stay in
canonical, language-independent values; only what a reader sees goes through here. Same
pattern as humedales/i18n.py in vigilancia-humedales.
"""
from __future__ import annotations

LANG_BY_COUNTRY = {"ES": "es", "FR": "fr"}
# Page of each country, in the order the country links are shown.
PAGES = {"ES": "index.html", "FR": "france.html"}
PAGES_2027 = {"ES": "2027.html", "FR": "france-2027.html"}

# French typography: a narrow no-break space as thousands separator and before «%».
_NNBSP = " "


def lang_of(country: str) -> str:
    return LANG_BY_COUNTRY.get(country, "es")


def n(v: float, lang: str) -> str:
    """Integer with the thousands separator of the language: 46.709 / 46 709."""
    s = f"{v:,.0f}"
    return s.replace(",", "." if lang == "es" else _NNBSP)


def d(v: float | None, lang: str, nd: int = 2) -> str:
    """Decimal with comma in both languages, thousands grouped: 1.234,56 / 1 234,56."""
    if v is None:
        return "—"
    s = f"{v:,.{nd}f}".replace(",", " ").replace(".", ",")
    return s.replace(" ", "." if lang == "es" else _NNBSP)


def p(x: float, lang: str) -> str:
    """A fraction as a percentage without decimals: 15 % / 15 %."""
    return f"{100 * x:.0f}{' ' if lang == 'es' else _NNBSP}%"


UI: dict[str, dict[str, str]] = {
    "es": {
        "countries": "Países",
        "country_ES": "España",
        "country_FR": "Francia",
        "siblings": "Proyectos hermanos",
    },
    "fr": {
        "countries": "Pays",
        "country_ES": "Espagne",
        "country_FR": "France",
        "siblings": "Projets associés",
        "title": "Débit écologique",
        "h1": "Débit <span>écologique</span>",
        "description": "Débit journalier des rivières face au débit de crise (DCR) fixé par le SDAGE.",
        "lede": ("Chaque jour, le débit moyen journalier aux points nodaux du bassin Adour-Garonne face au débit "
                 "de crise (DCR) que fixe le SDAGE 2022-2027. Débits de Hub'Eau ; seuils lus dans le fichier "
                 "ouvert de l'agence de l'eau."),
        "fig_points": "points nodaux (Adour-Garonne)",
        "fig_below_now": "sous le DCR le dernier jour avec données",
        "fig_below_any": "avec au moins un jour sous le DCR en {days} jours",
        "fig_crisis": "en zone de crise sécheresse aujourd'hui (VigiEau)",
        "nav_2027": "L'atteindra-t-elle en 2027 ? État et échéance de chaque masse d'eau →",
        "filter": "Filtrer",
        "f_all": "Tous",
        "f_below": "Sous le DCR maintenant",
        "f_history": "Au moins un jour sous le DCR",
        "f_crisis": "En crise (VigiEau)",
        "th_point": "Point nodal",
        "th_thresholds": "Seuils du SDAGE",
        "th_flow": "Débit dernier jour<br>m³/s",
        "th_dcr": "DCR<br>m³/s",
        "th_days": "Jours sous le DCR<br>({days} j)",
        "th_restriction": "Restrictions<br>(VigiEau)",
        "th_spark": "{days} derniers jours",
        "st_below": "Sous le DCR selon des données provisoires",
        "st_below_validated": "Sous le DCR (donnée validée)",
        "st_ok": "Au-dessus du DCR",
        "st_no_data": "Données insuffisantes",
        "st_no_rule": "Pas de DCR",
        "river": "{river}",
        "station": "station {code}",
        "consecutive_1": "{n} jour d'affilée",
        "consecutive_n": "{n} jours d'affilée",
        "provisional": "donnée provisoire",
        "validated": "donnée validée",
        "doe": "DOE {doe} m³/s",
        "doe_note": "objectif d'étiage, à tenir 8 années sur 10 : un jour en dessous n'est pas un manquement",
        "no_order": "Aucun arrêté",
        "order_since": "depuis le {date}",
        "level_vigilance": "Vigilance",
        "level_alerte": "Alerte",
        "level_alerte_renforcee": "Alerte renforcée",
        "level_crise": "Crise",
        "spark_label": "Débit des {days} derniers jours",
        "legend": ("Du {start} au {end}. Trait continu : débit moyen journalier ; pointillés : DCR ; ombré : jour "
                   "sous le DCR. Débits de Hub'Eau, en majorité provisoires (bruts, corrigés ou pré-validés), mis "
                   "à jour le {updated} (heure de Paris)."),
        "principle": ("Données publiques, règles visibles et chaque chiffre relié à sa source. Des indices, "
                      "pas des verdicts."),
        "code": 'Code sur <a href="{repo}">GitHub</a> (MIT) ; données propres CC BY 4.0.',
        "pressures": "Pressions sur le débit que signale l'état des lieux : {list}.",
        "no_pressures": "L'état des lieux ne signale pas, sur cette masse d'eau, de pression qui réduise le débit.",
        "aquifer": "Nappe {name} : {state}{risk}.",
        "aq_poor": "<b>état quantitatif médiocre</b>",
        "aq_good": "bon état quantitatif",
        "aq_unknown": "état quantitatif inconnu",
        "aq_risk": ", risque de ne pas atteindre le bon état",
        "aq_others_1": "Une autre nappe sous la station, sans état quantitatif médiocre.",
        "aq_others_n": "{n} autres nappes sous la station, sans état quantitatif médiocre.",
    },
}


def t(lang: str, key: str, **kw) -> str:
    """The string in `lang`, falling back to Spanish if a key is missing."""
    s = UI.get(lang, {}).get(key, UI["es"].get(key, key))
    return s.format(**kw) if kw else s


MONTHS = {
    "es": "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(),
    "fr": "janvier février mars avril mai juin juillet août septembre octobre novembre décembre".split(),
}


def long_date(day, lang: str) -> str:
    """15 de octubre de 2026 / 15 octobre 2026 (1er for the first of the month in French)."""
    if lang == "fr":
        return f"{'1er' if day.day == 1 else day.day} {MONTHS['fr'][day.month - 1]} {day.year}"
    return f"{day.day} de {MONTHS['es'][day.month - 1]} de {day.year}"


# «L'atteindra-t-elle en 2027 ?»: the verdicts of outlook.py and the reasons of the
# extensions, in French. The keys are the canonical values written to the JSON.
VERDICTS_FR = {
    "good": "En bon état",
    "by_2027": "Report jusqu'en 2027",
    "beyond_natural": "Au-delà de 2027 pour conditions naturelles",
    "beyond_other": "Au-delà de 2027 sans invoquer les conditions naturelles",
    "less_stringent": "Objectifs moins stricts",
    "unknown": "Non évalué",
}
REASONS_FR = {"natural conditions": "conditions naturelles", "technical feasibility": "faisabilité technique",
              "disproportionate cost": "coûts disproportionnés", "new modification": "nouvelle modification",
              "accidents": "accident"}


# Flow pressures reported to the EEA (WISE), in French; the Spanish ones live in sources/wise.py.
FLOW_PRESSURES_FR = {
    "P3-1": "prélèvements pour l'irrigation", "P3-2": "prélèvements pour l'eau potable",
    "P3-3": "prélèvements industriels", "P3-4": "prélèvements pour le refroidissement",
    "P3-5": "prélèvements hydroélectriques", "P3-6": "prélèvements piscicoles",
    "P3-7": "autres prélèvements",
    "P4-2-1": "barrages ou seuils hydroélectriques", "P4-2-2": "barrages ou seuils de protection contre les crues",
    "P4-2-3": "barrages ou seuils pour l'eau potable", "P4-2-4": "barrages ou seuils pour l'irrigation",
    "P4-2-5": "barrages ou seuils de loisirs", "P4-2-6": "barrages ou seuils industriels",
    "P4-2-7": "barrages ou seuils de navigation", "P4-2-8": "autres barrages ou seuils",
    "P4-2-9": "barrages ou seuils d'usage inconnu ou abandonnés",
    "P4-3-1": "régulation du débit pour l'irrigation", "P4-3-2": "régulation du débit pour le transport",
    "P4-3-3": "régulation du débit pour l'hydroélectricité", "P4-3-4": "régulation du débit pour l'eau potable",
    "P4-3-5": "régulation du débit pour l'aquaculture", "P4-3-6": "autre régulation du débit",
}


def country_nav(country: str, pages: dict[str, str] = PAGES) -> str:
    """Links between the country pages, the current one marked."""
    lang = lang_of(country)
    links = " · ".join(f'<a aria-current="page">{t(lang, f"country_{c}")}</a>' if c == country
                       else f'<a href="{f}">{t(lang, f"country_{c}")}</a>' for c, f in pages.items())
    return f'<nav class="paises label" aria-label="{t(lang, "countries")}">{links}</nav>'
