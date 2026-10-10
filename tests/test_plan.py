from caudal.plan import calendar_order, jucar_minimums, requirement_rows, to_m3s

HEAD = "<tr><th>Código</th><th>Nombre</th><th>Esp.</th><th>Temp.</th>" + "<th>m</th>" * 12 + "</tr>"


def row(code, name, prot, temp, months):
    return "<tr>" + "".join(f"<td>{c}</td>" for c in [code, name, prot, temp, *months]) + "</tr>"


ORD = ["0,5", "0,6<sup>(1)</sup>", "0,7", "0,8", "0,9", "1", "1,1", "1,2", "1,3", "Cese", "Cese", ""]
DRY = ["0,3"] * 12
FIXTURE = (
    f"<table>{HEAD}{row('18-33', 'Río Júcar: Alarcón - Picazo.', 'Sí', 'P', ORD)}</table>"
    f"<table>{HEAD}{row('18-33', 'Río Júcar: Alarcón - Picazo', 'Sí', 'P', DRY)}</table>"
    "<table><tr><th>Código masa</th><th>Nombre</th><th>Punto de seguimiento</th>"
    "<th>Dispositivo control caudal mínimo</th></tr>"
    "<tr><td>18-33</td><td>Júcar</td><td>Picazo</td><td>ROEA 08030</td></tr>"
    "<tr><td>18-34</td><td>Otra</td><td>Nueva</td><td>Nuevo aforo*</td></tr></table>"
)


def test_cells_to_m3s():
    assert to_m3s("0,03") == 0.03
    assert to_m3s("Cese") == 0.0
    assert to_m3s("") is None and to_m3s("-") is None
    assert to_m3s("80000", unit_factor=0.001) == 80.0
    assert to_m3s("1.250,5") == 1250.5


def test_hydrological_year_is_reordered_to_calendar():
    oct_first = list(range(10, 13)) + list(range(1, 10))
    assert calendar_order(oct_first) == tuple(range(1, 13))


def test_jucar_tables_parse_with_footnotes_cese_and_blanks():
    minimums, control = jucar_minimums(FIXTURE)
    wb = minimums["18-33"]
    assert wb.name == "Río Júcar: Alarcón - Picazo" and wb.protected
    # October first in the BOE → January first here: Jan is the 4th cell (0,8).
    assert wb.ordinary[0] == 0.8 and wb.ordinary[10] == 0.6     # November, footnote stripped
    assert wb.ordinary[6:9] == (0.0, 0.0, None)                 # Jul–Aug cese, Sep blank
    assert wb.drought == (0.3,) * 12
    assert control == {"18-33": ["08030"]}


def test_requirement_rows_skip_identical_drought_regime():
    minimums, _ = jucar_minimums(FIXTURE)
    rows = requirement_rows("jucar:13070", minimums["18-33"])
    assert [r["regime"] for r in rows] == ["ordinary", "drought"]
    assert rows[0]["m09"] == "" and rows[0]["m07"] == "0"


def test_spanish_title_case_keeps_particles_lower():
    from caudal.plan import title_es
    assert title_es("SALIDA DE ARQUILLO") == "Salida de Arquillo"
    assert title_es("EL PICAZO") == "El Picazo"
    assert title_es("RIO GUADIANA IV B") == "Río Guadiana IV B"
    assert title_es("RIVERA DE LOS LIMONETES") == "Rivera de los Limonetes"
    assert title_es("PONTENOVA (A)") == "Pontenova (A)" and title_es("PONTE DA MURIA") == "Ponte da Muria"


def _guadiana_fixture():
    def table(rows):
        return "<table>" + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</table>"
    h = '<p class="parrafo_2">Apéndice {} Título</p>'
    oct_first = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]
    return (
        h.format("6.1") + table([["Código masa", "Nombre", "Estación", "Denominación"],
                                 ["ES040MSPF000132180", "Guadiana V", "E2 25", "Azud de Badajoz"],
                                 ["ES040MSPF00013353A", "Guadiana IV A", "E1-06", "Embalse"],
                                 # Real slip in the BOE: the Guadajira gauge listed under Zújar II's code.
                                 ["ES040MSPF000134230", "RÍO GUADAJIRA II.", "CR2 37", "Guadajira"]])
        # A table under another heading in between must not be taken for 6.2.
        + h.format("6.1.1") + table([["ES040MSPF000132180", "Distractor", *["99"] * 13]])
        + h.format("6.2") + table([["ES040MSPF000132180", "Río Guadiana V.", *oct_first, "100"],
                                   ["ES040MSPF00013353A", "Río Guadiana IV A (*)", *oct_first, "100"],
                                   ["ES040MSPF000134230", "RIO ZUJAR II.", *oct_first, "100"],
                                   ["ES040MSPF000142300", "RIO GUADAJIRA II.", *oct_first, "100"]])
        + h.format("6.7") + table([["ES040MSPF000132180", "Río Guadiana V", *["0,5"] * 12, "15"]])
    )


def test_guadiana_sections_are_found_by_heading_and_pending_bodies_left_out():
    from caudal.plan import guadiana_minimums
    minimums, control, pending, corrected = guadiana_minimums(_guadiana_fixture())
    wb = minimums["ES040MSPF000132180"]
    assert wb.name == "Río Guadiana V" and wb.ordinary[0] == 4 and wb.ordinary[9] == 1   # Jan, Oct
    assert wb.drought == (0.5,) * 12
    assert control["ES040MSPF000132180"] == ["E2-25"]                                   # "E2 25" normalised
    assert pending == ["ES040MSPF00013353A"] and "ES040MSPF00013353A" not in minimums


def test_utm30_to_lonlat_lands_on_known_points():
    from caudal.plan import utm30_to_lonlat
    # Puerta del Sol, Madrid (ETRS89 UTM 30N 440291, 4474254) ≈ -3.70379, 40.41678
    lon, lat = utm30_to_lonlat(440291, 4474254)
    assert abs(lon + 3.70379) < 2e-4 and abs(lat - 40.41678) < 2e-4


def test_guadiana_control_code_contradicting_its_name_is_resolved_by_name():
    from caudal.plan import guadiana_minimums
    _, control, _, corrected = guadiana_minimums(_guadiana_fixture())
    assert control["ES040MSPF000142300"] == ["CR2-37"] and "ES040MSPF000134230" not in control
    assert len(corrected) == 1 and corrected[0].startswith("CR2-37")


def _cantabrico_fixture():
    def table(rows):
        return "<table>" + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</table>"
    h = '<p class="parrafo_2">Apéndice {} Título</p>'
    seasons = ["3,00", "2,00", "1,00", "1,50", "1,00", "0,50"]   # high, medium, low; ordinary then drought
    occidental = (
        h.format("4.1") + table([
            ["Sistema de explotación", "Código masa", "Nombre masa", "UTM X", "UTM Y", "km2", *["x"] * 6],
            # The first row of each exploitation system carries the system code in front.
            ["ES018SEXP05", "Nalón.", "ES018MSPFES170MAR001320", "Río Trubia III.", "260.000", "4.800.000", "472,79", *seasons],
            ["ES018MSPFES171MAR001380", "Río Nalón III.", "270.000", "4.800.000", "1.615,07", *seasons],
            ["ES018MSPFES134MAR000670", "Río Sella I*.", "300.000", "4.790.000", "57,17", *seasons]])
        + h.format("4.2") + table([["ES018MSPFES170MAR001320", "Distractor", "1", "2", "3", *["9"] * 6]]))
    oriental = h.format("4.1") + table([
        ["ES111R075010", "Barbadun-A.", "Barbadun 2.", "490.164", "4.794.427", "94,2", *seasons]])
    return {"a4-18": occidental, "a4-12": oriental}


def test_cantabrico_rows_map_seasons_to_months_and_skip_system_codes():
    from caudal.plan import cantabrico_points
    pts = cantabrico_points(_cantabrico_fixture()["a4-18"], "a4-18")
    assert [p.minimum.code for p in pts] == ["ES018MSPFES170MAR001320", "ES018MSPFES171MAR001380",
                                             "ES018MSPFES134MAR000670"]
    trubia = pts[0]
    assert (trubia.x, trubia.y, trubia.km2) == (260000, 4800000, 472.79)
    # Jan–Apr high, May–Jun medium, Jul–Oct low, Nov–Dec medium.
    assert trubia.minimum.ordinary == (3, 3, 3, 3, 2, 2, 1, 1, 1, 1, 2, 2)
    assert trubia.minimum.drought[0] == 1.5 and "anexo II" in trubia.minimum.legal_ref
    assert pts[2].river_reserve and pts[2].minimum.name == "Río Sella I"
    (barbadun,) = cantabrico_points(_cantabrico_fixture()["a4-12"], "a4-12")
    assert barbadun.minimum.name == "Barbadun-A (Barbadun 2)" and barbadun.km2 == 94.2


def test_cantabrico_gauge_is_compared_only_at_the_point_the_minimum_is_set_for():
    from caudal.plan import build_cantabrico
    from caudal.sources.cantabrico import Gauge
    line = {"ES018MSPFES170MAR001320": [[(250000, 4800000), (260000, 4800000)]],
            "ES018MSPFES171MAR001380": [[(260000, 4800000), (270000, 4800000)]],
            "ES018MSPFES134MAR000670": [[(295000, 4790000), (300000, 4790000)]]}
    gauges = {
        "1376": Gauge("1376", "TRUBIA (DESEMBOCADURA)", "TRUBIA", 259990, 4800010),   # at the confluence
        "1335": Gauge("1335", "EL CONDADO", "NALÓN", 265000, 4800020),               # mid-body
        "1297": Gauge("1297", "RIBOTA", "SELLA", 299000, 4790000),                   # river reserve
        "1999": Gauge("1999", "SIN ANUARIO", "NALÓN", 269000, 4800000),
    }
    areas = {"1376": 484.0, "1335": 343.0, "1297": 54.0}
    stations, reqs, unread = build_cantabrico(_cantabrico_fixture(), gauges, areas, line)
    # On both the Trubia and the Nalón lines, but only the Trubia point drains the same area.
    assert [(s["station_id"], s["water_body_code"]) for s in stations] == [
        ("cantabrico-1376", "ES018MSPFES170MAR001320")]
    assert {r["regime"] for r in reqs} == {"ordinary", "drought"}
    assert len(unread) == 3
    assert any("1335" in u and "cuenca" in u for u in unread)
    assert any("1297" in u and "reserva" in u for u in unread)
    assert any("1999" in u and "CEDEX" in u for u in unread)
