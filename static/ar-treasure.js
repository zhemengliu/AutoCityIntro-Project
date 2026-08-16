const TREASURE_CONFIG = {
  RADIUS_METERS: 50,
  CHECK_INTERVAL_MS: 3000,
  isDebugMode: false,
  debugLocation: {
    lat: 34.2658,
    lng: 108.0711
  },
  debugLocations: [
    { id: "kunchong_bowuguan", name: "昆虫博物馆", lat: 34.2658, lng: 108.0711 },
    { id: "yaowangdong", name: "药王洞", lat: 34.2580, lng: 108.0650 },
    { id: "wutai_shan_huanDao", name: "五台山环道公园", lat: 34.2750, lng: 108.0550 },
    { id: "fenghuangling_gongyuan", name: "凤凰岭公园", lat: 34.2800, lng: 108.0800 },
    { id: "yangling_fengqing", name: "杨凌风情商业街", lat: 34.2600, lng: 108.0700 },
    { id: "beijing", name: "北京（远离所有点）", lat: 39.9042, lng: 116.4074 }
  ],
  TREASURE_SPOTS: [
    {
      id: "kunchong_bowuguan",
      name: "昆虫博物馆",
      desc: "西北农林科技大学昆虫博物馆",
      lat: 34.2658,
      lng: 108.0711,
      rewards: [
        { type: "badge", name: "昆虫探索家", icon: "🦋", desc: "探索了昆虫博物馆" },
        { type: "points", value: 100, desc: "积分+100" }
      ]
    },
    {
      id: "yaowangdong",
      name: "药王洞",
      desc: "历史悠久的药王洞",
      lat: 34.2580,
      lng: 108.0650,
      rewards: [
        { type: "badge", name: "药王弟子", icon: "💊", desc: "探索了药王洞" },
        { type: "points", value: 150, desc: "积分+150" }
      ]
    },
    {
      id: "wutai_shan_huanDao",
      name: "五台山环道公园",
      desc: "五台山环道公园",
      lat: 34.2750,
      lng: 108.0550,
      rewards: [
        { type: "badge", name: "环道漫步者", icon: "🌲", desc: "探索了五台山环道公园" },
        { type: "points", value: 80, desc: "积分+80" }
      ]
    },
    {
      id: "fenghuangling_gongyuan",
      name: "凤凰岭公园",
      desc: "凤凰岭公园",
      lat: 34.2800,
      lng: 108.0800,
      rewards: [
        { type: "badge", name: "凤凰岭游客", icon: "🦅", desc: "探索了凤凰岭公园" },
        { type: "points", value: 120, desc: "积分+120" }
      ]
    },
    {
      id: "yangling_fengqing",
      name: "杨凌风情商业街",
      desc: "杨凌风情商业街",
      lat: 34.2600,
      lng: 108.0700,
      rewards: [
        { type: "badge", name: "商业街达人", icon: "🛍️", desc: "探索了杨凌风情商业街" },
        { type: "points", value: 200, desc: "积分+200" }
      ]
    }
  ]
};

class ARTreasureHunt {
  constructor() {
    this.collectedTreasures = new Set();
    this.currentSpot = null;
    this.nearbySpot = null;
    this.isInGeofence = false;
    this.watchId = null;
    this.checkTimer = null;
    this.loadCollectedTreasures();
  }

  loadCollectedTreasures() {
    try {
      const saved = localStorage.getItem("collected_treasures");
      if (saved) {
        const arr = JSON.parse(saved);
        arr.forEach(id => this.collectedTreasures.add(id));
      }
    } catch (e) {
      console.error("加载已收集宝藏失败:", e);
    }
  }

  saveCollectedTreasures() {
    try {
      localStorage.setItem("collected_treasures", JSON.stringify([...this.collectedTreasures]));
    } catch (e) {
      console.error("保存已收集宝藏失败:", e);
    }
  }

  init() {
    this.bindEvents();
    this.renderEntryButton();
    this.renderDebugToggle();
    this.renderDebugLocationSelector();
    this.renderDebugIndicator();
  }

  bindEvents() {
    const closeBtn = document.getElementById("arCloseBtn");
    if (closeBtn) {
      closeBtn.removeEventListener("click", this.closeARView.bind(this));
      closeBtn.addEventListener("click", () => {
        console.log("关闭AR面板");
        this.closeARView();
      });
    }
    document.getElementById("arOpenChestBtn")?.addEventListener("click", () => this.openChest());
    document.getElementById("arClaimRewardBtn")?.addEventListener("click", () => this.claimReward());
  }

  renderDebugToggle() {
    const actions = document.querySelector(".topbar-actions");
    if (!actions) return;

    const existingBtn = document.getElementById("debugToggleBtn");
    if (existingBtn) return;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.id = "debugToggleBtn";
    btn.className = "btn-debug-toggle";
    btn.title = "切换调试模式";
    btn.innerHTML = TREASURE_CONFIG.isDebugMode ? "🔧" : "✅";
    btn.addEventListener("click", () => this.toggleDebugMode());
    actions.appendChild(btn);

    const resetBtn = document.createElement("button");
    resetBtn.type = "button";
    resetBtn.id = "resetTreasuresBtn";
    resetBtn.className = "btn-reset-treasures";
    resetBtn.title = "重置已收集的宝藏";
    resetBtn.innerHTML = "🗑️";
    resetBtn.addEventListener("click", () => this.resetCollectedTreasures());
    actions.appendChild(resetBtn);
  }

  toggleDebugMode() {
    TREASURE_CONFIG.isDebugMode = !TREASURE_CONFIG.isDebugMode;
    const btn = document.getElementById("debugToggleBtn");
    if (btn) {
      btn.innerHTML = TREASURE_CONFIG.isDebugMode ? "🔧" : "✅";
    }
    this.updateDebugIndicator();
    this.updateDebugLocationSelector();

    if (TREASURE_CONFIG.isDebugMode) {
      this.updateDebugPosition();
    } else {
      this.hideAllHints();
    }

    alert(TREASURE_CONFIG.isDebugMode ? "已开启调试模式" : "已关闭调试模式");
  }

  resetCollectedTreasures() {
    this.collectedTreasures.clear();
    localStorage.removeItem("collected_treasures");
    alert("已重置所有已收集的宝藏！");
    if (TREASURE_CONFIG.isDebugMode) {
      this.updateDebugPosition();
    }
  }

  renderDebugLocationSelector() {
    const actions = document.querySelector(".topbar-actions");
    if (!actions) return;

    const existingSelector = document.getElementById("debugLocationSelector");
    if (existingSelector) return;

    const selector = document.createElement("select");
    selector.id = "debugLocationSelector";
    selector.className = "debug-location-selector";
    selector.title = "选择模拟位置";
    selector.style.display = TREASURE_CONFIG.isDebugMode ? "block" : "none";

    TREASURE_CONFIG.debugLocations.forEach((loc) => {
      const option = document.createElement("option");
      option.value = loc.id;
      option.textContent = loc.name;
      if (TREASURE_CONFIG.debugLocation.lat === loc.lat && TREASURE_CONFIG.debugLocation.lng === loc.lng) {
        option.selected = true;
      }
      selector.appendChild(option);
    });

    selector.addEventListener("change", (e) => {
      this.onDebugLocationChange(e.target.value);
    });

    actions.appendChild(selector);
  }

  updateDebugLocationSelector() {
    const selector = document.getElementById("debugLocationSelector");
    if (selector) {
      selector.style.display = TREASURE_CONFIG.isDebugMode ? "block" : "none";
    }
  }

  renderDebugIndicator() {
    const existingIndicator = document.getElementById("debugIndicator");
    if (existingIndicator) {
      existingIndicator.remove();
    }

    const indicator = document.createElement("div");
    indicator.id = "debugIndicator";
    indicator.className = "debug-indicator";
    indicator.textContent = "🔧 模拟测试模式";
    indicator.style.display = TREASURE_CONFIG.isDebugMode ? "block" : "none";
    document.body.appendChild(indicator);
  }

  updateDebugIndicator() {
    const indicator = document.getElementById("debugIndicator");
    if (indicator) {
      indicator.style.display = TREASURE_CONFIG.isDebugMode ? "block" : "none";
    }
  }

  onDebugLocationChange(locationId) {
    const location = TREASURE_CONFIG.debugLocations.find(loc => loc.id === locationId);
    if (location) {
      TREASURE_CONFIG.debugLocation = { lat: location.lat, lng: location.lng };
      this.resetTreasureState();
      this.updateDebugPosition();
    }
  }

  updateDebugPosition() {
    if (!TREASURE_CONFIG.isDebugMode) return;

    const fakePos = {
      coords: {
        latitude: TREASURE_CONFIG.debugLocation.lat,
        longitude: TREASURE_CONFIG.debugLocation.lng
      }
    };
    this.onLocationUpdate(fakePos);
  }

  resetTreasureState() {
    const overlay = document.getElementById("arOverlay");
    const videoEl = document.getElementById("arVideo");
    const rewardEl = document.getElementById("arRewardPanel");

    if (videoEl?.srcObject) {
      videoEl.srcObject.getTracks().forEach(t => t.stop());
      videoEl.srcObject = null;
    }

    overlay?.classList.add("hidden");
    rewardEl?.classList.add("hidden");

    const chestClosed = document.getElementById("chestClosed");
    const chestOpened = document.getElementById("chestOpened");
    const openBtn = document.getElementById("arOpenChestBtn");

    chestClosed?.classList.remove("hidden");
    chestClosed?.classList.add("bounce");
    chestOpened?.classList.add("hidden");
    openBtn?.classList.remove("hidden");

    this.currentSpot = null;
    this.isInGeofence = false;
  }

  renderEntryButton() {
    const actions = document.querySelector(".topbar-actions");
    if (!actions) return;

    const existingBtn = document.getElementById("arEntryBtn");
    if (existingBtn) return;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.id = "arEntryBtn";
    btn.className = "btn-ar-entry";
    btn.title = "AR寻宝";
    btn.innerHTML = `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>`;
    btn.addEventListener("click", () => this.startTreasureHunt());
    actions.appendChild(btn);
  }

  startTreasureHunt() {
    if (TREASURE_CONFIG.isDebugMode) {
      this.showStatus("调试模式：使用虚拟定位...");
      const fakePos = {
        coords: {
          latitude: TREASURE_CONFIG.debugLocation.lat,
          longitude: TREASURE_CONFIG.debugLocation.lng
        }
      };
      this.onLocationUpdate(fakePos);
      return;
    }

    if (navigator.geolocation) {
      this.showStatus("正在获取位置...");
      this.watchId = navigator.geolocation.watchPosition(
        (pos) => this.onLocationUpdate(pos),
        (err) => {
          console.error("定位失败:", err);
          this.showStatus("定位失败，请检查定位权限");
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 0
        }
      );
    } else {
      alert("您的浏览器不支持地理定位");
    }
  }

  stopTracking() {
    if (this.watchId) {
      navigator.geolocation.clearWatch(this.watchId);
      this.watchId = null;
    }
    if (this.checkTimer) {
      clearTimeout(this.checkTimer);
      this.checkTimer = null;
    }
  }

  onLocationUpdate(pos) {
    const userLat = pos.coords.latitude;
    const userLng = pos.coords.longitude;

    let nearestSpot = null;
    let nearestDistance = Infinity;

    for (const spot of TREASURE_CONFIG.TREASURE_SPOTS) {
      const distance = this.calcDistance(userLat, userLng, spot.lat, spot.lng);
      const effectiveDistance = TREASURE_CONFIG.isDebugMode ? 0 : distance;

      if (effectiveDistance <= TREASURE_CONFIG.RADIUS_METERS) {
        if (TREASURE_CONFIG.isDebugMode || !this.collectedTreasures.has(spot.id)) {
          nearestSpot = spot;
          nearestDistance = effectiveDistance;
          break;
        }
      }

      if (effectiveDistance < nearestDistance && (TREASURE_CONFIG.isDebugMode || !this.collectedTreasures.has(spot.id))) {
        nearestDistance = effectiveDistance;
        nearestSpot = spot;
      }
    }

    this.nearbySpot = nearestSpot;

    if (nearestSpot && nearestDistance <= TREASURE_CONFIG.RADIUS_METERS) {
      this.showTreasureAlert(nearestSpot, nearestDistance);
    } else if (nearestSpot) {
      this.showNearbyHint(nearestSpot, nearestDistance);
    } else {
      this.hideAllHints();
    }
  }

  calcDistance(lat1, lng1, lat2, lng2) {
    const R = 6371000;
    const dLat = this.toRad(lat2 - lat1);
    const dLng = this.toRad(lng2 - lng1);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(this.toRad(lat1)) * Math.cos(this.toRad(lat2)) *
      Math.sin(dLng / 2) * Math.sin(dLng / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  toRad(deg) {
    return deg * (Math.PI / 180);
  }

  showStatus(msg) {
    const statusBar = document.getElementById("statusBar");
    const statusText = document.getElementById("statusText");
    if (statusBar) {
      statusBar.classList.remove("hidden");
      if (statusText) statusText.textContent = msg;
    }
  }

  showTreasureAlert(spot, distance) {
    this.currentSpot = spot;
    this.isInGeofence = true;

    let alertEl = document.getElementById("arTreasureAlert");
    if (!alertEl) {
      alertEl = document.createElement("div");
      alertEl.id = "arTreasureAlert";
      alertEl.className = "ar-treasure-alert";
      document.body.appendChild(alertEl);
    }

    alertEl.innerHTML = `
      <div class="alert-content">
        <div class="alert-icon">📍</div>
        <div class="alert-info">
          <h4>发现宝藏点！</h4>
          <p>${spot.name}</p>
          <span class="alert-distance">距离 ${Math.round(distance)} 米</span>
        </div>
        <button type="button" id="arDiscoverBtn" class="btn-discover">发现宝藏</button>
      </div>
    `;

    alertEl.classList.remove("hidden");
    alertEl.querySelector("#arDiscoverBtn")?.addEventListener("click", () => this.openARView());

    this.stopTracking();
  }

  showNearbyHint(spot, distance) {
    this.currentSpot = spot;
    this.isInGeofence = false;

    let hintEl = document.getElementById("arNearbyHint");
    if (!hintEl) {
      hintEl = document.createElement("div");
      hintEl.id = "arNearbyHint";
      hintEl.className = "ar-nearby-hint";
      document.body.appendChild(hintEl);
    }

    hintEl.innerHTML = `
      <div class="hint-content">
        <span class="hint-icon">🔍</span>
        <span class="hint-text">附近有宝藏点: ${spot.name} (${Math.round(distance)}米)</span>
      </div>
    `;

    hintEl.classList.remove("hidden");

    setTimeout(() => {
      hintEl.classList.add("hidden");
    }, 5000);
  }

  hideAllHints() {
    document.getElementById("arTreasureAlert")?.classList.add("hidden");
    document.getElementById("arNearbyHint")?.classList.add("hidden");
    this.currentSpot = null;
    this.isInGeofence = false;
  }

  async openARView() {
    const overlay = document.getElementById("arOverlay");
    const videoEl = document.getElementById("arVideo");
    const chestClosed = document.getElementById("chestClosed");
    const chestOpened = document.getElementById("chestOpened");

    if (!overlay || !videoEl || !chestClosed || !chestOpened) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" }
      });
      videoEl.srcObject = stream;
    } catch (e) {
      console.error("无法访问摄像头:", e);
      videoEl.style.display = "none";
    }

    overlay.classList.remove("hidden");
    chestClosed.classList.remove("hidden");
    chestOpened.classList.add("hidden");
    chestClosed.classList.add("bounce");
    this.showStatus("");
  }

  closeARView() {
    const overlay = document.getElementById("arOverlay");
    const videoEl = document.getElementById("arVideo");
    const chestClosed = document.getElementById("chestClosed");
    const chestOpened = document.getElementById("chestOpened");
    const rewardEl = document.getElementById("arRewardPanel");
    const openBtn = document.getElementById("arOpenChestBtn");

    if (videoEl?.srcObject) {
      videoEl.srcObject.getTracks().forEach(t => t.stop());
      videoEl.srcObject = null;
    }

    overlay?.classList.add("hidden");
    rewardEl?.classList.add("hidden");
    chestClosed?.classList.remove("hidden");
    chestOpened?.classList.add("hidden");
    chestClosed?.classList.add("bounce");
    openBtn?.classList.remove("hidden");

    this.currentSpot = null;

    this.startTreasureHunt();
  }

  openChest() {
    const chestClosed = document.getElementById("chestClosed");
    const chestOpened = document.getElementById("chestOpened");
    const openBtn = document.getElementById("arOpenChestBtn");

    if (!chestClosed || !chestOpened || !openBtn || !this.currentSpot) return;

    chestClosed.classList.remove("bounce");
    chestClosed.classList.add("hidden");
    chestOpened.classList.remove("hidden");
    openBtn.classList.add("hidden");

    setTimeout(() => {
      this.showReward();
    }, 800);
  }

  showReward() {
    const rewardEl = document.getElementById("arRewardPanel");
    const spotNameEl = document.getElementById("rewardSpotName");
    const rewardListEl = document.getElementById("rewardList");

    if (!rewardEl || !spotNameEl || !rewardListEl || !this.currentSpot) return;

    spotNameEl.textContent = this.currentSpot.name;

    let rewardHtml = "";
    this.currentSpot.rewards.forEach((reward, index) => {
      rewardHtml += `
        <div class="reward-item" style="animation-delay: ${index * 0.1}s">
          <span class="reward-icon">${reward.icon || "🎁"}</span>
          <div class="reward-info">
            <span class="reward-name">${reward.name || reward.desc || "奖励"}</span>
            <span class="reward-desc">${reward.desc || ""}</span>
          </div>
        </div>
      `;
    });

    rewardListEl.innerHTML = rewardHtml;
    rewardEl.classList.remove("hidden");
  }

  claimReward() {
    if (!this.currentSpot) return;

    this.collectedTreasures.add(this.currentSpot.id);
    this.saveCollectedTreasures();

    const rewardEl = document.getElementById("arRewardPanel");
    rewardEl?.classList.add("hidden");

    alert(`恭喜！您已获得${this.currentSpot.name}的奖励！`);

    this.closeARView();
  }
}

const AR_TREASURE = new ARTreasureHunt();

document.addEventListener("DOMContentLoaded", () => {
  setTimeout(() => AR_TREASURE.init(), 500);
});