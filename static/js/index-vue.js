document.addEventListener("DOMContentLoaded", () => {
  try {
    if (typeof Vue === "undefined" || typeof antd === "undefined") {
      console.error("Critical dependencies missing:", {
        Vue: typeof Vue,
        antd: typeof antd,
      });
      const loadingError = document.getElementById("loading-error");
      if (loadingError) {
        loadingError.style.display = "block";
        loadingError.innerHTML += `<div>Error: Critical dependencies (Vue or AntD) failed to load.</div>`;
      }
      return;
    }

    const { createApp, ref, computed, onMounted } = Vue;
    const { theme } = antd;

    const initialNode = document.getElementById("vue-initial-data");
    const INITIAL_DATA = JSON.parse(initialNode?.textContent || "{}");

    const app = createApp({
      setup() {
        const darkTheme = {
          algorithm: theme.darkAlgorithm,
          token: {
            colorPrimary: "#1668dc",
            colorBgContainer: "rgba(255, 255, 255, 0.03)",
            colorBgElevated: "rgba(20, 20, 30, 0.95)",
            colorBorder: "rgba(255, 255, 255, 0.1)",
            borderRadius: 12,
          },
        };

        const selectedNav = ref(["dashboard"]);
        const lcuConnected = ref(INITIAL_DATA.lcuConnected);
        const summonerName = ref(INITIAL_DATA.summonerName);
        const recentGames = ref(INITIAL_DATA.recentGames);
        const searchName = ref("");
        const realtimeStatus = ref("等待指令...");

        const autoAcceptRunning = ref(false);
        const autoAnalyzeRunning = ref(false);
        const autoBanPickRunning = ref(false);

        const banChampions = ref([null]);
        const pickChampions = ref([null]);
        const championOptions = ref([]);

        const teammates = ref([]);
        const enemies = ref([]);

        const activeModulesCount = computed(() => {
          return [
            autoAcceptRunning.value,
            autoAnalyzeRunning.value,
            autoBanPickRunning.value,
          ].filter(Boolean).length;
        });

        let socket = null;

        onMounted(async () => {
          const overlay = document.getElementById("loading-overlay");
          if (overlay) {
            overlay.style.opacity = "0";
            setTimeout(() => overlay.remove(), 500);
          }

          try {
            const res = await fetch("/api/champions");
            const data = await res.json();
            championOptions.value = Object.entries(data).map(([id, name]) => ({
              value: parseInt(id),
              label: name,
            }));
          } catch (e) {
            console.error("Failed to load champions:", e);
          }

          loadPreferences();

          console.log("Initializing Socket.IO connection...");
          socket = io();
          socket.on("connect", () => {
            console.log("✅ WebSocket connected successfully");
            realtimeStatus.value = "已连接到服务器";
          });
          socket.on("connect_error", (error) => {
            console.error("❌ Socket.IO connection error:", error);
            realtimeStatus.value = "连接失败";
          });
          socket.on("disconnect", (reason) => {
            console.warn("🔌 Socket.IO disconnected:", reason);
            realtimeStatus.value = "连接已断开";
          });
          socket.on("status_update", (data) => {
            const msg = data.message || data.data || "";
            if (msg.includes("成功")) lcuConnected.value = true;
            else if (msg.includes("失败") || msg.includes("断开"))
              lcuConnected.value = false;
            realtimeStatus.value = msg;
          });
          socket.on("enemies_found", (data) => {
            enemies.value = data.enemies.map((e) => ({
              ...e,
              stats: "Loading...",
            }));
            realtimeStatus.value = `发现 ${data.enemies.length} 名敌人!`;
            data.enemies.forEach(async (enemy, idx) => {
              enemies.value[idx].stats = await fetchStats(
                enemy.gameName,
                enemy.tagLine
              );
            });
          });
          socket.on("teammates_found", (data) => {
            teammates.value = data.teammates.map((tm) => ({
              ...tm,
              stats: "Loading...",
            }));
            realtimeStatus.value = `发现 ${data.teammates.length} 名队友!`;
            data.teammates.forEach(async (tm, idx) => {
              teammates.value[idx].stats = await fetchStats(
                tm.gameName,
                tm.tagLine
              );
            });
          });
        });

        const searchSummoner = () => {
          if (!searchName.value.trim()) {
            antd.message.warning("请输入召唤师名称");
            return;
          }
          window.open(
            `/summoner/${encodeURIComponent(searchName.value)}`,
            "_blank"
          );
        };

        const searchTFT = () => {
          if (!searchName.value.trim()) {
            antd.message.warning("请输入召唤师名称");
            return;
          }
          window.open(
            `/tft_summoner/${encodeURIComponent(searchName.value)}`,
            "_blank"
          );
        };

        const ensureConnected = () => {
          if (!lcuConnected.value) {
            antd.message.error("请先连接到 LCU");
            return false;
          }
          return true;
        };

        const toggleAutoAccept = () => {
          if (!ensureConnected()) return;
          autoAcceptRunning.value = !autoAcceptRunning.value;
          socket.emit(
            autoAcceptRunning.value ? "start_auto_accept" : "stop_auto_accept"
          );
          antd.message.info(
            autoAcceptRunning.value ? "自动接受已启动" : "自动接受已停止"
          );
          savePreferences();
        };

        const toggleAutoAnalyze = () => {
          if (!ensureConnected()) return;
          autoAnalyzeRunning.value = !autoAnalyzeRunning.value;
          socket.emit(
            autoAnalyzeRunning.value
              ? "start_auto_analyze"
              : "stop_auto_analyze"
          );
          antd.message.info(
            autoAnalyzeRunning.value ? "敌我分析已启动" : "敌我分析已停止"
          );
          savePreferences();
        };

        const toggleAutoBanPick = () => {
          if (!ensureConnected()) return;
          autoBanPickRunning.value = !autoBanPickRunning.value;
          if (autoBanPickRunning.value) {
            socket.emit("start_auto_banpick", {
              ban_champion_id: banChampions.value[0],
              pick_champion_id: pickChampions.value[0],
              ban_candidates: banChampions.value.filter(Boolean),
              pick_candidates: pickChampions.value.filter(Boolean),
            });
          } else {
            socket.emit("stop_auto_banpick");
          }
          antd.message.info(
            autoBanPickRunning.value
              ? "自动Ban/Pick已启动"
              : "自动Ban/Pick已停止"
          );
          savePreferences();
        };

        const addBanSlot = () => banChampions.value.push(null);
        const addPickSlot = () => pickChampions.value.push(null);
        const filterChampion = (input, option) =>
          option.label.toLowerCase().includes(input.toLowerCase());

        const fetchStats = async (gameName, tagLine) => {
          try {
            const res = await fetch(
              `/api/summoner_stats/${encodeURIComponent(
                gameName
              )}/${encodeURIComponent(tagLine)}`
            );
            const data = await res.json();
            if (data.error) return "Stats unavailable";
            return `${data.wins}W ${data.losses}L (${data.winrate}% WR)`;
          } catch {
            return "Stats unavailable";
          }
        };

        const savePreferences = () => {
          try {
            localStorage.setItem(
              "lcu_ui_ban_champions",
              JSON.stringify(banChampions.value.filter(Boolean))
            );
            localStorage.setItem(
              "lcu_ui_pick_champions",
              JSON.stringify(pickChampions.value.filter(Boolean))
            );
          } catch {}
        };

        const loadPreferences = () => {
          try {
            const bans = JSON.parse(
              localStorage.getItem("lcu_ui_ban_champions") || "[]"
            );
            const picks = JSON.parse(
              localStorage.getItem("lcu_ui_pick_champions") || "[]"
            );
            if (bans.length) banChampions.value = [...bans, null];
            if (picks.length) pickChampions.value = [...picks, null];
          } catch {}
        };

        const navigateTo = (key) => {
          if (key === "stats") antd.message.info("实时游戏模块已移除");
          else if (key === "search")
            document.querySelector(".ant-input")?.focus();
        };

        return {
          darkTheme,
          selectedNav,
          lcuConnected,
          summonerName,
          recentGames,
          searchName,
          realtimeStatus,
          autoAcceptRunning,
          autoAnalyzeRunning,
          autoBanPickRunning,
          banChampions,
          pickChampions,
          championOptions,
          teammates,
          enemies,
          activeModulesCount,
          navigateTo,
          searchSummoner,
          searchTFT,
          toggleAutoAccept,
          toggleAutoAnalyze,
          toggleAutoBanPick,
          addBanSlot,
          addPickSlot,
          filterChampion,
        };
      },
    });

    app.use(antd);
    app.mount("#app");
  } catch (error) {
    console.error("Vue initialization error:", error);
    if (error && error.loc) {
      console.error("Vue template location:", error.loc);
    }
    try {
      const tpl = document.getElementById("app")?.innerHTML || "";
      console.error("Vue template preview:", tpl.slice(0, 500));
    } catch {}
    const loadingError = document.getElementById("loading-error");
    if (loadingError) {
      loadingError.style.display = "block";
      loadingError.innerHTML += `
        <div style="margin-top: 20px;">
          <strong>Vue Initialization Error:</strong><br>
          <small>${error.message || error.toString()}</small><br>
          ${
            error.loc
              ? `<div>Line: ${error.loc.start?.line}, Column: ${error.loc.start?.column}</div>`
              : ""
          }
          <pre style="text-align: left; font-size: 10px; margin-top: 10px; overflow-x: auto;">${
            error.stack || "No stack trace available"
          }</pre>
        </div>
      `;
    }
  }
});
