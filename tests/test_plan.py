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
