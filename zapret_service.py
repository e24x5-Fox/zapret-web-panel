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

import json
import os
import re
import shutil
import subprocess
import sys
import time
import winreg
from pathlib import Path

from i18n import t


def _app_dir() -> Path:
    """Folder the app 'lives in': next to the running .exe when packaged,
    or this script's own folder when running from source. Mirrors
    zapret_tester._app_dir() — kept local so this module stays a
    self-contained reimplementation of service.bat."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


_APP_DIR = _app_dir()

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


def stop_services(names, lang="ru") -> str:
    lines = []
    for n in names:
        res = subprocess.run(["net", "stop", n], capture_output=True, text=True, timeout=20)
        ok = res.returncode == 0
        lines.append(f"{n}: {t(lang, 'svc_stopped' if ok else 'svc_stop_failed')}")
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

def _extract_winws_command(bat_path: Path, version_dir: Path, lang="ru") -> str:
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
        raise RuntimeError(t(lang, "winws_didnt_start", bat_name=bat_path.name))
    return cmdline


def install_service(version_dir: Path, bat_name: str, lang="ru") -> str:
    bat_path = version_dir / bat_name
    if not bat_path.exists():
        raise ValueError(t(lang, "install_bat_not_found", bat_name=bat_name, version_dir=version_dir))

    cmdline = _extract_winws_command(bat_path, version_dir, lang=lang)
    m = re.match(r'^"([^"]+)"\s*(.*)$', cmdline)
    if not m:
        raise RuntimeError(t(lang, "cmdline_parse_failed", cmdline=cmdline))
    exe_path, args = m.group(1), m.group(2)

    subprocess.run(["net", "stop", "zapret"], capture_output=True, timeout=15)
    subprocess.run(["sc", "delete", "zapret"], capture_output=True, timeout=15)

    binpath = f'"{exe_path}" {args}'
    res = subprocess.run(
        ["sc", "create", "zapret", "binPath=", binpath, "DisplayName=", "zapret", "start=", "auto"],
        capture_output=True, text=True, timeout=20,
    )
    if res.returncode != 0:
        raise RuntimeError(t(lang, "sc_create_failed", stdout=res.stdout, stderr=res.stderr))

    subprocess.run(["sc", "description", "zapret", "Zapret DPI bypass software"], capture_output=True, timeout=10)
    start_res = subprocess.run(["sc", "start", "zapret"], capture_output=True, text=True, timeout=20)

    try:
        key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, r"System\CurrentControlSet\Services\zapret")
        winreg.SetValueEx(key, "zapret-discord-youtube", 0, winreg.REG_SZ, bat_path.stem)
        winreg.CloseKey(key)
    except OSError:
        pass

    extra = f"{start_res.stdout}{start_res.stderr}".strip()
    return t(lang, "service_installed_detail", bat_name=bat_name, extra=extra).strip()


def remove_service(lang="ru") -> str:
    lines = []
    if _service_state("zapret") is not None:
        subprocess.run(["net", "stop", "zapret"], capture_output=True, timeout=15)
        subprocess.run(["sc", "delete", "zapret"], capture_output=True, timeout=15)
        lines.append(t(lang, "service_stopped_removed"))
    else:
        lines.append(t(lang, "service_not_installed"))

    if _winws_running():
        subprocess.run(["taskkill", "/IM", "winws.exe", "/F", "/T"], capture_output=True, timeout=10)
        lines.append(t(lang, "winws_process_stopped"))

    if _service_state("WinDivert") is not None:
        subprocess.run(["net", "stop", "WinDivert"], capture_output=True, timeout=15)
        subprocess.run(["sc", "delete", "WinDivert"], capture_output=True, timeout=15)
        lines.append(t(lang, "windivert_removed"))

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


def service_status(version_dir: Path, lang="ru") -> str:
    lines = []
    zapret_state = _service_state("zapret")
    lines.append(t(lang, "status_zapret_line", state=zapret_state or t(lang, "status_not_installed")))
    if zapret_state:
        strat = installed_strategy_name()
        if strat:
            lines.append(t(lang, "status_installed_strategy", strategy=strat))

    windivert_state = _service_state("WinDivert")
    lines.append(t(lang, "status_windivert_line", state=windivert_state or t(lang, "status_not_installed")))

    sys_files = list((version_dir / "bin").glob("*.sys"))
    lines.append(t(lang, "status_sys_found" if sys_files else "status_sys_not_found"))

    lines.append(t(lang, "status_winws_running" if _winws_running() else "status_winws_stopped"))
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


# Panel-level preference, stored next to the app itself rather than inside
# any single zapret version's folder — so it survives switching between
# versions or installing a new one, instead of resetting to "off" every
# time (each version folder used to carry its own independent marker file).
CHECK_UPDATES_PREF_FILE = _APP_DIR / "check_updates_pref.json"


def load_check_updates_pref():
    """Returns the saved global preference, or None if nothing was saved yet."""
    if CHECK_UPDATES_PREF_FILE.exists():
        try:
            data = json.loads(CHECK_UPDATES_PREF_FILE.read_text(encoding="utf-8"))
            return bool(data["enabled"])
        except Exception:
            pass
    return None


def save_check_updates_pref(enabled: bool):
    CHECK_UPDATES_PREF_FILE.write_text(
        json.dumps({"enabled": enabled}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def check_updates_enabled(version_dir: Path) -> bool:
    """Per-version marker state, kept in sync with the global preference:
    if a preference is already saved, the version's own marker file is
    brought in line with it (fixing up any version that doesn't match yet
    — e.g. one just installed, or one that was toggled before this synced
    behavior existed). The first time this runs with no preference saved,
    the version's current marker state seeds the global preference."""
    current = (version_dir / "utils" / "check_updates.enabled").exists()
    pref = load_check_updates_pref()
    if pref is None:
        save_check_updates_pref(current)
        return current
    if pref != current:
        _write_check_updates_marker(version_dir, pref)
    return pref


def set_check_updates_enabled(version_dir: Path, enabled: bool):
    _write_check_updates_marker(version_dir, enabled)
    save_check_updates_pref(enabled)


def _write_check_updates_marker(version_dir: Path, enabled: bool):
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


def cycle_ipset(version_dir: Path, lang="ru") -> str:
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
            raise RuntimeError(t(lang, "ipset_no_backup"))
        if list_file.exists():
            list_file.unlink()
        backup_file.rename(list_file)

    return ipset_status(version_dir)


# --------------------------------------------------------------------------- #
# updates
# --------------------------------------------------------------------------- #

def update_ipset_list(version_dir: Path, lang="ru") -> str:
    list_file = version_dir / "lists" / "ipset-all.txt"
    list_file.parent.mkdir(exist_ok=True)
    tmp = list_file.with_suffix(".tmp")
    res = subprocess.run(
        ["curl.exe", "-L", "-s", "-o", str(tmp), IPSET_URL],
        capture_output=True, timeout=30, text=True,
    )
    if res.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        raise RuntimeError(t(lang, "ipset_download_failed"))
    tmp.replace(list_file)
    return t(lang, "ipset_updated", size=list_file.stat().st_size)


# --------------------------------------------------------------------------- #
# user domain/IP lists (list-general-user.txt, list-exclude-user.txt,
# ipset-exclude-user.txt) — every general*.bat strategy in a version reads
# these the same way (--hostlist/--hostlist-exclude/--ipset-exclude), so
# editing them here affects every strategy of that version uniformly.
# service.bat only ever scaffolds these with a placeholder on first run
# (see its own menu init) — there's no console-menu way to edit them, you're
# expected to open the .txt files by hand. This is that editor.
# --------------------------------------------------------------------------- #

USER_LISTS = {
    "general": ("list-general-user.txt", "# Never leave this file empty\ndomain.example.abc\n"),
    "exclude": ("list-exclude-user.txt", "domain.example.abc\n"),
    "ipset_exclude": ("ipset-exclude-user.txt", "203.0.113.113/32\n"),
}


def _user_list_path(version_dir: Path, key: str) -> Path:
    filename, _ = USER_LISTS[key]
    return version_dir / "lists" / filename


def read_user_lists(version_dir: Path) -> dict:
    out = {}
    for key, (_, default) in USER_LISTS.items():
        f = _user_list_path(version_dir, key)
        if not f.exists():
            f.parent.mkdir(exist_ok=True)
            f.write_text(default, encoding="utf-8")
        out[key] = f.read_text(encoding="utf-8", errors="ignore")
    return out


def write_user_list(version_dir: Path, key: str, content: str, lang="ru"):
    if key not in USER_LISTS:
        raise ValueError(t(lang, "err_bad_list_name"))
    f = _user_list_path(version_dir, key)
    f.parent.mkdir(exist_ok=True)
    if not content.endswith("\n"):
        content += "\n"
    f.write_text(content, encoding="utf-8")


def check_hosts_file(lang="ru") -> str:
    hosts_path = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
    tmp = Path(os.environ.get("TEMP", ".")) / "zapret_hosts.txt"
    res = subprocess.run(
        ["curl.exe", "-L", "-s", "-o", str(tmp), HOSTS_URL],
        capture_output=True, timeout=20, text=True,
    )
    if res.returncode != 0 or not tmp.exists():
        raise RuntimeError(t(lang, "hosts_download_failed"))

    lines = [l for l in tmp.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
    if not lines:
        raise RuntimeError(t(lang, "hosts_empty"))
    first, last = lines[0], lines[-1]
    current = hosts_path.read_text(encoding="utf-8", errors="ignore") if hosts_path.exists() else ""

    if first not in current or last not in current:
        subprocess.Popen(["notepad.exe", str(tmp)])
        subprocess.Popen(["explorer.exe", f"/select,{hosts_path}"])
        return t(lang, "hosts_needs_update")

    tmp.unlink(missing_ok=True)
    return t(lang, "hosts_up_to_date")


def local_version(version_dir: Path) -> str:
    sb = version_dir / "service.bat"
    if sb.exists():
        m = re.search(r'LOCAL_VERSION=([^\s"]+)', sb.read_text(encoding="utf-8", errors="ignore"))
        if m:
            return m.group(1)
    m = re.search(r"[\d.]+[a-z]?$", version_dir.name)
    return m.group(0) if m else version_dir.name


def check_for_updates(version_dir: Path, lang="ru") -> dict:
    res = subprocess.run(
        ["curl.exe", "-s", "-L", GITHUB_VERSION_URL],
        capture_output=True, timeout=15, text=True,
    )
    latest = res.stdout.strip()
    if res.returncode != 0 or not latest:
        raise RuntimeError(t(lang, "version_fetch_failed"))
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

def run_diagnostics(version_dir: Path, lang="ru"):
    """Returns (results, found_conflicting_services, windivert_conflict) where
    results is a list of {"name", "level" ("ok"/"warn"/"error"), "message"} dicts."""
    results = []

    def add(name_key, level, msg, services=None):
        entry = {"name": t(lang, name_key), "level": level, "message": msg}
        if services:
            entry["services"] = services
        results.append(entry)

    bfe = _service_state("BFE")
    add("name_bfe", "ok" if bfe == "RUNNING" else "error",
        t(lang, "bfe_ok") if bfe == "RUNNING" else t(lang, "bfe_error"))

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
        if enabled:
            try:
                server, _ = winreg.QueryValueEx(key, "ProxyServer")
            except FileNotFoundError:
                server = "?"
            add("name_proxy", "warn", t(lang, "proxy_warn", server=server))
        else:
            add("name_proxy", "ok", t(lang, "proxy_ok"))
        winreg.CloseKey(key)
    except OSError:
        add("name_proxy", "ok", t(lang, "proxy_not_configured"))

    out = subprocess.run(
        ["netsh", "interface", "tcp", "show", "global"], capture_output=True, text=True, timeout=10
    ).stdout
    ts_line = next((l for l in out.splitlines() if "timestamp" in l.lower()), "")
    if "enabled" in ts_line.lower():
        add("name_tcp_timestamps", "ok", t(lang, "ts_ok"))
    else:
        subprocess.run(
            ["netsh", "interface", "tcp", "set", "global", "timestamps=enabled"],
            capture_output=True, timeout=10,
        )
        add("name_tcp_timestamps", "warn", t(lang, "ts_warn"))

    tl = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq AdguardSvc.exe"], capture_output=True, text=True, timeout=10
    ).stdout
    if "adguardsvc.exe" in tl.lower():
        add("name_adguard", "error", t(lang, "adguard_error"))
    else:
        add("name_adguard", "ok", t(lang, "adguard_ok"))

    services_text = _query_all_active_services()

    add("name_killer", "error" if _lines_containing_all(services_text, "Killer") else "ok",
        t(lang, "killer_error") if _lines_containing_all(services_text, "Killer") else t(lang, "not_found_generic"))

    intel_hit = _lines_containing_all(services_text, "Intel", "Connectivity", "Network")
    add("name_intel", "error" if intel_hit else "ok",
        t(lang, "intel_error") if intel_hit else t(lang, "not_found_generic"))

    checkpoint_found = bool(_lines_containing_all(services_text, "TracSrvWrapper")) or \
        bool(_lines_containing_all(services_text, "EPWD"))
    add("name_checkpoint", "error" if checkpoint_found else "ok",
        t(lang, "found_conflicts_generic") if checkpoint_found else t(lang, "not_found_generic"))

    add("name_smartbyte", "error" if _lines_containing_all(services_text, "SmartByte") else "ok",
        t(lang, "found_conflicts_generic") if _lines_containing_all(services_text, "SmartByte") else t(lang, "not_found_generic"))

    sys_files = list((version_dir / "bin").glob("*.sys"))
    add("name_windivert_sys", "ok" if sys_files else "error",
        t(lang, "sys_found") if sys_files else t(lang, "sys_missing"))

    vpn_records = [r for r in _parse_sc_records(services_text)
                   if "vpn" in r["display_name"].lower() or "vpn" in r["name"].lower()]
    if vpn_records:
        labels = ", ".join(r["display_name"] or r["name"] for r in vpn_records)
        add("name_vpn", "warn", t(lang, "vpn_found", labels=labels),
            services=[{"name": r["name"], "display_name": r["display_name"] or r["name"]} for r in vpn_records])
    else:
        add("name_vpn", "ok", t(lang, "not_found_generic"))

    ps = ("(Get-ChildItem -Recurse -Path 'HKLM:System\\CurrentControlSet\\Services\\Dnscache\\"
          "InterfaceSpecificParameters\\' | Get-ItemProperty | "
          "Where-Object { $_.DohFlags -gt 0 } | Measure-Object).Count")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=15)
    try:
        doh_count = int((r.stdout or "0").strip() or "0")
    except ValueError:
        doh_count = 0
    add("name_doh", "ok" if doh_count > 0 else "warn",
        t(lang, "doh_ok") if doh_count > 0 else t(lang, "doh_warn"))

    hosts_path = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
    if hosts_path.exists():
        h = hosts_path.read_text(encoding="utf-8", errors="ignore").lower()
        yt_found = "youtube.com" in h or "youtu.be" in h
        add("name_hosts_file", "warn" if yt_found else "ok",
            t(lang, "hosts_check_warn") if yt_found else t(lang, "hosts_check_ok"))

    windivert_state = _service_state("WinDivert")
    winws_conflict = (not _winws_running()) and windivert_state in ("RUNNING", "STOP_PENDING")
    add("name_windivert_conflict", "warn" if winws_conflict else "ok",
        t(lang, "windivert_conflict_warn") if winws_conflict else t(lang, "windivert_conflict_ok"))

    found_conflicts = [n for n in CONFLICTING_BYPASS_SERVICES if _service_state(n) is not None]
    add("name_conflicting_services", "error" if found_conflicts else "ok",
        t(lang, "conflicts_found", names=", ".join(found_conflicts)) if found_conflicts else t(lang, "not_found_generic"))

    return results, found_conflicts, winws_conflict


def fix_windivert_conflict(lang="ru") -> str:
    """Stop and remove an orphaned WinDivert driver service (winws.exe not
    running but the driver still registered/active) — mirrors what
    service.bat's diagnostics attempts automatically in this situation."""
    lines = []
    for name in ("WinDivert", "WinDivert14"):
        state = _service_state(name)
        if state is None:
            lines.append(t(lang, "windivert_not_installed", name=name))
            continue
        subprocess.run(["net", "stop", name], capture_output=True, timeout=15)
        res = subprocess.run(["sc", "delete", name], capture_output=True, text=True, timeout=15)
        lines.append(t(lang, "svc_removed_short" if res.returncode == 0 else "svc_remove_failed_short", name=name))
    return "\n".join(lines)


def remove_conflicting_services(names, lang="ru") -> str:
    lines = []
    for n in names:
        subprocess.run(["net", "stop", n], capture_output=True, timeout=15)
        subprocess.run(["sc", "delete", n], capture_output=True, timeout=15)
        lines.append(t(lang, "svc_stopped_removed_maybe", name=n))
    subprocess.run(["net", "stop", "WinDivert"], capture_output=True, timeout=15)
    subprocess.run(["sc", "delete", "WinDivert"], capture_output=True, timeout=15)
    return "\n".join(lines)


def clear_discord_cache(lang="ru") -> str:
    subprocess.run(["taskkill", "/IM", "Discord.exe", "/F"], capture_output=True, timeout=10)
    base = Path(os.environ.get("APPDATA", "")) / "discord"
    removed = []
    for sub in ("Cache", "Code Cache", "GPUCache"):
        p = base / sub
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
            removed.append(sub)
    folders = ", ".join(removed) if removed else t(lang, "discord_no_folders")
    return t(lang, "discord_cache_cleared", folders=folders)
