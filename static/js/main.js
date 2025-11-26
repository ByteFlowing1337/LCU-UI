// main.js - module entrypoint (ES Module)
import {
  showInlineMessage,
  isLCUConnected,
  setLCUStatus,
  qs,
  formatRankBadge,
} from "./modules/ui.js";
import { fetchSummonerStats, fetchTFTMatches } from "./modules/api.js";
import { setupSocket } from "./modules/socketHandler.js";
import {
  loadChampionData,
  createChampionSelector,
  getChampionName,
} from "./modules/championSelector.js";

document.addEventListener("DOMContentLoaded", async () => {
  const detectBtn = qs("detect-btn");
  const fetchBtn = qs("fetch-btn");
  const fetchTftBtn = qs("fetch-tft-btn");
  const summonerNameInput = qs("summoner-name-input");
  const resultsDiv = qs("results-area");
  const autoAcceptBtn = qs("auto-accept-btn");
  const autoAnalyzeBtn = qs("auto-analyze-btn");
  const autoBanPickBtn = qs("auto-banpick-btn");
  const realtimeStatus = qs("realtime-status");
  const teammateResultsDiv = qs("teammate-results-area");
  const enemyResultsDiv = qs("enemy-results-area");

  // Initialize champion data and selectors
  await loadChampionData();

  // 动态 Ban/Pick 英雄选择器数组
  const banChampionSelectors = [];
  const pickChampionSelectors = [];

  // socket handlers
  const {
    socket,
    startAutoAccept,
    startAutoAnalyze,
    stopAutoAccept,
    stopAutoAnalyze,
    startAutoBanPick,
    stopAutoBanPick,
    configureBanPick,
  } = setupSocket({
    onConnect() {
      console.log("成功连接到WebSocket服务器!");
    },
    onStatusUpdate(data) {
      // Expect structured payload: { type: 'lcu'|'biz', message: '...' }
      const type = data.type || (data.data ? "lcu" : "biz");
      const message = data.message || data.data || "";

      if (type === "lcu") {
        // connection-related message -> update LCU status box
        if (message.includes("成功")) setLCUStatus(message, "ok");
        else if (message.includes("失败") || message.includes("无法"))
          setLCUStatus(message, "err");
        else setLCUStatus(message, "neutral");
      } else {
        // business message -> realtime area
        showInlineMessage(message, { level: "info", timeout: 5000 });
      }
    },
    onEnemiesFound: async (data) => {
      realtimeStatus.textContent = `💥 发现 ${data.enemies.length} 名敌人! 正在分析战绩...`;
      realtimeStatus.className = "badge bg-danger";
      enemyResultsDiv.innerHTML =
        '<h5 class="text-danger"><i class="bi bi-exclamation-triangle-fill me-2"></i>敌方目标分析:</h5>';
      const ul = document.createElement("ul");
      ul.className = "list-unstyled";
      enemyResultsDiv.appendChild(ul);

      const promises = data.enemies.map((enemy) => {
        const li = document.createElement("li");
        li.className = "d-flex flex-column border-bottom py-2 mb-2";
        const headerDiv = document.createElement("div");
        headerDiv.className =
          "d-flex justify-content-between align-items-center flex-wrap";

        const nameDiv = document.createElement("div");
        nameDiv.className = "d-flex align-items-center gap-2";

        const riotIdLink = document.createElement("a");
        riotIdLink.href = `/summoner/${encodeURIComponent(
          enemy.gameName + "#" + enemy.tagLine
        )}`;
        riotIdLink.target = "_blank";
        riotIdLink.rel = "noopener noreferrer";
        riotIdLink.className = "fw-bold text-danger text-decoration-none";
        riotIdLink.style.cursor = "pointer";
        riotIdLink.innerHTML = `<i class="bi bi-person-x-fill me-1"></i>${enemy.gameName}#${enemy.tagLine}`;
        riotIdLink.title = "点击查看详细战绩";
        nameDiv.appendChild(riotIdLink);

        // 添加段位信息
        if (enemy.rank) {
          const rankBadge = document.createElement("span");
          rankBadge.innerHTML = formatRankBadge(enemy.rank);
          nameDiv.appendChild(rankBadge);
        }

        headerDiv.appendChild(nameDiv);

        if (enemy.championId && enemy.championId !== "Unknown") {
          const championSpan = document.createElement("span");
          championSpan.className = "badge bg-dark";
          championSpan.textContent = enemy.championId;
          headerDiv.appendChild(championSpan);
        }
        li.appendChild(headerDiv);
        const statsDisplay = document.createElement("div");
        statsDisplay.textContent = "⏳ 查询中...";
        statsDisplay.className = "text-muted small mt-1";
        li.appendChild(statsDisplay);
        ul.appendChild(li);
        return fetchSummonerStats(enemy.gameName, enemy.tagLine, statsDisplay);
      });

      await Promise.all(promises);
      realtimeStatus.textContent = `✅ 敌方战绩分析完成!`;
      realtimeStatus.className = "badge bg-success";
    },
    onTeammatesFound: async (data) => {
      realtimeStatus.textContent = `👥 发现 ${data.teammates.length} 名队友! 正在分析战绩...`;
      realtimeStatus.className = "badge bg-info";
      teammateResultsDiv.innerHTML =
        '<h5 class="text-primary"><i class="bi bi-people-fill me-2"></i>本局队友分析:</h5>';
      const ul = document.createElement("ul");
      ul.className = "list-unstyled";
      teammateResultsDiv.appendChild(ul);

      const promises = data.teammates.map((tm) => {
        const li = document.createElement("li");
        li.className = "d-flex flex-column border-bottom py-2 mb-2";
        const headerDiv = document.createElement("div");
        headerDiv.className =
          "d-flex justify-content-between align-items-center flex-wrap";

        const nameDiv = document.createElement("div");
        nameDiv.className = "d-flex align-items-center gap-2";

        const riotIdLink = document.createElement("a");
        riotIdLink.href = `/summoner/${encodeURIComponent(
          tm.gameName + "#" + tm.tagLine
        )}`;
        riotIdLink.target = "_blank";
        riotIdLink.rel = "noopener noreferrer";
        riotIdLink.className = "fw-bold text-primary text-decoration-none";
        riotIdLink.style.cursor = "pointer";
        riotIdLink.innerHTML = `<i class="bi bi-person-check-fill me-1"></i>${tm.gameName}#${tm.tagLine}`;
        riotIdLink.title = "点击查看详细战绩";
        nameDiv.appendChild(riotIdLink);

        // 添加段位信息
        if (tm.rank) {
          const rankBadge = document.createElement("span");
          rankBadge.innerHTML = formatRankBadge(tm.rank);
          nameDiv.appendChild(rankBadge);
        }

        headerDiv.appendChild(nameDiv);
        li.appendChild(headerDiv);
        const statsDisplay = document.createElement("div");
        statsDisplay.textContent = "⏳ 查询中...";
        statsDisplay.className = "text-muted small mt-1";
        li.appendChild(statsDisplay);
        ul.appendChild(li);
        return fetchSummonerStats(tm.gameName, tm.tagLine, statsDisplay);
      });

      await Promise.all(promises);
      realtimeStatus.textContent = `✅ 队友分析完成! 等待游戏开始...`;
      realtimeStatus.className = "badge bg-success";
      console.log("队友战绩分析全部完成");
    },
  });

  // --- UI actions ---
  fetchBtn.addEventListener("click", () => {
    const summonerName = summonerNameInput.value.trim();
    if (!summonerName) {
      showInlineMessage("请输入召唤师名称 (格式: 名称#Tag)", { level: "warn" });
      return;
    }
    const encodedName = encodeURIComponent(summonerName);
    // Open summoner detail in a new tab instead of replacing current page
    window.open(`/summoner/${encodedName}`, "_blank", "noopener");
  });

  if (fetchTftBtn) {
    fetchTftBtn.addEventListener("click", () => {
      const summonerName = summonerNameInput.value.trim();
      if (!summonerName) {
        showInlineMessage("请输入召唤师名称 (格式: 名称#Tag)", {
          level: "warn",
        });
        return;
      }
      const encodedName = encodeURIComponent(summonerName);
      // open a dedicated TFT summoner page in a new tab
      window.open(`/tft_summoner/${encodedName}`, "_blank", "noopener");
    });
  }

  // --- Sidebar Navigation ---
  const navDashboard = document.getElementById("nav-dashboard");
  const navSearch = document.getElementById("nav-search");
  const navAutomation = document.getElementById("nav-automation");
  const navStats = document.getElementById("nav-stats");
  const navSettings = document.getElementById("nav-settings");
  const navLogout = document.getElementById("nav-logout");

  function setActiveNav(element) {
    document.querySelectorAll(".nav-item").forEach((el) => {
      el.classList.remove("active");
    });
    if (element) element.classList.add("active");
  }

  if (navDashboard) {
    navDashboard.addEventListener("click", (e) => {
      e.preventDefault();
      setActiveNav(navDashboard);
      // If we are not on the dashboard (index), go there.
      // Since this is a SPA-like feel but with multi-pages, we check pathname
      if (window.location.pathname !== "/") {
        window.location.href = "/";
      } else {
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    });
  }

  if (navSearch) {
    navSearch.addEventListener("click", (e) => {
      e.preventDefault();
      setActiveNav(navSearch);
      if (window.location.pathname !== "/") {
        window.location.href = "/?action=search";
      } else {
        summonerNameInput.focus();
        summonerNameInput.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  }

  if (navAutomation) {
    navAutomation.addEventListener("click", (e) => {
      e.preventDefault();
      setActiveNav(navAutomation);
      if (window.location.pathname !== "/") {
        window.location.href = "/?action=automation";
      } else {
        const automationHub = document.getElementById("automation-hub");
        if (automationHub) {
          automationHub.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }
    });
  }

  if (navStats) {
    navStats.addEventListener("click", (e) => {
      e.preventDefault();
      setActiveNav(navStats);
      window.location.href = "/live_game";
    });
  }

  if (navSettings) {
    navSettings.addEventListener("click", (e) => {
      e.preventDefault();
      setActiveNav(navSettings);
      showInlineMessage("设置功能开发中...", { level: "info" });
    });
  }

  if (navLogout) {
    navLogout.addEventListener("click", (e) => {
      e.preventDefault();
      showInlineMessage("退出功能暂不可用", { level: "warn" });
    });
  }

  // Check URL params for actions (e.g. coming from another page)
  const urlParams = new URLSearchParams(window.location.search);
  const action = urlParams.get("action");
  if (action === "search") {
    setTimeout(() => {
        setActiveNav(navSearch);
        summonerNameInput.focus();
        summonerNameInput.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 500);
  } else if (action === "automation") {
    setTimeout(() => {
        setActiveNav(navAutomation);
        const automationHub = document.getElementById("automation-hub");
        if (automationHub) {
            automationHub.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }, 500);
  } else if (window.location.pathname === "/live_game") {
      setActiveNav(navStats);
  } else if (window.location.pathname === "/") {
      setActiveNav(navDashboard);
  }

  let autoAcceptRunning = false;
  let autoAnalyzeRunning = false;
  let autoBanPickRunning = false;

  // localStorage 键名用于记忆自动化功能开关状态
  const STORAGE_KEY_AUTO_ACCEPT = "lcu_ui_auto_accept_enabled";
  const STORAGE_KEY_AUTO_ANALYZE = "lcu_ui_auto_analyze_enabled";
  const STORAGE_KEY_AUTO_BANPICK = "lcu_ui_auto_banpick_enabled";

  // 保存自动化功能开关状态
  function saveAutoFeatureStates() {
    try {
      localStorage.setItem(
        STORAGE_KEY_AUTO_ACCEPT,
        autoAcceptRunning.toString()
      );
      localStorage.setItem(
        STORAGE_KEY_AUTO_ANALYZE,
        autoAnalyzeRunning.toString()
      );
      localStorage.setItem(
        STORAGE_KEY_AUTO_BANPICK,
        autoBanPickRunning.toString()
      );
    } catch (e) {
      console.warn("保存自动化功能状态失败:", e);
    }
  }

  // 恢复自动化功能开关状态
  function restoreAutoFeatureStates() {
    try {
      const savedAutoAccept =
        localStorage.getItem(STORAGE_KEY_AUTO_ACCEPT) === "true";
      const savedAutoAnalyze =
        localStorage.getItem(STORAGE_KEY_AUTO_ANALYZE) === "true";
      const savedAutoBanPick =
        localStorage.getItem(STORAGE_KEY_AUTO_BANPICK) === "true";

      // 如果上次是开启状态，且 LCU 已连接，则自动启动
      if (savedAutoAccept && isLCUConnected()) {
        setTimeout(() => autoAcceptBtn.click(), 500);
      }
      if (savedAutoAnalyze && isLCUConnected()) {
        setTimeout(() => autoAnalyzeBtn.click(), 600);
      }
      if (savedAutoBanPick && isLCUConnected()) {
        setTimeout(() => autoBanPickBtn.click(), 700);
      }

      console.log("已恢复自动化功能状态:", {
        autoAccept: savedAutoAccept,
        autoAnalyze: savedAutoAnalyze,
        autoBanPick: savedAutoBanPick,
      });
    } catch (e) {
      console.warn("恢复自动化功能状态失败:", e);
    }
  }

  autoAcceptBtn.addEventListener("click", () => {
    if (!isLCUConnected()) {
      showInlineMessage(
        "无法启动自动接受：未检测到LCU连接，请先确保客户端已运行并且LCU已连接。",
        { level: "error", timeout: 8000 }
      );
      return;
    }

    if (!autoAcceptRunning) {
      // 启动
      startAutoAccept();
      autoAcceptRunning = true;
      autoAcceptBtn.innerHTML =
        '<i class="bi bi-stop-circle-fill me-1"></i> 停止接受';
      autoAcceptBtn.classList.remove("btn-success");
      autoAcceptBtn.classList.add("btn-danger");
      showInlineMessage("自动接受对局已启动", { level: "info" });
      saveAutoFeatureStates();
    } else {
      // 停止
      stopAutoAccept();
      autoAcceptRunning = false;
      autoAcceptBtn.innerHTML =
        '<i class="bi bi-check-circle-fill me-1"></i> 自动接受对局';
      autoAcceptBtn.classList.remove("btn-danger");
      autoAcceptBtn.classList.add("btn-success");
      showInlineMessage("自动接受对局已停止", { level: "info" });
      saveAutoFeatureStates();
    }
  });

  autoAnalyzeBtn.addEventListener("click", () => {
    if (!isLCUConnected()) {
      showInlineMessage(
        "无法启动敌我分析：未检测到LCU连接，请先确保客户端已运行并且LCU已连接。",
        { level: "error", timeout: 8000 }
      );
      return;
    }

    if (!autoAnalyzeRunning) {
      // 启动
      startAutoAnalyze();
      autoAnalyzeRunning = true;
      autoAnalyzeBtn.innerHTML =
        '<i class="bi bi-stop-circle-fill me-1"></i> 停止分析';
      autoAnalyzeBtn.classList.remove("btn-primary");
      autoAnalyzeBtn.classList.add("btn-danger");
      showInlineMessage("敌我分析已启动", { level: "info" });
      saveAutoFeatureStates();
    } else {
      // 停止
      stopAutoAnalyze();
      autoAnalyzeRunning = false;
      autoAnalyzeBtn.innerHTML =
        '<i class="bi bi-bar-chart-fill me-1"></i> 敌我分析';
      autoAnalyzeBtn.classList.remove("btn-danger");
      autoAnalyzeBtn.classList.add("btn-primary");
      showInlineMessage("敌我分析已停止", { level: "info" });
      saveAutoFeatureStates();
    }
  });

  // Auto Ban/Pick Button Handler
  if (autoBanPickBtn) {
    // Ban/Pick 英雄优先队列
    const banQueue = [];
    const pickQueue = [];

    const banSelectorsContainer = document.getElementById(
      "ban-selectors-container"
    );
    const pickSelectorsContainer = document.getElementById(
      "pick-selectors-container"
    );

    let banSelectorIdCounter = 0;
    let pickSelectorIdCounter = 0;

    // localStorage 键名
    const STORAGE_KEY_BAN = "lcu_ui_ban_champions";
    const STORAGE_KEY_PICK = "lcu_ui_pick_champions";

    // 添加新的 Ban 选择器
    function addBanSelector() {
      const index = banChampionSelectors.length;
      const selectorId = `ban-champion-selector-${banSelectorIdCounter++}`;
      const wrapper = document.createElement("div");
      wrapper.className = "selector-wrapper";
      wrapper.id = `${selectorId}-wrapper`;

      const selectorDiv = document.createElement("div");
      selectorDiv.id = selectorId;
      wrapper.appendChild(selectorDiv);

      // 添加删除按钮
      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "selector-delete-btn";
      deleteBtn.innerHTML = '<i class="bi bi-x-lg"></i>';
      deleteBtn.title = "删除此选择器";
      deleteBtn.addEventListener("click", () => {
        removeBanSelector(index);
      });
      wrapper.appendChild(deleteBtn);

      banSelectorsContainer.appendChild(wrapper);

      const selector = createChampionSelector(selectorId);
      banChampionSelectors.push(selector);

      // 监听选择变化
      document
        .getElementById(selectorId)
        .addEventListener("championChanged", () => {
          rebuildQueueFromSelectors();

          // 如果这是最后一个选择器且已选择英雄，添加新选择器
          const lastSelector =
            banChampionSelectors[banChampionSelectors.length - 1];
          if (selector === lastSelector && selector.getSelectedChampionId()) {
            addBanSelector();
          }

          updateBackendConfig();
        });

      return selector;
    }

    // 添加新的 Pick 选择器
    function addPickSelector() {
      const index = pickChampionSelectors.length;
      const selectorId = `pick-champion-selector-${pickSelectorIdCounter++}`;
      const wrapper = document.createElement("div");
      wrapper.className = "selector-wrapper";
      wrapper.id = `${selectorId}-wrapper`;

      const selectorDiv = document.createElement("div");
      selectorDiv.id = selectorId;
      wrapper.appendChild(selectorDiv);

      // 添加删除按钮
      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "selector-delete-btn";
      deleteBtn.innerHTML = '<i class="bi bi-x-lg"></i>';
      deleteBtn.title = "删除此选择器";
      deleteBtn.addEventListener("click", () => {
        removePickSelector(index);
      });
      wrapper.appendChild(deleteBtn);

      pickSelectorsContainer.appendChild(wrapper);

      const selector = createChampionSelector(selectorId);
      pickChampionSelectors.push(selector);

      // 监听选择变化
      document
        .getElementById(selectorId)
        .addEventListener("championChanged", () => {
          rebuildQueueFromSelectors();

          // 如果这是最后一个选择器且已选择英雄，添加新选择器
          const lastSelector =
            pickChampionSelectors[pickChampionSelectors.length - 1];
          if (selector === lastSelector && selector.getSelectedChampionId()) {
            addPickSelector();
          }

          updateBackendConfig();
        });

      return selector;
    }

    // 删除 Ban 选择器
    function removeBanSelector(index) {
      if (index >= 0 && index < banChampionSelectors.length) {
        // 通过遍历容器找到对应的 wrapper
        const wrappers =
          banSelectorsContainer.querySelectorAll(".selector-wrapper");
        if (wrappers[index]) {
          wrappers[index].remove();
        }

        banChampionSelectors.splice(index, 1);
        rebuildQueueFromSelectors();
        updateBackendConfig();

        // 确保至少有一个空选择器
        if (
          banChampionSelectors.length === 0 ||
          !banChampionSelectors.some((s) => !s.getSelectedChampionId())
        ) {
          addBanSelector();
        }
      }
    }

    // 删除 Pick 选择器
    function removePickSelector(index) {
      if (index >= 0 && index < pickChampionSelectors.length) {
        // 通过遍历容器找到对应的 wrapper
        const wrappers =
          pickSelectorsContainer.querySelectorAll(".selector-wrapper");
        if (wrappers[index]) {
          wrappers[index].remove();
        }

        pickChampionSelectors.splice(index, 1);
        rebuildQueueFromSelectors();
        updateBackendConfig();

        // 确保至少有一个空选择器
        if (
          pickChampionSelectors.length === 0 ||
          !pickChampionSelectors.some((s) => !s.getSelectedChampionId())
        ) {
          addPickSelector();
        }
      }
    }

    // 从队列中删除英雄（通过清除选择器并移除它）
    function removeChampionFromQueue(type, index) {
      if (type === "ban") {
        removeBanSelector(index);
      } else if (type === "pick") {
        removePickSelector(index);
      }
    }

    // 保存当前选择到 localStorage
    function saveSelectionsToStorage() {
      try {
        const banIds = banQueue.filter((id) => id);
        const pickIds = pickQueue.filter((id) => id);
        localStorage.setItem(STORAGE_KEY_BAN, JSON.stringify(banIds));
        localStorage.setItem(STORAGE_KEY_PICK, JSON.stringify(pickIds));
      } catch (e) {
        console.warn("保存 Ban/Pick 选择失败:", e);
      }
    }

    // 从 localStorage 恢复上次选择
    function loadSelectionsFromStorage() {
      try {
        const savedBanIds = JSON.parse(
          localStorage.getItem(STORAGE_KEY_BAN) || "[]"
        );
        const savedPickIds = JSON.parse(
          localStorage.getItem(STORAGE_KEY_PICK) || "[]"
        );

        // 为每个保存的 Ban ID 创建选择器并设置
        savedBanIds.forEach((id) => {
          const selector = addBanSelector();
          selector.setSelectedChampion(id);
        });

        // 为每个保存的 Pick ID 创建选择器并设置
        savedPickIds.forEach((id) => {
          const selector = addPickSelector();
          selector.setSelectedChampion(id);
        });

        // 重建队列
        rebuildQueueFromSelectors();
        console.log("已恢复上次 Ban/Pick 选择:", {
          ban: savedBanIds,
          pick: savedPickIds,
        });
      } catch (e) {
        console.warn("加载 Ban/Pick 选择失败:", e);
      }

      // 确保至少有一个空的 Ban 和 Pick 选择器
      if (
        banChampionSelectors.length === 0 ||
        !banChampionSelectors.some((s) => !s.getSelectedChampionId())
      ) {
        addBanSelector();
      }
      if (
        pickChampionSelectors.length === 0 ||
        !pickChampionSelectors.some((s) => !s.getSelectedChampionId())
      ) {
        addPickSelector();
      }
    }

    function rebuildQueueFromSelectors() {
      // 从所有选择器中读取已选英雄ID，按顺序构建队列
      banQueue.length = 0;
      pickQueue.length = 0;

      banChampionSelectors.forEach((selector) => {
        if (selector) {
          const id = selector.getSelectedChampionId();
          if (id) banQueue.push(id);
        }
      });

      pickChampionSelectors.forEach((selector) => {
        if (selector) {
          const id = selector.getSelectedChampionId();
          if (id) pickQueue.push(id);
        }
      });

      saveSelectionsToStorage();
    }

    // 更新后端配置
    function updateBackendConfig() {
      const banId = banQueue[0] || null;
      const pickId = pickQueue[0] || null;
      configureBanPick({
        ban_champion_id: banId,
        pick_champion_id: pickId,
        ban_candidates: [...banQueue],
        pick_candidates: [...pickQueue],
      });
    }

    autoBanPickBtn.addEventListener("click", () => {
      if (!isLCUConnected()) {
        showInlineMessage(
          "无法启动自动Ban/Pick：未检测到LCU连接，请先确保客户端已运行并且LCU已连接。",
          { level: "error", timeout: 8000 }
        );
        return;
      }

      if (!autoBanPickRunning) {
        // Get champion IDs from selectors
        rebuildQueueFromSelectors();
        const banId = banQueue[0] || null;
        const pickId = pickQueue[0] || null;

        const banCandidates = [...banQueue];
        const pickCandidates = [...pickQueue];

        // Start with configuration (包含备选队列)
        startAutoBanPick({
          ban_champion_id: banId,
          pick_champion_id: pickId,
          ban_candidates: banCandidates,
          pick_candidates: pickCandidates,
        });
        autoBanPickRunning = true;
        autoBanPickBtn.innerHTML =
          '<i class="bi bi-stop-circle-fill me-1"></i> 停止 Ban/Pick';
        autoBanPickBtn.classList.remove("btn-warning");
        autoBanPickBtn.classList.add("btn-danger");
        showInlineMessage(
          `自动Ban/Pick已启动 (Ban: ${banId || "未设置"}, Pick: ${
            pickId || "未设置"
          })`,
          { level: "info" }
        );
        saveAutoFeatureStates();
      } else {
        // Stop
        stopAutoBanPick();
        autoBanPickRunning = false;
        autoBanPickBtn.innerHTML =
          '<i class="bi bi-lightning-charge-fill me-1"></i> 启动自动 Ban/Pick';
        autoBanPickBtn.classList.remove("btn-danger");
        autoBanPickBtn.classList.add("btn-warning");
        showInlineMessage("自动Ban/Pick已停止", { level: "info" });
        saveAutoFeatureStates();
      }
    });

    // 页面加载时恢复上次的选择
    loadSelectionsFromStorage();
  }

  // 在 socket 连接后恢复自动化功能状态
  socket.on("connect", () => {
    setTimeout(() => {
      restoreAutoFeatureStates();
    }, 1000); // 等待 LCU 连接状态稳定
  });
});
// (removed duplicate legacy module block)
