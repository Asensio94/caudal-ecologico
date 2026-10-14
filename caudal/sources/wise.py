"""What the river basin plans themselves report about each control point, via the EEA.

Spain reports its 2022–2027 plans to the European Environment Agency (WISE, Water
Framework Directive). The EEA serves them as ArcGIS layers, the same for every basin:

- the groundwater body under the gauge: its quantitative status and whether it is at
  risk of failing the good quantitative status;
- the river water body at the gauge: the significant pressures the plan identified,
  of which abstractions and hydrological alterations (dams, regulation) bear on flow.

The ministry publishes the same layers, but its map server fails and its file downloads
sit behind an anti-bot challenge; the EEA copy needs neither.
"""
from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass

from . import session

BASE = "https://water.discomap.eea.europa.eu/arcgis/rest/services/WISE_WFD/"
GROUNDWATER = BASE + "WFD2022_GroundWaterBody_WM/MapServer/0/query"
GROUNDWATER_NAMES = BASE + "WFD2022_GroundWaterBody_WM/MapServer/2/query"   # names in Spanish, not translated
RIVERS = BASE + "WFD2022_SurfaceWaterBody_swSignificantPressureType_WM/MapServer/25/query"
VIEWER = "https://water.europa.eu/freshwater/resources/metadata/wfd-gis-layers"
SEARCH_METRES = 300

# WISE code lists: quantitative status 2 good, 3 poor; anything else is unknown.
QUANT_STATUS = {"2": "good", "3": "poor"}

# Pressures that take water out of the river or change its regime, in Spanish for the page.
FLOW_PRESSURES = {
    "P3-1": "extracción para regadío", "P3-2": "extracción para abastecimiento",
    "P3-3": "extracción para industria", "P3-4": "extracción para refrigeración",
    "P3-5": "extracción para hidroeléctrica", "P3-6": "extracción para piscifactorías",
    "P3-7": "otras extracciones",
    "P4-2-1": "presas o azudes hidroeléctricos", "P4-2-2": "presas o azudes de defensa",
    "P4-2-3": "presas o azudes de abastecimiento", "P4-2-4": "presas o azudes de riego",
    "P4-2-5": "presas o azudes de ocio", "P4-2-6": "presas o azudes industriales",
    "P4-2-7": "presas o azudes de navegación", "P4-2-8": "otras presas o azudes",
    "P4-2-9": "presas o azudes de uso desconocido u obsoleto",
    "P4-3-1": "regulación del caudal para regadío", "P4-3-2": "regulación del caudal por transporte",
    "P4-3-3": "regulación del caudal por hidroeléctrica", "P4-3-4": "regulación del caudal para abastecimiento",
    "P4-3-5": "regulación del caudal por acuicultura", "P4-3-6": "otra regulación del caudal",
}


@dataclass(frozen=True)
class Aquifer:
    code: str      # EU code, e.g. ES080MSBT080-133
    name: str
    status: str    # good, poor or unknown
    at_risk: bool  # at risk of failing the good quantitative status


@dataclass(frozen=True)
class RiverBody:
    code: str
    name: str
    flow_pressures: tuple[str, ...]   # FLOW_PRESSURES codes, in the order reported


def _point(lon: float, lat: float) -> dict:
    return {"geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects", "f": "json"}


def _get(http, url: str, params: dict) -> list[dict]:
    resp = http.get(url, params=params, timeout=60)
    resp.raise_for_status()
    body = resp.json()
    if "error" in body:
        raise RuntimeError(f"EEA query failed: {body['error']}")
    return body.get("features", [])


def aquifers_at(lon: float, lat: float, http=None) -> list[Aquifer]:
    """Groundwater bodies under the point; several where the plan stacks aquifers in horizons."""
    http = http or session()
    fields = "euGroundWaterBodyCode,groundWaterBodyName,gwQuantitativeStatusValue,gwAtRiskQuantitative"
    feats = _get(http, GROUNDWATER, {**_point(lon, lat), "outFields": fields, "returnGeometry": "false"})
    names = {f["attributes"]["thematicIdIdentifier"]: f["attributes"]["nameText"] for f in _get(
        http, GROUNDWATER_NAMES, {**_point(lon, lat), "outFields": "thematicIdIdentifier,nameText", "returnGeometry": "false"})}
    out = {}
    for f in feats:
        a = f["attributes"]
        out[a["euGroundWaterBodyCode"]] = Aquifer(
            a["euGroundWaterBodyCode"], (names.get(a["euGroundWaterBodyCode"]) or a["groundWaterBodyName"]).strip(),
            QUANT_STATUS.get(str(a["gwQuantitativeStatusValue"]), "unknown"), a["gwAtRiskQuantitative"] == "Yes")
    return sorted(out.values(), key=lambda x: x.code)


def flow_pressures(reported: str | None) -> tuple[str, ...]:
    """'P3-1 - Abstraction - Agriculture;P5-1 - …' → ('P3-1',), keeping only flow-related codes."""
    codes = [p.split(" - ")[0].strip() for p in (reported or "").split(";")]
    return tuple(c for c in codes if c in FLOW_PRESSURES)


def _distance_m(lon: float, lat: float, paths: list) -> float:
    """Shortest distance from the point to the polyline vertices, in metres (equirectangular)."""
    k = 111_320 * math.cos(math.radians(lat))
    return min(math.hypot((x - lon) * k, (y - lat) * 110_540) for path in paths for x, y in path)


def _plain(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.upper()) if unicodedata.category(c) != "Mn")


def river_body_at(lon: float, lat: float, code: str = "", river: str = "", http=None) -> RiverBody | None:
    """The plan's river water body at the gauge.

    With the water body code the plan gives (Júcar, Guadiana, Cantábrico), the reported body
    whose EU code ends with it. Without one (Guadalquivir), the nearest within SEARCH_METRES
    among those named after the gauge's river, so that a gauge by a confluence is not given
    the tributary's body.
    """
    http = http or session()
    fields = "euSurfaceWaterBodyCode,surfaceWaterBodyName,surfaceWaterBodyCategory,swSignificantPressureType"
    feats = _get(http, RIVERS, {**_point(lon, lat), "distance": SEARCH_METRES, "units": "esriSRUnit_Meter",
                                "outFields": fields, "returnGeometry": "true", "outSR": "4326"})
    feats = [f for f in feats if f["attributes"]["surfaceWaterBodyCategory"] == "RW"]
    if not feats:
        return None
    match = [f for f in feats if code and f["attributes"]["euSurfaceWaterBodyCode"].endswith(code)]
    if code and not match:
        return None   # the body the plan names is not where the gauge is: say nothing rather than guess
    if not match:
        named = [f for f in feats if _plain(river) and _plain(river) in _plain(f["attributes"]["surfaceWaterBodyName"])]
        if not named:
            return None
        feats = named
    best = match[0] if match else min(feats, key=lambda f: _distance_m(lon, lat, f["geometry"]["paths"]))
    a = best["attributes"]
    return RiverBody(a["euSurfaceWaterBodyCode"], a["surfaceWaterBodyName"].strip(),
                     flow_pressures(a["swSignificantPressureType"]))
