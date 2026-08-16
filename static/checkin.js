/**
 * 每日签到模块
 * 使用 localStorage 保存签到数据
 */

const CheckinModule = (() => {
  // 存储键名
  const STORAGE_KEY = 'cityintro_checkin_data';
  
  // 每日步数要求
  const DAILY_STEP_REQUIREMENT = 3000;
  
  // 奖励配置
  const REWARDS = {
    1: { coins: 10, name: '金币', desc: '基础奖励' },
    2: { coins: 15, name: '金币', desc: '连续签到奖励' },
    3: { coins: 20, name: '金币', desc: '连续签到奖励' },
    4: { coins: 25, name: '金币', desc: '连续签到奖励' },
    5: { coins: 30, name: '金币', desc: '连续签到奖励' },
    6: { coins: 40, name: '金币', desc: '连续签到奖励' },
    7: { coins: 100, name: '宝箱', desc: '大奖！绝版徽章', isGrand: true }
  };

  // 获取今日步数（基于定位移动计算）
  function getTodaySteps() {
    try {
      const data = localStorage.getItem('cityintro_steps_data');
      if (data) {
        const stepsData = JSON.parse(data);
        const today = getTodayStr();
        if (stepsData[today] !== undefined) {
          return stepsData[today];
        }
      }
    } catch {
      console.error('获取步数数据失败');
    }
    // 默认步数为0（未开始移动）
    return 0;
  }

  // 保存步数数据
  function saveTodaySteps(steps) {
    try {
      const data = localStorage.getItem('cityintro_steps_data');
      const stepsData = data ? JSON.parse(data) : {};
      const today = getTodayStr();
      stepsData[today] = steps;
      localStorage.setItem('cityintro_steps_data', JSON.stringify(stepsData));
    } catch (e) {
      console.error('保存步数数据失败:', e);
    }
  }

  // 根据位置变化计算步数（每步约0.7米）
  function calculateStepsFromDistance(distanceMeters) {
    const stepLength = 0.7; // 平均步长（米）
    return Math.round(distanceMeters / stepLength);
  }

  // 记录位置变化并更新步数
  function updateStepsFromLocation(newLocation, oldLocation) {
    if (!oldLocation || !newLocation) return;
    
    const distance = calculateDistance(
      oldLocation.latitude, oldLocation.longitude,
      newLocation.latitude, newLocation.longitude
    );
    
    if (distance > 1) { // 移动超过1米才计算
      const currentSteps = getTodaySteps();
      const addedSteps = calculateStepsFromDistance(distance);
      const newSteps = currentSteps + addedSteps;
      saveTodaySteps(newSteps);
      updateSidebarUI();
    }
  }

  // 计算两点之间的距离（米）
  function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371000; // 地球半径（米）
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = 
      Math.sin(dLat/2) * Math.sin(dLat/2) +
      Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * 
      Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
  }

  // 检查是否满足步数要求
  function hasEnoughSteps() {
    const steps = getTodaySteps();
    return steps >= DAILY_STEP_REQUIREMENT;
  }

  // 获取当前步数进度
  function getStepProgress() {
    const steps = getTodaySteps();
    return {
      current: steps,
      required: DAILY_STEP_REQUIREMENT,
      percentage: Math.min(100, Math.round((steps / DAILY_STEP_REQUIREMENT) * 100))
    };
  }

  // 获取今日日期字符串（YYYY-MM-DD）
  function getTodayStr() {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  }

  // 获取昨日日期字符串
  function getYesterdayStr() {
    const now = new Date();
    now.setDate(now.getDate() - 1);
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  }

  // 获取签到数据
  function getCheckinData() {
    try {
      const data = localStorage.getItem(STORAGE_KEY);
      return data ? JSON.parse(data) : null;
    } catch {
      return null;
    }
  }

  // 保存签到数据
  function saveCheckinData(data) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (e) {
      console.error('保存签到数据失败:', e);
    }
  }

  // 初始化/更新签到数据
  function initCheckinData() {
    let data = getCheckinData();
    const today = getTodayStr();
    
    if (!data) {
      // 首次使用，初始化数据
      data = {
        lastCheckInDate: null,
        continuousDays: 0,
        totalCoins: 0,
        completedDays: [] // 记录已完成的日期
      };
    }

    // 检查是否需要重置连续天数
    if (data.lastCheckInDate) {
      const yesterday = getYesterdayStr();
      // 如果上次签到不是昨天或今天，重置连续天数
      if (data.lastCheckInDate !== today && data.lastCheckInDate !== yesterday) {
        data.continuousDays = 0;
      }
    }

    return data;
  }

  // 判断今天是否已签到
  function hasCheckedInToday() {
    const data = getCheckinData();
    return data?.lastCheckInDate === getTodayStr();
  }

  // 获取当前连续签到天数
  function getContinuousDays() {
    const data = initCheckinData();
    return data.continuousDays;
  }

  // 执行签到
  function doCheckin() {
    if (hasCheckedInToday()) {
      return { success: false, message: '今天已经签到过了' };
    }

    // 检查步数要求
    if (!hasEnoughSteps()) {
      const progress = getStepProgress();
      return { 
        success: false, 
        message: `还需走 ${progress.required - progress.current} 步才能签到`,
        stepProgress: progress 
      };
    }

    let data = initCheckinData();
    const today = getTodayStr();
    
    // 计算新的连续天数
    let newDays = data.continuousDays + 1;
    if (newDays > 7) {
      newDays = 1; // 超过7天重新开始
    }

    // 获取今日奖励
    const reward = REWARDS[newDays] || { coins: 10, name: '金币', desc: '奖励' };

    // 更新数据
    data.lastCheckInDate = today;
    data.continuousDays = newDays;
    data.totalCoins += reward.coins;
    if (!data.completedDays.includes(today)) {
      data.completedDays.push(today);
    }

    // 保存数据
    saveCheckinData(data);

    // 更新UI
    updateSidebarUI();

    return {
      success: true,
      message: '签到成功！',
      days: newDays,
      reward: reward,
      totalCoins: data.totalCoins
    };
  }

  // 更新侧边栏UI
  function updateSidebarUI() {
    const days = getContinuousDays();
    const checkedIn = hasCheckedInToday();
    const stepProgress = getStepProgress();
    const hasSteps = hasEnoughSteps();

    // 更新签到按钮文字
    const checkinBtn = document.getElementById('checkinBtn');
    const checkinText = document.getElementById('checkinText');
    const checkinDays = document.getElementById('checkinDays');
    const progressBar = document.getElementById('progressBar');
    const daysLeft = document.getElementById('daysLeft');
    
    // 步数进度相关元素
    const stepProgressEl = document.getElementById('stepProgress');
    const stepProgressBar = document.getElementById('stepProgressBar');
    const stepText = document.getElementById('stepText');

    if (checkinBtn && checkinText) {
      if (checkedIn) {
        checkinBtn.classList.add('disabled');
        checkinText.textContent = '今日已签到';
      } else if (!hasSteps) {
        checkinBtn.classList.add('disabled');
        checkinText.textContent = '步数不足';
      } else {
        checkinBtn.classList.remove('disabled');
        checkinText.textContent = '每日签到';
      }
    }

    if (checkinDays) {
      checkinDays.textContent = `连续 ${days} 天`;
    }

    if (progressBar) {
      progressBar.style.width = `${(days / 7) * 100}%`;
    }

    if (daysLeft) {
      daysLeft.textContent = String(Math.max(0, 7 - days));
    }

    // 更新步数进度UI
    if (stepProgressEl && stepProgressBar && stepText) {
      stepProgressEl.style.display = 'block'; // 始终显示步数进度
      stepProgressBar.style.width = `${stepProgress.percentage}%`;
      if (checkedIn) {
        stepText.textContent = `✅ 今日已完成`;
        stepProgressBar.classList.add('completed');
      } else if (hasSteps) {
        stepText.textContent = `✅ 今日步数达标`;
        stepProgressBar.classList.add('completed');
      } else {
        stepText.textContent = `🏃 ${stepProgress.current}/${stepProgress.required} 步`;
        stepProgressBar.classList.remove('completed');
      }
    }
  }

  // 渲染签到日历
  function renderCheckinCalendar() {
    const container = document.getElementById('checkinDaysContainer');
    if (!container) return;

    const data = initCheckinData();
    const today = getTodayStr();
    const continuousDays = data.continuousDays;
    const completedDays = data.completedDays || [];
    const checkedInToday = hasCheckedInToday();

    let html = '';
    
    for (let i = 1; i <= 7; i++) {
      const reward = REWARDS[i];
      let classes = 'checkin-day-card';
      
      // 判断状态
      if (i <= continuousDays) {
        classes += ' completed';
      } else if (i === continuousDays + 1 && !checkedInToday) {
        classes += ' current';
      } else if (i > continuousDays + 1) {
        classes += ' locked';
      }
      
      // 第7天标记为大奖
      if (i === 7) {
        classes += ' grand-prize';
      }

      html += `
        <div class="${classes}">
          <span class="day-number">第${i}天</span>
          <span class="day-reward">${reward.isGrand ? '🏆' : `${reward.coins}${reward.name}`}</span>
        </div>
      `;
    }

    container.innerHTML = html;
  }

  // 创建撒花动画
  function createConfetti() {
    const container = document.getElementById('confettiContainer');
    if (!container) return;

    // 清除之前的撒花
    container.innerHTML = '';

    const colors = ['#fbbf24', '#22c55e', '#0ea5e9', '#a855f7', '#f97316', '#ec4899'];
    const count = 50;

    for (let i = 0; i < count; i++) {
      const confetti = document.createElement('div');
      confetti.className = 'confetti';
      confetti.style.left = `${Math.random() * 100}%`;
      confetti.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
      confetti.style.animationDelay = `${Math.random() * 0.5}s`;
      confetti.style.animationDuration = `${1.5 + Math.random() * 1}s`;
      confetti.style.width = `${6 + Math.random() * 8}px`;
      confetti.style.height = confetti.style.width;
      container.appendChild(confetti);
    }

    // 2秒后清除
    setTimeout(() => {
      container.innerHTML = '';
    }, 2000);
  }

  // 显示奖励弹窗
  function showReward(days, reward) {
    const rewardEl = document.getElementById('checkinReward');
    const rewardTitle = document.getElementById('rewardTitle');
    const rewardDesc = document.getElementById('rewardDesc');
    const rewardAmount = document.getElementById('rewardAmount');

    if (!rewardEl) return;

    rewardEl.classList.remove('hidden');
    
    if (reward.isGrand) {
      rewardTitle.textContent = '🎉 恭喜获得大奖！';
      rewardDesc.textContent = reward.desc;
      rewardAmount.textContent = `🏆 ${reward.coins} ${reward.name}`;
      rewardAmount.classList.add('grand');
    } else {
      rewardTitle.textContent = '🎊 签到成功！';
      rewardDesc.textContent = reward.desc;
      rewardAmount.textContent = `💰 +${reward.coins} ${reward.name}`;
      rewardAmount.classList.remove('grand');
    }

    // 创建撒花动画
    createConfetti();
  }

  // 打开签到弹窗
  function openCheckinModal() {
    const overlay = document.getElementById('checkinOverlay');
    const doCheckinBtn = document.getElementById('doCheckinBtn');
    
    if (!overlay) return;

    // 渲染日历
    renderCheckinCalendar();

    // 更新签到按钮状态
    const checkedIn = hasCheckedInToday();
    if (doCheckinBtn) {
      doCheckinBtn.disabled = checkedIn;
      doCheckinBtn.textContent = checkedIn ? '今日已签到' : '点击签到';
    }

    // 隐藏奖励提示
    const rewardEl = document.getElementById('checkinReward');
    if (rewardEl) {
      rewardEl.classList.add('hidden');
    }

    overlay.classList.add('open');
  }

  // 关闭签到弹窗
  function closeCheckinModal() {
    const overlay = document.getElementById('checkinOverlay');
    if (overlay) {
      overlay.classList.remove('open');
    }
  }

  // 绑定事件
  function bindEvents() {
    // 侧边栏签到按钮
    const checkinBtn = document.getElementById('checkinBtn');
    if (checkinBtn) {
      checkinBtn.addEventListener('click', () => {
        if (!checkinBtn.classList.contains('disabled')) {
          openCheckinModal();
        }
      });
    }

    // 弹窗关闭按钮
    const closeBtn = document.getElementById('checkinCloseBtn');
    if (closeBtn) {
      closeBtn.addEventListener('click', closeCheckinModal);
    }

    // 遮罩层点击关闭
    const overlay = document.getElementById('checkinOverlay');
    if (overlay) {
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
          closeCheckinModal();
        }
      });
    }

    // 执行签到按钮
    const doCheckinBtn = document.getElementById('doCheckinBtn');
    const stepWarning = document.getElementById('stepWarning');
    if (doCheckinBtn) {
      doCheckinBtn.addEventListener('click', () => {
        const result = doCheckin();
        if (result.success) {
          showReward(result.days, result.reward);
          // 更新日历和按钮状态
          renderCheckinCalendar();
          doCheckinBtn.disabled = true;
          doCheckinBtn.textContent = '今日已签到';
          // 隐藏步数警告
          if (stepWarning) {
            stepWarning.style.display = 'none';
          }
        } else {
          // 显示步数警告
          if (stepWarning && result.stepProgress) {
            stepWarning.style.display = 'block';
            stepWarning.innerHTML = `<p>🚶 今日步数：${result.stepProgress.current}/${result.stepProgress.required} 步</p><p>${result.message}</p>`;
          }
        }
      });
    }
  }

  // 初始化模块
  function init() {
    // 更新侧边栏UI
    updateSidebarUI();
    // 绑定事件
    bindEvents();
  }

  // 暴露方法供外部调用
  return {
    init,
    doCheckin,
    hasCheckedInToday,
    getContinuousDays,
    getTodaySteps,
    saveTodaySteps,
    updateStepsFromLocation
  };
})();

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
  CheckinModule.init();
});