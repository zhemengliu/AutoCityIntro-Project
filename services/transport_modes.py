"""出行方式：展示标签与高德 API 映射"""
from __future__ import annotations

from typing import Optional, Tuple

MODE_LABELS = {
    "walking": "步行",
    "driving": "驾车",
    "transit": "公交",
    "metro": "地铁",
    "riding": "骑行",
    "rail": "铁路",
    "train": "铁路",
    "flight": "飞机",
    "plane": "飞机",
}

MODE_ALIASES = {
    "metro": "transit",
    "train": "transit",
    "rail": "transit",
    "plane": "flight",
    "bus": "transit",
}

AMAP_ROUTE_MODES = frozenset({"walking", "driving", "transit", "riding"})

SEGMENT_COLORS = {
    "walking": "#10b981",
    "driving": "#0d8ecf",
    "transit": "#8b5cf6",
    "metro": "#8b5cf6",
    "riding": "#f59e0b",
    "rail": "#6366f1",
    "train": "#6366f1",
    "flight": "#ec4899",
}


def normalize_mode(mode: str) -> str:
    m = (mode or "walking").strip().lower()
    return MODE_ALIASES.get(m, m)


def mode_label(mode: str) -> str:
    return MODE_LABELS.get(normalize_mode(mode), mode or "出行")


def is_aerial_mode(mode: str) -> bool:
    return normalize_mode(mode) in ("flight",)


def resolve_amap_mode(mode: str) -> Optional[str]:
    """返回可用于 amap_route_planning 的 mode；飞机等返回 None。"""
    m = normalize_mode(mode)
    if is_aerial_mode(m):
        return None
    if m in AMAP_ROUTE_MODES:
        return m
    if m in ("metro", "train", "rail"):
        return "transit"
    return "walking"


def pick_segment_mode(
    distance_m: Optional[int],
    *,
    default: str = "walking",
    category: str = "",
) -> str:
    """按距离与站点类型建议段内出行方式。"""
    if category == "food" and (distance_m or 0) < 1500:
        return "walking"
    d = distance_m or 0
    if d > 8000:
        return "driving"
    if d > 2500:
        return "transit"
    if d > 800:
        return "walking"
    return normalize_mode(default) or "walking"


def segment_color(mode: str) -> str:
    return SEGMENT_COLORS.get(normalize_mode(mode), "#0d8ecf")


def format_segment_label(
    mode: str,
    distance: Optional[int] = None,
    duration_text: str = "",
    walking_distance: Optional[int] = None,
) -> str:
    parts = [mode_label(mode)]
    if distance is not None:
        try:
            d = int(distance)
            parts.append(f"{d}m" if d < 1000 else f"{d / 1000:.1f}km")
        except (TypeError, ValueError):
            pass
    if walking_distance is not None:
        try:
            wd = int(walking_distance)
            if wd > 0:
                parts.append(f"步行{wd}m")
        except (TypeError, ValueError):
            pass
    if duration_text:
        parts.append(duration_text)
    return " · ".join(parts)
