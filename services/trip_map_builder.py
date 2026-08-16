"""将结构化行程转为可绘制的 route_map（点连线 + 段标注）"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional

from services.halfday_trip import RouteFn, _format_duration, _merge_paths, _parse_lnglat, _plan_segment
from services.transport_modes import (
    format_segment_label,
    is_aerial_mode,
    mode_label,
    normalize_mode,
    pick_segment_mode,
    resolve_amap_mode,
    segment_color,
)

TripRouteFn = Callable[[str, str, str], Optional[Dict[str, Any]]]


def _loc_from_stop(stop: Dict[str, Any]) -> str:
    if stop.get("location"):
        return str(stop["location"])
    ll = stop.get("lnglat")
    if ll and len(ll) >= 2:
        return f"{ll[0]},{ll[1]}"
    return ""


def _lnglat_from_stop(stop: Dict[str, Any]) -> Optional[List[float]]:
    ll = stop.get("lnglat")
    if ll and len(ll) >= 2:
        try:
            return [float(ll[0]), float(ll[1])]
        except (TypeError, ValueError):
            pass
    loc = _loc_from_stop(stop)
    if loc and "," in loc:
        try:
            return _parse_lnglat(loc)
        except (ValueError, TypeError):
            return None
    return None


def _straight_path(a: List[float], b: List[float], points: int = 16) -> List[List[float]]:
    if not a or not b:
        return []
    out: List[List[float]] = []
    for i in range(points + 1):
        t = i / points
        out.append([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t])
    return out


def _haversine_m(a: List[float], b: List[float]) -> int:
    lng1, lat1 = a
    lng2, lat2 = b
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return int(2 * r * math.asin(math.sqrt(x)))


def _plan_aerial_segment(a: Dict[str, Any], b: Dict[str, Any], mode: str) -> Dict[str, Any]:
    alng = _lnglat_from_stop(a) or [0, 0]
    blng = _lnglat_from_stop(b) or [0, 0]
    dist = _haversine_m(alng, blng)
    path = _straight_path(alng, blng)
    return {
        "path": path,
        "distance": dist,
        "duration": max(600, dist // 800),
        "duration_text": mode_label(mode),
        "mode": normalize_mode(mode),
        "mode_label": mode_label(mode),
        "walking_distance": 0,
        "path_fallback": True,
    }


def build_route_map_from_trip(
    trip: Dict[str, Any],
    route_fn: TripRouteFn,
    *,
    default_mode: str = "walking",
    city: str = "",
) -> Optional[Dict[str, Any]]:
    stops = list(trip.get("stops") or [])
    if len(stops) < 2:
        timeline = trip.get("timeline") or []
        if timeline:
            from services.trip_store import normalize_trip

            stops = normalize_trip(trip).get("stops") or []
    if len(stops) < 2:
        return None

    chain: List[Dict[str, Any]] = []
    for s in stops:
        lnglat = _lnglat_from_stop(s)
        loc = _loc_from_stop(s)
        if not lnglat or not loc:
            continue
        chain.append(
            {
                "name": s.get("name") or "站点",
                "location": loc,
                "lnglat": lnglat,
                "time": s.get("time", ""),
                "category": s.get("category", ""),
            }
        )
    if len(chain) < 2:
        return None

    route_meta: Dict[tuple, Dict[str, Any]] = {}
    for r in trip.get("routes") or []:
        key = (r.get("from", ""), r.get("to", ""))
        route_meta[key] = r

    path_segments: List[List[List[float]]] = []
    segment_paths: List[Dict[str, Any]] = []
    segments_meta: List[Dict[str, Any]] = []
    total_distance = 0
    total_duration = 0

    for i in range(len(chain) - 1):
        a, b = chain[i], chain[i + 1]
        meta = route_meta.get((a["location"], b["location"]), {})
        seg_mode = normalize_mode(meta.get("mode") or default_mode)
        if not meta.get("mode"):
            dist_est = _haversine_m(a["lnglat"], b["lnglat"])
            seg_mode = pick_segment_mode(dist_est, default=default_mode, category=b.get("category", ""))

        if is_aerial_mode(seg_mode):
            seg = _plan_aerial_segment(a, b, seg_mode)
        else:
            amap_mode = resolve_amap_mode(seg_mode) or "walking"
            seg = _plan_segment(route_fn, a["location"], b["location"], amap_mode)
            if seg:
                seg["mode"] = seg_mode
                seg["mode_label"] = mode_label(seg_mode)

        if not seg or not seg.get("path"):
            seg = _plan_aerial_segment(a, b, seg_mode)

        path_segments.append(seg["path"])
        try:
            total_distance += int(seg.get("distance") or 0)
        except (TypeError, ValueError):
            pass
        try:
            total_duration += int(seg.get("duration") or 0)
        except (TypeError, ValueError):
            pass

        walking_distance = seg.get("walking_distance")
        if walking_distance is None and seg_mode in ("transit", "metro"):
            walking_distance = seg.get("distance")

        label = format_segment_label(
            seg_mode,
            seg.get("distance"),
            seg.get("duration_text", ""),
            walking_distance,
        )
        mid_idx = max(0, len(seg["path"]) // 2)
        mid = seg["path"][mid_idx] if seg.get("path") else a["lnglat"]

        seg_info = {
            "from": a["name"],
            "to": b["name"],
            "from_time": a.get("time", ""),
            "to_time": b.get("time", ""),
            "distance": seg.get("distance"),
            "walking_distance": walking_distance,
            "duration_text": seg.get("duration_text", ""),
            "mode": seg_mode,
            "mode_label": mode_label(seg_mode),
            "label": label,
            "midpoint": mid,
            "color": segment_color(seg_mode),
        }
        segments_meta.append(seg_info)
        segment_paths.append(
            {
                "path": seg["path"],
                "stroke_color": segment_color(seg_mode),
                "stroke_style": "dashed" if is_aerial_mode(seg_mode) else "solid",
                **seg_info,
            }
        )

    full_path = _merge_paths(path_segments)
    if len(full_path) < 2:
        return None

    first, last = chain[0], chain[-1]
    stop_markers = [
        {
            "order": idx + 1,
            "name": p["name"],
            "lnglat": p["lnglat"],
            "location": p["location"],
            "time": p.get("time", ""),
            "category": p.get("category", ""),
        }
        for idx, p in enumerate(chain)
    ]

    title = trip.get("title") or f"{trip.get('city', '')}行程".strip() or "旅游行程"
    names = [p["name"] for p in chain]
    summary = f"{title}：{' → '.join(names)}"
    if total_distance:
        summary += f" · 总路程约 {total_distance}m"
    if total_duration:
        summary += f" · 路上约 {_format_duration(total_duration)}"

    route_map: Dict[str, Any] = {
        "type": "route",
        "trip_type": "itinerary",
        "mode": default_mode,
        "mode_label": mode_label(default_mode),
        "city": city or trip.get("city", ""),
        "origin": {"name": first["name"], "location": first["location"], "lnglat": first["lnglat"]},
        "destination": {"name": last["name"], "location": last["location"], "lnglat": last["lnglat"]},
        "stops": stop_markers[1:-1] if len(stop_markers) > 2 else [],
        "path": full_path,
        "path_fallback": False,
        "distance": total_distance,
        "duration_text": _format_duration(total_duration),
        "segments": segments_meta,
        "segment_paths": segment_paths,
        "summary": summary,
    }

    from services.amap_uri import attach_navi_uri

    attach_navi_uri(route_map)
    return route_map


def enrich_trip_with_map(
    trip: Dict[str, Any],
    route_fn: TripRouteFn,
    *,
    city: str = "",
    default_mode: str = "walking",
) -> Dict[str, Any]:
    out = dict(trip)
    if out.get("route_map") and out["route_map"].get("segment_paths"):
        return out
    rm = build_route_map_from_trip(out, route_fn, default_mode=default_mode, city=city)
    if rm:
        out["route_map"] = rm
    return out
