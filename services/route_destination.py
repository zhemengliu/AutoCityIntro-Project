"""路线终点消歧：优先使用行程/会话/画像中的本地 POI 坐标。"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _normalize_poi_name(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r"^第\d+站\s*", "", name)
    return name


def names_match(query: str, candidate: str) -> bool:
    q = _normalize_poi_name(query)
    c = _normalize_poi_name(candidate)
    if not q or not c:
        return False
    if q == c or q in c or c in q:
        return True
    # 「福音堂」匹配「第3站 福音堂」
    return q in c.replace(" ", "")


def poi_location(poi: Dict[str, Any]) -> str:
    loc = (poi.get("location") or "").strip()
    if loc and "," in loc:
        return loc
    lnglat = poi.get("lnglat")
    if isinstance(lnglat, (list, tuple)) and len(lnglat) >= 2:
        return f"{lnglat[0]},{lnglat[1]}"
    return ""


def _scan_poi_candidates(dest_name: str, pois: List[Dict[str, Any]], source: str) -> Optional[Dict[str, str]]:
    for poi in pois or []:
        name = poi.get("name") or ""
        display = poi.get("display_name") or ""
        if not (names_match(dest_name, name) or (display and names_match(dest_name, display))):
            continue
        loc = poi_location(poi)
        if loc:
            label = display or _normalize_poi_name(name) or name
            return {"destination": loc, "name": label, "source": source}
    return None


def _scan_stops(dest_name: str, stops: List[Dict[str, Any]], source: str) -> Optional[Dict[str, str]]:
    return _scan_poi_candidates(dest_name, stops, source)


def find_destination_in_message(dest_name: str, msg: Dict[str, Any]) -> Optional[Dict[str, str]]:
    if msg.get("role") != "assistant":
        return None
    trip = msg.get("trip_plan") or {}
    hit = _scan_stops(dest_name, trip.get("stops") or [], "trip_plan")
    if hit:
        return hit
    rm = msg.get("route_map") or {}
    dest = rm.get("destination") or {}
    if names_match(dest_name, dest.get("name", "")):
        loc = poi_location(dest)
        if loc:
            return {"destination": loc, "name": dest.get("name", ""), "source": "route_map_dest"}
    hit = _scan_stops(dest_name, rm.get("stops") or [], "route_map_stops")
    if hit:
        return hit
    pois = (msg.get("poi_map") or {}).get("pois") or []
    return _scan_poi_candidates(dest_name, pois, "poi_map")


def find_destination_in_history(dest_name: str, history: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    for msg in reversed(history or []):
        hit = find_destination_in_message(dest_name, msg)
        if hit:
            return hit
    return None


def find_destination_in_profile(dest_name: str, profile: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    if not profile:
        return None
    for poi in profile.get("recent_pois") or []:
        name = poi.get("name") or ""
        if not names_match(dest_name, name):
            continue
        loc = (poi.get("location") or "").strip()
        if loc:
            return {"destination": loc, "name": name, "source": "profile"}
    return None


def find_destination_in_state(
    dest_name: str,
    *,
    trip_plan: Optional[Dict[str, Any]] = None,
    route_map: Optional[Dict[str, Any]] = None,
    poi_map: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, str]]:
    fake_msgs = []
    if trip_plan:
        fake_msgs.append({"role": "assistant", "trip_plan": trip_plan})
    if route_map:
        fake_msgs.append({"role": "assistant", "route_map": route_map})
    if poi_map:
        fake_msgs.append({"role": "assistant", "poi_map": poi_map})
    return find_destination_in_history(dest_name, fake_msgs)


def resolve_route_planning_args(
    dest_name: str,
    *,
    origin: str,
    mode: str = "driving",
    city: str = "",
    session_history: Optional[List[Dict[str, Any]]] = None,
    profile: Optional[Dict[str, Any]] = None,
    trip_plan: Optional[Dict[str, Any]] = None,
    route_map: Optional[Dict[str, Any]] = None,
    poi_map: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    构造 amap_route_planning 参数。
    若会话/画像/当前状态中有同名 POI 坐标，优先用坐标，避免全国重名误匹配。
    """
    args: Dict[str, Any] = {"origin": origin, "destination": dest_name, "mode": mode}
    if city:
        args["city"] = city

    hit = (
        find_destination_in_state(dest_name, trip_plan=trip_plan, route_map=route_map, poi_map=poi_map)
        or find_destination_in_history(dest_name, session_history or [])
        or find_destination_in_profile(dest_name, profile)
    )
    if hit:
        args["destination"] = hit["destination"]
        args["_resolved_name"] = hit["name"]
        args["_resolved_source"] = hit["source"]
    return args
