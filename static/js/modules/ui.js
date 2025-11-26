// ui.js - DOM helpers and inline messaging
export function qs(id) {
  return document.getElementById(id);
}

let lcuConnectionState = "unknown";

export function showInlineMessage(
  message,
  { targetId = "realtime-status", level = "info", timeout = 5000 } = {}
) {
  const contentEl = qs(targetId);
  const islandEl = qs("dynamic-island");

  if (!contentEl || !islandEl) return;

  contentEl.textContent = message;

  // Map levels to island status classes and icons
  const config = {
    info: { class: "island-status-info", icon: "bi-info-circle" },
    success: { class: "island-status-success", icon: "bi-check-circle" },
    warn: { class: "island-status-warning", icon: "bi-exclamation-triangle" },
    error: { class: "island-status-error", icon: "bi-x-circle" },
    neutral: { class: "island-status-idle", icon: "bi-activity" },
  }[level] || { class: "island-status-idle", icon: "bi-activity" };

  // Reset classes
  islandEl.className = `dynamic-island ${config.class}`;

  // Update icon
  const iconEl = islandEl.querySelector(".island-icon i");
  if (iconEl) {
    iconEl.className = `bi ${config.icon}`;
  }

  // Trigger animation
  islandEl.classList.add("expanded");
  setTimeout(() => islandEl.classList.remove("expanded"), 300);

  if (timeout && timeout > 0) {
    clearTimeout(contentEl._messageTimeout);
    contentEl._messageTimeout = setTimeout(() => {
      // Revert to idle state
      contentEl.textContent = "等待指令...";
      islandEl.className = "dynamic-island island-status-idle";
      if (iconEl) iconEl.className = "bi bi-activity";
    }, timeout);
  }
}

export function isLCUConnected() {
  const statusEl = qs("lcu-status");
  if (statusEl) {
    const txt = (statusEl.textContent || "").toLowerCase();
    if (
      txt.includes("成功") ||
      txt.includes("已连接") ||
      txt.includes("连接成功")
    ) {
      lcuConnectionState = "ok";
      return true;
    }
    if (txt.includes("失败") || txt.includes("未连接")) {
      lcuConnectionState = "err";
      return false;
    }
  }
  return lcuConnectionState === "ok";
}

let persistentNotificationId = null;

export function showNotification(message, type = "info", duration = 3000) {
  const container = qs("notification-container");
  if (!container) return null;

  const toast = document.createElement("div");
  toast.className = `notification-toast ${type}`;

  const iconMap = {
    info: "bi-info-circle-fill",
    success: "bi-check-circle-fill",
    warning: "bi-exclamation-triangle-fill",
    error: "bi-x-circle-fill",
  };

  toast.innerHTML = `
    <i class="bi ${iconMap[type] || iconMap.info} notification-icon"></i>
    <span>${message}</span>
  `;

  container.appendChild(toast);

  const remove = () => {
    toast.classList.add("hiding");
    toast.addEventListener("transitionend", () => {
      if (toast.parentElement) toast.remove();
    });
  };

  if (duration > 0) {
    setTimeout(remove, duration);
  }

  return { element: toast, remove };
}

export function setLCUStatus(message, style = "neutral") {
  // Update new UI status pill
  const statusPill = document.querySelector(".status-pill");
  if (statusPill) {
    const dot = statusPill.querySelector(".status-dot");
    const text = statusPill.querySelector("span");

    if (style === "ok") {
      statusPill.style.background = "rgba(16, 185, 129, 0.1)";
      statusPill.style.borderColor = "rgba(16, 185, 129, 0.2)";
      statusPill.style.color = "#10b981";
      if (dot) dot.style.background = "#10b981";
      if (text) text.textContent = "LCU Connected";
    } else if (style === "err") {
      statusPill.style.background = "rgba(239, 68, 68, 0.1)";
      statusPill.style.borderColor = "rgba(239, 68, 68, 0.2)";
      statusPill.style.color = "#ef4444";
      if (dot) dot.style.background = "#ef4444";
      if (text) text.textContent = "LCU Disconnected";
    } else {
      statusPill.style.background = "rgba(100, 116, 139, 0.1)";
      statusPill.style.borderColor = "rgba(100, 116, 139, 0.2)";
      statusPill.style.color = "#94a3b8";
      if (dot) dot.style.background = "#94a3b8";
      if (text) text.textContent = "Connecting...";
    }
  }

  if (style === "ok") {
    lcuConnectionState = "ok";
  } else if (style === "err") {
    lcuConnectionState = "err";
  } else {
    lcuConnectionState = "pending";
  }

  // If connected (success), show transient notification and clear persistent one
  if (style === "ok") {
    if (persistentNotificationId) {
      persistentNotificationId.remove();
      persistentNotificationId = null;
    }
    showNotification("LCU 连接成功", "success", 3000);
    return;
  }

  // If disconnected/waiting, show persistent notification
  const type = style === "err" ? "error" : "warning";

  // If we already have a persistent notification, update it if message changed, or do nothing
  if (persistentNotificationId) {
    const span = persistentNotificationId.element.querySelector("span");
    if (span && span.textContent !== message) {
      span.textContent = message;
    }
    // Update class if type changed
    persistentNotificationId.element.className = `notification-toast ${type}`;
    const icon = persistentNotificationId.element.querySelector("i");
    if (icon) {
      icon.className = `bi ${
        type === "error" ? "bi-x-circle-fill" : "bi-exclamation-triangle-fill"
      } notification-icon`;
    }
  } else {
    // Create new persistent notification (duration = 0)
    persistentNotificationId = showNotification(message, type, 0);
  }
}

export function formatRankBadge(rank) {
  if (!rank || rank.tier === "UNRANKED") {
    return '<span class="badge bg-secondary" style="font-size: 0.7rem;">未定级</span>';
  }

  const tierColors = {
    IRON: "#6B5D57",
    BRONZE: "#CD7F32",
    SILVER: "#C0C0C0",
    GOLD: "#FFD700",
    PLATINUM: "#4EC9B0",
    EMERALD: "#00C896",
    DIAMOND: "#B9F2FF",
    MASTER: "#9B4F96",
    GRANDMASTER: "#E74856",
    CHALLENGER: "#F1C40F",
  };

  const tierNames = {
    IRON: "黑铁",
    BRONZE: "青铜",
    SILVER: "白银",
    GOLD: "黄金",
    PLATINUM: "铂金",
    EMERALD: "翡翠",
    DIAMOND: "钻石",
    MASTER: "大师",
    GRANDMASTER: "宗师",
    CHALLENGER: "王者",
  };

  const divisionNames = {
    I: "I",
    II: "II",
    III: "III",
    IV: "IV",
  };

  const tier = rank.tier.toUpperCase();
  const color = tierColors[tier] || "#6C757D";
  const tierName = tierNames[tier] || tier;
  const division = rank.division
    ? divisionNames[rank.division] || rank.division
    : "";
  const lp = rank.lp || 0;

  let rankText = tierName;
  if (division) {
    rankText += ` ${division}`;
  }
  if (["MASTER", "GRANDMASTER", "CHALLENGER"].includes(tier)) {
    rankText += ` ${lp}点`;
  }

  return `<span class="badge" style="background-color: ${color}; font-size: 0.7rem;">${rankText}</span>`;
}
