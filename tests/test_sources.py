from datetime import date

from caudal.sources import cantabrico, expected_readings, jucar


def test_expected_readings_on_dst_days():
    assert expected_readings(date(2026, 10, 7), 5) == 288
    assert expected_readings(date(2026, 3, 29), 5) == 276    # clocks forward: 23 h
    assert expected_readings(date(2026, 10, 25), 5) == 300   # clocks back: 25 h


def test_jucar_keeps_valid_states_inside_the_local_day():
    payload = [
        {"valor": 1.0, "fecha": "2026-10-06T21:55:00.000Z", "estado": 0},   # 23:55 local, day before
        {"valor": 2.0, "fecha": "2026-10-06T22:00:00.000Z", "estado": 128}, # 00:00 local
        {"valor": 0.0, "fecha": "2026-10-06T22:05:00.000Z", "estado": 130}, # invalid code
        {"valor": 3.0, "fecha": "2026-10-07T21:55:00.000Z", "estado": 0},   # 23:55 local
        {"valor": 4.0, "fecha": "2026-10-07T22:00:00.000Z", "estado": 0},   # next day
    ]
    assert jucar.parse(payload, date(2026, 10, 7)) == [(0, 2.0), (1435, 3.0)]


def test_cantabrico_parses_utc_csv_and_skips_junk():
    text = "Valor;Fecha-hora UTC\n1.24;2026-10-05 22:00:00\nn/a;2026-10-05 22:05:00\n0.79;2026-10-06 21:55:00\n0.5;2026-10-06 22:00:00\n"
    assert cantabrico.parse(text, date(2026, 10, 6)) == [(0, 1.24), (1435, 0.79)]


def test_guadiana_drops_the_next_day_boundary_and_nulls():
    from caudal.sources import guadiana
    v = "CR2-25/QR1"
    payload = {"valores": [
        {"timestamp": "2026-10-06 22:00:00", v: 20.25},   # 00:00 local
        {"timestamp": "2026-10-06 22:10:00", v: None},
        {"timestamp": "2026-10-07 22:00:00", v: 19.73},   # 00:00 next local day
    ]}
    assert guadiana.parse(payload, v, date(2026, 10, 7)) == [(0, 20.25)]


def test_jucar_gauges_map_ea_numbers_to_roea():
    page = 'x; let aforos = [{"idVariable": "13070", "fldTNombre": "EA 89 HUERTO MULET", ' \
           '"fldTNombreVariable": "CAUDAL RÍO JÚCAR", "fldNCoordGPSLat": 715000.5, "fldNCoordGPSLon": 4330000.0}, ' \
           '{"idVariable": "1", "fldTNombre": "EMBALSE DE FORATA", "fldTNombreVariable": "CAUDAL SALIDA RÍO MAGRO", ' \
           '"fldNCoordGPSLat": 0, "fldNCoordGPSLon": 0}];'
    gauges = jucar.parse_gauges(page)
    assert list(gauges) == ["08089"]
    assert gauges["08089"].variable_id == "13070" and gauges["08089"].river == "Júcar"
