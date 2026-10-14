from caudal.sources import chj_piezometry, wise
from caudal.web import _title


class FakeHttp:
    """Answers each EEA query with the features given for that layer URL."""
    def __init__(self, by_url):
        self.by_url = by_url

    def get(self, url, params=None, timeout=None):
        body = {"features": self.by_url[url]}
        return type("R", (), {"raise_for_status": lambda s: None, "json": lambda s: body})()


def _river(code, name, pressures, path):
    return {"attributes": {"euSurfaceWaterBodyCode": code, "surfaceWaterBodyName": name,
                           "surfaceWaterBodyCategory": "RW", "swSignificantPressureType": pressures},
            "geometry": {"paths": [path]}}


def test_flow_pressures_keep_only_what_takes_or_regulates_water():
    reported = "P1-1 - Point - Urban waste water;P3-1 - Abstraction - Agriculture;P4-2-4 - Dams, barriers and locks - Irrigation;P5-1 - Introduced species and diseases"
    assert wise.flow_pressures(reported) == ("P3-1", "P4-2-4")
    assert wise.flow_pressures("None") == ()
    assert wise.flow_pressures(None) == ()


def test_river_body_by_plan_code_and_none_when_the_code_is_not_there():
    feats = [_river("ES080MSPF18-32-01-04", "RIVER MAGRO", "P3-1 - Abstraction - Agriculture", [[-1.12, 39.48]]),
             _river("ES080MSPF18-32-01-05", "RIVER MAGRO", "None", [[-1.1165, 39.478]])]
    http = FakeHttp({wise.RIVERS: feats})
    assert wise.river_body_at(-1.1165, 39.478, "18-32-01-04", http=http).flow_pressures == ("P3-1",)
    assert wise.river_body_at(-1.1165, 39.478, "18-99", http=http) is None


def test_river_body_without_code_takes_the_nearest_of_the_same_river():
    # At a confluence the tributary is nearer, but the gauge measures the main river.
    feats = [_river("ES050MSPF1", "RIVER GUADALBULLÓN", "None", [[-3.8001, 37.9]]),
             _river("ES050MSPF2", "TRAMO DEL RIVER GUADALQUIVIR", "P3-1 - Abstraction - Agriculture", [[-3.801, 37.9]])]
    http = FakeHttp({wise.RIVERS: feats})
    assert wise.river_body_at(-3.8, 37.9, "", "Guadalquivir", http=http).code == "ES050MSPF2"


def test_aquifer_status_codes_and_spanish_names():
    http = FakeHttp({
        wise.GROUNDWATER: [{"attributes": {"euGroundWaterBodyCode": "ES080MSBT080-133", "groundWaterBodyName": "REQUENA - UTIEL",
                                           "gwQuantitativeStatusValue": "3", "gwAtRiskQuantitative": "Yes"}}],
        wise.GROUNDWATER_NAMES: [{"attributes": {"thematicIdIdentifier": "ES080MSBT080-133", "nameText": "REQUENA - UTIEL"}}],
    })
    [a] = wise.aquifers_at(-1.1, 39.5, http=http)
    assert (a.status, a.at_risk) == ("poor", True)


def test_theil_sen_ignores_one_odd_year():
    years = [(2000 + i, 100 - 0.5 * i) for i in range(10)]
    years[4] = (2004, 60.0)          # a pumping test or a bad reading
    assert chj_piezometry.theil_sen(years) == -0.5


def test_aquifer_names_in_title_case():
    assert _title("BAILÉN - GUARROMÁN - LINARES") == "Bailén - Guarromán - Linares"
    assert _title("ALUVIAL DEL GUADALQUIVIR - CURSO ALTO") == "Aluvial del Guadalquivir - Curso Alto"
    assert _title("LUCENA - L'ALCORA") == "Lucena - l'Alcora"
