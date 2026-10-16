from datetime import date

from caudal import i18n, plan_fr
from caudal.compliance import DayResult, Status
from caudal.signals import river_flow
from caudal.sources import hubeau, vigieau
from caudal.wfd import body_name, file_name, title_fr


# --- Hub'Eau ----------------------------------------------------------------------

def test_hubeau_rows_become_daily_flows_in_m3s_with_their_status():
    rows = [
        {"code_site": "O9000010", "date_obs_elab": "2026-10-02", "resultat_obs_elab": 1500.0,
         "libelle_statut": "Donnée brute"},
        {"code_site": "O9000010", "date_obs_elab": "2026-10-01", "resultat_obs_elab": 2000.0,
         "libelle_statut": hubeau.VALIDATED},
        {"code_site": "O9000010", "date_obs_elab": "2026-10-03", "resultat_obs_elab": None},
    ]
    [a, b, c] = hubeau.to_flows(rows)["O9000010"]
    assert (a.day, a.mean, a.status) == (date(2026, 10, 1), 2.0, hubeau.VALIDATED)
    assert (b.mean, b.status) == (1.5, "Donnée brute")
    assert c.mean is None and c.readings == 0


# --- SDAGE table C3 ---------------------------------------------------------------

TABLE = """Bassin;Riviere;Point nodal;Code Station Hydro1;Code Station Hydro2;DOE;DCR
Charente;Le Né;Né à Salles d'Angles;R4130010;R4130011;0.15;0.05
Garonne;La Séoune;Séoune à St Pierre de Clairac;O6625010;;0.2;0,08
Lot;Le Lot;Lot à Aiguillon;O8231530;;17/13;5
Adour;L'Adour;Adour à Aire;;;3;1
Adour;Le Luy;Luy à Saint-Pandelon;Q3464010;;1.2;
"""


def test_table_c3_is_parsed_with_both_gauges_and_written_doe():
    points = plan_fr.parse_table(TABLE)
    assert [p.codes for p in points] == [("R4130010", "R4130011"), ("O6625010",), ("O8231530",), (), ("Q3464010",)]
    assert points[1].dcr == 0.08 and points[2].doe == "17/13" and points[4].dcr is None
    assert plan_fr.doe_value("17/13") is None and plan_fr.doe_value("0,2") == 0.2


def site(name):
    return {"name": name, "river": "", "insee": "16359", "department": "16", "lon": -0.35, "lat": 45.6,
            "catchment_km2": None}


def test_build_reads_the_replacement_gauge_and_says_why_others_stay_out():
    points = plan_fr.parse_table(TABLE)
    sites = {"R4130011": site("Le Né [bras rive gauche] à Salles-d'Angles"), "O6625010": site("La Séoune à Saint-Pierre")}
    stations, reqs, unread = plan_fr.build(points, {"R4130011", "O6625010"}, sites)
    assert [s["station_id"] for s in stations] == ["fr-R4130011", "fr-O6625010"]
    ne, seoune = stations
    assert ne["river"] == "Né" and ne["municipality"] == "16359" and ne["roea"] == ""
    assert "R4130010" in ne["note"] and "un bras" in ne["note"]   # moved gauge, one arm of the river
    assert seoune["note"] == ""
    assert reqs[0]["m01"] == reqs[0]["m12"] == "0.05" and reqs[0]["objective"] == "0.15"
    assert reqs[0]["legal_ref"] == plan_fr.LEGAL_REF
    assert len(unread) == 3
    assert "Hub'Eau ne publie pas" in unread[0] and "aucune station" in unread[1] and "pas de DCR" in unread[2]


# --- Loire-Bretagne and Rhône-Méditerranée transcriptions ----------------------------

def lb_row(point, river, location, dcr, code="", agency="", reason="", dsa="1,0"):
    return {"point": point, "river": river, "location": location, "doe": "2,5", "dsa": dsa, "dcr": dcr,
            "pdf_page": "113", "agency_code": agency, "code": code, "reason": reason}


def rm_row(id, river, location, dcr, code="", reason="", revisable="0"):
    return {"id": id, "department": "26", "river": river, "location": location, "station_state": "existante",
            "water_body_code": "FRDR10", "doe": "non pertinent", "dcr": dcr, "revisable": revisable,
            "pdf_page": "250", "code": code, "reason": reason}


def test_labels_read_like_the_sdage():
    assert plan_fr._label("Mayenne", "Chambellay") == "Mayenne à Chambellay"
    assert plan_fr._label("Les Usses", "Les Usses aval") == "Les Usses aval"
    assert plan_fr._label("Lay", "aval immédiat de la confluence") == "Lay, aval immédiat de la confluence"
    assert plan_fr._label("Vilaine", "Au pont-de-Cran") == "Vilaine, au pont-de-Cran"


def test_loire_bretagne_keeps_the_dsa_and_says_when_the_agency_names_another_gauge():
    points = plan_fr.loire_bretagne([
        lb_row("Bl1", "Blavet", "Inzinzac-Lochrist", "0,9", code="J5712010", agency="J5712011"),
        lb_row("Rce", "Rance", "entre Saint-Juvas et Tréfumel", "0,1", reason="aucune station ne porte ce nom"),
    ])
    sites = {"J5712010": site("Le Blavet à Inzinzac-Lochrist")}
    basin = plan_fr.BASINS[plan_fr.LB]
    [blavet], [req], [rance] = plan_fr.build(points, {"J5712010"}, sites, basin)
    assert blavet["basin"] == "loire-bretagne" and "J5712011" in blavet["note"]
    assert req["m07"] == "0.9" and req["objective"] == "2,5" and req["alert"] == "1,0"
    assert req["legal_ref"].endswith("point Bl1 (p. 113)") and req["source_url"].endswith("#page=113")
    assert rance == "Rance, entre Saint-Juvas et Tréfumel : aucune station ne porte ce nom"


def test_rhone_mediterranee_flags_revisable_values_and_leaves_out_undefined_dcr():
    points = plan_fr.rhone_mediterranee([
        rm_row("7", "Drôme", "Saillans", "0,8", code="V4264010", revisable="1"),
        rm_row("8", "Roubion", "Soyans", "à définir"),
    ])
    basin = plan_fr.BASINS[plan_fr.RM]
    [drome], [req], [roubion] = plan_fr.build(points, {"V4264010"}, {"V4264010": site("La Drôme à Saillans")}, basin)
    assert drome["water_body_code"] == "FRDR10" and "susceptibles d'être modifiés" in drome["note"]
    assert req["objective"] == "" and req["alert"] == "" and req["legal_ref"].endswith("tableau 7C, point 7")
    assert roubion == "Roubion à Soyans : le tableau 7C ne donne pas de DCR chiffré pour ce point (« à définir »)"


def test_the_transcriptions_in_the_repository_load():
    for slug, load in ((plan_fr.LB, plan_fr.loire_bretagne), (plan_fr.RM, plan_fr.rhone_mediterranee)):
        points = load(plan_fr.read_transcription(slug))
        assert len(points) > 50
        assert all(p.codes or p.why or p.dcr is None for p in points)   # every point without a gauge says why


# --- VigiEau ----------------------------------------------------------------------

class Resp:
    def __init__(self, status, payload=None):
        self.status_code, self.payload = status, payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class Http:
    def __init__(self, resp):
        self.resp = resp

    def get(self, *a, **kw):
        return self.resp


def test_vigieau_takes_the_strictest_surface_zone():
    payload = [
        {"type": "SUP", "niveauGravite": "alerte", "code": "A", "nom": "Zone A", "arrete": {}},
        {"type": "SUP", "niveauGravite": "crise", "code": "B", "nom": "Zone B",
         "arrete": {"dateDebutValidite": "2026-09-01T00:00:00", "dateFinValidite": "2026-10-31",
                    "cheminFichier": "https://example.org/arrete.pdf"}},
        {"type": "SOU", "niveauGravite": "crise", "code": "C", "nom": "Nappe"},
    ]
    z = vigieau.zone_at(0.0, 45.0, Http(Resp(200, payload)))
    assert (z["level"], z["zone_code"], z["order_from"], z["order_to"]) == ("crise", "B", "2026-09-01", "2026-10-31")


def test_vigieau_without_a_zone_is_none():
    assert vigieau.zone_at(0.0, 45.0, Http(Resp(404))) is None
    assert vigieau.zone_at(0.0, 45.0, Http(Resp(200, []))) is None


# --- Names and formats ------------------------------------------------------------

def test_french_names_in_capitals_and_in_mixed_case():
    assert title_fr("LA GARONNE DU CONFLUENT DE L'ARIÈGE AU CONFLUENT DE L'AVEYRON") == \
        "La Garonne du confluent de l'Ariège au confluent de l'Aveyron"
    assert title_fr("Le Boublon et Ses Affluents Depuis la Source Jusqu'A la Confluence Avec la Bouble") == \
        "Le Boublon et ses affluents depuis la source jusqu'à la confluence avec la Bouble"
    assert body_name("Saint-Jean-de-Luz", "FR") == "Saint-Jean-de-Luz"
    assert file_name("water_bodies.csv", "ES") == "water_bodies.csv"
    assert file_name("water_bodies.csv", "FR") == "water_bodies_fr.csv"


def test_number_formats_follow_the_language():
    nnbsp = " "
    assert i18n.n(46709, "es") == "46.709" and i18n.n(46709, "fr") == f"46{nnbsp}709"
    assert i18n.d(1234.5, "es") == "1.234,50" and i18n.d(1234.5, "fr") == f"1{nnbsp}234,50"
    assert i18n.p(0.15, "es") == "15 %" and i18n.p(0.15, "fr") == f"15{nnbsp}%"
    assert i18n.long_date(date(2026, 11, 1), "fr") == "1er novembre 2026"
    assert i18n.t("fr", "country_ES") == "Espagne" and i18n.t("fr", "countries") == "Pays"


# --- signals.json -----------------------------------------------------------------

def french_row():
    results = [DayResult(date(2026, 10, 14), 0.0, 0.05, None, Status.BELOW, provisional=True)]
    return {"station": {"station_id": "fr-R4130011", "name": "Le Né à Salles-d'Angles", "river": "Né",
                        "water_body_code": "", "water_body_name": "Né à Salles d'Angles", "lon": "-0.35",
                        "lat": "45.6", "country": "FR", "municipality": "16359"},
            "results": results, "latest": results[-1], "below_days": 1, "context": None}


def test_french_signals_carry_country_insee_and_the_dcr():
    [s] = river_flow([french_row()])
    assert s["country"] == "FR" and s["municipalities"] == ["16359"]
    assert s["url"].endswith("france.html#fr-R4130011")
    assert "caudal de crisis (DCR) según datos provisionales" in s["title"]
    assert s["details"]["threshold"] == "DCR" and s["details"]["provisional"] is True
