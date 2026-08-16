"""城市探索导航：路况、POI、天气、空气质量"""
from __future__ import annotations

import os
from typing import Any, Dict, List

import requests

from graph.parsers import parse_poi_map_result
from services.traffic_status import query_traffic_status
from tools.mcp_client import call_mcp_tool

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

POI_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "food": {
        "keywords": "美食",
        "types": "050000",
        "radius": 2500,
        "poi_category": "food",
        "title": "周边美食",
    },
    "hotel": {
        "keywords": "酒店",
        "types": "100000",
        "radius": 3500,
        "poi_category": "hotel",
        "title": "附近住宿",
        "fallback_keywords": ["住宿", "宾馆", "民宿"],
    },
    "specialty": {
        "keywords": "特色",
        "types": "050000",
        "radius": 2500,
        "poi_category": "specialty",
        "title": "本地特色",
        "fallback_keywords": ["老字号", "小吃"],
    },
    "sight": {
        "keywords": "景点",
        "types": "110000",
        "radius": 4000,
        "poi_category": "sight",
        "title": "附近景点",
        "fallback_keywords": ["风景名胜", "公园"],
    },
    "entertainment": {
        "keywords": "娱乐",
        "types": "080000",
        "radius": 3500,
        "poi_category": "entertainment",
        "title": "附近娱乐",
        "fallback_keywords": ["KTV", "电影院", "休闲"],
    },
    "sports": {
        "keywords": "运动",
        "types": "080000",
        "radius": 3500,
        "poi_category": "sports",
        "title": "附近运动场所",
        "fallback_keywords": ["健身", "体育馆", "羽毛球馆", "游泳馆"],
    },
    "hospital": {
        "keywords": "医院",
        "types": "090000",
        "radius": 4000,
        "poi_category": "hospital",
        "title": "附近医院",
        "fallback_keywords": ["诊所", "卫生服务中心", "急救"],
    },
    "mall": {
        "keywords": "商场",
        "types": "060000",
        "radius": 4000,
        "poi_category": "mall",
        "title": "附近商场",
        "fallback_keywords": ["购物中心", "百货"],
    },
}

# 4×3 主网格 + 第 4 行「路线」（旅游串联）
NAV_ITEMS = [
    {"id": "weather", "label": "天气", "desc": "预报与穿衣建议"},
    {"id": "air", "label": "空气", "desc": "AQI 与污染指数"},
    {"id": "route", "label": "出行", "desc": "驾车·步行·公交导航"},
    {"id": "traffic", "label": "路况", "desc": "高德实时路况"},
    {"id": "food", "label": "美食", "desc": "餐饮推荐"},
    {"id": "hotel", "label": "住宿", "desc": "酒店·民宿"},
    {"id": "specialty", "label": "特色", "desc": "本地特色小吃"},
    {"id": "sight", "label": "景点", "desc": "景区名胜"},
    {"id": "entertainment", "label": "娱乐", "desc": "KTV·影院·休闲"},
    {"id": "sports", "label": "运动", "desc": "健身·场馆"},
    {"id": "hospital", "label": "医院", "desc": "医院·诊所"},
    {"id": "mall", "label": "商场", "desc": "购物中心"},
    {"id": "tourism", "label": "路线", "desc": "串联景点·美食旅游路线"},
]

NAV_ORDER = [item["id"] for item in NAV_ITEMS]

# 兼容旧 id
_CATEGORY_ALIASES = {"business": "mall"}


def _parse_lnglat(location: str):
    lng, lat = location.split(",", 1)[:2]
    return float(lng), float(lat)


def _decorate_poi_map(poi_map: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(poi_map)
    out["title"] = cfg.get("title") or out.get("title") or "周边推荐"
    cat = cfg.get("poi_category", "")
    pois = []
    for p in out.get("pois") or []:
        item = dict(p)
        item["category"] = cat or item.get("category") or "stop"
        pois.append(item)
    out["pois"] = pois
    return out


def _search_attempts(cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    attempts: List[Dict[str, str]] = [
        {"keywords": cfg["keywords"], "types": cfg.get("types", "")},
    ]
    for kw in cfg.get("fallback_keywords") or []:
        attempts.append({"keywords": kw, "types": cfg.get("types", "")})
    attempts.append({"keywords": cfg["keywords"], "types": ""})
    if cfg.get("types"):
        attempts.append({"keywords": "", "types": cfg["types"]})
    return attempts


_CITY_POI_MCP_CAT = {
    "food": "food",
    "sight": "sightseeing",
    "specialty": "food",
}


def _fetch_city_poi_category(city: str, category: str) -> Dict[str, Any]:
    """按城市名拉取 POI（对话切换城市后，探索栏以该城市为准）。"""
    cfg = POI_CATEGORIES.get(category)
    if not cfg:
        return {"error": f"未知类别: {category}"}
    city_key = (city or "").replace("市", "").strip()
    if not city_key:
        return {"error": "请先指定城市"}

    mcp_cat = _CITY_POI_MCP_CAT.get(category)
    if mcp_cat:
        raw = call_mcp_tool(
            "get_city_poi",
            {"city": city_key, "category": mcp_cat, "page_size": 12},
        )
        poi_map, summary = parse_poi_map_result(raw)
        if poi_map and poi_map.get("pois"):
            poi_map = _decorate_poi_map(poi_map, cfg)
            poi_map["title"] = f"{city_key} · {cfg.get('title', '推荐')}"
            return {
                "summary": summary,
                "poi_map": poi_map,
                "category": category,
                "city": city_key,
            }

    from services.city_context import resolve_city_center

    center = resolve_city_center(city_key)
    if not center or not center.get("location"):
        return {
            "summary": f"未能解析城市 {city_key} 坐标",
            "poi_map": None,
            "category": category,
            "city": city_key,
        }
    result = _fetch_poi_category(center["location"], category)
    if result.get("poi_map"):
        pm = result["poi_map"]
        pm["title"] = f"{city_key} · {cfg.get('title', pm.get('title', ''))}"
        result["poi_map"] = pm
    result["city"] = city_key
    return result


def _fetch_poi_category(location: str, category: str) -> Dict[str, Any]:
    cfg = POI_CATEGORIES.get(category)
    if not cfg:
        return {"error": f"未知类别: {category}"}

    last_summary = ""
    for attempt in _search_attempts(cfg):
        raw = call_mcp_tool(
            "amap_place_around",
            {
                "location": location,
                "keywords": attempt["keywords"],
                "types": attempt["types"],
                "radius": cfg["radius"],
                "page_size": 12,
            },
        )
        poi_map, summary = parse_poi_map_result(raw)
        last_summary = summary or last_summary
        if poi_map and poi_map.get("pois"):
            return {
                "summary": summary,
                "poi_map": _decorate_poi_map(poi_map, cfg),
                "category": category,
            }

    return {
        "summary": last_summary or f"未找到{cfg['title']}，请尝试扩大搜索范围或更换位置",
        "poi_map": None,
        "category": category,
    }


def _aqi_label(aqi: int) -> str:
    if aqi <= 50:
        return "优"
    if aqi <= 100:
        return "良"
    if aqi <= 150:
        return "轻度污染"
    if aqi <= 200:
        return "中度污染"
    if aqi <= 300:
        return "重度污染"
    return "严重污染"


def _fetch_air_quality(location: str) -> Dict[str, Any]:
    if not OPENWEATHER_API_KEY:
        return {"error": "未配置 OPENWEATHER_API_KEY，无法查询空气质量"}
    try:
        lng, lat = _parse_lnglat(location)
    except (ValueError, TypeError):
        return {"error": "坐标格式无效"}
    url = "http://api.openweathermap.org/data/2.5/air_pollution"
    try:
        resp = requests.get(
            url,
            params={"lat": lat, "lon": lng, "appid": OPENWEATHER_API_KEY},
            timeout=10,
        )
        data = resp.json()
        item = (data.get("list") or [{}])[0]
        main = item.get("main") or {}
        aqi = int(main.get("aqi") or 0)
        components = item.get("components") or {}
        label = _aqi_label(aqi)
        summary = (
            f"当前空气质量指数 AQI：{aqi}（{label}）\n"
            f"PM2.5: {components.get('pm2_5', '?')} μg/m³\n"
            f"PM10: {components.get('pm10', '?')} μg/m³\n"
            f"O₃: {components.get('o3', '?')} μg/m³"
        )
        return {
            "summary": summary,
            "info_type": "air",
            "air": {"aqi": aqi, "label": label, "components": components},
        }
    except Exception as e:
        return {"error": f"空气质量查询失败: {e}"}


def _fetch_weather(city: str) -> Dict[str, Any]:
    if not city:
        return {"error": "请先定位或指定城市"}
    raw = call_mcp_tool("get_city_weather_cn", {"city": city})
    if "未找到" in raw or "出错" in raw:
        return {"error": raw}
    return {"summary": raw, "info_type": "weather", "city": city}


def explore(
    category: str,
    *,
    location: str = "",
    city: str = "",
    location_label: str = "",
) -> Dict[str, Any]:
    """按导航类别返回地图数据或信息摘要。"""
    category = _CATEGORY_ALIASES.get(category, (category or "").strip().lower())

    if category == "traffic":
        loc = location
        if not loc and city:
            from services.city_context import resolve_city_center

            center = resolve_city_center(city)
            if center:
                loc = center["location"]
                location_label = location_label or center.get("label", "")
        if not loc:
            return {"error": "查看路况需要先定位或在对话中指定城市"}
        result = query_traffic_status(loc, radius=2000, center_name=location_label or "当前位置")
        if result.get("error"):
            return result
        return {
            "summary": result.get("summary", ""),
            "traffic_map": result.get("traffic_map"),
            "category": "traffic",
        }

    if category in POI_CATEGORIES:
        city_key = (city or "").replace("市", "").strip()
        if city_key:
            return _fetch_city_poi_category(city_key, category)
        if not location:
            return {"error": "查看周边需要先定位或在对话中指定城市"}
        return _fetch_poi_category(location, category)

    if category == "weather":
        target = city or (location_label.split("·")[0].strip() if location_label else "")
        if not target and location:
            raw = call_mcp_tool("amap_regeocode", {"location": location})
            for line in raw.splitlines():
                if line.startswith("城市："):
                    target = line.split("：", 1)[-1].strip()
                    break
                if line.startswith("省份：") and not target:
                    target = line.split("：", 1)[-1].strip().replace("市", "") + "市"
        return _fetch_weather(target)

    if category == "air":
        loc = location
        if not loc and city:
            from services.city_context import resolve_city_center

            center = resolve_city_center(city)
            if center:
                loc = center["location"]
        if not loc:
            return {"error": "查看空气需要先定位或在对话中指定城市"}
        return _fetch_air_quality(loc)

    if category == "route":
        return {
            "summary": "请选择出行方式并输入目的地，可在地图查看路线。",
            "info_type": "route",
            "category": "route",
        }

    if category == "tourism":
        return {
            "summary": "规划串联景点与美食的旅游路线，可在地图查看途经点。",
            "info_type": "tourism",
            "category": "tourism",
        }

    return {"error": f"不支持的探索类别: {category}"}


def list_nav_items() -> list:
    return NAV_ITEMS
