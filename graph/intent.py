"""意图识别（规则引擎）"""
import re
from typing import List, Optional

_NEARBY_HINTS = ("附近", "周边", "周围", "近的", "好吃", "美食", "餐厅", "吃", "景点")
_CITY_QUERY_SKIP = frozenset(
    {
        "哪些", "什么", "哪里", "哪儿", "附近", "周边", "周围",
        "这里", "当地", "国内", "我国", "全国",
    }
)
_CITY_QUERY_PATTERNS = [
    re.compile(
        r"^([\u4e00-\u9fa5]{2,6})(?:市)?有(?:哪些|什么|啥).*(?:好玩|景点|推荐|美食|餐厅|吃的|去哪)"
    ),
    re.compile(r"^([\u4e00-\u9fa5]{2,6})(?:市)?(?:有)?(?:哪些|什么).*(?:好吃|美食)"),
    re.compile(r"(?:在|到|去)([\u4e00-\u9fa5]{2,6})(?:市)?.*(?:好玩|景点|玩|逛|美食)"),
]
_ROUTE_HINTS = (
    "怎么走", "怎么去", "路线", "导航", "驾车", "开车", "自驾",
    "步行", "骑行", "公交", "到", "去", "前往",
)
_ROUTE_DEST_SKIP = frozenset({"这里", "这儿", "当前", "当前位置", "我的位置", "附近", "周边", "周围"})
_ROUTE_DEST_INVALID_EXACT = frozenset({"旅游", "游玩", "行程", "规划", "攻略", "附近", "周边", "周围"})
_NEARBY_MAX_ROUTE_METERS = 120_000
_COMPLEX_PLAN_HINTS = (
    "规划", "行程", "攻略", "旅游", "游玩", "几天", "周末",
    "带孩子", "避开拥堵", "夜景", "同时", "还要",
)


def extract_query_city(text: str) -> Optional[str]:
    t = text.strip()
    if re.match(r"^(附近|周边|周围)", t):
        return None
    for pat in _CITY_QUERY_PATTERNS:
        m = pat.search(t)
        if not m:
            continue
        city = m.group(1).strip().rstrip("市区县")
        if not city or city in _CITY_QUERY_SKIP or len(city) < 2:
            continue
        if any(x in city for x in ("附近", "周边", "周围", "什么")):
            continue
        return city
    return None


def is_weather_query(text: str) -> bool:
    return any(k in text for k in ("天气", "下雨", "温度", "预报", "气温", "出行建议", "冷不冷", "热不热"))


def is_city_poi_query(text: str) -> bool:
    return extract_query_city(text) is not None


def city_poi_category(text: str) -> str:
    if any(k in text for k in ("好吃", "美食", "餐厅", "吃", "饭", "小吃")):
        return "food"
    return "sightseeing"


def is_transit_station_query(text: str) -> bool:
    if not any(k in text for k in ("地铁", "公交站", "公交车站", "公交站点")):
        return False
    return any(
        k in text
        for k in ("最近", "附近", "周边", "周围", "怎么走", "怎么去", "在哪", "哪个")
    )


def is_traffic_query(text: str) -> bool:
    return any(
        k in text
        for k in ("路况", "拥堵", "缓行", "畅通", "交通状况", "堵车", "通行", "实时路况")
    )


def is_nearby_query(text: str) -> bool:
    if is_traffic_query(text):
        return False
    if extract_query_city(text):
        return False
    if any(k in text for k in ("附近", "周边", "周围")):
        return True
    return any(h in text for h in _NEARBY_HINTS)


def nearby_poi_params(text: str) -> dict:
    if any(k in text for k in ("好吃", "美食", "餐厅", "吃", "饭", "小吃")):
        return {"keywords": "美食", "types": "050000", "radius": 2000}
    if any(k in text for k in ("景点", "玩", "游", "逛", "景区", "好玩")):
        return {"keywords": "景点", "types": "110000", "radius": 3000}
    return {"keywords": "", "types": "", "radius": 2000}


def wants_nearby_food_and_sights(text: str) -> bool:
    """是否同时需要周边美食与景点（含通用周边推荐）。"""
    if not is_nearby_query(text):
        return False
    t = text.strip()
    has_food = any(k in t for k in ("好吃", "美食", "餐厅", "吃", "饭", "小吃", "餐饮"))
    has_sight = any(k in t for k in ("景点", "玩", "游", "逛", "景区", "好玩"))
    if has_food and has_sight:
        return True
    if any(k in t for k in ("周边推荐", "附近推荐", "美食与景点", "好吃和好玩")):
        return True
    return False


def clean_route_destination(dest: str) -> str:
    dest = dest.strip().strip("，,、？?！!。")
    for prefix in ("一下", "介绍下"):
        if dest.startswith(prefix):
            dest = dest[len(prefix) :].strip()
    for suffix in (
        "怎么走",
        "怎么去",
        "如何去",
        "如何到达",
        "怎么开",
        "导航",
        "驾车",
        "开车",
        "自驾",
        "步行",
        "骑行",
        "公交",
    ):
        if dest.endswith(suffix):
            dest = dest[: -len(suffix)].strip()
    return dest


def wants_navigation(text: str) -> bool:
    return any(
        k in text for k in ("怎么走", "怎么去", "如何去", "如何到达", "导航", "路线")
    )


def is_valid_route_destination(dest: str) -> bool:
    if not dest or dest in _ROUTE_DEST_SKIP:
        return False
    if dest in _ROUTE_DEST_INVALID_EXACT:
        return False
    if any(dest.startswith(part) for part in ("附近", "周边", "周围")):
        return False
    return len(dest) >= 2


def extract_route_destination(text: str) -> Optional[str]:
    patterns = [
        r"从(?:这里|这儿|当前(?:位置)?|我的位置|我这|此处)?\s*(?:到|去|前往)\s*([^，。！？\s\d]{2,24})",
        r"介绍(?:一下)?\s*([^，。！？\n,，]{2,30}?)\s*[,，]?\s*(?:怎么去|怎么走|如何去|如何到达)",
        r"([^，。！？\n,，]{2,30}?)\s*[,，]?\s*(?:怎么去|怎么走|如何去|如何到达)",
        r"(?:到|去|前往)\s*([^，。！？\s\d]{2,24}?)(?:\s*(?:驾车|开车|步行|骑行|公交|怎么走|怎么去|怎么开|导航))",
        r"(?:到|去|前往)\s*([^，。！？\s]{2,24})",
    ]
    for pat in patterns:
        m = re.search(pat, text.strip())
        if not m:
            continue
        dest = clean_route_destination(m.group(1))
        if is_valid_route_destination(dest):
            return dest
    return None


def is_halfday_trip_query(text: str) -> bool:
    has_trip = any(k in text for k in ("半日游", "半日", "一日游", "一日"))
    has_context = any(
        k in text
        for k in ("当前位置", "我这里", "我的位置", "从这里", "附近", "周边", "根据", "规划", "行程")
    )
    return has_trip and has_context


def is_nearby_trip_query(text: str) -> bool:
    has_near = any(k in text for k in ("附近", "周边", "周围"))
    has_trip = any(
        k in text
        for k in ("旅游", "游玩", "游", "行程", "攻略", "规划", "线路", "路线", "一日游", "半日游")
    )
    if not (has_near and has_trip):
        return False
    if re.search(r"从\s*.+\s*(?:到|去|前往)\s*", text):
        return not is_valid_route_destination(extract_route_destination(text) or "")
    return True


def should_emit_route_map(user_text: str, route_data: Optional[dict]) -> bool:
    if not route_data or route_data.get("path_fallback"):
        return False
    if is_nearby_trip_query(user_text):
        return False
    try:
        dist = int(route_data.get("distance", 0))
    except (TypeError, ValueError):
        dist = 0
    if is_nearby_query(user_text) and dist > _NEARBY_MAX_ROUTE_METERS:
        return False
    if dist > 500_000 and not extract_route_destination(user_text):
        return False
    return True


def is_route_query(text: str) -> bool:
    if is_nearby_trip_query(text):
        return False
    if is_halfday_trip_query(text):
        return False
    if wants_navigation(text):
        return extract_route_destination(text) is not None
    if not any(h in text for h in _ROUTE_HINTS):
        return False
    dest = extract_route_destination(text)
    if dest:
        return True
    if any(k in text for k in ("规划", "行程", "攻略", "旅游", "游玩")):
        return False
    return any(k in text for k in ("怎么走", "怎么去", "导航", "驾车", "开车", "自驾"))


def infer_route_mode(text: str) -> str:
    if "步行" in text:
        return "walking"
    if "骑行" in text or "骑车" in text:
        return "riding"
    if "公交" in text or "地铁" in text:
        return "transit"
    return "driving"


def needs_complex_planning(text: str) -> bool:
    hits = sum(1 for h in _COMPLEX_PLAN_HINTS if h in text)
    return hits >= 2 or ("规划" in text and len(text) > 15)


def extract_plan_subtasks(user_text: str) -> List[str]:
    tasks = []
    if any(k in user_text for k in ("天气", "下雨", "温度")):
        tasks.append("查询目的地天气预报")
    if any(k in user_text for k in ("景点", "玩", "游", "逛", "夜景")):
        tasks.append("搜索热门景点 POI")
    if any(k in user_text for k in ("美食", "吃", "餐厅")):
        tasks.append("搜索美食推荐")
    if any(k in user_text for k in ("路线", "导航", "怎么走", "拥堵", "驾车")):
        tasks.append("规划最优路线并查询路况")
    if any(k in user_text for k in ("规划", "行程", "攻略", "几天", "周末")):
        tasks.append("生成多日行程安排")
    if not tasks:
        tasks = ["分析用户需求", "调用相关工具获取数据", "整合个性化推荐"]
    return tasks[:5]


def route_to_subagent(user_text: str) -> str:
    if is_route_query(user_text):
        return "general"
    if any(k in user_text for k in ("紧急", "医院", "120", "急救", "路况", "拥堵", "事故")):
        return "realtime_guard"
    if any(k in user_text for k in ("规划", "行程", "攻略", "几天", "周末", "旅游", "游玩")):
        return "trip_planner"
    if needs_complex_planning(user_text):
        return "trip_planner"
    return "companion"


def classify_intent(user_text: str) -> str:
    if is_route_query(user_text):
        return "route"
    if any(k in user_text for k in ("紧急", "医院", "120", "急救")):
        return "emergency"
    if is_weather_query(user_text):
        return "weather"
    if is_city_poi_query(user_text):
        return "city_poi"
    if is_nearby_query(user_text):
        return "nearby"
    if needs_complex_planning(user_text):
        return "complex"
    if any(k in user_text for k in ("生成", "效果图", "实景图", "图片")):
        return "image_gen"
    return "chat"
