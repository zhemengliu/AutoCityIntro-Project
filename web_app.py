"""Web 聊天界面与 API 网关"""
import json
import os
from pathlib import Path
from typing import List, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from graph_runner import get_city_agent
import session_store
import user_profile
from services.companion import suggest_next_stop, track_companion
from services.export import create_share_link, export_session_itinerary, load_share, trip_to_markdown
from services.feedback import record_feedback, record_feedback_batch
from services.metrics import inc, snapshot as metrics_snapshot
from services.offline_cache import get_cached_poi, get_cached_poi_detail, cache_poi_detail
from services.privacy import is_minor_mode, mask_location, privacy_policy_text, sanitize_for_minor
from services.persona import get_persona_list, get_persona_config, validate_persona
from services.accounts import (
    add_favorite_poi,
    add_favorite_trip,
    remove_favorite_poi,
    remove_favorite_trip,
    get_device_prefs_profile,
    get_profile_for_owner,
    register_account,
    resolve_owner_id,
)
from services.trip_store import (
    add_collaborator,
    delete_trip,
    get_trip,
    list_trips,
    normalize_trip,
    save_trip,
    trip_from_halfday,
    trip_from_plan,
    update_trip,
)
from tools.mcp_client import call_mcp_tool

load_dotenv()

WEB_PORT = int(os.getenv("WEB_PORT", "7003"))
STATIC_DIR = Path(__file__).parent / "static"
AUDIO_DIR = Path(os.getenv("AUDIO_OUTPUT_DIR", "data/audio"))
IMAGE_DIR = Path(os.getenv("IMAGE_OUTPUT_DIR", "data/images"))
BASE_URL = os.getenv("WEB_BASE_URL", f"http://localhost:{WEB_PORT}")

app = FastAPI(title="AutoCityIntro Web", version="4.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static-audio", StaticFiles(directory=str(AUDIO_DIR)), name="static-audio")
app.mount("/static-images", StaticFiles(directory=str(IMAGE_DIR)), name="static-images")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None
    device_id: Optional[str] = Field(None, description="设备/用户标识，用于跨会话画像")
    location: Optional[str] = Field(None, description="用户位置，格式：经度,纬度")
    location_label: Optional[str] = Field(None, description="位置描述，如：上海外滩")


class ChatResponse(BaseModel):
    reply: str
    session_id: str


class ImageAnalyzeRequest(BaseModel):
    image_base64: str = Field(..., min_length=10)
    session_id: Optional[str] = None
    device_id: Optional[str] = None
    location: Optional[str] = None


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=500)
    session_id: Optional[str] = None
    device_id: Optional[str] = None


class FeedbackTargetItem(BaseModel):
    target: str = Field(..., min_length=1, max_length=200)
    category: str = Field("poi", description="poi/route/trip/reply/traffic")
    rating: int = Field(..., ge=-1, le=1)


class FeedbackRequest(BaseModel):
    device_id: str
    target: Optional[str] = Field(None, min_length=1, max_length=200)
    rating: Optional[int] = Field(None, ge=-1, le=1)
    category: str = "poi"
    targets: Optional[List[FeedbackTargetItem]] = None


class ShareTripRequest(BaseModel):
    session_id: str
    trip: dict


class PrivacyDeleteRequest(BaseModel):
    device_id: str
    session_ids: Optional[List[str]] = None


class AccountRegisterRequest(BaseModel):
    display_name: str = Field("", max_length=40)
    device_id: Optional[str] = None


class TripCreateRequest(BaseModel):
    device_id: Optional[str] = None
    account_token: Optional[str] = None
    trip: dict


class TripUpdateRequest(BaseModel):
    device_id: Optional[str] = None
    account_token: Optional[str] = None
    patch: dict


class TripCollaboratorRequest(BaseModel):
    device_id: Optional[str] = None
    account_token: Optional[str] = None
    collaborator_id: str


class FavoritePoiRequest(BaseModel):
    device_id: str
    account_token: Optional[str] = None
    poi_name: str


class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    voice_id: str = "female-shaonv"


class PreferencesPatch(BaseModel):
    persona: Optional[str] = None
    voice_pack: Optional[str] = None
    transport: Optional[str] = None
    focus: Optional[str] = None
    ui_lang: Optional[str] = None


class TripMapBuildRequest(BaseModel):
    trip: dict
    city: str = ""
    device_id: Optional[str] = None


@app.get("/")
async def index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "请将 static/index.html 放在项目目录"}


@app.get("/p/{token}")
async def share_public_page(token: str):
    page = STATIC_DIR / "share.html"
    if page.exists():
        return FileResponse(page)
    raise HTTPException(status_code=404, detail="分享页不存在")


@app.get("/admin")
async def admin_dashboard_page():
    page = STATIC_DIR / "admin.html"
    if page.exists():
        return FileResponse(page)
    raise HTTPException(status_code=404, detail="管理页不存在")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "web", "metrics": metrics_snapshot()}


class ChatResumeRequest(BaseModel):
    session_id: str
    device_id: Optional[str] = None
    confirm: bool = True


@app.get("/manifest.json")
async def pwa_manifest():
    manifest = STATIC_DIR / "manifest.json"
    if manifest.exists():
        return FileResponse(manifest, media_type="application/manifest+json")
    raise HTTPException(status_code=404)


@app.get("/sw.js")
async def service_worker():
    sw = STATIC_DIR / "sw.js"
    if sw.exists():
        return FileResponse(sw, media_type="application/javascript")
    raise HTTPException(status_code=404)


@app.get("/api/config")
async def app_config():
    """前端能力开关"""
    return {
        "speech_enabled": os.getenv("SPEECH_ENABLED", "true").lower() == "true",
        "image_gen_enabled": bool(os.getenv("MINIMAX_API_KEY")),
        "vision_enabled": True,
        "minor_mode": is_minor_mode(),
        "llm_intent_enabled": os.getenv("USE_LLM_INTENT", "false").lower() == "true",
        "offline_cache_enabled": True,
        "pwa_enabled": True,
        "version": "4.2.0",
    }


@app.get("/api/location/city")
async def location_city(
    location: str = Query(..., description="经度,纬度"),
    device_id: Optional[str] = None,
):
    """逆地理编码：由 GPS 解析当前城市与地址标签"""
    raw = call_mcp_tool("amap_regeocode", {"location": location})
    from services.location_utils import format_location_label, parse_city_from_regeo_text

    city = parse_city_from_regeo_text(raw) or ""
    district = ""
    address = ""
    for line in raw.splitlines():
        if line.startswith("区县："):
            district = line.split("：", 1)[-1].strip()
        if line.startswith("地址："):
            address = line.split("：", 1)[-1].strip()
    label = format_location_label(city, district, address)
    if device_id and city:
        profile = user_profile.get_or_create_profile(device_id)
        user_profile.record_city(profile, city)
        user_profile.save_profile(profile)
    return {"city": city, "district": district, "address": address, "label": label, "location": location}


@app.get("/api/location/geocode")
async def location_geocode(
    keywords: str = Query(..., description="目的地名称或地址"),
    city: str = Query("", description="城市名，用于优先匹配本地 POI"),
    near: str = Query("", description="经度,纬度，多个候选时选距其最近"),
):
    """地理编码：将用户输入的目的地解析为坐标（供导航唤起）"""
    from services.geocode import resolve_place

    result = resolve_place(keywords, city, near)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/api/config/map")
async def map_config():
    """供前端加载高德 JS API（Web 端 Key，未配置时回退 REST Key）"""
    key = os.getenv("AMAP_JS_KEY") or os.getenv("AMAP_API_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="未配置 AMAP_JS_KEY 或 AMAP_API_KEY")
    security = os.getenv("AMAP_SECURITY_CODE") or os.getenv("AMAP_JS_SECRET", "")
    return {"amap_key": key, "security_code": security}


@app.get("/api/location/city-center")
async def location_city_center(city: str = Query(..., description="城市名，如 西安 或 西安市")):
    """将城市解析为市中心坐标，供地图默认中心与探索使用"""
    from services.city_context import normalize_city_display, resolve_city_center

    resolved = resolve_city_center(city)
    if not resolved:
        raise HTTPException(status_code=400, detail=f"无法解析城市：{city}")
    return {
        "city": normalize_city_display(resolved.get("city_key") or city),
        "city_key": resolved.get("city_key", ""),
        "location": resolved["location"],
        "label": resolved["label"],
        "lnglat": resolved.get("lnglat"),
    }


@app.get("/api/sessions/{session_id}/context")
async def session_context(session_id: str):
    """会话绑定的城市与定位（切换会话时前端同步）"""
    from services.city_context import normalize_city_display

    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    active = session.get("active_city") or ""
    return {
        "session_id": session_id,
        "active_city": normalize_city_display(active) if active else "",
        "active_city_key": active,
        "user_location": session.get("user_location", ""),
        "location_label": session.get("user_location_label", ""),
    }


@app.get("/api/explore/nav")
async def explore_nav():
    """城市探索导航菜单"""
    from services.explore import list_nav_items

    return {"items": list_nav_items()}


@app.get("/api/explore/{category}")
async def explore_category(
    category: str,
    location: str = Query("", description="经度,纬度"),
    city: str = Query("", description="城市名（天气等）"),
    location_label: str = Query("", description="位置描述"),
):
    """按类别探索：路况/美食/景点/特色/商圈/天气/空气"""
    from services.explore import explore

    result = explore(
        category,
        location=location,
        city=city,
        location_label=location_label,
    )
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/tourism/route")
async def tourism_route(
    location: str = Query("", description="经度,纬度；空则按 city 取市中心"),
    city: str = Query("", description="城市名（无定位时必填）"),
    location_label: str = Query("", description="起点描述"),
    mode: str = Query("walking", description="driving/walking/transit/riding"),
    max_stops: int = Query(5, ge=2, le=8),
):
    """旅游路线：多景点串联 + 地图 route_map / poi_map"""
    from graph.parsers import parse_route_result
    from services.tourism_route import build_tourism_route_maps

    if not location and not city:
        raise HTTPException(status_code=400, detail="请提供定位坐标或城市名")

    def route_fn(origin: str, dest: str, m: str):
        raw = call_mcp_tool(
            "amap_route_planning",
            {"origin": origin, "destination": dest, "mode": m, "city": city},
        )
        return parse_route_result(raw)

    maps = build_tourism_route_maps(
        origin_loc=location,
        origin_label=location_label or "起点",
        route_fn=route_fn,
        city=city.replace("市", "") if city else "",
        mode=mode,
        max_stops=max_stops,
    )
    if not maps:
        raise HTTPException(status_code=400, detail="未能生成旅游路线，请换城市或先定位")
    return {
        "route_map": maps["route_map"],
        "poi_map": maps["poi_map"],
        "summary": maps["route_map"].get("summary", ""),
    }


@app.get("/api/route/plan")
async def route_plan(
    origin: str = Query(..., description="起点坐标或地址"),
    destination: str = Query(..., description="目的地"),
    mode: str = Query("driving", description="driving/walking/transit/riding"),
    city: str = Query("", description="城市名（公交建议填写）"),
):
    """路线规划并返回 route_map 供前端地图绘制"""
    from graph.parsers import parse_route_result

    raw = call_mcp_tool(
        "amap_route_planning",
        {"origin": origin, "destination": destination, "mode": mode, "city": city},
    )
    route = parse_route_result(raw)
    if not route:
        raise HTTPException(status_code=400, detail=raw[:300] if raw else "路线规划失败")
    return {"route_map": route, "summary": route.get("summary", "")}


@app.get("/api/suggestions")
async def get_suggestions(
    session_id: Optional[str] = None,
    device_id: Optional[str] = None,
    location: Optional[str] = None,
    location_label: Optional[str] = None,
):
    agent = get_city_agent(session_id, device_id=device_id)
    if location:
        agent.set_user_location(location, location_label or "")
    return {"suggestions": agent.get_proactive_suggestions()}


@app.get("/api/profile/{device_id}")
async def get_profile(device_id: str):
    profile = user_profile.get_or_create_profile(device_id)
    from services.feedback import feedback_summary

    return {
        "device_id": device_id,
        "summary": user_profile.profile_summary(profile),
        "feedback_summary": feedback_summary(profile),
        "preferences": profile.get("preferences", {}),
        "favorite_cities": profile.get("favorite_cities", []),
        "favorite_poi_names": profile.get("favorite_poi_names", []),
        "poi_weights": profile.get("poi_weights", {}),
        "feedback_history": profile.get("feedback_history", [])[:20],
    }


@app.patch("/api/profile/{device_id}/preferences")
async def patch_profile_preferences(device_id: str, body: PreferencesPatch):
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=400, detail="无有效偏好字段")
    profile = user_profile.update_preferences(device_id, patch)
    return {"ok": True, "preferences": profile.get("preferences", {})}


@app.post("/api/trip/map")
async def build_trip_map(body: TripMapBuildRequest):
    """为结构化行程生成带分段标注的 route_map"""
    from graph.parsers import parse_route_result
    from services.trip_map_builder import enrich_trip_with_map
    from tools.mcp_client import call_mcp_tool

    city = (body.city or body.trip.get("city") or "").replace("市", "")
    prefs = user_profile.get_or_create_profile(body.device_id or "").get("preferences", {})
    default_mode = prefs.get("transport") or "walking"

    def route_fn(origin: str, dest: str, mode: str):
        raw = call_mcp_tool(
            "amap_route_planning",
            {"origin": origin, "destination": dest, "mode": mode, "city": city},
        )
        return parse_route_result(raw)

    trip = enrich_trip_with_map(
        body.trip,
        route_fn,
        city=city,
        default_mode=default_mode,
    )
    if not trip.get("route_map"):
        raise HTTPException(status_code=400, detail="无法生成行程地图，请确认站点含有效坐标")
    return {"trip": trip, "route_map": trip["route_map"]}


@app.delete("/api/profile/{device_id}")
async def clear_profile(device_id: str):
    if not user_profile.delete_profile(device_id):
        raise HTTPException(status_code=404, detail="画像不存在")
    return {"deleted": device_id}


@app.delete("/api/profile/{device_id}/city")
async def remove_profile_city(
    device_id: str,
    city: str = Query(..., min_length=1),
    account_token: Optional[str] = None,
):
    profile = get_device_prefs_profile(device_id)
    user_profile.remove_favorite_city(profile, city)
    user_profile.save_profile(profile)
    return {"ok": True, "favorite_cities": profile.get("favorite_cities", [])}


@app.delete("/api/profile/{device_id}/feedback")
async def remove_profile_feedback(
    device_id: str,
    target: str = Query(..., min_length=1),
    category: str = Query("poi"),
    account_token: Optional[str] = None,
):
    from services.feedback import remove_feedback_entry

    profile = get_device_prefs_profile(device_id)
    remove_feedback_entry(profile, target, category)
    user_profile.save_profile(profile)
    return {"ok": True, "poi_weights": profile.get("poi_weights", {})}


@app.delete("/api/profile/{device_id}/feedback/all")
async def clear_profile_feedback(
    device_id: str,
    account_token: Optional[str] = None,
):
    from services.feedback import clear_all_feedback

    profile = get_device_prefs_profile(device_id)
    clear_all_feedback(profile)
    user_profile.save_profile(profile)
    return {"ok": True}


@app.get("/api/sessions")
async def list_sessions():
    return {"sessions": session_store.list_sessions()}


@app.post("/api/sessions")
async def create_session():
    session = session_store.create_session()
    return session


@app.delete("/api/sessions/{session_id}")
async def remove_session(session_id: str):
    if not session_store.delete_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"deleted": session_id}


@app.post("/api/feedback")
async def submit_feedback(req: FeedbackRequest):
    profile = user_profile.get_or_create_profile(req.device_id)
    if req.targets:
        results = record_feedback_batch(
            profile,
            [t.model_dump() for t in req.targets],
        )
    elif req.target is not None and req.rating is not None:
        results = [record_feedback(profile, req.target, req.rating, req.category)]
    else:
        raise HTTPException(status_code=400, detail="请提供 target/rating 或 targets 列表")
    if not results or not any(r.get("ok") for r in results):
        raise HTTPException(status_code=400, detail="反馈内容无效")
    user_profile.save_profile(profile)
    return {"ok": True, "results": results, "poi_weights": profile.get("poi_weights", {})}


@app.get("/api/metrics")
async def metrics():
    return metrics_snapshot()


@app.post("/api/account/register")
async def account_register(req: AccountRegisterRequest):
    return register_account(req.display_name, req.device_id)


@app.get("/api/favorites")
async def list_favorites(device_id: Optional[str] = None, account_token: Optional[str] = None):
    owner = resolve_owner_id(device_id, account_token)
    device_profile = get_device_prefs_profile(device_id)
    trips = list_trips(owner, favorites_only=True)
    return {
        "favorite_trip_ids": device_profile.get("favorite_trip_ids", []),
        "favorite_poi_names": device_profile.get("favorite_poi_names", []),
        "favorite_cities": device_profile.get("favorite_cities", []),
        "favorite_trips": trips,
        "account_token": device_profile.get("account_token"),
        "display_name": device_profile.get("display_name", ""),
    }


@app.post("/api/favorites/poi")
async def favorite_poi(req: FavoritePoiRequest):
    profile = get_device_prefs_profile(req.device_id)
    add_favorite_poi(profile, req.poi_name)
    user_profile.save_profile(profile)
    return {"ok": True, "favorite_poi_names": profile.get("favorite_poi_names", [])}


@app.delete("/api/favorites/poi")
async def unfavorite_poi(
    poi_name: str = Query(..., min_length=1),
    device_id: str = Query(...),
    account_token: Optional[str] = None,
):
    profile = get_device_prefs_profile(device_id)
    remove_favorite_poi(profile, poi_name)
    user_profile.save_profile(profile)
    return {"ok": True, "favorite_poi_names": profile.get("favorite_poi_names", [])}


@app.delete("/api/favorites/trip/{trip_id}")
async def unfavorite_trip(
    trip_id: str,
    device_id: Optional[str] = None,
    account_token: Optional[str] = None,
):
    owner = resolve_owner_id(device_id, account_token)
    updated = update_trip(trip_id, owner, {"favorite": False})
    if not updated:
        raise HTTPException(status_code=404, detail="行程不存在")
    profile = get_device_prefs_profile(device_id)
    remove_favorite_trip(profile, trip_id)
    user_profile.save_profile(profile)
    return {"ok": True, "trip_id": trip_id}


@app.get("/api/trips")
async def trips_list(device_id: Optional[str] = None, account_token: Optional[str] = None):
    owner = resolve_owner_id(device_id, account_token)
    return {"trips": list_trips(owner)}


@app.post("/api/trips")
async def trips_create(req: TripCreateRequest):
    inc("trip_save")
    owner = resolve_owner_id(req.device_id, req.account_token)
    trip = normalize_trip(req.trip, owner_id=owner)
    saved = save_trip(trip)
    profile = get_device_prefs_profile(req.device_id)
    add_favorite_trip(profile, saved["trip_id"])
    user_profile.save_profile(profile)
    return saved


@app.get("/api/trips/{trip_id}")
async def trips_get(trip_id: str, device_id: Optional[str] = None, account_token: Optional[str] = None):
    trip = get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="行程不存在")
    owner = resolve_owner_id(device_id, account_token)
    if trip.get("owner_id") != owner and owner not in (trip.get("collaborators") or []):
        raise HTTPException(status_code=403, detail="无权访问该行程")
    return trip


@app.put("/api/trips/{trip_id}")
async def trips_update(trip_id: str, req: TripUpdateRequest):
    owner = resolve_owner_id(req.device_id, req.account_token)
    updated = update_trip(trip_id, owner, req.patch)
    if not updated:
        raise HTTPException(status_code=404, detail="行程不存在或无权修改")
    return updated


@app.delete("/api/trips/{trip_id}")
async def trips_delete(trip_id: str, device_id: Optional[str] = None, account_token: Optional[str] = None):
    trip = get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="行程不存在")
    owner = resolve_owner_id(device_id, account_token)
    if trip.get("owner_id") != owner:
        raise HTTPException(status_code=403, detail="无权删除")
    delete_trip(trip_id)
    return {"deleted": trip_id}


@app.post("/api/trips/{trip_id}/favorite")
async def trips_favorite(trip_id: str, device_id: Optional[str] = None, account_token: Optional[str] = None):
    owner = resolve_owner_id(device_id, account_token)
    updated = update_trip(trip_id, owner, {"favorite": True})
    if not updated:
        raise HTTPException(status_code=404, detail="行程不存在")
    profile = get_device_prefs_profile(device_id)
    add_favorite_trip(profile, trip_id)
    user_profile.save_profile(profile)
    return updated


@app.post("/api/trips/{trip_id}/collaborators")
async def trips_add_collaborator(trip_id: str, req: TripCollaboratorRequest):
    owner = resolve_owner_id(req.device_id, req.account_token)
    updated = add_collaborator(trip_id, owner, req.collaborator_id)
    if not updated:
        raise HTTPException(status_code=404, detail="行程不存在或无权邀请")
    return updated


@app.get("/api/poi/detail")
async def poi_detail(
    keywords: str,
    city: str = "",
    poi_id: str = "",
    hint_location: str = Query("", description="推荐 POI 坐标，用于详情检索消歧"),
):
    cache_key = poi_id or keywords
    cached = get_cached_poi_detail(cache_key, city)
    if cached:
        return cached
    raw = call_mcp_tool(
        "get_poi_detail",
        {
            "keywords": keywords,
            "city": city,
            "poi_id": poi_id,
            "hint_location": hint_location,
        },
    )
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("type") == "poi_detail":
            cache_poi_detail(cache_key, city, data)
            return data
    except json.JSONDecodeError:
        pass
    inc("mcp_errors")
    raise HTTPException(status_code=502, detail=raw[:200])


@app.get("/api/companion/next")
async def companion_next(
    location: str = Query(..., description="经度,纬度"),
    device_id: Optional[str] = None,
    lang: str = "zh",
):
    profile = get_profile_for_owner(device_id, None) if device_id else {}
    cached = get_cached_poi(location, "")
    pois = (cached or {}).get("parsed", {}).get("pois", [])
    if not pois:
        raw = call_mcp_tool(
            "amap_place_around",
            {"location": location, "radius": 2000, "page_size": 8},
        )
        try:
            data = json.loads(raw)
            pois = data.get("poi_map", {}).get("pois", [])
        except json.JSONDecodeError:
            pois = []
    from services.i18n import localize_poi_list

    pois = localize_poi_list(pois, lang)
    result = suggest_next_stop(pois, profile=profile or None)
    if is_minor_mode() and result.get("suggestion"):
        result["suggestion"] = sanitize_for_minor(result["suggestion"])
    inc("companion_next")
    return result


@app.get("/api/companion/track")
async def companion_track(
    location: str = Query(..., description="经度,纬度"),
    device_id: Optional[str] = None,
    account_token: Optional[str] = None,
    trip_id: Optional[str] = None,
    persist: bool = Query(True, description="是否持久化到站进度"),
):
    """全程伴游：geofence 检测到达、推进行程进度、返回下一站。"""
    inc("companion_track")
    profile = get_profile_for_owner(device_id, account_token) if device_id or account_token else {}
    trip = get_trip(trip_id) if trip_id else None
    if trip_id and not trip:
        raise HTTPException(status_code=404, detail="行程不存在")

    result = track_companion(location, trip, profile=profile or None)
    if persist and trip and result.get("ok") and result.get("mode") == "trip":
        owner = resolve_owner_id(device_id, account_token)
        if trip.get("owner_id") == owner or owner in (trip.get("collaborators") or []):
            patch = {
                "stops": result.get("stops"),
                "active_stop_index": result.get("active_stop_index"),
                "status": result.get("status", trip.get("status")),
            }
            update_trip(trip_id, trip.get("owner_id", owner), patch)
    if is_minor_mode() and result.get("message"):
        result["message"] = sanitize_for_minor(result["message"])
    return result


@app.get("/api/offline/poi")
async def offline_poi(location: str, keywords: str = ""):
    cached = get_cached_poi(location, keywords)
    if not cached:
        raise HTTPException(status_code=404, detail="无离线缓存")
    payload = dict(cached)
    payload["offline"] = True
    if payload.get("parsed"):
        parsed = dict(payload["parsed"])
        parsed["offline"] = True
        payload["parsed"] = parsed
    return payload


@app.post("/api/tts")
async def api_tts(req: TtsRequest):
    raw = call_mcp_tool("tts_speak", {"text": req.text[:500], "voice_id": req.voice_id})
    try:
        data = json.loads(raw.strip())
        if isinstance(data, dict) and data.get("type") == "tts" and data.get("url"):
            return {"ok": True, "url": data["url"], "type": "tts"}
        if isinstance(data, dict) and data.get("error"):
            raise HTTPException(status_code=503, detail=data["error"])
    except json.JSONDecodeError:
        pass
    if "TTS 不可用" in raw or "没有可朗读" in raw:
        raise HTTPException(status_code=503, detail=raw[:300])
    raise HTTPException(status_code=502, detail=raw[:300])


@app.get("/api/taxi/uri")
async def taxi_uri(
    lon: float = Query(..., description="经度"),
    lat: float = Query(..., description="纬度"),
    name: str = Query("目的地"),
):
    from services.amap_uri import build_taxi_uri

    uri = build_taxi_uri(lon, lat, name)
    return {"uri": uri, "label": "在高德 App 中叫车"}


@app.post("/api/export/share")
async def export_share(req: ShareTripRequest):
    link = create_share_link(req.session_id, req.trip, base_url=BASE_URL)
    return link


@app.get("/api/share/{token}")
async def get_share(token: str):
    data = load_share(token)
    if not data:
        raise HTTPException(status_code=404, detail="分享链接无效或已过期")
    return data


@app.get("/api/export/session/{session_id}")
async def export_session(session_id: str):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    md = export_session_itinerary(session.get("conversation_history", []))
    return PlainTextResponse(md, media_type="text/markdown; charset=utf-8")


@app.get("/api/privacy/policy")
async def privacy_policy():
    return {"policy": privacy_policy_text()}


@app.get("/api/persona/list")
async def persona_list():
    """获取可用的助手人格列表"""
    personas = get_persona_list()
    return {"personas": personas}


class PersonaSelectRequest(BaseModel):
    persona_id: str
    device_id: Optional[str] = None


@app.post("/api/persona/select")
async def persona_select(req: PersonaSelectRequest):
    """选择助手人格"""
    if not validate_persona(req.persona_id):
        raise HTTPException(status_code=400, detail="无效的人格ID")
    
    config = get_persona_config(req.persona_id)
    if not config:
        raise HTTPException(status_code=400, detail="人格配置不存在")
    
    if req.device_id:
        profile = user_profile.get_or_create_profile(req.device_id)
        profile["current_persona"] = req.persona_id
        user_profile.save_profile(profile)
    
    return {
        "ok": True,
        "persona_id": req.persona_id,
        "persona_name": config["name"],
        "message": f"已切换为{config['name']}"
    }


@app.delete("/api/privacy/data")
async def delete_user_data(req: PrivacyDeleteRequest):
    user_profile.delete_profile(req.device_id)
    deleted_sessions = []
    if req.session_ids:
        for sid in req.session_ids:
            if session_store.delete_session(sid):
                deleted_sessions.append(sid)
    return {
        "deleted_profile": req.device_id,
        "deleted_sessions": deleted_sessions,
        "location_masked_example": mask_location("108.931645,34.242741"),
    }


@app.get("/api/sessions/{session_id}/history")
async def get_history(session_id: str):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    raw = session.get("conversation_history", [])
    messages = [
        m for m in raw if m.get("content") and str(m.get("content", "")).strip()
    ]
    return {
        "session_id": session_id,
        "title": session.get("title", ""),
        "messages": messages,
    }


@app.post("/api/analyze_image")
async def analyze_image(req: ImageAnalyzeRequest):
    agent = get_city_agent(req.session_id, device_id=req.device_id)
    if req.location:
        agent.set_user_location(req.location, "")
    try:
        reply = agent.analyze_image(req.image_base64, location=req.location)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"reply": reply, "session_id": agent.session_id}


@app.post("/api/generate_image")
async def generate_image(req: ImageGenerateRequest):
    agent = get_city_agent(req.session_id, device_id=req.device_id)
    raw = agent._call_mcp_tool(
        "generate_poi_visual",
        {"poi_name": req.prompt, "style": "实景照片"},
    )
    try:
        data = json.loads(raw.strip())
        if data.get("error"):
            raise HTTPException(status_code=503, detail=data["error"])
        url = data.get("url", "")
        if url and not url.startswith("http"):
            url = url if url.startswith("/") else f"/{url}"
        return {"url": url, "prompt": req.prompt, "session_id": agent.session_id}
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=raw[:200])


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    agent = get_city_agent(req.session_id, device_id=req.device_id)
    if req.location:
        agent.set_user_location(req.location, req.location_label or "")
    reply = agent.chat(req.message)
    return ChatResponse(reply=reply, session_id=agent.session_id)


@app.post("/api/chat/resume")
async def chat_resume(req: ChatResumeRequest):
    """HITL：确认或取消图像生成"""
    agent = get_city_agent(req.session_id, device_id=req.device_id)

    def event_generator():
        for event in agent.resume_image_gen(confirm=req.confirm):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    inc("chat_stream")
    agent = get_city_agent(req.session_id, device_id=req.device_id)

    def event_generator():
        for event in agent.chat_stream(
            req.message,
            user_location=req.location,
            location_label=req.location_label or "",
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    session_store.ensure_data_dir()
    print(f"[Web] 启动于 http://localhost:{WEB_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=WEB_PORT)
