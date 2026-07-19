#!/usr/bin/env python3
"""Shared ru/en message catalog for backend-generated text (diagnostics,
service status/output, error messages) that reaches the web UI. The web UI
sends the user's chosen language via the X-Zapret-Lang header on every
request; zapret_web.py reads it and passes `lang` down into zapret_service.py
/ zapret_tester.py functions, which format their output through t()."""

MESSAGES = {
    # -- generic ----------------------------------------------------- #
    "not_found_generic": {"ru": "не найдено", "en": "not found"},
    "found_conflicts_generic": {"ru": "найдено — конфликтует с zapret", "en": "found — conflicts with zapret"},

    # -- zapret_service: stop_services -------------------------------- #
    "svc_stopped": {"ru": "остановлена", "en": "stopped"},
    "svc_stop_failed": {"ru": "не удалось остановить", "en": "failed to stop"},

    # -- zapret_service: install_service ------------------------------ #
    "install_bat_not_found": {"ru": "{bat_name} не найден в {version_dir}", "en": "{bat_name} not found in {version_dir}"},
    "winws_didnt_start": {
        "ru": "winws.exe не запустился для {bat_name} — не удалось прочитать его параметры.",
        "en": "winws.exe didn't start for {bat_name} — couldn't read its parameters.",
    },
    "cmdline_parse_failed": {
        "ru": "Не удалось разобрать командную строку winws.exe:\n{cmdline}",
        "en": "Couldn't parse winws.exe's command line:\n{cmdline}",
    },
    "sc_create_failed": {"ru": "sc create не удался:\n{stdout}\n{stderr}", "en": "sc create failed:\n{stdout}\n{stderr}"},
    "service_installed_detail": {
        "ru": "Служба 'zapret' создана и запущена со стратегией {bat_name}.\n{extra}",
        "en": "The 'zapret' service was created and started with strategy {bat_name}.\n{extra}",
    },

    # -- zapret_service: remove_service -------------------------------- #
    "service_stopped_removed": {"ru": "Служба 'zapret' остановлена и удалена.", "en": "The 'zapret' service was stopped and removed."},
    "service_not_installed": {"ru": "Служба 'zapret' не была установлена.", "en": "The 'zapret' service wasn't installed."},
    "winws_process_stopped": {"ru": "Процесс winws.exe остановлен.", "en": "The winws.exe process was stopped."},
    "windivert_removed": {"ru": "Служба 'WinDivert' удалена.", "en": "The 'WinDivert' service was removed."},

    # -- zapret_service: service_status --------------------------------- #
    "status_zapret_line": {"ru": "Служба 'zapret': {state}", "en": "'zapret' service: {state}"},
    "status_not_installed": {"ru": "не установлена", "en": "not installed"},
    "status_installed_strategy": {"ru": "  Установленная стратегия: {strategy}", "en": "  Installed strategy: {strategy}"},
    "status_windivert_line": {"ru": "Служба 'WinDivert': {state}", "en": "'WinDivert' service: {state}"},
    "status_sys_found": {"ru": "WinDivert64.sys: найден", "en": "WinDivert64.sys: found"},
    "status_sys_not_found": {"ru": "WinDivert64.sys: НЕ найден", "en": "WinDivert64.sys: NOT found"},
    "status_winws_running": {"ru": "winws.exe: ЗАПУЩЕН", "en": "winws.exe: RUNNING"},
    "status_winws_stopped": {"ru": "winws.exe: не запущен", "en": "winws.exe: not running"},

    # -- zapret_service: cycle_ipset ------------------------------------ #
    "ipset_no_backup": {
        "ru": "Нет резервной копии для восстановления. Сначала обновите список IPSet.",
        "en": "No backup to restore from. Update the IPSet list first.",
    },

    # -- zapret_service: update_ipset_list / check_hosts_file ------------ #
    "ipset_download_failed": {"ru": "Не удалось скачать список IPSet.", "en": "Failed to download the IPSet list."},
    "ipset_updated": {"ru": "ipset-all.txt обновлён ({size} байт).", "en": "ipset-all.txt updated ({size} bytes)."},
    "hosts_download_failed": {"ru": "Не удалось скачать эталонный hosts-файл.", "en": "Failed to download the reference hosts file."},
    "hosts_empty": {"ru": "Скачанный hosts-файл пуст.", "en": "The downloaded hosts file is empty."},
    "hosts_needs_update": {
        "ru": "Файл hosts нужно обновить. Открыт Notepad со скачанным файлом и проводник — скопируйте содержимое вручную.",
        "en": "The hosts file needs updating. Notepad (with the downloaded file) and Explorer were opened — copy the contents over manually.",
    },
    "hosts_up_to_date": {"ru": "Файл hosts в актуальном состоянии.", "en": "The hosts file is up to date."},
    "version_fetch_failed": {"ru": "Не удалось получить версию с GitHub.", "en": "Failed to fetch the version from GitHub."},

    # -- zapret_downloader ------------------------------------------------ #
    "err_download_network": {
        "ru": "Не удалось связаться с GitHub. Проверьте подключение к интернету.",
        "en": "Couldn't reach GitHub. Check your internet connection.",
    },
    "err_download_rate_limited": {
        "ru": "GitHub временно ограничил количество запросов с этого адреса. Попробуйте позже.",
        "en": "GitHub is temporarily rate-limiting requests from this address. Try again later.",
    },
    "err_download_not_found": {"ru": "Релиз не найден на GitHub.", "en": "Release not found on GitHub."},
    "err_download_no_asset": {
        "ru": "В этом релизе нет zip-архива для скачивания.",
        "en": "This release has no zip archive to download.",
    },
    "err_download_hash_mismatch": {
        "ru": "Скачанный файл не совпадает с официальной контрольной суммой GitHub — загрузка отменена.",
        "en": "The downloaded file doesn't match GitHub's published checksum — download cancelled.",
    },
    "err_download_already_exists": {
        "ru": "Папка {name} уже скачана.",
        "en": "{name} has already been downloaded.",
    },

    # -- zapret_service: run_diagnostics — check names ------------------- #
    "name_bfe": {"ru": "Base Filtering Engine", "en": "Base Filtering Engine"},
    "name_proxy": {"ru": "Системный прокси", "en": "System proxy"},
    "name_tcp_timestamps": {"ru": "TCP timestamps", "en": "TCP timestamps"},
    "name_adguard": {"ru": "AdGuard", "en": "AdGuard"},
    "name_killer": {"ru": "Killer", "en": "Killer"},
    "name_intel": {"ru": "Intel Connectivity", "en": "Intel Connectivity"},
    "name_checkpoint": {"ru": "Check Point", "en": "Check Point"},
    "name_smartbyte": {"ru": "SmartByte", "en": "SmartByte"},
    "name_windivert_sys": {"ru": "WinDivert64.sys", "en": "WinDivert64.sys"},
    "name_vpn": {"ru": "VPN", "en": "VPN"},
    "name_doh": {"ru": "Secure DNS (DoH)", "en": "Secure DNS (DoH)"},
    "name_hosts_file": {"ru": "Файл hosts", "en": "Hosts file"},
    "name_windivert_conflict": {"ru": "Конфликт WinDivert", "en": "WinDivert conflict"},
    "name_conflicting_services": {"ru": "Конфликтующие bypass-службы", "en": "Conflicting bypass services"},

    # -- zapret_service: run_diagnostics — messages ----------------------- #
    "bfe_ok": {"ru": "запущен", "en": "running"},
    "bfe_error": {"ru": "НЕ запущен — обязателен для работы zapret", "en": "NOT running — required for zapret to work"},
    "proxy_warn": {
        "ru": "включён: {server}. Проверьте, что он рабочий, либо отключите",
        "en": "enabled: {server}. Make sure it's valid, or disable it",
    },
    "proxy_ok": {"ru": "отключён", "en": "disabled"},
    "proxy_not_configured": {"ru": "не настроен", "en": "not configured"},
    "ts_ok": {"ru": "включены", "en": "enabled"},
    "ts_warn": {"ru": "были выключены — включены автоматически", "en": "were disabled — enabled automatically"},
    "adguard_error": {
        "ru": "процесс AdguardSvc.exe найден — может конфликтовать с Discord",
        "en": "AdguardSvc.exe process found — may conflict with Discord",
    },
    "adguard_ok": {"ru": "не найден", "en": "not found"},
    "killer_error": {"ru": "службы Killer найдены — конфликтуют с zapret", "en": "Killer services found — conflict with zapret"},
    "intel_error": {"ru": "служба найдена — конфликтует с zapret", "en": "service found — conflicts with zapret"},
    "sys_found": {"ru": "найден", "en": "found"},
    "sys_missing": {"ru": "файл не найден в bin/", "en": "file not found in bin/"},
    "vpn_found": {
        "ru": "найдены службы VPN: {labels}. Могут конфликтовать с zapret",
        "en": "VPN services found: {labels}. May conflict with zapret",
    },
    "doh_ok": {"ru": "настроен хотя бы на одном интерфейсе", "en": "configured on at least one interface"},
    "doh_warn": {
        "ru": "не настроен — рекомендуется включить DNS через HTTPS в браузере или Windows 11",
        "en": "not configured — consider enabling DNS over HTTPS in your browser or Windows 11",
    },
    "hosts_check_warn": {
        "ru": "содержит записи youtube.com/youtu.be — может мешать доступу к YouTube",
        "en": "contains youtube.com/youtu.be entries — may interfere with YouTube access",
    },
    "hosts_check_ok": {"ru": "не содержит подозрительных записей YouTube", "en": "no suspicious YouTube entries found"},
    "windivert_conflict_warn": {
        "ru": "winws не запущен, но служба WinDivert активна — возможен конфликт с другим bypass-инструментом",
        "en": "winws isn't running but the WinDivert service is active — possible conflict with another bypass tool",
    },
    "windivert_conflict_ok": {"ru": "не обнаружено", "en": "not detected"},
    "conflicts_found": {"ru": "найдены: {names}", "en": "found: {names}"},

    # -- zapret_service: fix_windivert_conflict --------------------------- #
    "windivert_not_installed": {"ru": "{name}: не установлена", "en": "{name}: not installed"},
    "svc_removed_short": {"ru": "{name}: удалена", "en": "{name}: removed"},
    "svc_remove_failed_short": {"ru": "{name}: не удалось удалить", "en": "{name}: failed to remove"},

    # -- zapret_service: remove_conflicting_services ------------------------ #
    "svc_stopped_removed_maybe": {
        "ru": "{name}: остановлена и удалена (если существовала)",
        "en": "{name}: stopped and removed (if it existed)",
    },

    # -- zapret_service: clear_discord_cache --------------------------------- #
    "discord_cache_cleared": {"ru": "Discord закрыт. Удалены папки: {folders}", "en": "Discord closed. Removed folders: {folders}"},
    "discord_no_folders": {"ru": "не найдены", "en": "none found"},

    # -- zapret_web: errors ---------------------------------------------------- #
    "err_test_already_running": {"ru": "Тест уже выполняется", "en": "A test is already running"},
    "err_strategies_not_found": {"ru": "Стратегии не найдены", "en": "Strategies not found"},
    "err_services_not_found": {"ru": "Сервисы не найдены", "en": "Services not found"},
    "err_no_service_selected": {"ru": "Не выбрано ни одной службы", "en": "No service selected"},
    "err_version_not_specified": {"ru": "Версия не указана", "en": "Version not specified"},
    "err_unknown_version": {"ru": "Неизвестная версия: {name}", "en": "Unknown version: {name}"},
    "err_strategy_not_found": {"ru": "Стратегия не найдена: {strategy}", "en": "Strategy not found: {strategy}"},
    "err_bad_scan_mode": {"ru": "Неизвестный режим поиска версий", "en": "Unknown version scan mode"},
    "err_no_custom_dir": {"ru": "Папка не выбрана", "en": "No folder chosen"},
    "err_generator_already_running": {"ru": "Подбор стратегии уже выполняется", "en": "A generator run is already in progress"},
    "err_bad_generator_mode": {"ru": "Неизвестный режим подбора стратегии", "en": "Unknown generator mode"},
    "err_generator_candidate_not_found": {
        "ru": "Вариант не найден — запустите подбор заново",
        "en": "Candidate not found — run the generator again",
    },
    "err_zapret2_no_version": {
        "ru": "Версия zapret2 не найдена — обновите список",
        "en": "Zapret2 version not found — reload the list",
    },
    "err_zapret2_profile_not_found": {
        "ru": "Профиль не найден — обновите список",
        "en": "Profile not found — reload the list",
    },

    # -- zapret_generator: log lines reaching the web UI ------------------------- #
    "gen_baseline_start": {
        "ru": "Замеряю доступность без обхода (baseline)...",
        "en": "Measuring connectivity with no bypass running (baseline)...",
    },
    "gen_stage1": {"ru": "Этап 1: пробую {count} комбинаций методов...", "en": "Stage 1: trying {count} method combinations..."},
    "gen_stage2": {
        "ru": "Этап 2: уточняю параметры вокруг лучших ({winners}), ещё {count} вариантов...",
        "en": "Stage 2: refining parameters around the best result(s) ({winners}), {count} more candidates...",
    },
    "gen_inconclusive_warning": {
        "ru": "Ни один вариант не показал результат лучше, чем совсем без обхода — "
              "возможно, выбранные сайты у вас и так не заблокированы, либо нужно "
              "подбирать вручную.",
        "en": "No candidate scored better than running with no bypass at all — the "
              "selected sites may not actually be blocked for you, or this needs "
              "manual tuning.",
    },

    # -- zapret_tester: log lines reaching the web UI --------------------------- #
    "stopped_by_user": {"ru": "Остановлено пользователем.", "en": "Stopped by user."},
    "strategy_didnt_start": {
        "ru": "    [WARN] winws.exe не запустился для этой стратегии — пропуск.",
        "en": "    [WARN] winws.exe didn't start for this strategy — skipping.",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    lang = lang if lang in ("ru", "en") else "ru"
    entry = MESSAGES.get(key)
    if entry is None:
        return key
    template = entry.get(lang) or entry.get("ru", key)
    return template.format(**kwargs) if kwargs else template
