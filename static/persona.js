/** 使用身份：游客 / 本地 / 学者 — 影响文案、建议与界面强调 */
const Persona = (() => {
  const STORAGE_KEY = "cityintro_persona";

  const PERSONAS = {
    tourist: {
      id: "tourist",
      label: "游客",
      icon: "🧳",
      desc: "景点、路线、门票与轻松游玩",
      chipStyle: "warm",
      placeholder: "帮我规划一日游，推荐必去景点和美食…",
      greeting: "欢迎来探索这座城市",
    },
    local: {
      id: "local",
      label: "本地",
      icon: "🏠",
      desc: "路况、周边实用、美食与出行",
      chipStyle: "route",
      placeholder: "附近有什么好吃的？现在路况怎么样？",
      greeting: "本地生活助手已就绪",
    },
    scholar: {
      id: "scholar",
      label: "学者",
      icon: "📚",
      desc: "文化、博物馆、深度百科",
      chipStyle: "poi",
      placeholder: "介绍这座城市的历史文化与博物馆…",
      greeting: "人文探索模式",
    },
  };

  let current = localStorage.getItem(STORAGE_KEY) || "tourist";

  function get() {
    return PERSONAS[current] ? current : "tourist";
  }

  function getMeta(id) {
    return PERSONAS[id || get()] || PERSONAS.tourist;
  }

  function applyToDocument(personaId) {
    const id = personaId || get();
    current = PERSONAS[id] ? id : "tourist";
    localStorage.setItem(STORAGE_KEY, current);
    document.body.classList.remove("persona-tourist", "persona-local", "persona-scholar");
    document.body.classList.add(`persona-${current}`);
    const input = document.getElementById("messageInput");
    if (input) input.placeholder = getMeta().placeholder;
    return current;
  }

  async function saveToServer(deviceId) {
    if (!deviceId) return;
    try {
      await fetch(`/api/profile/${encodeURIComponent(deviceId)}/preferences`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persona: get() }),
      });
    } catch (_) {}
  }

  async function loadFromServer(deviceId) {
    if (!deviceId) return applyToDocument();
    try {
      const res = await fetch(`/api/profile/${encodeURIComponent(deviceId)}`);
      if (res.ok) {
        const data = await res.json();
        const p = data.preferences?.persona;
        if (p && PERSONAS[p]) return applyToDocument(p);
      }
    } catch (_) {}
    return applyToDocument();
  }

  function renderSelector(container, { onChange } = {}) {
    if (!container) return;
    container.innerHTML = Object.values(PERSONAS)
      .map(
        (p) => `
      <button type="button" class="persona-chip ${p.id === get() ? "active" : ""}" data-persona="${p.id}">
        <span class="persona-chip-icon">${p.icon}</span>
        <span class="persona-chip-label">${p.label}</span>
        <span class="persona-chip-desc">${p.desc}</span>
      </button>`
      )
      .join("");
    container.querySelectorAll("[data-persona]").forEach((btn) => {
      btn.addEventListener("click", () => {
        applyToDocument(btn.dataset.persona);
        container.querySelectorAll("[data-persona]").forEach((b) => {
          b.classList.toggle("active", b.dataset.persona === get());
        });
        onChange?.(get());
      });
    });
  }

  return {
    PERSONAS,
    get,
    getMeta,
    applyToDocument,
    saveToServer,
    loadFromServer,
    renderSelector,
  };
})();
