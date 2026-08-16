/** 城市探索：4×3 网格 + 「路线」旅游规划 + 百科/高德外链 */
const CityNav = (() => {
  const NAV_ORDER = [
    "weather",
    "air",
    "route",
    "traffic",
    "food",
    "hotel",
    "specialty",
    "sight",
    "entertainment",
    "sports",
    "hospital",
    "mall",
    "tourism",
  ];

  const NAV_FALLBACK = [
    { id: "weather", label: "天气", desc: "预报与穿衣" },
    { id: "air", label: "空气", desc: "AQI 指数" },
    { id: "route", label: "出行", desc: "驾车·步行·公交" },
    { id: "traffic", label: "路况", desc: "实时路况" },
    { id: "food", label: "美食", desc: "餐饮" },
    { id: "hotel", label: "住宿", desc: "酒店民宿" },
    { id: "specialty", label: "特色", desc: "本地特色" },
    { id: "sight", label: "景点", desc: "景区" },
    { id: "entertainment", label: "娱乐", desc: "休闲" },
    { id: "sports", label: "运动", desc: "健身场馆" },
    { id: "hospital", label: "医院", desc: "医院诊所" },
    { id: "mall", label: "商场", desc: "购物" },
    { id: "tourism", label: "路线", desc: "旅游路线规划" },
  ];

  const NAV_ICONS = {
    weather: "🌤",
    air: "💨",
    route: "🚗",
    traffic: "🚦",
    food: "🍜",
    hotel: "🏨",
    specialty: "✨",
    sight: "🏛",
    entertainment: "🎬",
    sports: "🏃",
    hospital: "🏥",
    mall: "🏬",
    tourism: "🗺️",
  };

  const CATEGORY_BAIKE = {
    weather: "天气预报",
    air: "空气质量指数",
    route: "导航系统",
    traffic: "实时路况",
    food: "美食",
    hotel: "酒店",
    specialty: "地方特色小吃",
    sight: "旅游景点",
    entertainment: "休闲娱乐",
    sports: "体育运动场馆",
    hospital: "医院",
    mall: "购物中心",
    tourism: "旅游路线",
  };

  let menuEl, contentEl, locationEl, linksEl;
  let activeId = null;
  let ctx = {};
  let routeMode = "driving";
  let tourMode = "walking";
  let lastRouteDest = null;

  function sortNavItems(items) {
    const map = new Map(items.map((i) => [i.id, i]));
    return NAV_ORDER.map((id) => map.get(id)).filter(Boolean);
  }

  function baiduUrl(keyword) {
    return `https://baike.baidu.com/search/word?word=${encodeURIComponent(keyword)}`;
  }

  function amapSearchUrl(keyword, city) {
    const q = city ? `${city}${keyword}` : keyword;
    return `https://uri.amap.com/search?query=${encodeURIComponent(q)}&src=AutoCityIntro`;
  }

  function amapPoiUrl(poi) {
    if (poi?.poi_id) return `https://www.amap.com/place/${poi.poi_id}`;
    if (poi?.lnglat?.length >= 2) {
      return `https://uri.amap.com/marker?position=${poi.lnglat[0]},${poi.lnglat[1]}&name=${encodeURIComponent(poi.name || "地点")}&src=AutoCityIntro`;
    }
    return amapSearchUrl(poi?.name || "地点", getCity());
  }

  function amapLocationUrl() {
    const loc = getLocation();
    if (!loc) return "https://www.amap.com/";
    const label = getLocationLabel() || "当前位置";
    return `https://uri.amap.com/marker?position=${loc}&name=${encodeURIComponent(label)}&src=AutoCityIntro`;
  }

  function showExternalLinks(baiduKeyword, amapUrl) {
    if (!linksEl) return;
    const city = getCity();
    const locLabel = getLocationLabel();
    const baidu = baiduUrl(baiduKeyword);
    const locBaidu = locLabel
      ? baiduUrl(city ? `${city}${locLabel.split("·")[0]}` : locLabel)
      : "";
    const amap = amapUrl || amapSearchUrl(baiduKeyword, city);
    linksEl.innerHTML = `
      <a class="link-baidu" href="${baidu}" target="_blank" rel="noopener noreferrer">📖 百度百科</a>
      ${locBaidu ? `<a class="link-baidu" href="${locBaidu}" target="_blank" rel="noopener noreferrer">📍 当前位置百科</a>` : ""}
      <a class="link-amap" href="${amap}" target="_blank" rel="noopener noreferrer">🗺 高德地图</a>`;
    linksEl.classList.remove("hidden");
  }

  function formatPoiBrief(p) {
    const lines = [];
    const hours = (p.opentime || "").trim() || "以现场公告为准";
    lines.push(`<span>🕐 开放：${hours}</span>`);
    if ((p.ticket || "").trim()) {
      lines.push(`<span>🎫 门票：${p.ticket}</span>`);
    } else if ((p.cost || "").trim()) {
      lines.push(`<span>💰 消费：${p.cost}</span>`);
    } else if (activeId === "sight" || activeId === "entertainment") {
      lines.push(`<span>🎫 门票：请查询官方渠道</span>`);
    }
    if ((p.rating || "").trim()) {
      lines.push(`<span>⭐ ${p.rating}</span>`);
    }
    return lines.join("");
  }

  async function openTaxiTo(lng, lat, name) {
    if (lng == null || lat == null) {
      alert("暂无坐标，无法叫车");
      return;
    }
    try {
      const params = new URLSearchParams({ lon: lng, lat, name: name || "目的地" });
      const res = await fetch(`/api/taxi/uri?${params}`);
      const data = await res.json();
      if (res.ok && data.uri) AmapUri.openInAmap(data.uri);
      else alert("无法生成叫车链接");
    } catch {
      alert("叫车服务暂不可用");
    }
  }

  function hideExternalLinks() {
    linksEl?.classList.add("hidden");
  }

  function init(options = {}) {
    ctx = options;
    menuEl = document.getElementById("cityNavMenu");
    contentEl = document.getElementById("cityNavContent");
    locationEl = document.getElementById("cityNavLocation");
    linksEl = document.getElementById("cityNavLinks");
    loadNavMenu();
    renderPlaceholder();
    updateLocationLabel();
  }

  function getLocation() {
    return ctx.getLocation?.() || null;
  }
  function getCity() {
    return ctx.getCity?.() || "";
  }
  function getLocationLabel() {
    return ctx.getLocationLabel?.() || "";
  }

  function formatCityName(city) {
    const key = (city || "").replace(/市$/, "").trim();
    return key ? `${key}市` : "";
  }

  function updateLocationLabel() {
    if (!locationEl) return;
    const loc = getLocation();
    const label = getLocationLabel();
    const cityName = formatCityName(getCity());
    locationEl.classList.toggle("has-city", !!cityName);
    if (cityName) {
      const shortLabel = (label || "").split("·")[0].trim();
      locationEl.textContent = loc
        ? `${cityName} · ${shortLabel || "市中心"}`
        : `${cityName}（当前探索城市）`;
      return;
    }
    locationEl.textContent = loc ? label || loc : "未定位 · 对话中可报城市名";
  }

  async function reloadActiveExplore() {
    updateLocationLabel();
    if (!activeId) return;
    if (activeId === "route") {
      renderRoutePanel();
      return;
    }
    if (activeId === "tourism") {
      renderTourismPanel();
      return;
    }
    await selectCategory(activeId);
  }

  async function loadNavMenu() {
    if (!menuEl) return;
    let items = NAV_FALLBACK;
    try {
      const res = await fetch("/api/explore/nav");
      if (res.ok) {
        const data = await res.json();
        if (data.items?.length) items = sortNavItems(data.items);
      }
    } catch (_) {}

    menuEl.innerHTML = items
      .map(
        (item) => `
      <button type="button" class="city-nav-item${item.id === "tourism" ? " city-nav-item-wide" : ""}" data-id="${item.id}" title="${item.desc || ""}">
        <span class="city-nav-icon">${NAV_ICONS[item.id] || "📍"}</span>
        <span class="city-nav-label">${item.label}</span>
      </button>`
      )
      .join("");

    menuEl.querySelectorAll(".city-nav-item").forEach((btn) => {
      btn.addEventListener("click", () => selectCategory(btn.dataset.id));
    });
  }

  function setActive(id) {
    activeId = id;
    menuEl?.querySelectorAll(".city-nav-item").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.id === id);
    });
  }

  function renderPlaceholder() {
    if (!contentEl) return;
    contentEl.innerHTML =
      '<p class="city-nav-placeholder">选择上方类别探索<br><span>对话中提到城市会自动切换地图与探索范围</span></p>';
    hideExternalLinks();
  }

  function renderLoading(label) {
    contentEl.innerHTML = `<p class="city-nav-loading">正在加载${label}...</p>`;
    hideExternalLinks();
  }

  function renderError(msg) {
    contentEl.innerHTML = `<p class="city-nav-error">${msg}</p>`;
    hideExternalLinks();
  }

  function renderInfo(title, summary, extraHtml = "") {
    contentEl.innerHTML = `
      <div class="city-nav-info">
        <h4>${title}</h4>
        <pre class="city-nav-summary">${summary || "暂无数据"}</pre>
        ${extraHtml}
        <button type="button" class="btn-ghost city-nav-ask">在对话中详细询问</button>
      </div>`;
    contentEl.querySelector(".city-nav-ask")?.addEventListener("click", () => {
      const city = getCity() ? `${getCity()}市` : "";
      ctx.sendMessage?.(city ? `详细介绍${city}的${title}` : `请详细介绍${title}`);
    });
  }

  function renderPoiList(poiMap) {
    const pois = poiMap?.pois || [];
    const list = pois
      .slice(0, 12)
      .map((p, i) => {
        const name = (p.name || "未知").replace(/</g, "");
        const brief = formatPoiBrief(p);
        return `
      <div class="city-nav-poi" data-idx="${i}">
        <button type="button" class="city-nav-poi-main">
          <span class="city-nav-poi-name">${name}</span>
          <span class="city-nav-poi-meta">${p.distance ? p.distance + "m · " : ""}${p.address || ""}</span>
        </button>
        ${brief ? `<div class="city-nav-poi-brief">${brief}</div>` : ""}
        <div class="city-nav-poi-actions">
          <button type="button" class="poi-btn-detail" data-idx="${i}">详情</button>
          <a class="poi-btn-baike" href="${baiduUrl(getCity() ? `${getCity()}${name}` : name)}" target="_blank" rel="noopener">百科</a>
          <a href="${amapPoiUrl(p)}" target="_blank" rel="noopener">高德</a>
        </div>
      </div>`;
      })
      .join("");

    contentEl.innerHTML = `
      <div class="city-nav-info">
        <h4>${poiMap?.title || "周边推荐"}</h4>
        <p class="city-nav-hint">共 ${pois.length} 处 · 点击名称地图定位 · 详情含门票与开放时间</p>
        <div class="city-nav-poi-list">${list || '<p class="city-nav-empty">暂无结果</p>'}</div>
        <button type="button" class="btn-ghost city-nav-ask">让助手详细介绍</button>
      </div>`;

    contentEl.querySelectorAll(".city-nav-poi-main").forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = Number(btn.closest(".city-nav-poi")?.dataset.idx);
        const poi = pois[idx];
        if (poi) MapPanel.showPoi?.(poiMap, poi);
      });
    });
    contentEl.querySelectorAll(".poi-btn-detail").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const idx = Number(btn.dataset.idx);
        const poi = pois[idx];
        if (poi) openPoiDetail(poi, poiMap);
      });
    });
    contentEl.querySelector(".city-nav-ask")?.addEventListener("click", () => {
      ctx.sendMessage?.(`介绍一下${poiMap?.title || "这些地点"}，包含门票、开放时间和游玩建议`);
    });

    const catKey = CATEGORY_BAIKE[activeId] || poiMap?.title || "周边";
    showExternalLinks(getCity() ? `${getCity()}${catKey}` : catKey, amapLocationUrl());
  }

  function renderRoutePanel() {
    if (!contentEl) return;
    const cityHint = getCity() ? `${getCity()}市` : "";
    contentEl.innerHTML = `
      <div class="city-nav-info">
        <h4>出行导航</h4>
        <p class="city-nav-hint">${cityHint ? `当前城市 ${cityHint} · ` : ""}输入目的地，地图标注路线</p>
        <input id="cityNavRouteDest" class="city-nav-route-input" type="text" placeholder="目的地，如：火车站、商场" />
        <div class="city-nav-route-modes city-nav-transport-grid">
          <button type="button" class="city-nav-route-mode ${routeMode === "driving" ? "active" : ""}" data-mode="driving">🚗 驾车</button>
          <button type="button" class="city-nav-route-mode ${routeMode === "walking" ? "active" : ""}" data-mode="walking">🚶 步行</button>
          <button type="button" class="city-nav-route-mode ${routeMode === "transit" ? "active" : ""}" data-mode="transit">🚌 公交</button>
          <button type="button" class="city-nav-route-mode ${routeMode === "metro" ? "active" : ""}" data-mode="metro">🚇 地铁</button>
          <button type="button" class="city-nav-route-mode ${routeMode === "riding" ? "active" : ""}" data-mode="riding">🚲 骑行</button>
        </div>
        <button type="button" class="btn-ghost primary city-nav-route-plan" id="cityNavRoutePlan">规划并在地图显示</button>
        <button type="button" class="btn-ghost city-nav-route-taxi hidden" id="cityNavRouteTaxi">🚕 高德叫车前往目的地</button>
        <button type="button" class="btn-ghost city-nav-open-route">打开完整路线面板</button>
      </div>`;

    contentEl.querySelectorAll(".city-nav-route-mode").forEach((btn) => {
      btn.addEventListener("click", () => {
        routeMode = btn.dataset.mode || "driving";
        contentEl.querySelectorAll(".city-nav-route-mode").forEach((b) => {
          b.classList.toggle("active", b.dataset.mode === routeMode);
        });
      });
    });

    document.getElementById("cityNavRoutePlan")?.addEventListener("click", planRouteOnMap);
    document.getElementById("cityNavRouteTaxi")?.addEventListener("click", () => {
      if (lastRouteDest?.lnglat?.length >= 2) {
        openTaxiTo(lastRouteDest.lnglat[0], lastRouteDest.lnglat[1], lastRouteDest.name);
      } else {
        alert("请先规划路线以获取目的地坐标");
      }
    });
    contentEl.querySelector(".city-nav-open-route")?.addEventListener("click", () => {
      ctx.openRoute?.(routeMode);
    });

    lastRouteDest = null;
    showExternalLinks("导航", amapLocationUrl());
  }

  function renderTourismPanel() {
    if (!contentEl) return;
    const defaultCity = getCity() || "";
    contentEl.innerHTML = `
      <div class="city-nav-info">
        <h4>旅游路线</h4>
        <p class="city-nav-hint">串联景点与美食；对话中说城市名会自动切换定位</p>
        <input id="cityNavTourCity" class="city-nav-route-input" type="text" value="${defaultCity}" placeholder="城市，如：西安（留空用当前定位）" />
        <div class="city-nav-route-modes city-nav-tour-modes city-nav-transport-grid">
          <button type="button" class="city-nav-tour-mode ${tourMode === "walking" ? "active" : ""}" data-mode="walking">🚶 步行</button>
          <button type="button" class="city-nav-tour-mode ${tourMode === "driving" ? "active" : ""}" data-mode="driving">🚗 驾车</button>
          <button type="button" class="city-nav-tour-mode ${tourMode === "transit" ? "active" : ""}" data-mode="transit">🚌 公交</button>
          <button type="button" class="city-nav-tour-mode ${tourMode === "metro" ? "active" : ""}" data-mode="metro">🚇 地铁</button>
          <button type="button" class="city-nav-tour-mode ${tourMode === "riding" ? "active" : ""}" data-mode="riding">🚲 骑行</button>
          <button type="button" class="city-nav-tour-mode ${tourMode === "rail" ? "active" : ""}" data-mode="rail">🚄 铁路</button>
          <button type="button" class="city-nav-tour-mode ${tourMode === "flight" ? "active" : ""}" data-mode="flight">✈️ 飞机</button>
        </div>
        <button type="button" class="btn-ghost primary" id="cityNavTourPlan">规划旅游路线</button>
        <button type="button" class="btn-ghost city-nav-ask-tour">在对话中规划</button>
      </div>`;

    contentEl.querySelectorAll(".city-nav-tour-mode").forEach((btn) => {
      btn.addEventListener("click", () => {
        tourMode = btn.dataset.mode || "walking";
        contentEl.querySelectorAll(".city-nav-tour-mode").forEach((b) => {
          b.classList.toggle("active", b.dataset.mode === tourMode);
        });
      });
    });

    document.getElementById("cityNavTourPlan")?.addEventListener("click", planTourismOnMap);
    contentEl.querySelector(".city-nav-ask-tour")?.addEventListener("click", () => {
      const c = document.getElementById("cityNavTourCity")?.value?.trim() || getCity();
      const prompt = c
        ? `请规划${c.replace(/市$/, "")}市的旅游路线，串联景点与美食，并在地图显示`
        : "请根据当前位置规划旅游路线，串联景点与美食，并在地图显示";
      ctx.sendMessage?.(prompt);
    });

    const baiduKey = defaultCity ? `${defaultCity}市旅游路线` : "旅游路线规划";
    showExternalLinks(baiduKey, amapSearchUrl("景点", defaultCity));
  }

  async function ensureOriginLocation() {
    let origin = getLocation();
    let city = getCity() || "";
    if (!origin && city) {
      try {
        const res = await fetch(`/api/location/city-center?city=${encodeURIComponent(city)}`);
        if (res.ok) {
          const data = await res.json();
          if (data.location) {
            origin = data.location;
            ctx.applyLocation?.(data);
          }
        }
      } catch (_) {}
    }
    if (!origin) {
      try {
        await ctx.requestLocation?.({ reverseGeocode: true });
        origin = getLocation();
        city = getCity() || city;
      } catch (_) {}
    }
    return { origin, city };
  }

  async function planTourismOnMap() {
    const cityInput = document.getElementById("cityNavTourCity")?.value?.trim();
    let { origin: location, city } = await ensureOriginLocation();
    if (cityInput) city = cityInput.replace(/市$/, "");

    if (!location && !city) {
      alert("请先定位、填写城市，或在对话中说「西安」等切换城市");
      return;
    }

    const planBtn = document.getElementById("cityNavTourPlan");
    if (planBtn) {
      planBtn.disabled = true;
      planBtn.textContent = "规划中...";
    }

    try {
      const params = new URLSearchParams({ mode: tourMode, max_stops: "5" });
      if (location) params.set("location", location);
      if (city) params.set("city", city.replace(/市$/, ""));
      if (getLocationLabel()) params.set("location_label", getLocationLabel());

      const res = await fetch(`/api/tourism/route?${params}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "旅游路线规划失败");

      MapPanel.showRoute(data.route_map);
      if (data.poi_map) MapPanel.showPoi?.(data.poi_map);
      MapPanel.showTrafficLegend?.(false);

      const summary = data.route_map?.summary || data.summary || "";
      const hint = document.createElement("pre");
      hint.className = "city-nav-summary";
      hint.textContent = summary.slice(0, 500);
      contentEl.querySelector(".city-nav-info")?.appendChild(hint);
    } catch (e) {
      alert(e.message || "旅游路线规划失败");
    } finally {
      if (planBtn) {
        planBtn.disabled = false;
        planBtn.textContent = "规划旅游路线";
      }
    }
  }

  async function planRouteOnMap() {
    const dest = document.getElementById("cityNavRouteDest")?.value?.trim();
    if (!dest) {
      alert("请输入目的地");
      return;
    }

    const { origin, city } = await ensureOriginLocation();
    if (!origin) {
      alert("请先定位或在对话中指定城市");
      return;
    }

    const planBtn = document.getElementById("cityNavRoutePlan");
    if (planBtn) {
      planBtn.disabled = true;
      planBtn.textContent = "规划中...";
    }

    try {
      const params = new URLSearchParams({
        origin,
        destination: dest,
        mode: routeMode,
        city: city || getCity() || "",
      });
      const res = await fetch(`/api/route/plan?${params}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "路线规划失败");

      MapPanel.showRoute(data.route_map);
      MapPanel.showTrafficLegend?.(false);
      const destLnglat =
        data.route_map?.destination?.lnglat ||
        (data.route_map?.destination?.location || "").split(",").map(Number);
      if (destLnglat?.length >= 2 && !Number.isNaN(destLnglat[0])) {
        lastRouteDest = { name: dest, lnglat: destLnglat };
        document.getElementById("cityNavRouteTaxi")?.classList.remove("hidden");
      }
      showExternalLinks(dest, amapPoiUrl({ name: dest, lnglat: destLnglat }));

      const summary = data.route_map?.summary || data.summary || "";
      const hint = document.createElement("pre");
      hint.className = "city-nav-summary";
      hint.textContent = summary.slice(0, 400);
      contentEl.querySelector(".city-nav-info")?.appendChild(hint);
    } catch (e) {
      alert(e.message || "路线规划失败");
    } finally {
      if (planBtn) {
        planBtn.disabled = false;
        planBtn.textContent = "规划并在地图显示";
      }
    }
  }

  async function selectCategory(id) {
    setActive(id);
    const label = NAV_FALLBACK.find((n) => n.id === id)?.label || id;

    if (id === "route") {
      renderRoutePanel();
      return;
    }
    if (id === "tourism") {
      renderTourismPanel();
      return;
    }

    const hasCity = !!getCity();
    if (!["weather"].includes(id) && !getLocation() && !hasCity) {
      renderError("请先定位或在对话中指定城市（如：西安有什么好玩的）");
      try {
        await ctx.requestLocation?.({ reverseGeocode: true });
        updateLocationLabel();
      } catch (_) {}
      if (!getLocation() && !getCity() && id !== "weather") return;
    }

    renderLoading(label);

    try {
      const params = new URLSearchParams();
      const location = getLocation();
      if (location) params.set("location", location);
      if (getCity()) params.set("city", getCity());
      if (getLocationLabel()) params.set("location_label", getLocationLabel());

      const res = await fetch(`/api/explore/${encodeURIComponent(id)}?${params}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

      if (data.traffic_map) {
        MapPanel.showTraffic(data.traffic_map);
        MapPanel.showTrafficLegend?.(true);
        renderInfo(
          "周边实时路况",
          data.summary,
          `<p class="city-nav-traffic-tip">已加载 <strong class="traffic-on">高德官方实时路况</strong></p>
           <div class="traffic-legend-inline">
             <span class="tl-item tl-green">畅通</span>
             <span class="tl-item tl-yellow">缓行</span>
             <span class="tl-item tl-orange">拥堵</span>
             <span class="tl-item tl-red">严重</span>
           </div>`
        );
        showExternalLinks("实时路况", amapLocationUrl());
        return;
      }

      if (data.poi_map) {
        MapPanel.showTrafficLegend?.(false);
        MapPanel.showPoi(data.poi_map);
        renderPoiList(data.poi_map);
        return;
      }

      if (data.info_type === "weather" || data.info_type === "air") {
        if (location && id === "air") {
          MapPanel.showDefault?.({
            lnglat: location.split(",").map(Number),
            label: getLocationLabel() || "当前位置",
            meta: `AQI ${data.air?.aqi ?? "?"}`,
          });
        }
        const extra =
          data.info_type === "air" && data.air
            ? `<div class="city-nav-aqi aqi-${data.air.aqi <= 2 ? "good" : data.air.aqi <= 3 ? "mid" : "bad"}">AQI ${data.air.aqi} · ${data.air.label}</div>`
            : "";
        renderInfo(label, data.summary, extra);
        return;
      }

      renderInfo(label, data.summary || "暂无数据");
    } catch (e) {
      renderError(e.message || "加载失败");
    }
  }

  function refresh() {
    reloadActiveExplore();
  }

  return { init, refresh, updateLocationLabel, reloadActiveExplore, selectCategory };
})();
