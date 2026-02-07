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
        const summonerProfile = ref(null);
        const summonerHistory = ref([]);
        const profileLoading = ref(false);
        const profileError = ref("");

        const autoAcceptRunning = ref(false);
        const autoAnalyzeRunning = ref(false);
        const autoBanPickRunning = ref(false);

        const banChampions = ref([null]);
        const pickChampions = ref([null]);
        const championOptions = ref([]);
        const championById = ref({});

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
        let lcuStatusTimer = null;

        const applyLcuConnected = (value) => {
          if (typeof value === "boolean") {
            lcuConnected.value = value;
          }
        };

        const syncLcuStatus = async () => {
          try {
            const res = await fetch("/api/lcu_status");
            const data = await res.json();
            applyLcuConnected(!!data.connected);
          } catch (err) {
            console.warn("fetch /api/lcu_status failed", err);
          }
        };

        const startLcuStatusPolling = () => {
          if (lcuStatusTimer) return;
          lcuStatusTimer = setInterval(() => {
            syncLcuStatus();
          }, 5000);
        };

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
            championById.value = Object.fromEntries(
              Object.entries(data).map(([id, name]) => [parseInt(id), name]),
            );
          } catch (e) {
            console.error("Failed to load champions:", e);
          }

          loadPreferences();

          console.log("Initializing Socket.IO connection...");
          socket = io();
          socket.on("connect", () => {
            console.log("✅ WebSocket connected successfully");
            realtimeStatus.value = "已连接到服务器";
            syncLcuStatus();
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
            const msgType = data.type || "biz";

            console.debug("[status_update]", { msgType, msg, data });

            if (typeof data.connected === "boolean") {
              applyLcuConnected(data.connected);
            }

            // 仅当消息类型为 lcu 时才更新连接状态，避免业务失败提示误判
            if (msgType === "lcu") {
              const lowered = String(msg || "").toLowerCase();
              if (
                msg.includes("成功") ||
                msg.includes("已连接") ||
                msg.includes("连接成功") ||
                lowered.includes("connected")
              ) {
                lcuConnected.value = true;
              } else if (
                msg.includes("失败") ||
                msg.includes("未连接") ||
                msg.includes("断开") ||
                lowered.includes("disconnected")
              ) {
                lcuConnected.value = false;
              }
            }

            realtimeStatus.value = msg;
          });
          socket.on("lcu_status", (data) => {
            if (data && typeof data.connected === "boolean") {
              applyLcuConnected(data.connected);
            }
          });

          // 在页面加载时主动拉取一次 LCU 状态，防止 websocket 消息丢失
          syncLcuStatus();
          startLcuStatusPolling();
          socket.on("enemies_found", (data) => {
            enemies.value = data.enemies.map((e) => ({
              ...e,
              stats: null,
            }));
            realtimeStatus.value = `发现 ${data.enemies.length} 名敌人!`;
            data.enemies.forEach(async (enemy, idx) => {
              enemies.value[idx].stats = await fetchStats(
                enemy.gameName,
                enemy.tagLine,
                enemy.puuid,
              );
            });
          });
          socket.on("teammates_found", (data) => {
            teammates.value = data.teammates.map((tm) => ({
              ...tm,
              stats: null,
            }));
            realtimeStatus.value = `发现 ${data.teammates.length} 名队友!`;
            data.teammates.forEach(async (tm, idx) => {
              teammates.value[idx].stats = await fetchStats(
                tm.gameName,
                tm.tagLine,
                tm.puuid,
              );
            });
          });
        });

        const searchSummoner = async () => {
          if (!searchName.value.trim()) {
            antd.message.warning("请输入召唤师名称");
            return;
          }
          profileError.value = "";
          profileLoading.value = true;
          summonerProfile.value = null;
          summonerHistory.value = [];
          const encoded = encodeURIComponent(searchName.value.trim());
          try {
            const rankRes = await fetch(
              `/api/get_summoner_rank?name=${encoded}`,
            );
            const rankJson = await rankRes.json();
            if (!rankRes.ok || !rankJson.success) {
              throw new Error(rankJson.message || "召唤师信息获取失败");
            }

            const historyRes = await fetch(
              `/api/get_history?name=${encoded}&count=5&page=1`,
            );
            const historyJson = await historyRes.json();
            if (!historyRes.ok || !historyJson.success) {
              throw new Error(historyJson.message || "战绩获取失败");
            }

            const ranks = Array.isArray(rankJson.ranked?.queues)
              ? rankJson.ranked.queues.map((q) => ({
                  label: q.queueType || q.queue || q.type || "",
                  tier: q.tier,
                  division: q.division,
                  lp: q.lp ?? q.leaguePoints ?? null,
                  wins: q.wins ?? null,
                  losses: q.losses ?? null,
                  queueType: q.queueType || q.queue || q.type || "",
                }))
              : [];

            summonerProfile.value = {
              displayName: searchName.value.trim(),
              level: rankJson.summoner_level,
              iconUrl: `https://ddragon.leagueoflegends.com/cdn/14.23.1/img/profileicon/${rankJson.profile_icon_id}.png`,
              ranks,
            };

            summonerHistory.value = Array.isArray(historyJson.games)
              ? historyJson.games.map((g) => ({
                  result: g.result || g.win_status || (g.win ? "Win" : "Loss"),
                  queue: g.queue || g.queue_name || "",
                  kills: g.kills ?? 0,
                  deaths: g.deaths ?? 0,
                  assists: g.assists ?? 0,
                  gameCreation: g.gameCreation || g.game_creation || Date.now(),
                }))
              : [];

            antd.message.success("查询完成");
          } catch (err) {
            console.error(err);
            profileError.value = err.message || "查询失败";
            antd.message.error(profileError.value);
          } finally {
            profileLoading.value = false;
          }
        };

        const searchTFT = () => {
          if (!searchName.value.trim()) {
            antd.message.warning("请输入召唤师名称");
            return;
          }
          window.open(
            `/tft_summoner/${encodeURIComponent(searchName.value)}`,
            "_blank",
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
            autoAcceptRunning.value ? "start_auto_accept" : "stop_auto_accept",
          );
          antd.message.info(
            autoAcceptRunning.value ? "自动接受已启动" : "自动接受已停止",
          );
          savePreferences();
        };

        const toggleAutoAnalyze = () => {
          if (!ensureConnected()) return;
          autoAnalyzeRunning.value = !autoAnalyzeRunning.value;
          socket.emit(
            autoAnalyzeRunning.value
              ? "start_auto_analyze"
              : "stop_auto_analyze",
          );
          antd.message.info(
            autoAnalyzeRunning.value ? "敌我分析已启动" : "敌我分析已停止",
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
              : "自动Ban/Pick已停止",
          );
          savePreferences();
        };

        const addBanSlot = () => banChampions.value.push(null);
        const addPickSlot = () => pickChampions.value.push(null);
        const filterChampion = (input, option) =>
          option.label.toLowerCase().includes(input.toLowerCase());

        const fetchStats = async (gameName, tagLine, puuid) => {
          try {
            const safeGameName = gameName || "unknown";
            const safeTagLine = tagLine || "unknown";
            const encodedName = encodeURIComponent(safeGameName);
            const encodedTag = encodeURIComponent(safeTagLine);
            const queryPuuid = puuid
              ? `puuid=${encodeURIComponent(puuid)}`
              : "";
            const historyParams = new URLSearchParams();
            if (puuid) {
              historyParams.set("puuid", puuid);
            } else if (gameName && tagLine) {
              historyParams.set("name", `${gameName}#${tagLine}`);
            } else if (gameName) {
              historyParams.set("name", gameName);
            }
            historyParams.set("count", "20");
            historyParams.set("page", "1");

            // 并行获取：段位信息 + 最近20场战绩
            const [rankRes, histRes] = await Promise.all([
              fetch(
                `/api/summoner_stats/${encodedName}/${encodedTag}${
                  queryPuuid ? `?${queryPuuid}` : ""
                }`,
              ),
              fetch(
                `/api/get_history?${historyParams.toString()}`,
              ),
            ]);

            const safeJson = async (res) => {
              try {
                return await res.json();
              } catch (err) {
                console.warn("Failed to parse JSON response", err);
                return null;
              }
            };

            const [rankJson, histJson] = await Promise.all([
              safeJson(rankRes),
              safeJson(histRes),
            ]);

            if (!rankJson && !histJson) {
              throw new Error("Stats API response invalid");
            }

            const rankQueues = Array.isArray(rankJson?.queues)
              ? rankJson.queues
              : [];
            const primaryRank =
              rankQueues.find((q) =>
                String(q.queueType || q.queue || q.type || "")
                  .toUpperCase()
                  .includes("SOLO"),
              ) || rankQueues[0];
            const rankLabel = primaryRank
              ? `${primaryRank.tier || "Unranked"} ${
                  primaryRank.division || ""
                }`.trim()
              : "Unranked";
            const lpPart =
              primaryRank &&
              (primaryRank.lp ?? primaryRank.leaguePoints) !== undefined
                ? ` ${primaryRank.lp ?? primaryRank.leaguePoints}LP`
                : "";

            let wins = 0;
            let losses = 0;
            let totalKills = 0;
            let totalDeaths = 0;
            let totalAssists = 0;
            let streakResult = null;
            let streakCount = 0;
            const games = Array.isArray(histJson?.games)
              ? [...histJson.games]
              : [];
            if (games.length) {
              games.sort((a, b) => {
                const aTime =
                  a.gameCreation || a.game_creation || a.timestamp || 0;
                const bTime =
                  b.gameCreation || b.game_creation || b.timestamp || 0;
                return bTime - aTime; // newest first
              });

              games.forEach((g) => {
                const winFlag =
                  g.win === true ||
                  g.result === "Win" ||
                  g.win_status === "Win" ||
                  g.stats?.win === true;
                if (winFlag) wins += 1;
                else losses += 1;

                const k = g.kills ?? g.stats?.kills ?? 0;
                const d = g.deaths ?? g.stats?.deaths ?? 0;
                const a = g.assists ?? g.stats?.assists ?? 0;
                totalKills += k;
                totalDeaths += d;
                totalAssists += a;
              });

              for (const g of games) {
                const winFlag =
                  g.win === true ||
                  g.result === "Win" ||
                  g.win_status === "Win" ||
                  g.stats?.win === true;
                const current = winFlag ? "W" : "L";
                if (streakResult === null) {
                  streakResult = current;
                  streakCount = 1;
                } else if (streakResult === current) {
                  streakCount += 1;
                } else {
                  break;
                }
              }
            }
            const total = wins + losses;
            const winrate = total > 0 ? ((wins / total) * 100).toFixed(1) : "0";

            const kda =
              totalDeaths > 0
                ? ((totalKills + totalAssists) / totalDeaths).toFixed(2)
                : totalKills + totalAssists > 0
                  ? "Perfect"
                  : "0";

            return {
              summary: `${wins}W ${losses}L (${winrate}% WR) · ${rankLabel}${lpPart}`,
              kda,
              streakType: streakCount >= 3 ? streakResult : null,
              streakCount: streakCount >= 3 ? streakCount : null,
            };
          } catch (err) {
            console.error(err);
            return {
              summary: "Stats unavailable",
              kda: null,
              streakType: null,
              streakCount: null,
            };
          }
        };

        const getChampionIcon = (championId) => {
          if (!championId) return null;
          const name = championById.value[championId];
          if (!name) return null;
          return `https://ddragon.leagueoflegends.com/cdn/15.23.1/img/champion/${name.replace(
            " ",
            "",
          )}.png`;
        };

        const savePreferences = () => {
          try {
            localStorage.setItem(
              "lcu_ui_ban_champions",
              JSON.stringify(banChampions.value.filter(Boolean)),
            );
            localStorage.setItem(
              "lcu_ui_pick_champions",
              JSON.stringify(pickChampions.value.filter(Boolean)),
            );
          } catch {}
        };

        const loadPreferences = () => {
          try {
            const bans = JSON.parse(
              localStorage.getItem("lcu_ui_ban_champions") || "[]",
            );
            const picks = JSON.parse(
              localStorage.getItem("lcu_ui_pick_champions") || "[]",
            );
            if (bans.length) banChampions.value = [...bans, null];
            if (picks.length) pickChampions.value = [...picks, null];
          } catch {}
        };

        const timeAgo = (value) => {
          if (!value) return "";
          const now = Date.now();
          const diffMs = now - value;
          const diffSec = Math.floor(diffMs / 1000);
          const diffMin = Math.floor(diffSec / 60);
          const diffHour = Math.floor(diffMin / 60);
          const diffDay = Math.floor(diffHour / 24);
          if (diffDay > 0) return `${diffDay}d ago`;
          if (diffHour > 0) return `${diffHour}h ago`;
          if (diffMin > 0) return `${diffMin}m ago`;
          return `${diffSec}s ago`;
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
          summonerProfile,
          summonerHistory,
          profileLoading,
          profileError,
          autoAcceptRunning,
          autoAnalyzeRunning,
          autoBanPickRunning,
          banChampions,
          pickChampions,
          championOptions,
          championById,
          teammates,
          enemies,
          activeModulesCount,
          getChampionIcon,
          navigateTo,
          searchSummoner,
          searchTFT,
          toggleAutoAccept,
          toggleAutoAnalyze,
          toggleAutoBanPick,
          addBanSlot,
          addPickSlot,
          filterChampion,
          timeAgo,
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
