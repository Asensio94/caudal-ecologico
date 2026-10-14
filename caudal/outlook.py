"""Will each water body reach good status by 2027? Pure: rows in, verdicts out.

2027 is the last deadline of the Water Framework Directive. Article 4(4) allows extending
the 2015 deadline for at most two plan updates, that is to 2027, "except in cases where
the natural conditions are such that the objectives cannot be achieved within this
period". Article 4(5) allows less stringent objectives instead. So after 2027 a body
still short of good status can only be waiting for nature to catch up, or have its bar
lowered.

Vocabulary on purpose, as in compliance.py: a deadline beyond 2027 without natural
conditions is *not justified by natural conditions in what was reported*, never "illegal".
The Commission assesses the plans; a bot reads what they say.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Status codes of WISE. Ecological: 1 high, 2 good, 3 moderate, 4 poor, 5 bad.
# Chemical and groundwater quantitative: 2 good, 3 failing to achieve good.
GOOD = {"ecological": {"1", "2"}, "chemical": {"2"}, "quantitative": {"2"}}
SURFACE_ASPECTS = ("ecological", "chemical")
GROUND_ASPECTS = ("quantitative", "chemical")

# EEA bands of the expected date of good status, as plain horizons.
BANDS = {"2021 or earlier": "2021", "2027 or earlier": "2027", "Beyond 2027": ">2027",
         "Less stringent objectives already achieved": "4(5)"}
ORDER = {"": 0, "2015": 1, "2021": 1, "2027": 2, ">2027": 3}
NATURAL = "natural conditions"

VERDICTS = {
    "good": "En buen estado",
    "by_2027": "Prórroga hasta 2027",
    "beyond_natural": "Más allá de 2027 por condiciones naturales",
    "beyond_other": "Más allá de 2027 sin alegar condiciones naturales",
    "less_stringent": "Objetivos menos rigurosos",
    "unknown": "Sin evaluar",
}
EXEMPTIONS = {"4(4)", "4(5)", "4(6)", "4(7)"}


@dataclass
class Outlook:
    code: str
    verdict: str
    failing: list[str]                 # aspects not in good status
    horizon: str                       # '2027', '>2027', '4(5)'… for the failing aspects
    horizon_source: str                # 'boe' or 'eea'
    articles: list[str]                # exemptions applied, from either source
    reasons: list[str] = field(default_factory=list)    # of the 4(4) extensions
    eea_horizon: str = ""
    boe_horizon: str = ""

    @property
    def sources_differ(self) -> bool:
        # The EEA band "2021 or earlier" covers a BOE 2015: only a different band counts.
        band = lambda h: "2021" if h in ("2015", "2021") else h
        return bool(self.eea_horizon and self.boe_horizon) and band(self.eea_horizon) != band(self.boe_horizon)


def aspects(body: dict) -> tuple[str, ...]:
    return GROUND_ASPECTS if body["category"] == "GW" else SURFACE_ASPECTS


def worst(horizons) -> str:
    return max(horizons, key=lambda h: ORDER.get(h, 0), default="")


def assess(body: dict, exemptions: list[dict], objective: dict | None = None) -> Outlook:
    """`body` is a data/wfd/water_bodies.csv row, `exemptions` its exemption rows and
    `objective` its data/wfd/objectives.csv row from the BOE, if the basin has one.

    The year comes from the BOE where there is one (aspect-specific first, then the
    overall one), else from the EEA band. Where both give one, they are kept apart to
    show when they disagree.
    """
    asp = aspects(body)
    failing = [a for a in asp if body.get(a) and body[a] != "Unknown" and body[a] not in GOOD[a]]
    unknown = [a for a in asp if not body.get(a) or body[a] == "Unknown"]
    mine = [e for e in exemptions if e["code"] == body["code"]]
    arts = {e["article"] for e in mine}
    if objective:
        arts |= {a for a in objective["articles"].split(";") if a}
    arts &= EXEMPTIONS

    looked_at = failing or [a for a in asp if a not in unknown]
    bands = [BANDS.get(body.get(f"{a}_by") or "", "") for a in looked_at]
    eea_ls = "4(5)" in bands
    eea = worst(b for b in bands if b != "4(5)")
    boe = worst((objective.get(f"{a}_by") or objective.get("global_by") or "") for a in looked_at) if objective else ""
    horizon, source = (boe, "boe") if boe else (eea, "eea")

    reasons = sorted({e["reason"] for e in mine if e["article"] == "4(4)" and (not failing or e["aspect"] in failing)})
    out = Outlook(body["code"], "unknown", failing, horizon, source, sorted(arts), reasons, eea, boe)
    if not failing:
        out.verdict = "unknown" if unknown else "good"
    elif eea_ls or any(e["article"] == "4(5)" and e["aspect"] in failing for e in mine) or \
            (objective and "4(5)" in objective["articles"]):
        out.verdict, out.horizon = "less_stringent", out.horizon or "4(5)"
    elif horizon == ">2027":
        out.verdict = "beyond_natural" if reasons and set(reasons) <= {NATURAL} else "beyond_other"
    elif horizon in ("2015", "2021", "2027"):
        # Reported as reached by 2021 while still failing: it can only be pending to 2027.
        out.verdict = "by_2027"
    return out


def flagged(o: Outlook) -> bool:
    """Bodies that go to signals.json: short of good status, or under an exemption."""
    return o.verdict in ("by_2027", "beyond_natural", "beyond_other", "less_stringent") or bool(o.articles)
