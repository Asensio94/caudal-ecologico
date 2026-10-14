"""Deadlines and exemptions of each water body, from the basin plans in the BOE.

The EEA gives the expected date of good status in bands ("2027 or earlier", "Beyond
2027"). Real Decreto 35/2023 gives the year and the article of the Directive applied,
in an appendix on environmental objectives in each annex. Every basin lays that
table out differently, so each one has its own small reader; all of them return the
same rows. Only the intercommunity basins are in the RD: Júcar, Guadiana and the
two Cantábrico plans so far, the ones whose minimum flows this project already reads.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .plan import BOE_ID, CONSOLIDATED_URL, parse_tables, tables_by_appendix

# block → (district, legal reference)
BLOCKS = {
    "a1-193": ("ES080", "RD 35/2023, anexo XI (Júcar), apéndice 11"),
    "a1-107": ("ES040", "RD 35/2023, anexo VI (Guadiana), apéndice de objetivos medioambientales"),
    "a8-2": ("ES017", "RD 35/2023, anexo I (Cantábrico Oriental), apéndice 8"),
    "a8-4": ("ES018", "RD 35/2023, anexo II (Cantábrico Occidental), apéndice 8"),
}
AFTER_2027 = ">2027"
_CODE = re.compile(r"^(ES\d{3}[A-Z0-9-]+|\d{2}(?:-\d{2})*[A-Z]?|\d{3}-\d{3}[A-Z]?|[LCT]\d{2,4})$")
_ARTICLE = re.compile(r"4\s*[.(]\s*([1-7])")
_YEAR = re.compile(r"\b(20\d{2})\b")


@dataclass
class Objective:
    boe_code: str
    rbd: str
    horizons: dict[str, str]      # aspect ('global', 'ecological', 'chemical', 'quantitative') → horizon
    articles: list[str]           # '4(4)', '4(7)'…; 4(1) and 4(3) are kept, they are not exemptions
    legal_ref: str
    source_url: str


def is_code(cell: str) -> bool:
    return bool(_CODE.match(cell.strip()))


def horizon(cell: str) -> str:
    """'2027.' → '2027'; '2021 o antes' and '2016 - 2021' → '2021'; 'Después de 2022 - 2027'
    → '>2027'; blank or '-' → ''."""
    text = cell.strip(" .").lower()
    years = [int(y) for y in _YEAR.findall(text)]
    if "después" in text or "posterior" in text or (years and max(years) > 2027):
        return AFTER_2027
    return str(max(years)) if years else ""


def articles(cell: str) -> list[str]:
    """'4 (3); 4 (4)' → ['4(3)', '4(4)']; 'Art.4.4 a) i' → ['4(4)']; '4.3 4.4' → ['4(3)', '4(4)']."""
    return sorted({f"4({n})" for n in _ARTICLE.findall(cell)})


def _merge(found: dict[str, Objective], code: str, rbd: str, ref: str, url: str,
           horizons: dict[str, str], arts: list[str]) -> None:
    o = found.setdefault(code, Objective(code, rbd, {}, [], ref, url))
    o.horizons.update({k: v for k, v in horizons.items() if v})
    o.articles = sorted(set(o.articles) | set(arts))


def jucar(html: str, block: str = "a1-193") -> list[Objective]:
    """Appendix 11: code, name, year of good status, article. 11.5 lists the bodies a
    new modification (4(7)) will affect, with the code in the second column."""
    rbd, ref = BLOCKS[block]
    url = CONSOLIDATED_URL.format(boe=BOE_ID, block=block)
    found: dict[str, Objective] = {}
    for t in parse_tables(html):
        for r in t:
            if len(r) == 4 and is_code(r[0]):
                _merge(found, r[0], rbd, ref, url, {"global": horizon(r[2])}, articles(r[3]))
            elif len(r) == 3 and is_code(r[1]):
                _merge(found, r[1], rbd, ref, url, {}, ["4(7)"])
            elif len(r) == 2 and is_code(r[0]):       # same modification, next body (rowspan)
                _merge(found, r[0], rbd, ref, url, {}, ["4(7)"])
    return list(found.values())


def guadiana(html: str, block: str = "a1-107") -> list[Objective]:
    """Code, name, ecological, chemical and overall status, objective, planning horizon,
    exemption. Groundwater bodies share the layout with quantitative status."""
    rbd, ref = BLOCKS[block]
    url = CONSOLIDATED_URL.format(boe=BOE_ID, block=block)
    found: dict[str, Objective] = {}
    for t in parse_tables(html):
        for r in t:
            if len(r) == 8 and is_code(r[0]):
                _merge(found, r[0], rbd, ref, url, {"global": horizon(r[6])}, articles(r[7]))
    return list(found.values())


def cantabrico(html: str, block: str) -> list[Objective]:
    """Both plans: category, code, name, ecological year, chemical year, article for
    surface bodies; code, name, quantitative year, chemical year, article for groundwater.
    A table of new modifications lists code, name and the reason (4(7))."""
    rbd, ref = BLOCKS[block]
    url = CONSOLIDATED_URL.format(boe=BOE_ID, block=block)
    found: dict[str, Objective] = {}
    for t in (t for ts in tables_by_appendix(html).values() for t in ts):
        for r in t:
            if len(r) == 6 and is_code(r[1]):
                _merge(found, r[1], rbd, ref, url, {"ecological": horizon(r[3]), "chemical": horizon(r[4])},
                       articles(r[5]))
            elif len(r) == 5 and is_code(r[0]):
                _merge(found, r[0], rbd, ref, url, {"quantitative": horizon(r[2]), "chemical": horizon(r[3])},
                       articles(r[4]))
            elif len(r) == 3 and is_code(r[0]):
                _merge(found, r[0], rbd, ref, url, {}, ["4(7)"])
    return list(found.values())


READERS = {"a1-193": jucar, "a1-107": guadiana, "a8-2": cantabrico, "a8-4": cantabrico}

OBJ_FIELDS = ["code", "boe_code", "rbd", "global_by", "ecological_by", "chemical_by", "quantitative_by",
              "articles", "legal_ref", "source_url"]


def rows(objectives: list[Objective], known: set[str]) -> tuple[list[dict], list[str]]:
    """CSV rows keyed by EU code, and the plan codes that match no reported body."""
    from .wfd import match_code
    out, unmatched = [], []
    for o in objectives:
        code = match_code(o.boe_code, o.rbd, known)
        if code is None:
            unmatched.append(f"{o.rbd} {o.boe_code}")
            continue
        out.append({"code": code, "boe_code": o.boe_code, "rbd": o.rbd,
                    **{f"{a}_by": o.horizons.get(a, "") for a in ("global", "ecological", "chemical", "quantitative")},
                    "articles": ";".join(o.articles), "legal_ref": o.legal_ref, "source_url": o.source_url})
    return sorted(out, key=lambda r: r["code"]), unmatched
