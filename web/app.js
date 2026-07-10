"use strict";

const API = {
  async get(path) {
    const res = await fetch(path, {
      headers: {
        "X-Zapret-Token": window.ZAPRET_TOKEN || "",
        "X-Zapret-Lang": getLang(),
      },
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.error || res.statusText);
    return body;
  },
  async post(path, payload) {
    const res = await fetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Zapret-Token": window.ZAPRET_TOKEN || "",
        "X-Zapret-Lang": getLang(),
      },
      body: JSON.stringify(payload || {}),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.error || res.statusText);
    return body;
  },
};

const state = {
  version: null,
  versions: [],
  strategies: [],
};

let logCursor = 0;
let testPollTimer = null;
let lastConflicts = [];

// ------------------------------------------------------------------ //
// small helpers
// ------------------------------------------------------------------ //

function $(id) { return document.getElementById(id); }

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function toast(message, type = "info") {
  const container = $("toast-container");
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = message;
  container.appendChild(el);
  requestAnimationFrame(() => el.classList.add("show"));
  setTimeout(() => {
    el.classList.remove("show");
    setTimeout(() => el.remove(), 300);
  }, 4500);
}

function confirmModal(title, message) {
  return new Promise((resolve) => {
    const overlay = $("modal-overlay");
    $("modal-title").textContent = title;
    $("modal-message").textContent = message;
    overlay.classList.remove("hidden");

    const confirmBtn = $("modal-confirm");
    const cancelBtn = $("modal-cancel");

    function cleanup(result) {
      overlay.classList.add("hidden");
      confirmBtn.removeEventListener("click", onConfirm);
      cancelBtn.removeEventListener("click", onCancel);
      overlay.removeEventListener("click", onOverlay);
      resolve(result);
    }
    function onConfirm() { cleanup(true); }
    function onCancel() { cleanup(false); }
    function onOverlay(e) { if (e.target === overlay) cleanup(false); }

    confirmBtn.addEventListener("click", onConfirm);
    cancelBtn.addEventListener("click", onCancel);
    overlay.addEventListener("click", onOverlay);
  });
}

function setDotStatus(id, ok) {
  $(id).className = "dot " + (ok ? "dot-ok" : "dot-off");
}

function renderSelect(id, items) {
  const sel = $(id);
  const prev = sel.value;
  sel.innerHTML = items.map((s) => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join("");
  if (items.includes(prev)) sel.value = prev;
}

// ------------------------------------------------------------------ //
// tabs
// ------------------------------------------------------------------ //

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    $(`tab-${btn.dataset.tab}`).classList.add("active");
  });
});

// ------------------------------------------------------------------ //
// version / strategies loading
// ------------------------------------------------------------------ //

async function loadVersions() {
  const { versions } = await API.get("/api/versions");
  state.versions = versions;
  const sel = $("version-select");
  sel.innerHTML = versions.map((v) => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join("");
  if (versions.length) {
    sel.value = versions[versions.length - 1];
    state.version = sel.value;
  }
}

async function loadStrategiesForAllTabs() {
  if (!state.version) return;
  const { strategies } = await API.get(`/api/strategies?version=${encodeURIComponent(state.version)}`);
  state.strategies = strategies;
  renderTestStrategyList(strategies);
  renderSelect("manual-strategy", strategies);
  renderSelect("service-strategy", strategies);
  await loadServiceSettings();
}

const DEFAULT_CHECKED_SERVICES = new Set(["Discord", "YouTube", "Cloudflare"]);

async function loadServiceCatalog() {
  const { services } = await API.get("/api/services");
  $("service-list").innerHTML = Object.entries(services).map(([name, hosts]) => `
    <label class="strategy-item" title="${escapeHtml(hosts.join(", "))}">
      <input type="checkbox" class="service-checkbox-filter" value="${escapeHtml(name)}"
        ${DEFAULT_CHECKED_SERVICES.has(name) ? "checked" : ""}>
      <span>${escapeHtml(name)}</span>
    </label>
  `).join("");
}

function getSelectedServices() {
  return [...document.querySelectorAll(".service-checkbox-filter:checked")].map((cb) => cb.value);
}

$("services-select-all").addEventListener("click", () => {
  document.querySelectorAll(".service-checkbox-filter").forEach((cb) => (cb.checked = true));
});
$("services-select-none").addEventListener("click", () => {
  document.querySelectorAll(".service-checkbox-filter").forEach((cb) => (cb.checked = false));
});

$("version-select").addEventListener("change", async (e) => {
  state.version = e.target.value;
  await loadStrategiesForAllTabs();
});

$("reload-versions").addEventListener("click", async () => {
  await loadVersions();
  await loadStrategiesForAllTabs();
  toast(t("msg_versions_reloaded"), "info");
});

// ------------------------------------------------------------------ //
// env / status bar
// ------------------------------------------------------------------ //

async function loadEnv() {
  try {
    const env = await API.get("/api/env");
    setDotStatus("admin-dot", env.admin);
    $("admin-text").textContent = env.admin ? t("admin_yes") : t("admin_no");
    if (!env.curl) toast(t("err_curl_not_found"), "error");
    if (env.zapret_service_installed) {
      toast(t("msg_service_installed_warning"), "info");
    }
  } catch (e) { /* ignore */ }
}

async function pollWinwsStatus() {
  try {
    const { running } = await API.get("/api/manual/status");
    setDotStatus("winws-dot", running);
    $("winws-text").textContent = running ? t("winws_running") : t("winws_stopped");
    setDotStatus("manual-dot", running);
    $("manual-status-text").textContent = running ? t("winws_running_caps") : t("winws_stopped2");
  } catch (e) { /* ignore */ }
}

// ------------------------------------------------------------------ //
// Тест tab
// ------------------------------------------------------------------ //

function renderTestStrategyList(strategies) {
  $("strategy-list").innerHTML = strategies.map((s) => `
    <label class="strategy-item">
      <input type="checkbox" class="strategy-checkbox" value="${escapeHtml(s)}" checked>
      <span>${escapeHtml(s)}</span>
    </label>
  `).join("");
}

function getSelectedStrategies() {
  return [...document.querySelectorAll(".strategy-checkbox:checked")].map((cb) => cb.value);
}

$("select-all").addEventListener("click", () => {
  document.querySelectorAll(".strategy-checkbox").forEach((cb) => (cb.checked = true));
});
$("select-none").addEventListener("click", () => {
  document.querySelectorAll(".strategy-checkbox").forEach((cb) => (cb.checked = false));
});

function setTestRunningUI(running) {
  $("run-test").disabled = running;
  $("stop-test").disabled = !running;
}

function updateProgress({ done, total }) {
  const pct = total ? Math.round((done / total) * 100) : 0;
  $("test-progress-fill").style.width = pct + "%";
  $("test-progress-text").textContent = `${done}/${total}`;
}

function appendLogLines(lines) {
  if (!lines || !lines.length) return;
  const el = $("test-log");
  el.textContent += lines.join("\n") + "\n";
  el.scrollTop = el.scrollHeight;
}

function summaryRow(label, value, stratName) {
  return `
    <div class="summary-row">
      <div>
        <div class="summary-label">${escapeHtml(label)}</div>
        <div class="summary-value">${escapeHtml(value)}</div>
      </div>
      <button class="btn btn-primary btn-small" data-activate="${escapeHtml(stratName)}">${t("btn_enable")}</button>
    </div>`;
}

function renderTestSummary(best, reportPath) {
  const container = $("test-summary");
  if (!best) {
    container.innerHTML = `<div class="muted">${t("msg_no_results")}</div>`;
    return;
  }
  let html = "";
  for (const [service, info] of Object.entries(best.per_service)) {
    html += summaryRow(service, `${info.strategy} (${info.score}/${info.total})`, info.strategy);
  }
  if (best.overall) {
    html += summaryRow(t("label_best_overall"),
      `${best.overall.strategy} (${best.overall.score}/${best.overall.total})`, best.overall.strategy);
  }
  if (reportPath) {
    html += `<div class="muted small">${escapeHtml(t("label_report_saved"))}${escapeHtml(reportPath)}</div>`;
  }
  container.innerHTML = html;
  container.querySelectorAll("[data-activate]").forEach((btn) => {
    btn.addEventListener("click", () => activateStrategy(btn.dataset.activate));
  });
}

async function activateStrategy(name) {
  try {
    await API.post("/api/manual/launch", { version: state.version, strategy: name });
    toast(t("msg_strategy_launched", { name }), "success");
  } catch (e) {
    toast(e.message, "error");
  }
}

async function startTest() {
  if (!state.version) return toast(t("err_select_version"), "error");
  const strategies = getSelectedStrategies();
  if (!strategies.length) return toast(t("err_select_strategy"), "error");
  const services = getSelectedServices();
  if (!services.length) return toast(t("err_select_service"), "error");

  const ok = await confirmModal(
    t("confirm_run_test_title"),
    t("confirm_run_test_msg", { count: strategies.length, services: services.join(", ") })
  );
  if (!ok) return;

  $("test-log").textContent = "";
  $("test-summary").innerHTML = "";
  logCursor = 0;
  updateProgress({ done: 0, total: strategies.length });
  setTestRunningUI(true);

  try {
    await API.post("/api/test/start", { version: state.version, strategies, services });
  } catch (e) {
    toast(e.message, "error");
    setTestRunningUI(false);
    return;
  }
  pollTest();
}

function pollTest() {
  clearInterval(testPollTimer);
  testPollTimer = setInterval(async () => {
    try {
      const snap = await API.get(`/api/test/status?since=${logCursor}`);
      appendLogLines(snap.log);
      logCursor = snap.log_len;
      updateProgress(snap.progress);
      if (!snap.running) {
        clearInterval(testPollTimer);
        setTestRunningUI(false);
        renderTestSummary(snap.best, snap.report_path);
      }
    } catch (e) { /* transient — keep polling */ }
  }, 700);
}

async function stopTest() {
  try {
    await API.post("/api/test/stop", {});
  } catch (e) { /* ignore */ }
}

$("run-test").addEventListener("click", startTest);
$("stop-test").addEventListener("click", stopTest);

// ------------------------------------------------------------------ //
// Ручной запуск tab
// ------------------------------------------------------------------ //

$("manual-launch").addEventListener("click", async () => {
  const strategy = $("manual-strategy").value;
  if (!state.version || !strategy) return;
  try {
    await API.post("/api/manual/launch", { version: state.version, strategy });
    toast(t("msg_launched", { strategy }), "success");
  } catch (e) { toast(e.message, "error"); }
});

$("manual-stop").addEventListener("click", async () => {
  try {
    await API.post("/api/manual/stop", {});
    toast(t("msg_winws_stopped"), "success");
  } catch (e) { toast(e.message, "error"); }
});

// ------------------------------------------------------------------ //
// Служба tab
// ------------------------------------------------------------------ //

function logService(text) {
  const el = $("service-output");
  el.textContent += text + "\n\n";
  el.scrollTop = el.scrollHeight;
}

function setSegmentedValue(containerId, value) {
  const container = $(containerId);
  [...container.children].forEach((btn) => btn.classList.toggle("active", btn.dataset.value === value));
}

async function loadServiceSettings() {
  if (!state.version) return;
  try {
    const s = await API.get(`/api/service/settings?version=${encodeURIComponent(state.version)}`);
    setSegmentedValue("game-filter-segmented", s.game_filter);
    $("ipset-status-badge").textContent = s.ipset;
    $("check-updates-toggle").checked = s.check_updates;
  } catch (e) { /* ignore */ }
}

$("game-filter-segmented").addEventListener("click", async (e) => {
  const btn = e.target.closest("button");
  if (!btn || !state.version) return;
  setSegmentedValue("game-filter-segmented", btn.dataset.value);
  try {
    await API.post("/api/service/settings/game_filter", { version: state.version, mode: btn.dataset.value });
    logService(t("log_game_filter_set", { mode: btn.dataset.value }));
  } catch (e) { toast(e.message, "error"); }
});

$("ipset-cycle").addEventListener("click", async () => {
  if (!state.version) return;
  try {
    const { status } = await API.post("/api/service/settings/ipset_cycle", { version: state.version });
    $("ipset-status-badge").textContent = status;
    logService(t("log_ipset_switched", { status }));
  } catch (e) { toast(e.message, "error"); }
});

$("check-updates-toggle").addEventListener("change", async (e) => {
  if (!state.version) return;
  try {
    await API.post("/api/service/settings/check_updates", { version: state.version, enabled: e.target.checked });
    logService(t("log_check_updates_toggled", { state: e.target.checked ? t("state_enabled") : t("state_disabled") }));
  } catch (err) { toast(err.message, "error"); }
});

$("service-install").addEventListener("click", async () => {
  const strategy = $("service-strategy").value;
  if (!state.version || !strategy) return;
  const ok = await confirmModal(
    t("confirm_install_service_title"),
    t("confirm_install_service_msg", { strategy })
  );
  if (!ok) return;
  logService(t("log_installing_service", { strategy }));
  try {
    const { output } = await API.post("/api/service/install", { version: state.version, strategy });
    logService(output);
    toast(t("msg_service_installed"), "success");
  } catch (e) {
    logService(t("label_error_prefix", { message: e.message }));
    toast(e.message, "error");
  }
});

$("service-remove").addEventListener("click", async () => {
  const ok = await confirmModal(t("confirm_remove_service_title"), t("confirm_remove_service_msg"));
  if (!ok) return;
  logService(t("log_removing_service"));
  try {
    const { output } = await API.post("/api/service/remove", {});
    logService(output);
    toast(t("msg_service_removed"), "success");
  } catch (e) {
    logService(t("label_error_prefix", { message: e.message }));
    toast(e.message, "error");
  }
});

$("service-status").addEventListener("click", async () => {
  if (!state.version) return;
  logService(t("log_checking_status"));
  try {
    const { text } = await API.get(`/api/service/status?version=${encodeURIComponent(state.version)}`);
    logService(text);
  } catch (e) { logService(t("label_error_prefix", { message: e.message })); }
});

$("update-ipset").addEventListener("click", async () => {
  if (!state.version) return;
  logService(t("log_updating_ipset"));
  try {
    const { output } = await API.post("/api/service/update/ipset", { version: state.version });
    logService(output);
    const s = await API.get(`/api/service/settings?version=${encodeURIComponent(state.version)}`);
    $("ipset-status-badge").textContent = s.ipset;
  } catch (e) { logService(t("label_error_prefix", { message: e.message })); }
});

$("update-hosts").addEventListener("click", async () => {
  logService(t("log_checking_hosts"));
  try {
    const { output } = await API.post("/api/service/update/hosts", {});
    logService(output);
  } catch (e) { logService(t("label_error_prefix", { message: e.message })); }
});

$("check-updates-btn").addEventListener("click", async () => {
  if (!state.version) return;
  logService(t("log_checking_updates"));
  try {
    const info = await API.post("/api/service/update/check", { version: state.version });
    if (info.up_to_date) {
      logService(t("log_latest_version", { version: info.local }));
    } else {
      logService(t("log_new_version_available", { local: info.local, latest: info.latest, url: info.release_url }));
      window.open(info.download_url, "_blank");
    }
  } catch (e) { logService(t("label_error_prefix", { message: e.message })); }
});

// ------------------------------------------------------------------ //
// Диагностика tab
// ------------------------------------------------------------------ //

function renderDiagnostics(results) {
  $("diagnostics-results").innerHTML = results.map((r, idx) => {
    let servicesHtml = "";
    if (r.services && r.services.length) {
      const items = r.services.map((s) => `
        <label class="service-item">
          <input type="checkbox" class="service-checkbox" data-row="${idx}" value="${escapeHtml(s.name)}" checked>
          <span>${escapeHtml(s.display_name)}</span>
        </label>`).join("");
      servicesHtml = `
        <div class="diag-services">
          ${items}
          <button class="btn btn-danger btn-small" data-stop-row="${idx}">${t("btn_stop_selected")}</button>
        </div>`;
    }
    return `
      <div class="diag-row diag-${r.level}">
        <span class="diag-icon">${r.level === "ok" ? "✓" : r.level === "warn" ? "!" : "✕"}</span>
        <div class="diag-body">
          <div class="diag-name">${escapeHtml(r.name)}</div>
          <div class="diag-message">${escapeHtml(r.message)}</div>
          ${servicesHtml}
        </div>
      </div>`;
  }).join("");

  document.querySelectorAll("[data-stop-row]").forEach((btn) => {
    btn.addEventListener("click", () => stopSelectedServices(btn.dataset.stopRow));
  });
}

async function stopSelectedServices(rowIdx) {
  const checked = [...document.querySelectorAll(`.service-checkbox[data-row="${rowIdx}"]:checked`)]
    .map((cb) => cb.value);
  if (!checked.length) return toast(t("err_nothing_selected"), "error");
  const ok = await confirmModal(t("confirm_stop_services_title"), t("confirm_stop_services_msg", { names: checked.join(", ") }));
  if (!ok) return;
  try {
    const { output } = await API.post("/api/diagnostics/stop_services", { names: checked });
    toast(output, "success");
  } catch (e) { toast(e.message, "error"); }
}

$("run-diagnostics").addEventListener("click", async () => {
  if (!state.version) return;
  $("diagnostics-results").innerHTML = `<div class="muted">${t("msg_diagnostics_running")}</div>`;
  $("remove-conflicts").disabled = true;
  $("fix-windivert").disabled = true;
  try {
    const { results, conflicts, windivert_conflict } =
      await API.post("/api/diagnostics/run", { version: state.version });
    lastConflicts = conflicts;
    renderDiagnostics(results);
    $("remove-conflicts").disabled = conflicts.length === 0;
    $("fix-windivert").disabled = !windivert_conflict;
  } catch (e) {
    $("diagnostics-results").innerHTML = `<div class="muted">${escapeHtml(t("label_error_prefix", { message: e.message }))}</div>`;
  }
});

$("fix-windivert").addEventListener("click", async () => {
  const ok = await confirmModal(t("confirm_fix_windivert_title"), t("confirm_fix_windivert_msg"));
  if (!ok) return;
  try {
    const { output } = await API.post("/api/diagnostics/fix_windivert", {});
    toast(output, "success");
    $("fix-windivert").disabled = true;
  } catch (e) { toast(e.message, "error"); }
});

$("remove-conflicts").addEventListener("click", async () => {
  if (!lastConflicts.length) return;
  const ok = await confirmModal(
    t("confirm_remove_conflicts_title"),
    t("confirm_remove_conflicts_msg", { names: lastConflicts.join(", ") })
  );
  if (!ok) return;
  try {
    const { output } = await API.post("/api/diagnostics/remove_conflicts", { names: lastConflicts });
    toast(output, "success");
    $("remove-conflicts").disabled = true;
  } catch (e) { toast(e.message, "error"); }
});

$("clear-discord-cache").addEventListener("click", async () => {
  const ok = await confirmModal(t("confirm_clear_discord_title"), t("confirm_clear_discord_msg"));
  if (!ok) return;
  try {
    const { output } = await API.post("/api/diagnostics/clear_discord_cache", {});
    toast(output, "success");
  } catch (e) { toast(e.message, "error"); }
});

// ------------------------------------------------------------------ //
// init
// ------------------------------------------------------------------ //

(async function init() {
  await loadEnv();
  await loadServiceCatalog();
  await loadVersions();
  await loadStrategiesForAllTabs();
  pollWinwsStatus();
  setInterval(pollWinwsStatus, 2000);
})();
