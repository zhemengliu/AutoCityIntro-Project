"""对话城市上下文：识别城市、解析市中心坐标、与会话绑定"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from graph.intent import extract_query_city
from services.geocode import resolve_place

_CITY_MENTION_PATTERNS = [
    re.compile(r"^([\u4e00-\u9fa5]{2,8})(?:市)?有(?:哪些|什么|啥)"),
    re.compile(r"(?:在|来)([\u4e00-\u9fa5]{2,8})(?:市)?(?:玩|游|逛|旅游|出差|生活)?"),
    re.compile(r"去([\u4e00-\u9fa5]{2,8})(?:市)?(?:玩|旅游|游玩|旅行|看看)"),
    re.compile(
        r"([\u4e00-\u9fa5]{2,8})(?:市)?(?:的)?"
        r"(?:天气|景点|美食|旅游|好玩|怎么样|介绍|攻略|路线|行程)"
    ),
    re.compile(r"介绍(?:一下)?\s*([\u4e00-\u9fa5]{2,8})(?:市)?"),
    re.compile(r"([\u4e00-\u9fa5]{2,8})(?:市)?有什么(?:好玩|好吃|推荐)"),
    re.compile(r"([\u4e00-\u9fa5]{2,8})(?:市)?(?:三日|两日|一日|几天|周末)"),
    re.compile(r"(?:我想|打算|准备)(?:去|到)([\u4e00-\u9fa5]{2,8})(?:市)?"),
]

_SKIP = frozenset(
    {
        "哪些",
        "什么",
        "哪里",
        "哪儿",
        "附近",
        "周边",
        "周围",
        "这里",
        "当地",
        "国内",
        "我国",
        "全国",
        "今天",
        "明天",
        "周末",
        "当地",
        "本地",
        "当前",
    }
)


def normalize_city_key(city: str) -> str:
    """会话存储用：不含「市」的短名，如 西安"""
    s = (city or "").strip().replace(" ", "")
    return s.rstrip("市区县省")


def normalize_city_display(city: str) -> str:
    key = normalize_city_key(city)
    if not key:
        return ""
    return key if key.endswith("市") else f"{key}市"


def extract_conversation_city(text: str) -> Optional[str]:
    """从对话中提取目标城市（规则，优先 extract_query_city）。"""
    found = extract_query_city(text)
    if found:
        return normalize_city_key(found)
    t = (text or "").strip()
    if re.match(r"^(附近|周边|周围)", t):
        return None
    for pat in _CITY_MENTION_PATTERNS:
        m = pat.search(t)
        if not m:
            continue
        city = normalize_city_key(m.group(1))
        if not city or len(city) < 2 or city in _SKIP:
            continue
        if any(x in city for x in ("附近", "周边", "什么", "怎么", "哪里")):
            continue
        return city
    return None


def resolve_city_center(city: str) -> Optional[Dict[str, Any]]:
    """将城市名解析为市中心坐标与展示标签。"""
    key = normalize_city_key(city)
    if not key:
        return None

    from services.tourism_route import _city_center

    center = _city_center(key)
    if center and center.get("location"):
        display = normalize_city_display(key)
        label = center.get("label") or f"{display} · 市中心"
        if display not in label:
            label = f"{display} · {label.split('·')[-1].strip()}" if "·" in label else f"{display} · 市中心"
        lnglat = center.get("lnglat")
        if not lnglat and "," in center["location"]:
            parts = center["location"].split(",", 1)
            lnglat = [float(parts[0]), float(parts[1])]
        return {
            "city": display,
            "city_key": key,
            "location": center["location"],
            "label": label,
            "lnglat": lnglat,
        }

    r = resolve_place(key, city=key)
    if r.get("error") or not r.get("location"):
        return None
    display = normalize_city_display(key)
    return {
        "city": display,
        "city_key": key,
        "location": r["location"],
        "label": f"{display} · {r.get('name') or '市中心'}",
        "lnglat": r.get("lnglat"),
    }


def should_update_active_city(message_city: str, active_city: str) -> bool:
    if not message_city:
        return False
    if not active_city:
        return True
    return normalize_city_key(message_city) != normalize_city_key(active_city)


def build_location_update_from_city(city: str) -> Optional[Dict[str, Any]]:
    resolved = resolve_city_center(city)
    if not resolved:
        return None
    return {
        "location": resolved["location"],
        "label": resolved["label"],
        "city": resolved["city"],
        "city_key": resolved["city_key"],
        "lnglat": resolved.get("lnglat"),
        "place_name": resolved["city_key"],
        "source": "conversation_city",
    }


def try_apply_city_from_message(
    text: str,
    active_city: str = "",
    *,
    force_same: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    若消息中提到城市且与当前会话城市不同（或 force_same），返回定位更新包。
    显式「切换定位」由 location_switch 处理，此处覆盖「报城市名」类对话。
    """
    from services.location_switch import extract_switch_place

    if extract_switch_place(text):
        return None

    msg_city = extract_conversation_city(text)
    if not msg_city:
        return None
    if not force_same and not should_update_active_city(msg_city, active_city):
        return None
    return build_location_update_from_city(msg_city)
