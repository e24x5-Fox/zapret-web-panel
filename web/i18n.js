"use strict";

const I18N = {
  ru: {
    page_title: "Zapret Control Panel",
    brand_sub: "Панель управления",
    field_version: "Версия",
    btn_reload_versions: "Обновить список версий",
    nav_test: "Тест",
    nav_manual: "Ручной запуск",
    nav_service: "Служба",
    nav_diagnostics: "Диагностика",
    checking: "проверка...",
    checking_dots: "Проверка...",

    test_title: "Тест стратегий",
    test_desc: "Прогоняет выбранные стратегии по выбранным сервисам и показывает, какая реально пробивает блокировку.",
    strategies_title: "Стратегии",
    select_all: "Все",
    select_none: "Ничего",
    services_title: "Сервисы",
    test_progress_title: "Ход теста",
    btn_run_test: "Запустить тест",
    btn_stop: "Остановить",

    manual_title: "Ручной запуск",
    manual_desc: "Запустите любую стратегию из выбранной версии напрямую, без теста.",
    field_strategy: "Стратегия",
    btn_launch: "Запустить",

    service_title: "Служба",
    service_desc: "Полный функционал service.bat — install/remove, настройки, обновления. Без консоли.",
    autostart_title: "Автозапуск",
    field_install_strategy: "Стратегия для установки",
    btn_service_install: "Установить как службу",
    btn_service_remove: "Удалить службу",
    btn_status: "Статус",
    settings_title: "Настройки",
    label_game_filter: "Игровой фильтр",
    gf_disabled: "Выкл",
    label_ipset: "Список IP (ipset)",
    btn_switch: "Переключить",
    label_check_updates: "Автопроверка обновлений zapret",
    updates_title: "Обновления",
    btn_update_ipset: "Обновить список IPSet",
    btn_update_hosts: "Проверить/обновить hosts",
    btn_check_updates: "Проверить обновления zapret",
    output_title: "Вывод",

    diagnostics_title: "Диагностика",
    diagnostics_desc: "Проверки конфликтов и здоровья системы — как в service.bat → Run Diagnostics.",
    btn_run_diagnostics: "Запустить диагностику",
    btn_remove_conflicts: "Удалить конфликтующие службы",
    btn_fix_windivert: "Исправить конфликт WinDivert",
    btn_clear_discord_cache: "Очистить кэш Discord",

    modal_cancel: "Отмена",
    modal_confirm: "Подтвердить",

    // dynamic
    msg_versions_reloaded: "Список версий обновлён",
    admin_yes: "Администратор",
    admin_no: "НЕТ прав администратора",
    err_curl_not_found: "curl.exe не найден в PATH — тесты не будут работать",
    msg_service_installed_warning: "Служба 'zapret' сейчас установлена — тест недоступен, пока она не удалена",
    winws_running: "winws: запущен",
    winws_stopped: "winws: остановлен",
    winws_running_caps: "winws ЗАПУЩЕН",
    winws_stopped2: "winws остановлен",
    btn_enable: "Включить",
    msg_no_results: "Ни одна стратегия не дала результатов.",
    label_best_overall: "Лучшая в целом",
    label_report_saved: "Отчёт сохранён: ",
    msg_strategy_launched: "Запущена стратегия: {name}",
    err_select_version: "Выберите версию",
    err_select_strategy: "Выберите хотя бы одну стратегию",
    err_select_service: "Выберите хотя бы один сервис",
    confirm_run_test_title: "Запустить тест?",
    confirm_run_test_msg: "Будет протестировано {count} стратегий(и) по сервисам: {services}.\nНа время теста ваш текущий winws будет остановлен (после теста восстановится).",
    msg_launched: "Запущено: {strategy}",
    msg_winws_stopped: "winws.exe остановлен",
    log_game_filter_set: "Игровой фильтр: {mode}. Перезапустите стратегию, чтобы применить.",
    log_ipset_switched: "Список IP переключён на: {status}",
    log_check_updates_toggled: "Автопроверка обновлений: {state}",
    state_enabled: "включена",
    state_disabled: "выключена",
    confirm_install_service_title: "Установить службу?",
    confirm_install_service_msg: "Стратегия «{strategy}» будет установлена как автозапускаемая служба Windows 'zapret'.\nЭто изменение сохранится после перезагрузки.",
    log_installing_service: ">>> Установка службы: {strategy}",
    msg_service_installed: "Служба установлена",
    label_error_prefix: "Ошибка: {message}",
    confirm_remove_service_title: "Удалить службу?",
    confirm_remove_service_msg: "Удалить службу 'zapret', если она установлена?",
    log_removing_service: ">>> Удаление службы",
    msg_service_removed: "Служба удалена (если была установлена)",
    log_checking_status: ">>> Проверка статуса",
    log_updating_ipset: ">>> Обновление списка IPSet",
    log_checking_hosts: ">>> Проверка hosts-файла",
    log_checking_updates: ">>> Проверка обновлений zapret",
    log_latest_version: "Установлена последняя версия: {version}",
    log_new_version_available: "Установлена: {local}, доступна новая: {latest}\nСтраница релиза: {url}",
    msg_diagnostics_running: "Выполняется диагностика...",
    confirm_fix_windivert_title: "Исправить конфликт WinDivert?",
    confirm_fix_windivert_msg: "Служба WinDivert (драйвер перехвата трафика) будет остановлена и удалена — она переустановится автоматически при следующем запуске любой стратегии.",
    confirm_remove_conflicts_title: "Удалить конфликтующие службы?",
    confirm_remove_conflicts_msg: "Будут остановлены и удалены службы:\n{names}",
    confirm_clear_discord_title: "Очистить кэш Discord?",
    confirm_clear_discord_msg: "Discord будет закрыт, а его папки Cache/Code Cache/GPUCache — удалены.\nDiscord пересоздаст их при следующем запуске.",
    btn_stop_selected: "Остановить выбранные",
    err_nothing_selected: "Ничего не выбрано",
    confirm_stop_services_title: "Остановить службы?",
    confirm_stop_services_msg: "Будут остановлены:\n{names}",

    // console-menu screen
    menu_cat_service: "SERVICE",
    menu_cat_settings: "SETTINGS",
    menu_cat_updates: "UPDATES",
    menu_cat_tools: "TOOLS",
    menu_install_service: "Установить службу",
    menu_remove_services: "Удалить службы",
    menu_check_status: "Проверить статус",
    menu_manual_launch: "Ручной запуск стратегии",
    menu_game_filter: "Игровой фильтр",
    menu_ipset_filter: "Список IP (ipset)",
    menu_autoupdate: "Автопроверка обновлений",
    menu_update_ipset: "Обновить список IPSet",
    menu_update_hosts: "Обновить hosts-файл",
    menu_check_updates: "Проверить обновления",
    menu_run_diagnostics: "Запустить диагностику",
    menu_run_tests: "Запустить тест",
    err_no_versions_found: "Не найдено ни одной версии zapret ни рядом с панелью, ни на дисках компьютера",
    msg_scanning: "Сканирование дисков...",
    label_scan_mode: "Поиск версий",
    scan_mode_global: "Всё устройство",
    scan_mode_custom: "Конкретная папка",
    btn_show_paths: "[показать пути]",
    btn_hide_paths: "[скрыть пути]",
    btn_pick_folder: "[выбрать...]",
    btn_picking_folder: "[открываю диалог...]",
    label_no_custom_dir: "папка не выбрана",
    btn_open_folder: "открыть папку",
    found_paths_empty: "Ничего не найдено.",
    msg_scan_settings_saved: "Настройка поиска сохранена, список версий обновлён",
    btn_delete_folder: "удалить",
    confirm_delete_folder_title: "Удалить папку?",
    confirm_delete_folder_msg: "Папка будет удалена безвозвратно:\n{path}\n\nЭто действие нельзя отменить.",
    msg_folder_deleted: "Папка удалена",
  },

  en: {
    page_title: "Zapret Control Panel",
    brand_sub: "Control Panel",
    field_version: "Version",
    btn_reload_versions: "Refresh version list",
    nav_test: "Test",
    nav_manual: "Manual launch",
    nav_service: "Service",
    nav_diagnostics: "Diagnostics",
    checking: "checking...",
    checking_dots: "Checking...",

    test_title: "Strategy test",
    test_desc: "Runs the selected strategies against the selected services and shows which one actually gets through.",
    strategies_title: "Strategies",
    select_all: "All",
    select_none: "None",
    services_title: "Services",
    test_progress_title: "Test progress",
    btn_run_test: "Run test",
    btn_stop: "Stop",

    manual_title: "Manual launch",
    manual_desc: "Start any strategy from the selected version directly, no test needed.",
    field_strategy: "Strategy",
    btn_launch: "Launch",

    service_title: "Service",
    service_desc: "Everything service.bat's console can do — install/remove, settings, updates. No console.",
    autostart_title: "Autostart",
    field_install_strategy: "Strategy to install",
    btn_service_install: "Install as service",
    btn_service_remove: "Remove service",
    btn_status: "Status",
    settings_title: "Settings",
    label_game_filter: "Game filter",
    gf_disabled: "Off",
    label_ipset: "IP list (ipset)",
    btn_switch: "Switch",
    label_check_updates: "Auto-check zapret updates",
    updates_title: "Updates",
    btn_update_ipset: "Update IPSet list",
    btn_update_hosts: "Check/update hosts",
    btn_check_updates: "Check zapret updates",
    output_title: "Output",

    diagnostics_title: "Diagnostics",
    diagnostics_desc: "Conflict/health checks — same as service.bat's Run Diagnostics.",
    btn_run_diagnostics: "Run diagnostics",
    btn_remove_conflicts: "Remove conflicting services",
    btn_fix_windivert: "Fix WinDivert conflict",
    btn_clear_discord_cache: "Clear Discord cache",

    modal_cancel: "Cancel",
    modal_confirm: "Confirm",

    // dynamic
    msg_versions_reloaded: "Version list refreshed",
    admin_yes: "Administrator",
    admin_no: "NOT running as administrator",
    err_curl_not_found: "curl.exe not found in PATH — tests won't work",
    msg_service_installed_warning: "The 'zapret' service is currently installed — testing is unavailable until it's removed",
    winws_running: "winws: running",
    winws_stopped: "winws: stopped",
    winws_running_caps: "winws RUNNING",
    winws_stopped2: "winws stopped",
    btn_enable: "Enable",
    msg_no_results: "No strategy produced any results.",
    label_best_overall: "Best overall",
    label_report_saved: "Report saved: ",
    msg_strategy_launched: "Strategy launched: {name}",
    err_select_version: "Select a version",
    err_select_strategy: "Select at least one strategy",
    err_select_service: "Select at least one service",
    confirm_run_test_title: "Run the test?",
    confirm_run_test_msg: "{count} strategy(ies) will be tested against: {services}.\nYour current winws will be stopped during the test (restored afterwards).",
    msg_launched: "Launched: {strategy}",
    msg_winws_stopped: "winws.exe stopped",
    log_game_filter_set: "Game filter: {mode}. Restart the strategy to apply.",
    log_ipset_switched: "IP list switched to: {status}",
    log_check_updates_toggled: "Auto-update check: {state}",
    state_enabled: "enabled",
    state_disabled: "disabled",
    confirm_install_service_title: "Install as service?",
    confirm_install_service_msg: "Strategy «{strategy}» will be installed as the autostart Windows service 'zapret'.\nThis change persists across reboots.",
    log_installing_service: ">>> Installing service: {strategy}",
    msg_service_installed: "Service installed",
    label_error_prefix: "Error: {message}",
    confirm_remove_service_title: "Remove the service?",
    confirm_remove_service_msg: "Remove the 'zapret' service, if installed?",
    log_removing_service: ">>> Removing service",
    msg_service_removed: "Service removed (if it was installed)",
    log_checking_status: ">>> Checking status",
    log_updating_ipset: ">>> Updating IPSet list",
    log_checking_hosts: ">>> Checking hosts file",
    log_checking_updates: ">>> Checking zapret updates",
    log_latest_version: "Latest version already installed: {version}",
    log_new_version_available: "Installed: {local}, new version available: {latest}\nRelease page: {url}",
    msg_diagnostics_running: "Running diagnostics...",
    confirm_fix_windivert_title: "Fix the WinDivert conflict?",
    confirm_fix_windivert_msg: "The WinDivert service (traffic interception driver) will be stopped and removed — it reinstalls itself automatically the next time any strategy runs.",
    confirm_remove_conflicts_title: "Remove conflicting services?",
    confirm_remove_conflicts_msg: "These services will be stopped and removed:\n{names}",
    confirm_clear_discord_title: "Clear Discord's cache?",
    confirm_clear_discord_msg: "Discord will be closed and its Cache/Code Cache/GPUCache folders removed.\nDiscord recreates them on next launch.",
    btn_stop_selected: "Stop selected",
    err_nothing_selected: "Nothing selected",
    confirm_stop_services_title: "Stop these services?",
    confirm_stop_services_msg: "These will be stopped:\n{names}",

    // console-menu screen
    menu_cat_service: "SERVICE",
    menu_cat_settings: "SETTINGS",
    menu_cat_updates: "UPDATES",
    menu_cat_tools: "TOOLS",
    menu_install_service: "Install Service",
    menu_remove_services: "Remove Services",
    menu_check_status: "Check Status",
    menu_manual_launch: "Manual strategy launch",
    menu_game_filter: "Game Filter",
    menu_ipset_filter: "IPSet Filter",
    menu_autoupdate: "Auto-Update Check",
    menu_update_ipset: "Update IPSet List",
    menu_update_hosts: "Update Hosts File",
    menu_check_updates: "Check for Updates",
    menu_run_diagnostics: "Run Diagnostics",
    menu_run_tests: "Run Tests",
    err_no_versions_found: "No zapret version folders found next to the panel or anywhere on the machine's drives",
    msg_scanning: "Scanning drives...",
    label_scan_mode: "Version scan",
    scan_mode_global: "Whole computer",
    scan_mode_custom: "Specific folder",
    btn_show_paths: "[show paths]",
    btn_hide_paths: "[hide paths]",
    btn_pick_folder: "[choose...]",
    btn_picking_folder: "[opening dialog...]",
    label_no_custom_dir: "no folder chosen",
    btn_open_folder: "open folder",
    found_paths_empty: "Nothing found.",
    msg_scan_settings_saved: "Scan setting saved, version list refreshed",
    btn_delete_folder: "delete",
    confirm_delete_folder_title: "Delete this folder?",
    confirm_delete_folder_msg: "This folder will be permanently deleted:\n{path}\n\nThis cannot be undone.",
    msg_folder_deleted: "Folder deleted",
  },
};

let currentLang = localStorage.getItem("zapret_lang") || "ru";
if (!I18N[currentLang]) currentLang = "ru";

function t(key, params) {
  let template = (I18N[currentLang] && I18N[currentLang][key]) || I18N.ru[key] || key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      template = template.split(`{${k}}`).join(v);
    }
  }
  return template;
}

function getLang() {
  return currentLang;
}

function applyStaticTranslations() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.title = t("page_title");
  document.documentElement.lang = currentLang;
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.lang === currentLang);
  });
}

function setLang(lang) {
  if (!I18N[lang] || lang === currentLang) return;
  currentLang = lang;
  localStorage.setItem("zapret_lang", lang);
  applyStaticTranslations();
  document.dispatchEvent(new CustomEvent("zapret:langchange"));
}

document.addEventListener("DOMContentLoaded", () => {
  applyStaticTranslations();
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.addEventListener("click", () => setLang(btn.dataset.lang));
  });
});
