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
  paths: {},
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
// console menu (accordion) — replaces the old sidebar tab switcher
// ------------------------------------------------------------------ //

function closeAllMenuPanels() {
  document.querySelectorAll(".menu-panel.open").forEach((p) => p.classList.remove("open"));
  document.querySelectorAll(".menu-item.active").forEach((i) => i.classList.remove("active"));
}

function toggleMenuPanel(item) {
  const panel = $(item.dataset.target);
  if (!panel) return;
  const wasOpen = panel.classList.contains("open");
  closeAllMenuPanels();
  if (!wasOpen) {
    panel.classList.add("open");
    item.classList.add("active");
  }
}

document.querySelectorAll(".menu-item").forEach((item) => {
  item.setAttribute("role", "button");
  item.setAttribute("tabindex", "0");
  item.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (item.dataset.target) toggleMenuPanel(item);
      else item.click();
    }
  });
});

document.querySelectorAll(".menu-item[data-target]").forEach((item) => {
  item.addEventListener("click", () => toggleMenuPanel(item));
});

// ------------------------------------------------------------------ //
// version / strategies loading
// ------------------------------------------------------------------ //

async function loadVersions(rescan) {
  const { versions, paths } = await API.get(`/api/versions${rescan ? "?rescan=1" : ""}`);
  state.versions = versions;
  state.paths = paths || {};
  const sel = $("version-select");
  sel.innerHTML = versions.map((v) => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join("");
  if (versions.length) {
    sel.value = versions[versions.length - 1];
    state.version = sel.value;
  } else {
    state.version = null;
    toast(t("err_no_versions_found"), "error");
  }
  $("home-version-label").textContent = state.version ? t("home_version_label", { version: state.version }) : "";
  renderFoundPaths();
}

// ------------------------------------------------------------------ //
// version-scan mode (whole computer vs. one specific folder)
// ------------------------------------------------------------------ //

let scanSettings = { mode: "global", custom_dir: null };

function renderScanSettings() {
  document.querySelectorAll("#scan-mode-segmented button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.value === scanSettings.mode);
  });
  $("scan-custom-row").style.display = scanSettings.mode === "custom" ? "flex" : "none";
  $("scan-custom-dir-text").textContent = scanSettings.custom_dir || t("label_no_custom_dir");
}

async function loadScanSettings() {
  try {
    scanSettings = await API.get("/api/scan/settings");
  } catch (e) { /* ignore */ }
  renderScanSettings();
}

function renderFoundPaths() {
  const container = $("found-paths");
  const names = state.versions || [];
  if (!names.length) {
    container.innerHTML = `<div class="muted">${t("found_paths_empty")}</div>`;
    return;
  }
  container.innerHTML = names.map((name) => `
    <div class="found-path-row">
      <span class="found-path-name">${escapeHtml(name)}</span>
      <span class="found-path-value" title="${escapeHtml(state.paths[name] || "")}">${escapeHtml(state.paths[name] || "")}</span>
      <button class="found-path-open" data-open="${escapeHtml(name)}">${t("btn_open_folder")}</button>
      <button class="found-path-delete" data-delete="${escapeHtml(name)}">${t("btn_delete_folder")}</button>
    </div>
  `).join("");
  container.querySelectorAll("[data-open]").forEach((btn) => {
    btn.addEventListener("click", () => openFolder(btn.dataset.open));
  });
  container.querySelectorAll("[data-delete]").forEach((btn) => {
    btn.addEventListener("click", () => deleteFolder(btn.dataset.delete));
  });
}

async function openFolder(name) {
  try {
    await API.post("/api/open_folder", { name });
  } catch (e) { toast(e.message, "error"); }
}

async function deleteFolder(name) {
  const path = (state.paths && state.paths[name]) || name;
  const ok = await confirmModal(t("confirm_delete_folder_title"), t("confirm_delete_folder_msg", { path }));
  if (!ok) return;
  try {
    await API.post("/api/delete_folder", { name });
    toast(t("msg_folder_deleted"), "success");
    await loadVersions();
    await loadStrategiesForAllTabs();
  } catch (e) { toast(e.message, "error"); }
}

$("toggle-found-paths").addEventListener("click", () => {
  const container = $("found-paths");
  const isOpen = container.classList.toggle("open");
  $("toggle-found-paths").textContent = isOpen ? t("btn_hide_paths") : t("btn_show_paths");
});

document.addEventListener("zapret:langchange", () => {
  const isOpen = $("found-paths").classList.contains("open");
  $("toggle-found-paths").textContent = isOpen ? t("btn_hide_paths") : t("btn_show_paths");
  renderScanSettings();
});

document.querySelectorAll("#scan-mode-segmented button").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (btn.dataset.value === scanSettings.mode) return;
    if (btn.dataset.value === "global") {
      try {
        await API.post("/api/scan/settings", { mode: "global", custom_dir: null });
        scanSettings = { mode: "global", custom_dir: scanSettings.custom_dir };
        renderScanSettings();
        toast(t("msg_scan_settings_saved"), "info");
        await loadVersions(true);
        await loadStrategiesForAllTabs();
      } catch (e) { toast(e.message, "error"); }
    } else {
      scanSettings.mode = "custom";
      renderScanSettings();
    }
  });
});

$("scan-pick-folder").addEventListener("click", async () => {
  const btn = $("scan-pick-folder");
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = t("btn_picking_folder");
  try {
    const { path } = await API.post("/api/scan/pick_folder", {});
    if (!path) return;
    await API.post("/api/scan/settings", { mode: "custom", custom_dir: path });
    scanSettings = { mode: "custom", custom_dir: path };
    renderScanSettings();
    toast(t("msg_scan_settings_saved"), "info");
    await loadVersions(true);
    await loadStrategiesForAllTabs();
  } catch (e) {
    toast(e.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
});

async function loadStrategiesForAllTabs() {
  if (!state.version) return;
  const { strategies } = await API.get(`/api/strategies?version=${encodeURIComponent(state.version)}`);
  state.strategies = strategies;
  renderTestStrategyList(strategies);
  renderSelect("hero-strategy-select", strategies);
  renderSelect("service-strategy", strategies);
  updateConnectUI();
  await loadServiceSettings();
}

const DEFAULT_CHECKED_SERVICES = new Set(["Discord", "YouTube", "Cloudflare"]);

function renderServiceChecklist(containerId, className, services) {
  $(containerId).innerHTML = Object.entries(services).map(([name, hosts]) => `
    <label class="strategy-item" title="${escapeHtml(hosts.join(", "))}">
      <input type="checkbox" class="${className}" value="${escapeHtml(name)}"
        ${DEFAULT_CHECKED_SERVICES.has(name) ? "checked" : ""}>
      <span>${escapeHtml(name)}</span>
    </label>
  `).join("");
}

function getSelectedFromClass(className) {
  return [...document.querySelectorAll(`.${className}:checked`)].map((cb) => cb.value);
}

function wireSelectAllNone(selectAllId, selectNoneId, className) {
  $(selectAllId).addEventListener("click", () => {
    document.querySelectorAll(`.${className}`).forEach((cb) => (cb.checked = true));
  });
  $(selectNoneId).addEventListener("click", () => {
    document.querySelectorAll(`.${className}`).forEach((cb) => (cb.checked = false));
  });
}

async function loadServiceCatalog() {
  const { services } = await API.get("/api/services");
  renderServiceChecklist("service-list", "service-checkbox-filter", services);
  renderServiceChecklist("generator-service-list", "gen-service-checkbox-filter", services);
}

function getSelectedServices() {
  return getSelectedFromClass("service-checkbox-filter");
}

wireSelectAllNone("services-select-all", "services-select-none", "service-checkbox-filter");
wireSelectAllNone("generator-services-select-all", "generator-services-select-none", "gen-service-checkbox-filter");

$("version-select").addEventListener("change", async (e) => {
  state.version = e.target.value;
  $("home-version-label").textContent = state.version ? t("home_version_label", { version: state.version }) : "";
  await loadStrategiesForAllTabs();
});

$("reload-versions").addEventListener("click", async () => {
  const btn = $("reload-versions");
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = t("msg_scanning");
  try {
    await loadVersions(true);
    await loadStrategiesForAllTabs();
    toast(t("msg_versions_reloaded"), "info");
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
});

// ------------------------------------------------------------------ //
// env / status bar
// ------------------------------------------------------------------ //

async function loadEnv() {
  try {
    const env = await API.get("/api/env");
    setDotStatus("admin-dot", env.admin);
    $("admin-text").textContent = env.admin ? t("admin_yes") : t("admin_no");
    $("home-admin-warning").style.display = env.admin ? "none" : "block";
    if (!env.curl) toast(t("err_curl_not_found"), "error");
    if (env.zapret_service_installed) {
      toast(t("msg_service_installed_warning"), "info");
    }
  } catch (e) { /* ignore */ }
}

let winwsRunning = false;

async function pollWinwsStatus() {
  try {
    const { running } = await API.get("/api/manual/status");
    winwsRunning = running;
    setDotStatus("winws-dot", running);
    $("winws-text").textContent = running ? t("winws_running") : t("winws_stopped");
    updateConnectUI();
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
// Подбор стратегии (generator) tab
// ------------------------------------------------------------------ //

let generatorMode = "simple";
let generatorLogCursor = 0;
let generatorPollTimer = null;

document.querySelectorAll("#generator-mode-segmented button").forEach((btn) => {
  btn.addEventListener("click", () => {
    generatorMode = btn.dataset.value;
    setSegmentedValue("generator-mode-segmented", generatorMode);
    $("generator-mode-hint").textContent = t(
      generatorMode === "simple" ? "generator_mode_simple_hint" : "generator_mode_advanced_hint"
    );
  });
});

function setGeneratorRunningUI(running) {
  $("run-generator").disabled = running;
  $("stop-generator").disabled = !running;
}

function updateGeneratorProgress({ done, total }) {
  const pct = total ? Math.round((done / total) * 100) : 0;
  $("generator-progress-fill").style.width = pct + "%";
  $("generator-progress-text").textContent = `${done}/${total}`;
}

function appendGeneratorLogLines(lines) {
  if (!lines || !lines.length) return;
  const el = $("generator-log");
  el.textContent += lines.join("\n") + "\n";
  el.scrollTop = el.scrollHeight;
}

async function saveCandidate(name, btn) {
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = t("msg_saving");
  try {
    const { path } = await API.post("/api/generator/save", { version: state.version, candidate: name, save_as: name });
    toast(t("msg_strategy_saved", { path }), "success");
    await loadStrategiesForAllTabs();
  } catch (e) {
    toast(e.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

function generatorSummaryRow(label, value, candidateName) {
  const row = document.createElement("div");
  row.className = "summary-row";
  row.innerHTML = `
    <div>
      <div class="summary-label">${escapeHtml(label)}</div>
      <div class="summary-value">${escapeHtml(value)}</div>
    </div>
    <button class="btn btn-primary btn-small">${t("btn_save_strategy")}</button>`;
  row.querySelector("button").addEventListener("click", (e) => saveCandidate(candidateName, e.target));
  return row;
}

function renderGeneratorSummary(snap) {
  const container = $("generator-summary");
  container.innerHTML = "";

  if (snap.baseline) {
    const baselineText = Object.entries(snap.baseline).map(([svc, d]) => `${svc} ${d.score}/${d.total}`).join(", ");
    const el = document.createElement("div");
    el.className = "muted small";
    el.textContent = `${t("label_baseline")}: ${baselineText}`;
    container.appendChild(el);
  }

  if (!snap.best) {
    const el = document.createElement("div");
    el.className = "muted";
    el.textContent = t("msg_no_results");
    container.appendChild(el);
    return;
  }

  for (const [service, info] of Object.entries(snap.best.per_service)) {
    container.appendChild(generatorSummaryRow(service, `${info.strategy} (${info.score}/${info.total})`, info.strategy));
  }
  if (snap.best.overall) {
    container.appendChild(generatorSummaryRow(
      t("label_best_overall"),
      `${snap.best.overall.strategy} (${snap.best.overall.score}/${snap.best.overall.total})`,
      snap.best.overall.strategy
    ));
  }
}

async function startGenerator() {
  if (!state.version) return toast(t("err_select_version"), "error");
  const services = getSelectedFromClass("gen-service-checkbox-filter");
  if (!services.length) return toast(t("err_select_service"), "error");

  const ok = await confirmModal(t("confirm_run_generator_title"), t("confirm_run_generator_msg", { services: services.join(", ") }));
  if (!ok) return;

  $("generator-log").textContent = "";
  $("generator-summary").innerHTML = "";
  generatorLogCursor = 0;
  updateGeneratorProgress({ done: 0, total: 0 });
  setGeneratorRunningUI(true);

  try {
    await API.post("/api/generator/start", { version: state.version, mode: generatorMode, services });
  } catch (e) {
    toast(e.message, "error");
    setGeneratorRunningUI(false);
    return;
  }
  pollGenerator();
}

function pollGenerator() {
  clearInterval(generatorPollTimer);
  generatorPollTimer = setInterval(async () => {
    try {
      const snap = await API.get(`/api/generator/status?since=${generatorLogCursor}`);
      appendGeneratorLogLines(snap.log);
      generatorLogCursor = snap.log_len;
      updateGeneratorProgress(snap.progress);
      if (!snap.running) {
        clearInterval(generatorPollTimer);
        setGeneratorRunningUI(false);
        renderGeneratorSummary(snap);
      }
    } catch (e) { /* transient — keep polling */ }
  }, 700);
}

async function stopGenerator() {
  try {
    await API.post("/api/generator/stop", {});
  } catch (e) { /* ignore */ }
}

$("run-generator").addEventListener("click", startGenerator);
$("stop-generator").addEventListener("click", stopGenerator);

// ------------------------------------------------------------------ //
// home screen — VPN-style connect circle (manual launch/stop)
// ------------------------------------------------------------------ //

function updateConnectUI() {
  const circle = $("connect-circle");
  const select = $("hero-strategy-select");
  const strategy = select.value;

  circle.classList.toggle("connected", winwsRunning);
  select.disabled = winwsRunning;

  const statusEl = $("connect-status");
  statusEl.classList.toggle("connected", winwsRunning);
  statusEl.textContent = winwsRunning ? t("home_status_connected") : t("home_status_disconnected");

  if (winwsRunning) {
    $("connect-sub").textContent = t("home_sub_connected", { strategy: strategy || "" });
  } else if (strategy) {
    $("connect-sub").textContent = t("home_sub_disconnected", { strategy });
  } else {
    $("connect-sub").textContent = t("home_sub_no_strategy");
  }
}

$("hero-strategy-select").addEventListener("change", updateConnectUI);

$("connect-circle").addEventListener("click", async () => {
  if (!state.version) return toast(t("err_select_version"), "error");
  const circle = $("connect-circle");
  circle.classList.add("busy");
  try {
    if (winwsRunning) {
      await API.post("/api/manual/stop", {});
      toast(t("msg_winws_stopped"), "success");
    } else {
      const strategy = $("hero-strategy-select").value;
      if (!strategy) { toast(t("err_select_strategy"), "error"); return; }
      await API.post("/api/manual/launch", { version: state.version, strategy });
      toast(t("msg_launched", { strategy }), "success");
    }
  } catch (e) {
    toast(e.message, "error");
  } finally {
    circle.classList.remove("busy");
    await pollWinwsStatus();
  }
});

// ------------------------------------------------------------------ //
// home <-> settings view switching
// ------------------------------------------------------------------ //

function switchView(showId, hideId) {
  const show = $(showId);
  const hide = $(hideId);
  hide.classList.remove("visible");
  show.classList.add("active");
  requestAnimationFrame(() => requestAnimationFrame(() => show.classList.add("visible")));
  setTimeout(() => hide.classList.remove("active"), 260);
}

$("open-settings").addEventListener("click", () => switchView("view-settings", "view-home"));
$("close-settings").addEventListener("click", () => switchView("view-home", "view-settings"));

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

function syncStateBadge(id, value) {
  $(id).textContent = `[${value}]`;
}

async function loadServiceSettings() {
  if (!state.version) return;
  try {
    const s = await API.get(`/api/service/settings?version=${encodeURIComponent(state.version)}`);
    setSegmentedValue("game-filter-segmented", s.game_filter);
    syncStateBadge("state-gamefilter", s.game_filter === "disabled" ? t("gf_disabled") : s.game_filter.toUpperCase());
    syncStateBadge("state-ipset", s.ipset);
    syncStateBadge("state-autoupdate", s.check_updates ? t("state_enabled") : t("state_disabled"));
    $("check-updates-toggle").checked = s.check_updates;
  } catch (e) { /* ignore */ }
}

$("game-filter-segmented").addEventListener("click", async (e) => {
  const btn = e.target.closest("button");
  if (!btn || !state.version) return;
  setSegmentedValue("game-filter-segmented", btn.dataset.value);
  syncStateBadge("state-gamefilter", btn.dataset.value === "disabled" ? t("gf_disabled") : btn.dataset.value.toUpperCase());
  try {
    await API.post("/api/service/settings/game_filter", { version: state.version, mode: btn.dataset.value });
    logService(t("log_game_filter_set", { mode: btn.dataset.value }));
  } catch (e) { toast(e.message, "error"); }
});

$("ipset-cycle").addEventListener("click", async () => {
  if (!state.version) return;
  try {
    const { status } = await API.post("/api/service/settings/ipset_cycle", { version: state.version });
    syncStateBadge("state-ipset", status);
    logService(t("log_ipset_switched", { status }));
  } catch (e) { toast(e.message, "error"); }
});

$("check-updates-toggle").addEventListener("change", async (e) => {
  if (!state.version) return;
  const label = e.target.checked ? t("state_enabled") : t("state_disabled");
  try {
    await API.post("/api/service/settings/check_updates", { version: state.version, enabled: e.target.checked });
    syncStateBadge("state-autoupdate", label);
    logService(t("log_check_updates_toggled", { state: label }));
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
    syncStateBadge("state-ipset", s.ipset);
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
  await loadScanSettings();
  await loadVersions();
  await loadStrategiesForAllTabs();
  pollWinwsStatus();
  setInterval(pollWinwsStatus, 2000);
})();
