/**
 * 主题切换模块
 * 使用 localStorage 保存用户选择的主题
 */

const ThemeModule = (() => {
  // 存储键名
  const STORAGE_KEY = 'cityintro_theme';
  
  // 默认主题
  const DEFAULT_THEME = 'dark';

  // 主题配置
  const THEMES = {
    light: {
      id: 'light',
      name: '明亮模式',
      icon: '☀️',
      previewColors: ['#FFFFFF', '#333333', '#007BFF']
    },
    dark: {
      id: 'dark',
      name: '暗黑模式',
      icon: '🌙',
      previewColors: ['#121212', '#E0E0E0', '#BB86FC']
    },
    forest: {
      id: 'forest',
      name: '森林绿',
      icon: '🌲',
      previewColors: ['#F1F8E9', '#1B5E20', '#4CAF50']
    },
    ocean: {
      id: 'ocean',
      name: '海洋蓝',
      icon: '🌊',
      previewColors: ['#E3F2FD', '#0D47A1', '#2196F3']
    },
    pink: {
      id: 'pink',
      name: '少女粉',
      icon: '🌸',
      previewColors: ['#FCE4EC', '#880E4F', '#E91E63']
    }
  };

  // 获取保存的主题
  function getSavedTheme() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved && THEMES[saved] ? saved : DEFAULT_THEME;
    } catch {
      return DEFAULT_THEME;
    }
  }

  // 保存主题到 localStorage
  function saveTheme(themeId) {
    try {
      localStorage.setItem(STORAGE_KEY, themeId);
    } catch (e) {
      console.error('保存主题失败:', e);
    }
  }

  // 应用主题
  function applyTheme(themeId) {
    if (!THEMES[themeId]) return;

    // 移除所有主题类
    document.body.classList.remove(...Object.keys(THEMES).map(id => `${id}-theme`));
    
    // 添加新主题类
    document.body.classList.add(`${themeId}-theme`);

    // 保存到 localStorage
    saveTheme(themeId);

    // 更新主题弹窗中的选中状态
    updateThemeList(themeId);

    // 更新主题切换按钮显示
    updateThemeToggleBtn(themeId);
  }

  // 更新主题列表UI
  function updateThemeList(activeThemeId) {
    const themeCards = document.querySelectorAll('.theme-card');
    themeCards.forEach(card => {
      const cardThemeId = card.dataset.themeId;
      if (cardThemeId === activeThemeId) {
        card.classList.add('active');
      } else {
        card.classList.remove('active');
      }
    });
  }

  // 更新主题切换按钮显示
  function updateThemeToggleBtn(themeId) {
    const theme = THEMES[themeId];
    const toggleBtn = document.getElementById('themeToggleBtn');
    if (toggleBtn && theme) {
      toggleBtn.innerHTML = `${theme.icon} ${theme.name}`;
    }
  }

  // 渲染主题列表
  function renderThemeList() {
    const container = document.getElementById('themeList');
    if (!container) return;

    const currentTheme = getSavedTheme();
    let html = '';

    Object.values(THEMES).forEach(theme => {
      const previewColors = theme.previewColors.map((color, index) => 
        `<span class="theme-preview-color" style="background-color: ${color}" title="${index === 0 ? '背景色' : index === 1 ? '文字色' : '主色'}"></span>`
      ).join('');

      html += `
        <div class="theme-card ${theme.id === currentTheme ? 'active' : ''}" data-theme-id="${theme.id}">
          <span class="theme-icon">${theme.icon}</span>
          <span class="theme-name">${theme.name}</span>
          <span class="theme-desc">点击切换</span>
          <div class="theme-preview">${previewColors}</div>
        </div>
      `;
    });

    container.innerHTML = html;

    // 绑定点击事件
    const themeCards = container.querySelectorAll('.theme-card');
    themeCards.forEach(card => {
      card.addEventListener('click', () => {
        const themeId = card.dataset.themeId;
        applyTheme(themeId);
      });
    });
  }

  // 打开主题选择弹窗
  function openThemeModal() {
    const overlay = document.getElementById('themeOverlay');
    if (!overlay) return;

    // 渲染主题列表
    renderThemeList();

    overlay.classList.add('open');
  }

  // 关闭主题选择弹窗
  function closeThemeModal() {
    const overlay = document.getElementById('themeOverlay');
    if (overlay) {
      overlay.classList.remove('open');
    }
  }

  // 绑定事件
  function bindEvents() {
    // 主题切换按钮
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    if (themeToggleBtn) {
      themeToggleBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        openThemeModal();
        // 关闭更多菜单
        const moreMenu = document.getElementById('moreMenu');
        moreMenu?.classList.add('hidden');
      });
    }

    // 弹窗关闭按钮
    const closeBtn = document.getElementById('themeCloseBtn');
    if (closeBtn) {
      closeBtn.addEventListener('click', closeThemeModal);
    }

    // 遮罩层点击关闭
    const overlay = document.getElementById('themeOverlay');
    if (overlay) {
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
          closeThemeModal();
        }
      });
    }
  }

  // 初始化模块
  function init() {
    // 应用保存的主题
    const savedTheme = getSavedTheme();
    applyTheme(savedTheme);

    // 绑定事件
    bindEvents();
  }

  // 暴露方法供外部调用
  return {
    init,
    applyTheme,
    getSavedTheme,
    THEMES
  };
})();

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
  ThemeModule.init();
});