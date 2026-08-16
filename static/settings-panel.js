/** 设置与隐私面板 + 我的偏好可见 */

const SettingsPanel = (() => {

  const overlay = () => document.getElementById("settingsOverlay");

  const policyEl = () => document.getElementById("settingsPolicy");

  const profileEl = () => document.getElementById("settingsProfile");

  const personaEl = () => document.getElementById("settingsPersona");



  function open() {

    overlay()?.classList.add("open");

    loadPolicy();

    loadProfileView();

    loadPersonaList();

  }



  function close() {

    overlay()?.classList.remove("open");

  }



  async function loadPolicy() {

    if (!policyEl()) return;

    try {

      const res = await fetch("/api/privacy/policy");

      const data = await res.json();

      policyEl().textContent = data.policy || "";

    } catch {

      policyEl().textContent = "无法加载隐私政策";

    }

  }



  function renderFeedbackHistory(items) {

    if (!items?.length) return '<p class="settings-muted">暂无反馈记录</p>';

    return `<ul class="settings-feedback-list">${items

      .slice(0, 10)

      .map((item) => {

        const icon = item.rating > 0 ? "👍" : "👎";

        const cat = item.category || "poi";

        return `<li>${icon} <span>${item.target}</span> <em>${cat}</em></li>`;

      })

      .join("")}</ul>`;

  }



  function renderWeights(weights) {

    const entries = Object.entries(weights || {});

    if (!entries.length) return '<p class="settings-muted">暂无权重记录</p>';

    return `<ul class="settings-weight-list">${entries

      .slice(0, 12)

      .map(([key, val]) => {

        const label = key.split(":", 1)[1] || key;

        const sign = val > 0 ? "+" : "";

        return `<li><span>${label}</span> <strong>${sign}${val}</strong></li>`;

      })

      .join("")}</ul>`;

  }



  async function loadProfileView() {

    const el = profileEl();

    if (!el) return;

    el.innerHTML = '<p class="settings-muted">加载偏好...</p>';

    try {

      const res = await fetch(`${API}/api/profile/${ensureDeviceId()}`);

      if (!res.ok) throw new Error("加载失败");

      const data = await res.json();

      const cities = (data.favorite_cities || []).join("、") || "暂无";

      el.innerHTML = `

        <div class="settings-profile-block">

          <h4>我的城市记忆</h4>

          <p class="settings-profile-summary">${data.feedback_summary || data.summary || "暂无偏好摘要"}</p>

          <p class="settings-muted">常去城市：${cities}</p>

        </div>

        <div class="settings-profile-block">

          <h4>反馈记录</h4>

          ${renderFeedbackHistory(data.feedback_history)}

        </div>

        <div class="settings-profile-block">

          <h4>推荐权重</h4>

          ${renderWeights(data.poi_weights)}

        </div>`;

    } catch {

      el.innerHTML = '<p class="settings-muted">无法加载偏好数据</p>';

    }

  }



  async function deleteMyData() {

    if (!confirm("确定删除本设备上的画像与指定会话数据吗？此操作不可恢复。")) return;

    try {

      const res = await fetch("/api/privacy/data", {

        method: "DELETE",

        headers: { "Content-Type": "application/json" },

        body: JSON.stringify({

          device_id: ensureDeviceId(),

          session_ids: sessionId ? [sessionId] : [],

        }),

      });

      if (!res.ok) throw new Error("删除失败");

      localStorage.removeItem("account_token");

      alert("数据已删除");

      close();

      await FavoritesPanel.refresh?.();

      await loadSuggestions?.();

    } catch (e) {

      alert(e.message || "删除失败");

    }

  }

  async function loadPersonaList() {
    const el = personaEl();
    if (!el) return;

    el.innerHTML = '<p class="settings-muted">加载人格列表...</p>';

    try {
      const res = await fetch("/api/persona/list");
      if (!res.ok) throw new Error("加载失败");
      const data = await res.json();
      
      const currentPersona = localStorage.getItem("current_persona") || "professional";
      
      el.innerHTML = `
        <div class="settings-profile-block">
          <h4>助手人格</h4>
          <div class="persona-list">
            ${data.personas.map(p => `
              <button 
                type="button" 
                class="persona-item ${currentPersona === p.id ? 'active' : ''}"
                data-persona-id="${p.id}"
              >
                <strong>${p.name}</strong>
                <span>${p.description}</span>
              </button>
            `).join("")}
          </div>
        </div>`;

      el.querySelectorAll(".persona-item").forEach(btn => {
        btn.addEventListener("click", () => selectPersona(btn.dataset.personaId));
      });
    } catch {
      el.innerHTML = '<p class="settings-muted">无法加载人格列表</p>';
    }
  }

  async function selectPersona(personaId) {
    try {
      const res = await fetch("/api/persona/select", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persona_id: personaId, device_id: ensureDeviceId() })
      });
      
      if (!res.ok) throw new Error("切换失败");
      
      localStorage.setItem("current_persona", personaId);
      
      document.querySelectorAll(".persona-item").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.personaId === personaId);
      });

      const data = await res.json();
      alert(`已切换为「${data.persona_name}」，下次对话将以新风格响应`);
    } catch (e) {
      alert(e.message || "切换失败");
    }
  }

  function bind() {

    document.getElementById("settingsOpenBtn")?.addEventListener("click", open);

    document.getElementById("settingsCloseBtn")?.addEventListener("click", close);

    overlay()?.addEventListener("click", (e) => {

      if (e.target === overlay()) close();

    });

    document.getElementById("settingsDeleteBtn")?.addEventListener("click", deleteMyData);

    document.getElementById("settingsAdminBtn")?.addEventListener("click", () => {

      window.open("/admin", "_blank");

    });

    document.getElementById("settingsExportBtn")?.addEventListener("click", () => {

      if (!sessionId) return alert("请先开始对话");

      window.open(`${API}/api/export/session/${sessionId}`, "_blank");

    });

  }



  bind();

  return { open, close };

})();


