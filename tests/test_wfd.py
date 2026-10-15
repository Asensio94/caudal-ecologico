from datetime import date

from caudal import objectives
from caudal.compliance import DayResult, Status
from caudal.outlook import assess, flagged
from caudal.signals import build, river_flow, water_status
from caudal.wfd import body_name, match_code, parse_exemption, reported_on


def tr(*cells):
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


# --- EEA ---------------------------------------------------------------------------

def test_exemption_values_split_into_article_and_reason():
    assert parse_exemption("Article 4(4) - Technical feasibility") == ("4(4)", "technical feasibility")
    assert parse_exemption("Article 4(7)") == ("4(7)", "")
    assert parse_exemption("None") is None and parse_exemption(None) is None


def test_reported_date_comes_from_the_file_name():
    assert reported_on("https://cdr.eionet.europa.eu/es/eu/wfd2022/SWB_ES_ES125_20250228.xml") == "2025-02-28"
    assert reported_on("") == ""


def test_names_are_title_cased_across_hyphens():
    assert body_name("ZUMAIA-IRUN") == "Zumaia-Irun"


def test_plan_codes_match_eu_codes():
    known = {"ES080MSPF18-33", "ES080MSBT080-102", "ES017MSPFES052MAR002710", "ES040MSPF000134420"}
    assert match_code("18-33", "ES080", known) == "ES080MSPF18-33"
    assert match_code("080-102", "ES080", known) == "ES080MSBT080-102"
    assert match_code("ES052MAR002710", "ES017", known) == "ES017MSPFES052MAR002710"
    assert match_code("ES040MSPF000134420", "ES040", known) == "ES040MSPF000134420"
    assert match_code("99-99", "ES080", known) is None


# --- BOE ---------------------------------------------------------------------------

def test_horizons_and_articles():
    assert objectives.horizon("2027.") == "2027"
    assert objectives.horizon("2016 - 2021") == "2021"
    assert objectives.horizon("Después de 2022 - 2027") == ">2027"
    assert objectives.horizon("2039") == ">2027"
    assert objectives.horizon("-") == ""
    assert objectives.articles("4 (3); 4 (4)") == ["4(3)", "4(4)"]
    assert objectives.articles("Art.4.4 a) i") == ["4(4)"]


def test_jucar_reader_with_new_modifications():
    html = ("<table>" + tr("18-33", "Río Júcar", "2027", "4 (4)") + tr("080-102", "Acuífero", "2039", "4.4") + "</table>"
            "<table>" + tr("Presa X", "18-33", "Río Júcar") + tr("18-34", "Otro") + "</table>")
    got = {o.boe_code: o for o in objectives.jucar(html)}
    assert got["18-33"].horizons == {"global": "2027"} and got["18-33"].articles == ["4(4)", "4(7)"]
    assert got["080-102"].horizons["global"] == ">2027"
    assert got["18-34"].articles == ["4(7)"]


def test_guadiana_reader():
    html = "<table>" + tr("ES040MSPF000134420", "Río", "Mod", "Bueno", "Peor", "Bueno", "Después de 2022 - 2027",
                          "Art.4.4 a) i") + "</table>"
    [o] = objectives.guadiana(html)
    assert o.horizons == {"global": ">2027"} and o.articles == ["4(4)"]


def test_cantabrico_reader_surface_ground_and_modifications():
    html = ('<p class="parrafo">Apéndice 8.1</p><table>'
            + tr("Río", "ES018MAR002491", "Urumea II", "2027", "2015", "4 (4)")
            + tr("ES018MSBT013-001", "Acuífero", "2021", "2027", "4 (4)") + "</table>"
            '<p class="parrafo">Apéndice 8.2</p><table>' + tr("ES018MAR002491", "Urumea II", "Presa") + "</table>"
            '<p class="parrafo">Apéndice 9</p>')
    got = {o.boe_code: o for o in objectives.cantabrico(html, "a8-4")}
    assert got["ES018MAR002491"].horizons == {"ecological": "2027", "chemical": "2015"}
    assert got["ES018MAR002491"].articles == ["4(4)", "4(7)"]
    assert got["ES018MSBT013-001"].horizons == {"quantitative": "2021", "chemical": "2027"}


# --- verdicts ----------------------------------------------------------------------

def body(**kw):
    base = {"code": "ESX", "rbd": "ES080", "category": "RW", "ecological": "2", "chemical": "2", "quantitative": "",
            "ecological_by": "2021 or earlier", "chemical_by": "2021 or earlier", "quantitative_by": ""}
    return {**base, **kw}


def ex(article, reason, aspect="ecological"):
    return {"code": "ESX", "aspect": aspect, "article": article, "reason": reason, "pressures": ""}


def test_good_and_unknown():
    assert assess(body(), []).verdict == "good"
    assert assess(body(ecological="Unknown"), []).verdict == "unknown"
    assert not flagged(assess(body(), []))


def test_failing_with_2027_band_is_an_extension_to_2027():
    o = assess(body(ecological="3", ecological_by="2027 or earlier"), [ex("4(4)", "technical feasibility")])
    assert o.verdict == "by_2027" and o.articles == ["4(4)"] and flagged(o)


def test_beyond_2027_needs_natural_conditions_alone():
    b = body(ecological="4", ecological_by="Beyond 2027")
    assert assess(b, [ex("4(4)", "natural conditions")]).verdict == "beyond_natural"
    assert assess(b, [ex("4(4)", "natural conditions"), ex("4(4)", "technical feasibility")]).verdict == "beyond_other"
    assert assess(b, []).verdict == "beyond_other"


def test_less_stringent_objectives():
    assert assess(body(ecological="3", ecological_by="Less stringent objectives already achieved"), []).verdict \
        == "less_stringent"
    assert assess(body(chemical="3", chemical_by="2027 or earlier"), [ex("4(5)", "disproportionate cost", "chemical")]
                  ).verdict == "less_stringent"


def test_boe_year_wins_over_eea_band():
    obj = {"global_by": "", "ecological_by": ">2027", "chemical_by": "", "quantitative_by": "", "articles": "4(4)"}
    o = assess(body(ecological="3", ecological_by="2027 or earlier"), [ex("4(4)", "natural conditions")], obj)
    assert o.verdict == "beyond_natural" and o.horizon_source == "boe" and o.sources_differ


def test_boe_2015_is_inside_the_eea_2021_band():
    obj = {"global_by": "2015", "ecological_by": "", "chemical_by": "", "quantitative_by": "", "articles": ""}
    assert not assess(body(), [], obj).sources_differ


def test_groundwater_uses_quantitative_and_chemical():
    gw = body(category="GW", ecological="", ecological_by="", quantitative="3", quantitative_by="2027 or earlier")
    assert assess(gw, []).verdict == "by_2027"


# --- signals.json ------------------------------------------------------------------

def station_row(below_days):
    day = date(2026, 10, 12)
    status = Status.BELOW if below_days else Status.OK
    results = [DayResult(day, 0.1, 0.2, None, status)]
    return {"station": {"station_id": "jucar-08030", "name": "El Terde", "river": "Mijares",
                        "water_body_code": "10-03A", "lon": "-0.7", "lat": "40.1"},
            "results": results, "latest": results[-1], "below_days": below_days}


def countdown_body(verdict_body, exemptions=()):
    o = assess(verdict_body, list(exemptions))
    return {**verdict_body, "name": "Río X", "reported": "2023-08-07", "lon": "-1", "lat": "40",
            "outlook": o, "flagged": flagged(o)}


def test_river_flow_only_for_stations_with_a_day_below():
    [s] = river_flow([station_row(1), station_row(0)])
    assert s["kind"] == "river_flow" and s["url"].endswith("#jucar-08030")
    assert s["title"] == "El Terde: 1 de 1 días por debajo del caudal mínimo"
    assert s["details"]["point"] == [-0.7, 40.1]


def test_water_status_only_for_flagged_bodies_and_never_a_deadline():
    good = countdown_body(body())
    late = countdown_body(body(ecological="4", ecological_by="Beyond 2027"), [ex("4(4)", "natural conditions")])
    [s] = water_status([good, late])
    assert s["kind"] == "water_status" and s["status"] == "beyond_natural" and s["deadline"] is None
    assert s["url"].endswith("2027.html#ESX") and s["details"]["reasons"] == ["condiciones naturales"]


def test_document_follows_the_contract():
    doc = build([station_row(2)])
    assert doc["source"] == "caudal-ecologico" and doc["version"] == 1 and doc["coverage"]["sites"] is None
    for s in doc["signals"]:
        assert all(s.get(k) for k in ("id", "kind", "date", "title", "url", "precision"))


def test_document_leaves_water_status_out_until_the_hub_takes_it():
    assert {s["kind"] for s in build([station_row(2)])["signals"]} == {"river_flow"}
