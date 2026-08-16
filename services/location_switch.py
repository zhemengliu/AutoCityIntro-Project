"""从对话中识别并解析定位切换（城市/地点 → 坐标）"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, Optional

from services.geocode import resolve_place
from services.location_utils import format_location_label, parse_city_from_regeo_text

_SWITCH_PATTERNS = [
    re.compile(
        r"(?:切换|改|换|移到|定位到|定位在|定在|设为|改为)(?:到|为|在)?\s*"
        r"([\u4e00-\u9fa5]{2,10}(?:市|省|县|区)?)"
    ),
    re.compile(r"(?:我现在|我在|目前在|人现在在)\s*([\u4e00-\u9fa5]{2,10}(?:市)?)"),
    re.compile(
        r"(?:以|从)\s*([\u4e00-\u9fa5]{2,10}(?:市)?)\s*(?:为|作为)?(?:起点|中心|出发|定位)"
    ),
    re.compile(r"去\s*([\u4e00-\u9fa5]{2,10}(?:市)?)\s*(?:玩|旅游|游玩|旅行)"),
]

_SKIP_NAMES = frozenset(
    {
        "这里",
        "这儿",
        "当前",
        "当前位置",
        "我的位置",
        "附近",
        "周边",
        "当地",
        "本地",
    }
)


def _clean_place(name: str) -> str:
    s = (name or "").strip().rstrip("市区县省")
    if s.endswith("市") and len(s) > 2:
        return s
    return s


def extract_switch_place(text: str) -> Optional[str]:
    t = (text or "").strip()
    for pat in _SWITCH_PATTERNS:
        m = pat.search(t)
        if not m:
            continue
        place = _clean_place(m.group(1))
        if not place or len(place) < 2 or place in _SKIP_NAMES:
            continue
        if any(x in place for x in ("附近", "周边", "什么", "怎么")):
            continue
        return place
    return None


def try_switch_location_from_message(
    text: str,
    *,
    call_mcp_regeocode: Optional[Callable[[str], str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    若用户要求切换定位，解析地名并返回 {location, label, city, place_name}。
  失败返回 None（不阻断正常对话）。
    """
    place = extract_switch_place(text)
    if not place:
        return None

    resolved = resolve_place(place, city=place)
    if resolved.get("error"):
        if call_mcp_regeocode:
            from tools.mcp_client import call_mcp_tool

            raw = call_mcp_tool("amap_geocode", {"address": place})
            if "坐标为" in raw:
                loc = raw.split("坐标为：", 1)[-1].strip().split("）")[0].strip()
                if "," in loc:
                    resolved = {
                        "name": place,
                        "location": loc,
                        "lnglat": [float(loc.split(",")[0]), float(loc.split(",")[1])],
                        "city": place,
                    }
        if resolved.get("error"):
            return None

    loc = resolved.get("location") or ""
    if not loc or "," not in loc:
        return None

    city = resolved.get("city") or place.replace("市", "") + "市"
    label = resolved.get("name") or place
    if call_mcp_regeocode:
        try:
            regeo = call_mcp_regeocode(loc)
            c = parse_city_from_regeo_text(regeo)
            if c:
                city = c
            for line in regeo.splitlines():
                if line.startswith("地址："):
                    addr = line.split("：", 1)[-1].strip()
                    label = format_location_label(city, "", addr) or label
                    break
        except Exception:
            pass

    from services.city_context import normalize_city_display, normalize_city_key

    city_key = normalize_city_key(city or place)
    lnglat = resolved.get("lnglat")
    if not lnglat:
        try:
            lnglat = [float(loc.split(",")[0]), float(loc.split(",")[1])]
        except (ValueError, TypeError, IndexError):
            lnglat = None
    return {
        "location": loc,
        "label": label,
        "city": normalize_city_display(city_key),
        "city_key": city_key,
        "lnglat": lnglat,
        "place_name": place,
    }
