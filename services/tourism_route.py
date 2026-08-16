"""旅游路线规划：多景点串联 + 真实路网（支持当前定位或指定城市）"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from graph.parsers import parse_poi_map_result
from services.geocode import resolve_place
from services.halfday_trip import RouteFn, build_halfday_trip_maps
from tools.mcp_client import call_mcp_tool

from services.transport_modes import MODE_LABELS  # noqa: F401 — re-export


def _city_center(city: str) -> Optional[Dict[str, Any]]:
    if not city:
        return None
    r = resolve_place(city, city=city)
    if not r.get("error") and r.get("location"):
        return {
            "location": r["location"],
            "label": r.get("name") or city,
            "lnglat": r.get("lnglat"),
        }
    try:
        import json

        raw = call_mcp_tool(
            "get_city_poi",
            {"city": city.replace("市", ""), "category": "sightseeing", "page_size": 3},
        )
        data = json.loads(raw.strip()) if raw and raw.strip().startswith("{") else {}
        pm = data.get("poi_map") or {}
        center = pm.get("center") or {}
        if center.get("lnglat"):
            return {
                "location": center.get("location")
                or f"{center['lnglat'][0]},{center['lnglat'][1]}",
                "label": f"{city} · {center.get('name', city)}",
                "lnglat": center["lnglat"],
            }
    except Exception:
        pass
    return None


def _fetch_tourism_pois(location: str, city: str = "", max_each: int = 8) -> List[Dict[str, Any]]:
    """合并景点与美食 POI，去重后供路线选点。"""
    pois: List[Dict[str, Any]] = []
    seen = set()

    def add_from(raw: str):
        parsed, _ = parse_poi_map_result(raw)
        if not parsed:
            return
        for p in parsed.get("pois") or []:
            name = (p.get("name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            pois.append(dict(p))

    for kw, types, radius in (
        ("景点", "110000", 5000),
        ("风景名胜", "110000", 6000),
        ("美食", "050000", 3000),
    ):
        raw = call_mcp_tool(
            "amap_place_around",
            {
                "location": location,
                "keywords": kw,
                "types": types,
                "radius": radius,
                "page_size": max_each,
            },
        )
        add_from(raw)

    if city and len(pois) < 4:
        for cat in ("sightseeing", "food"):
            raw = call_mcp_tool(
                "get_city_poi",
                {"city": city.replace("市", ""), "category": cat, "page_size": 6},
            )
            add_from(raw)

    return pois


def build_tourism_route_maps(
    *,
    origin_loc: str,
    origin_label: str,
    route_fn: RouteFn,
    city: str = "",
    mode: str = "walking",
    max_stops: int = 5,
) -> Optional[Dict[str, Any]]:
    loc = origin_loc
    label = origin_label or "起点"
    lnglat = None

    if not loc or "," not in loc:
        center = _city_center(city)
        if not center:
            return None
        loc = center["location"]
        label = center["label"]
        lnglat = center.get("lnglat")

    pois = _fetch_tourism_pois(loc, city, max_each=10)
    if not pois:
        return None

    def poi_fn():
        try:
            olng, olat = loc.split(",", 1)[:2]
            center_ll = [float(olng), float(olat)]
        except (ValueError, TypeError):
            center_ll = lnglat or [0, 0]
        return {
            "type": "poi_map",
            "title": "旅游路线候选点",
            "center": {"name": label, "location": loc, "lnglat": center_ll},
            "pois": pois,
        }

    result = build_halfday_trip_maps(
        loc,
        label,
        route_fn,
        poi_fn,
        mode=mode,
        max_stops=max_stops,
    )
    if not result:
        return None

    route_map = result["route_map"]
    poi_map = result["poi_map"]
    route_map["trip_type"] = "tourism"
    route_map["mode_label"] = MODE_LABELS.get(mode, mode)
    stops = route_map.get("stops") or []
    stop_names = [s.get("name", "") for s in stops if s.get("name")]
    city_part = f"{city} · " if city else ""
    route_map["summary"] = (
        f"{city_part}旅游路线：{route_map.get('origin', {}).get('name', label)}"
        f" → {route_map.get('destination', {}).get('name', '终点')}"
        + (f"（途经 {' · '.join(stop_names)}）" if stop_names else "")
    )
    poi_map["title"] = "旅游路线途经点"

    ctx = result.get("context_text", "").replace("半日游", "旅游")
    ctx = ctx.replace("半日游结构化路线", "旅游路线规划")
    result["context_text"] = ctx
    result["route_map"] = route_map
    result["poi_map"] = poi_map
    return result
