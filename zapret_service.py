#!/usr/bin/env python3
"""
Native re-implementation of service.bat's menu — service install/remove/status,
settings toggles, list/hosts updates, and diagnostics — without ever shelling
out to service.bat's own interactive console.

Install works by briefly starting the chosen strategy's bat, reading the exact
resolved winws.exe command line back from Windows (via WMI), and registering
that as the 'zapret' service. This sidesteps re-implementing service.bat's
own fragile %VAR% / quoting parser.
"""

import os
import re
import shutil
import subprocess
import time
import winreg
from pathlib import Path

IPSET_URL = "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/refs/heads/main/.service/ipset-service.txt"
HOSTS_URL = "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/refs/heads/main/.service/hosts"
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/main/.service/version.txt"
GITHUB_RELEASE_URL = "https://github.com/Flowseal/zapret-discord-youtube/releases/tag/"
GITHUB_DOWNLOAD_URL = "https://github.com/Flowseal/zapret-discord-youtube/releases/latest"

CONFLICTING_BYPASS_SERVICES = ["GoodbyeDPI", "discordfix_zapret", "winws1", "winws2"]


# --------------------------------------------------------------------------- #
# low-level helpers
# --------------------------------------------------------------------------- #

_STATE_WORDS = (
    "STOP_PENDING", "START_PENDING", "PAUSE_PENDING", "CONTINUE_PENDING",
    "RUNNING", "PAUSED", "STOPPED",
)


def _service_state(name: str):
    # sc.exe's field labels are localized (e.g. Russian "СОСТОЯНИЕ" instead of
    # "STATE"), but the state value itself (RUNNING/STOPPED/...) always stays
    # in English, so match on that instead of the label.
    res = subprocess.run(["sc", "query", name], capture_output=True, text=True, timeout=10)
    if res.returncode != 0:
        return None
    text = res.stdout.upper()
    for word in _STATE_WORDS:
        if word in text:
            return word
    return None


def _query_all_active_services() -> str:
    return subprocess.run(["sc", "query"], capture_output=True, text=True, timeout=15).stdout or ""


def _parse_sc_records(text: str):
    """Parse bare `sc query` output into [{"name": ..., "display_name": ...}, ...].

    sc.exe's field labels (SERVICE_NAME:/DISPLAY_NAME:) are usually English
    even on localized Windows, but on this machine some entries come back
    with Russian labels instead (a known sc.exe MUI-loading quirk) — mixed
    within the same output. So this parses by position within each
    blank-line-separated record (name always first, display name always
    second) rather than matching the label text.
    """
    records = []
    for block in text.split("\n\n"):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        name_line, display_line = lines[0], lines[1]
        if ":" not in name_line or ":" not in display_line:
            continue
        records.append({
            "name": name_line.split(":", 1)[1].strip(),
            "display_name": display_line.split(":", 1)[1].strip(),
        })
    return records


def stop_services(names) -> str:
    lines = []
    for n in names:
        res = subprocess.run(["net", "stop", n], capture_output=True, text=True, timeout=20)
        ok = res.returncode == 0
        lines.append(f"{n}: {'остановлена' if ok else 'не удалось остановить'}")
    return "\n".join(lines)


def _lines_containing_all(text, *words):
    hits = []
    for line in text.splitlines():
        up = line.upper()
        if all(w.upper() in up for w in words):
            hits.append(line.strip())
    return hits


def _winws_running() -> bool:
    out = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq winws.exe"], capture_output=True, text=True, timeout=10
    ).stdout
    return "winws.exe" in out.lower()


# --------------------------------------------------------------------------- #
# service install / remove / status
# --------------------------------------------------------------------------- #

def _extract_winws_command(bat_path: Path, version_dir: Path) -> str:
    """Briefly launch bat_path so Windows resolves the real winws.exe command
    line (all %BIN%/%LISTS%/%GameFilter% substitutions already applied by
    cmd.exe), read it back via WMI, then stop it."""
    subprocess.run(["taskkill", "/IM", "winws.exe", "/F", "/T"], capture_output=True, timeout=10)
    time.sleep(1)
    subprocess.Popen(
        ["cmd", "/c", str(bat_path)], cwd=str(version_dir),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    cmdline = None
    for _ in range(20):
        time.sleep(0.5)
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"Name='winws.exe'\").CommandLine"],
            capture_output=True, text=True, timeout=10,
        )
        out = res.stdout.strip()
        if out:
            cmdline = out
            break

    subprocess.run(["taskkill", "/IM", "winws.exe", "/F", "/T"], capture_output=True, timeout=10)

    if not cmdline:
        raise RuntimeError(f"winws.exe не запустился для {bat_path.name} — не удалось прочитать его параметры.")
    return cmdline


def install_service(version_dir: Path, bat_name: str) -> str:
    bat_path = version_dir / bat_name
    if not bat_path.exists():
        raise ValueError(f"{bat_name} не найден в {version_dir}")

    cmdline = _extract_winws_command(bat_path, version_dir)
    m = re.match(r'^"([^"]+)"\s*(.*)$', cmdline)
    if not m:
        raise RuntimeError(f"Не удалось разобрать командную строку winws.exe:\n{cmdline}")
    exe_path, args = m.group(1), m.group(2)

    subprocess.run(["net", "stop", "zapret"], capture_output=True, timeout=15)
    subprocess.run(["sc", "delete", "zapret"], capture_output=True, timeout=15)

    binpath = f'"{exe_path}" {args}'
    res = subprocess.run(
        ["sc", "create", "zapret", "binPath=", binpath, "DisplayName=", "zapret", "start=", "auto"],
        capture_output=True, text=True, timeout=20,
    )
    if res.returncode != 0:
        raise RuntimeError(f"sc create не удался:\n{res.stdout}\n{res.stderr}")

    subprocess.run(["sc", "description", "zapret", "Zapret DPI bypass software"], capture_output=True, timeout=10)
    start_res = subprocess.run(["sc", "start", "zapret"], capture_output=True, text=True, timeout=20)

    try:
        key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, r"System\CurrentControlSet\Services\zapret")
        winreg.SetValueEx(key, "zapret-discord-youtube", 0, winreg.REG_SZ, bat_path.stem)
        winreg.CloseKey(key)
    except OSError:
        pass

    return f"Служба 'zapret' создана и запущена со стратегией {bat_name}.\n{start_res.stdout}{start_res.stderr}".strip()


def remove_service() -> str:
    lines = []
    if _service_state("zapret") is not None:
        subprocess.run(["net", "stop", "zapret"], capture_output=True, timeout=15)
        subprocess.run(["sc", "delete", "zapret"], capture_output=True, timeout=15)
        lines.append("Служба 'zapret' остановлена и удалена.")
    else:
        lines.append("Служба 'zapret' не была установлена.")

    if _winws_running():
        subprocess.run(["taskkill", "/IM", "winws.exe", "/F", "/T"], capture_output=True, timeout=10)
        lines.append("Процесс winws.exe остановлен.")

    if _service_state("WinDivert") is not None:
        subprocess.run(["net", "stop", "WinDivert"], capture_output=True, timeout=15)
        subprocess.run(["sc", "delete", "WinDivert"], capture_output=True, timeout=15)
        lines.append("Служба 'WinDivert' удалена.")

    subprocess.run(["net", "stop", "WinDivert14"], capture_output=True, timeout=15)
    subprocess.run(["sc", "delete", "WinDivert14"], capture_output=True, timeout=15)

    return "\n".join(lines)


def installed_strategy_name():
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"System\CurrentControlSet\Services\zapret")
        val, _ = winreg.QueryValueEx(key, "zapret-discord-youtube")
        winreg.CloseKey(key)
        return val
    except OSError:
        return None


def service_status(version_dir: Path) -> str:
    lines = []
    zapret_state = _service_state("zapret")
    lines.append(f"Служба 'zapret': {zapret_state or 'не установлена'}")
    if zapret_state:
        strat = installed_strategy_name()
        if strat:
            lines.append(f"  Установленная стратегия: {strat}")

    windivert_state = _service_state("WinDivert")
    lines.append(f"Служба 'WinDivert': {windivert_state or 'не установлена'}")

    sys_files = list((version_dir / "bin").glob("*.sys"))
    lines.append("WinDivert64.sys: найден" if sys_files else "WinDivert64.sys: НЕ найден")

    lines.append("winws.exe: ЗАПУЩЕН" if _winws_running() else "winws.exe: не запущен")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# settings toggles (mirrors :game_switch / :ipset_switch / :check_updates_switch)
# --------------------------------------------------------------------------- #

def game_filter_status(version_dir: Path) -> str:
    f = version_dir / "utils" / "game_filter.enabled"
    if not f.exists():
        return "disabled"
    content = f.read_text(encoding="utf-8", errors="ignore").strip().lower()
    return content if content in ("all", "tcp", "udp") else "disabled"


def set_game_filter(version_dir: Path, mode: str):
    f = version_dir / "utils" / "game_filter.enabled"
    if mode == "disabled":
        if f.exists():
            f.unlink()
        return
    f.parent.mkdir(exist_ok=True)
    f.write_text(mode + "\n", encoding="utf-8")


def check_updates_enabled(version_dir: Path) -> bool:
    return (version_dir / "utils" / "check_updates.enabled").exists()


def set_check_updates_enabled(version_dir: Path, enabled: bool):
    f = version_dir / "utils" / "check_updates.enabled"
    if enabled:
        f.parent.mkdir(exist_ok=True)
        f.write_text("ENABLED\n", encoding="utf-8")
    elif f.exists():
        f.unlink()


def ipset_status(version_dir: Path) -> str:
    f = version_dir / "lists" / "ipset-all.txt"
    if not f.exists():
        return "any"
    text = f.read_text(encoding="utf-8", errors="ignore")
    if len(text.splitlines()) == 0:
        return "any"
    return "none" if "203.0.113.113/32" in text else "loaded"


def cycle_ipset(version_dir: Path) -> str:
    """Advance loaded -> none -> any -> loaded, exactly like service.bat's toggle."""
    list_file = version_dir / "lists" / "ipset-all.txt"
    backup_file = version_dir / "lists" / "ipset-all.txt.backup"
    status = ipset_status(version_dir)
    list_file.parent.mkdir(exist_ok=True)

    if status == "loaded":
        if backup_file.exists():
            backup_file.unlink()
        list_file.rename(backup_file)
        list_file.write_text("203.0.113.113/32\n", encoding="utf-8")
    elif status == "none":
        list_file.write_text("", encoding="utf-8")
    else:  # any
        if not backup_file.exists():
            raise RuntimeError("Нет резервной копии для восстановления. Сначала обновите список IPSet.")
        if list_file.exists():
            list_file.unlink()
        backup_file.rename(list_file)

    return ipset_status(version_dir)


# --------------------------------------------------------------------------- #
# updates
# --------------------------------------------------------------------------- #

def update_ipset_list(version_dir: Path) -> str:
    list_file = version_dir / "lists" / "ipset-all.txt"
    list_file.parent.mkdir(exist_ok=True)
    tmp = list_file.with_suffix(".tmp")
    res = subprocess.run(
        ["curl.exe", "-L", "-s", "-o", str(tmp), IPSET_URL],
        capture_output=True, timeout=30, text=True,
    )
    if res.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        raise RuntimeError("Не удалось скачать список IPSet.")
    tmp.replace(list_file)
    return f"ipset-all.txt обновлён ({list_file.stat().st_size} байт)."


def check_hosts_file() -> str:
    hosts_path = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
    tmp = Path(os.environ.get("TEMP", ".")) / "zapret_hosts.txt"
    res = subprocess.run(
        ["curl.exe", "-L", "-s", "-o", str(tmp), HOSTS_URL],
        capture_output=True, timeout=20, text=True,
    )
    if res.returncode != 0 or not tmp.exists():
        raise RuntimeError("Не удалось скачать эталонный hosts-файл.")

    lines = [l for l in tmp.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
    if not lines:
        raise RuntimeError("Скачанный hosts-файл пуст.")
    first, last = lines[0], lines[-1]
    current = hosts_path.read_text(encoding="utf-8", errors="ignore") if hosts_path.exists() else ""

    if first not in current or last not in current:
        subprocess.Popen(["notepad.exe", str(tmp)])
        subprocess.Popen(["explorer.exe", f"/select,{hosts_path}"])
        return "Файл hosts нужно обновить. Открыт Notepad со скачанным файлом и проводник — скопируйте содержимое вручную."

    tmp.unlink(missing_ok=True)
    return "Файл hosts в актуальном состоянии."


def local_version(version_dir: Path) -> str:
    sb = version_dir / "service.bat"
    if sb.exists():
        m = re.search(r'LOCAL_VERSION=([^\s"]+)', sb.read_text(encoding="utf-8", errors="ignore"))
        if m:
            return m.group(1)
    m = re.search(r"[\d.]+[a-z]?$", version_dir.name)
    return m.group(0) if m else version_dir.name


def check_for_updates(version_dir: Path) -> dict:
    res = subprocess.run(
        ["curl.exe", "-s", "-L", GITHUB_VERSION_URL],
        capture_output=True, timeout=15, text=True,
    )
    latest = res.stdout.strip()
    if res.returncode != 0 or not latest:
        raise RuntimeError("Не удалось получить версию с GitHub.")
    local = local_version(version_dir)
    return {
        "local": local,
        "latest": latest,
        "up_to_date": local == latest,
        "release_url": GITHUB_RELEASE_URL + latest,
        "download_url": GITHUB_DOWNLOAD_URL,
    }


# --------------------------------------------------------------------------- #
# diagnostics (mirrors :service_diagnostics)
# --------------------------------------------------------------------------- #

def run_diagnostics(version_dir: Path):
    """Returns (results, found_conflicting_services) where results is a list
    of {"name", "level" ("ok"/"warn"/"error"), "message"} dicts."""
    results = []

    def add(name, level, msg, services=None):
        entry = {"name": name, "level": level, "message": msg}
        if services:
            entry["services"] = services
        results.append(entry)

    bfe = _service_state("BFE")
    add("Base Filtering Engine", "ok" if bfe == "RUNNING" else "error",
        "запущен" if bfe == "RUNNING" else "НЕ запущен — обязателен для работы zapret")

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
        if enabled:
            try:
                server, _ = winreg.QueryValueEx(key, "ProxyServer")
            except FileNotFoundError:
                server = "?"
            add("Системный прокси", "warn", f"включён: {server}. Проверьте, что он рабочий, либо отключите")
        else:
            add("Системный прокси", "ok", "отключён")
        winreg.CloseKey(key)
    except OSError:
        add("Системный прокси", "ok", "не настроен")

    out = subprocess.run(
        ["netsh", "interface", "tcp", "show", "global"], capture_output=True, text=True, timeout=10
    ).stdout
    ts_line = next((l for l in out.splitlines() if "timestamp" in l.lower()), "")
    if "enabled" in ts_line.lower():
        add("TCP timestamps", "ok", "включены")
    else:
        subprocess.run(
            ["netsh", "interface", "tcp", "set", "global", "timestamps=enabled"],
            capture_output=True, timeout=10,
        )
        add("TCP timestamps", "warn", "были выключены — включены автоматически")

    tl = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq AdguardSvc.exe"], capture_output=True, text=True, timeout=10
    ).stdout
    if "adguardsvc.exe" in tl.lower():
        add("AdGuard", "error", "процесс AdguardSvc.exe найден — может конфликтовать с Discord")
    else:
        add("AdGuard", "ok", "не найден")

    services_text = _query_all_active_services()

    add("Killer", "error" if _lines_containing_all(services_text, "Killer") else "ok",
        "службы Killer найдены — конфликтуют с zapret" if _lines_containing_all(services_text, "Killer") else "не найдено")

    intel_hit = _lines_containing_all(services_text, "Intel", "Connectivity", "Network")
    add("Intel Connectivity", "error" if intel_hit else "ok",
        "служба найдена — конфликтует с zapret" if intel_hit else "не найдено")

    checkpoint_found = bool(_lines_containing_all(services_text, "TracSrvWrapper")) or \
        bool(_lines_containing_all(services_text, "EPWD"))
    add("Check Point", "error" if checkpoint_found else "ok",
        "найдено — конфликтует с zapret" if checkpoint_found else "не найдено")

    add("SmartByte", "error" if _lines_containing_all(services_text, "SmartByte") else "ok",
        "найдено — конфликтует с zapret" if _lines_containing_all(services_text, "SmartByte") else "не найдено")

    sys_files = list((version_dir / "bin").glob("*.sys"))
    add("WinDivert64.sys", "ok" if sys_files else "error",
        "найден" if sys_files else "файл не найден в bin/")

    vpn_records = [r for r in _parse_sc_records(services_text)
                   if "vpn" in r["display_name"].lower() or "vpn" in r["name"].lower()]
    if vpn_records:
        labels = ", ".join(r["display_name"] or r["name"] for r in vpn_records)
        add("VPN", "warn", f"найдены службы VPN: {labels}. Могут конфликтовать с zapret",
            services=[{"name": r["name"], "display_name": r["display_name"] or r["name"]} for r in vpn_records])
    else:
        add("VPN", "ok", "не найдено")

    ps = ("(Get-ChildItem -Recurse -Path 'HKLM:System\\CurrentControlSet\\Services\\Dnscache\\"
          "InterfaceSpecificParameters\\' | Get-ItemProperty | "
          "Where-Object { $_.DohFlags -gt 0 } | Measure-Object).Count")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=15)
    try:
        doh_count = int((r.stdout or "0").strip() or "0")
    except ValueError:
        doh_count = 0
    add("Secure DNS (DoH)", "ok" if doh_count > 0 else "warn",
        "настроен хотя бы на одном интерфейсе" if doh_count > 0
        else "не настроен — рекомендуется включить DNS через HTTPS в браузере или Windows 11")

    hosts_path = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
    if hosts_path.exists():
        h = hosts_path.read_text(encoding="utf-8", errors="ignore").lower()
        yt_found = "youtube.com" in h or "youtu.be" in h
        add("Hosts file", "warn" if yt_found else "ok",
            "содержит записи youtube.com/youtu.be — может мешать доступу к YouTube" if yt_found
            else "не содержит подозрительных записей YouTube")

    windivert_state = _service_state("WinDivert")
    winws_conflict = (not _winws_running()) and windivert_state in ("RUNNING", "STOP_PENDING")
    add("WinDivert конфликт", "warn" if winws_conflict else "ok",
        "winws не запущен, но служба WinDivert активна — возможен конфликт с другим bypass-инструментом"
        if winws_conflict else "не обнаружено")

    found_conflicts = [n for n in CONFLICTING_BYPASS_SERVICES if _service_state(n) is not None]
    add("Конфликтующие bypass-службы", "error" if found_conflicts else "ok",
        f"найдены: {', '.join(found_conflicts)}" if found_conflicts else "не найдено")

    return results, found_conflicts, winws_conflict


def fix_windivert_conflict() -> str:
    """Stop and remove an orphaned WinDivert driver service (winws.exe not
    running but the driver still registered/active) — mirrors what
    service.bat's diagnostics attempts automatically in this situation."""
    lines = []
    for name in ("WinDivert", "WinDivert14"):
        state = _service_state(name)
        if state is None:
            lines.append(f"{name}: не установлена")
            continue
        subprocess.run(["net", "stop", name], capture_output=True, timeout=15)
        res = subprocess.run(["sc", "delete", name], capture_output=True, text=True, timeout=15)
        lines.append(f"{name}: удалена" if res.returncode == 0 else f"{name}: не удалось удалить")
    return "\n".join(lines)


def remove_conflicting_services(names) -> str:
    lines = []
    for n in names:
        subprocess.run(["net", "stop", n], capture_output=True, timeout=15)
        subprocess.run(["sc", "delete", n], capture_output=True, timeout=15)
        lines.append(f"{n}: остановлена и удалена (если существовала)")
    subprocess.run(["net", "stop", "WinDivert"], capture_output=True, timeout=15)
    subprocess.run(["sc", "delete", "WinDivert"], capture_output=True, timeout=15)
    return "\n".join(lines)


def clear_discord_cache() -> str:
    subprocess.run(["taskkill", "/IM", "Discord.exe", "/F"], capture_output=True, timeout=10)
    base = Path(os.environ.get("APPDATA", "")) / "discord"
    removed = []
    for sub in ("Cache", "Code Cache", "GPUCache"):
        p = base / sub
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
            removed.append(sub)
    return f"Discord закрыт. Удалены папки: {', '.join(removed) if removed else 'не найдены'}"
