"use strict";

const API = {
  async get(path) {
    const res = await fetch(path, {
      headers: { "X-Zapret-Token": window.ZAPRET_TOKEN || "" },
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
  toast("Список версий обновлён", "info");
});

// ------------------------------------------------------------------ //
// env / status bar
// ------------------------------------------------------------------ //

async function loadEnv() {
  try {
    const env = await API.get("/api/env");
    setDotStatus("admin-dot", env.admin);
    $("admin-text").textContent = env.admin ? "Администратор" : "НЕТ прав администратора";
    if (!env.curl) toast("curl.exe не найден в PATH — тесты не будут работать", "error");
    if (env.zapret_service_installed) {
      toast("Служба 'zapret' сейчас установлена — тест недоступен, пока она не удалена", "info");
    }
  } catch (e) { /* ignore */ }
}

async function pollWinwsStatus() {
  try {
    const { running } = await API.get("/api/manual/status");
    setDotStatus("winws-dot", running);
    $("winws-text").textContent = running ? "winws: запущен" : "winws: остановлен";
    setDotStatus("manual-dot", running);
    $("manual-status-text").textContent = running ? "winws ЗАПУЩЕН" : "winws остановлен";
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
      <button class="btn btn-primary btn-small" data-activate="${escapeHtml(stratName)}">Включить</button>
    </div>`;
}

function renderTestSummary(best, reportPath) {
  const container = $("test-summary");
  if (!best) {
    container.innerHTML = `<div class="muted">Ни одна стратегия не дала результатов.</div>`;
    return;
  }
  let html = "";
  for (const [service, info] of Object.entries(best.per_service)) {
    html += summaryRow(service, `${info.strategy} (${info.score}/${info.total})`, info.strategy);
  }
  if (best.overall) {
    html += summaryRow("Лучшая в целом",
      `${best.overall.strategy} (${best.overall.score}/${best.overall.total})`, best.overall.strategy);
  }
  if (reportPath) {
    html += `<div class="muted small">Отчёт сохранён: ${escapeHtml(reportPath)}</div>`;
  }
  container.innerHTML = html;
  container.querySelectorAll("[data-activate]").forEach((btn) => {
    btn.addEventListener("click", () => activateStrategy(btn.dataset.activate));
  });
}

async function activateStrategy(name) {
  try {
    await API.post("/api/manual/launch", { version: state.version, strategy: name });
    toast(`Запущена стратегия: ${name}`, "success");
  } catch (e) {
    toast(e.message, "error");
  }
}

async function startTest() {
  if (!state.version) return toast("Выберите версию", "error");
  const strategies = getSelectedStrategies();
  if (!strategies.length) return toast("Выберите хотя бы одну стратегию", "error");
  const services = getSelectedServices();
  if (!services.length) return toast("Выберите хотя бы один сервис", "error");

  const ok = await confirmModal(
    "Запустить тест?",
    `Будет протестировано ${strategies.length} стратегий(и) по сервисам: ${services.join(", ")}.\n` +
    "На время теста ваш текущий winws будет остановлен (после теста восстановится)."
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
    toast(`Запущено: ${strategy}`, "success");
  } catch (e) { toast(e.message, "error"); }
});

$("manual-stop").addEventListener("click", async () => {
  try {
    await API.post("/api/manual/stop", {});
    toast("winws.exe остановлен", "success");
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
    logService(`Игровой фильтр: ${btn.dataset.value}. Перезапустите стратегию, чтобы применить.`);
  } catch (e) { toast(e.message, "error"); }
});

$("ipset-cycle").addEventListener("click", async () => {
  if (!state.version) return;
  try {
    const { status } = await API.post("/api/service/settings/ipset_cycle", { version: state.version });
    $("ipset-status-badge").textContent = status;
    logService(`Список IP переключён на: ${status}`);
  } catch (e) { toast(e.message, "error"); }
});

$("check-updates-toggle").addEventListener("change", async (e) => {
  if (!state.version) return;
  try {
    await API.post("/api/service/settings/check_updates", { version: state.version, enabled: e.target.checked });
    logService(`Автопроверка обновлений: ${e.target.checked ? "включена" : "выключена"}`);
  } catch (err) { toast(err.message, "error"); }
});

$("service-install").addEventListener("click", async () => {
  const strategy = $("service-strategy").value;
  if (!state.version || !strategy) return;
  const ok = await confirmModal(
    "Установить службу?",
    `Стратегия «${strategy}» будет установлена как автозапускаемая служба Windows 'zapret'.\n` +
    "Это изменение сохранится после перезагрузки."
  );
  if (!ok) return;
  logService(`>>> Установка службы: ${strategy}`);
  try {
    const { output } = await API.post("/api/service/install", { version: state.version, strategy });
    logService(output);
    toast("Служба установлена", "success");
  } catch (e) {
    logService(`Ошибка: ${e.message}`);
    toast(e.message, "error");
  }
});

$("service-remove").addEventListener("click", async () => {
  const ok = await confirmModal("Удалить службу?", "Удалить службу 'zapret', если она установлена?");
  if (!ok) return;
  logService(">>> Удаление службы");
  try {
    const { output } = await API.post("/api/service/remove", {});
    logService(output);
    toast("Служба удалена (если была установлена)", "success");
  } catch (e) {
    logService(`Ошибка: ${e.message}`);
    toast(e.message, "error");
  }
});

$("service-status").addEventListener("click", async () => {
  if (!state.version) return;
  logService(">>> Проверка статуса");
  try {
    const { text } = await API.get(`/api/service/status?version=${encodeURIComponent(state.version)}`);
    logService(text);
  } catch (e) { logService(`Ошибка: ${e.message}`); }
});

$("update-ipset").addEventListener("click", async () => {
  if (!state.version) return;
  logService(">>> Обновление списка IPSet");
  try {
    const { output } = await API.post("/api/service/update/ipset", { version: state.version });
    logService(output);
    const s = await API.get(`/api/service/settings?version=${encodeURIComponent(state.version)}`);
    $("ipset-status-badge").textContent = s.ipset;
  } catch (e) { logService(`Ошибка: ${e.message}`); }
});

$("update-hosts").addEventListener("click", async () => {
  logService(">>> Проверка hosts-файла");
  try {
    const { output } = await API.post("/api/service/update/hosts", {});
    logService(output);
  } catch (e) { logService(`Ошибка: ${e.message}`); }
});

$("check-updates-btn").addEventListener("click", async () => {
  if (!state.version) return;
  logService(">>> Проверка обновлений zapret");
  try {
    const info = await API.post("/api/service/update/check", { version: state.version });
    if (info.up_to_date) {
      logService(`Установлена последняя версия: ${info.local}`);
    } else {
      logService(`Установлена: ${info.local}, доступна новая: ${info.latest}\nСтраница релиза: ${info.release_url}`);
      window.open(info.download_url, "_blank");
    }
  } catch (e) { logService(`Ошибка: ${e.message}`); }
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
          <button class="btn btn-danger btn-small" data-stop-row="${idx}">Остановить выбранные</button>
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
  if (!checked.length) return toast("Ничего не выбрано", "error");
  const ok = await confirmModal("Остановить службы?", "Будут остановлены:\n" + checked.join(", "));
  if (!ok) return;
  try {
    const { output } = await API.post("/api/diagnostics/stop_services", { names: checked });
    toast(output, "success");
  } catch (e) { toast(e.message, "error"); }
}

$("run-diagnostics").addEventListener("click", async () => {
  if (!state.version) return;
  $("diagnostics-results").innerHTML = `<div class="muted">Выполняется диагностика...</div>`;
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
    $("diagnostics-results").innerHTML = `<div class="muted">Ошибка: ${escapeHtml(e.message)}</div>`;
  }
});

$("fix-windivert").addEventListener("click", async () => {
  const ok = await confirmModal(
    "Исправить конфликт WinDivert?",
    "Служба WinDivert (драйвер перехвата трафика) будет остановлена и удалена — " +
    "она переустановится автоматически при следующем запуске любой стратегии."
  );
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
    "Удалить конфликтующие службы?",
    "Будут остановлены и удалены службы:\n" + lastConflicts.join(", ")
  );
  if (!ok) return;
  try {
    const { output } = await API.post("/api/diagnostics/remove_conflicts", { names: lastConflicts });
    toast(output, "success");
    $("remove-conflicts").disabled = true;
  } catch (e) { toast(e.message, "error"); }
});

$("clear-discord-cache").addEventListener("click", async () => {
  const ok = await confirmModal(
    "Очистить кэш Discord?",
    "Discord будет закрыт, а его папки Cache/Code Cache/GPUCache — удалены.\n" +
    "Discord пересоздаст их при следующем запуске."
  );
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
