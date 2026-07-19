#!/usr/bin/env python3
"""
Alternative-engine support for zapret2 (nfqws2/winws2, bol-van/zapret2).

This is opt-in and fully separate from the default zapret1 (winws.exe)
flow the rest of the panel drives — nothing here is imported by or wired
into that path. A "zapret2 install" is any folder that either is, or
contains a `zapret-winws` subfolder that is, the layout shipped by the
official bol-van/zapret-win-bundle: winws2.exe plus its lua/files/
windivert.filter siblings and a set of preset*.cmd launchers.

Discovery mirrors zapret_tester's whole-computer version scan: rather than
pointing at one folder by hand, every fixed drive gets walked for
directories that look like a zapret2 install, so multiple downloaded
copies/versions all show up as pickable "versions", the same way zapret1
release folders do.
"""

import json
import os
import subprocess
import time
from pathlib import Path

import zapret_tester as zt  # reuse BASE_DIR, natural_key, TARGETS, check_target, scan helpers

# .cmd files that ship alongside winws2.exe in the official bundle but
# don't launch it (service install/remove, admin console, driver cleanup).
# Profiles are still identified by content (must mention winws2.exe), this
# is just a fast-path skip so those never even get opened.
_EXCLUDE_CMD_NAMES = {
    "_cmd_admin.cmd", "enable_timestamps.cmd", "windivert_delete.cmd",
    "service_create.cmd", "service_del.cmd", "service_start.cmd", "service_stop.cmd",
    "service1_create.cmd", "service2_create.cmd",
}


def find_engine_dir(folder) -> Path | None:
    """A folder counts as a zapret2 install if it (or its immediate
    'zapret-winws' subfolder, matching the official win-bundle layout)
    contains winws2.exe directly."""
    if not folder:
        return None
    folder = Path(folder)
    if not folder.exists():
        return None
    if (folder / "winws2.exe").exists():
        return folder
    nested = folder / "zapret-winws"
    if (nested / "winws2.exe").exists():
        return nested
    return None


def find_profiles(engine_dir: Path):
    """*.cmd launchers that actually start winws2.exe (the preset*.cmd
    convention from bol-van/zapret-win-bundle), matched by content rather
    than name so a user's own added scripts are picked up too."""
    profiles = []
    for f in sorted(engine_dir.glob("*.cmd")):
        if f.name.lower() in _EXCLUDE_CMD_NAMES:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        if "winws2.exe" in text:
            profiles.append(f)
    profiles.sort(key=lambda p: zt.natural_key(p.name))
    return profiles


# --------------------------------------------------------------------------- #
# Whole-computer scan for zapret2 installs. Unlike zapret1's release
# folders (always named "zapret-discord-youtube-X.Y.Z"), zapret2 has no
# reliable naming convention — a raw GitHub release zip puts winws2.exe
# under a "windows-x86_64" subfolder that doesn't mention zapret/winws at
# all — so every directory is tested directly via find_engine_dir instead
# of pre-filtering by name. Same skip list and depth cap as zapret1's scan.
# --------------------------------------------------------------------------- #

# Folder names that identify an architecture/bin layout detail rather than
# an actual release — not useful on their own as a "version" label.
_GENERIC_LEAF_NAMES = {
    "windows-x86", "windows-x86_64", "win32", "win64", "x86", "x64",
    "amd64", "arm64", "bin", "binaries", "zapret-winws",
}


def _display_name(directory: Path) -> str:
    """Human label for a discovered install. A raw GitHub release zip
    puts the actual version in the folder *above* the architecture one
    ('zapret2-v1.0.2/binaries/windows-x86_64') — so if the matched folder
    itself is just an architecture/bin tag, climb up for the nearest
    ancestor that actually mentions zapret and use that, with the
    original leaf kept in parentheses so windows-x86 and windows-x86_64
    from the same release still show up as two distinct entries."""
    leaf = directory.name
    if leaf.lower() not in _GENERIC_LEAF_NAMES:
        return leaf
    parent = directory.parent
    for _ in range(4):
        if parent is None or parent == parent.parent:
            break
        parent_lower = parent.name.lower()
        if "zapret" in parent_lower and parent_lower not in _GENERIC_LEAF_NAMES:
            return f"{parent.name} ({leaf})"
        parent = parent.parent
    return leaf


def _scan_dir_for_zapret2(directory: Path, found: dict, depth: int = 0):
    if depth > zt._MAX_SCAN_DEPTH:
        return
    engine_dir = find_engine_dir(directory)
    if engine_dir:
        found.setdefault(_display_name(directory), engine_dir)
        return  # a matched install's own contents aren't candidates
    try:
        entries = list(os.scandir(directory))
    except OSError:
        return
    for entry in entries:
        try:
            if not entry.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        name_lower = entry.name.lower()
        if name_lower.startswith("$") or name_lower in zt._SKIP_SCAN_DIR_NAMES:
            continue
        _scan_dir_for_zapret2(Path(entry.path), found, depth + 1)


def find_versions_global() -> dict:
    """name -> engine_dir Path for every zapret2 install found: the app's
    own folder (always, with priority on name clashes, regardless of
    depth — same rationale as zapret1's own scan) plus every fixed drive."""
    found = {}
    _scan_dir_for_zapret2(zt._APP_DIR, found)
    for drive in zt.list_fixed_drives():
        _scan_dir_for_zapret2(drive, found)
    return found


# --------------------------------------------------------------------------- #
# winws2 process control
# --------------------------------------------------------------------------- #

def kill_winws2():
    subprocess.run(
        ["taskkill", "/IM", "winws2.exe", "/F", "/T"],
        capture_output=True, timeout=10,
    )


def winws2_running() -> bool:
    res = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq winws2.exe"],
        capture_output=True, timeout=10, text=True,
    )
    return "winws2.exe" in res.stdout.lower()


def _ensure_windivert_free():
    """The WinDivert kernel driver stays loaded (bound to whichever .sys
    file first started it) even after the process that started it exits —
    confirmed by hand: after a zapret1 session, the driver can still be
    RUNNING against zapret-discord-youtube's own WinDivert64.sys, and
    Windows won't let a winws2.exe from a different folder rebind it to
    its own copy, so winws2 silently fails to intercept anything. Only
    safe to force this when zapret1 isn't actually using it right now."""
    try:
        if zt.winws_running():
            return
        subprocess.run(
            ["sc.exe", "stop", "WinDivert"],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass


def snapshot_winws2():
    """Mirrors zapret_tester.snapshot_winws for winws2.exe — used by the
    generator so a search run can restore whatever the user had running
    (if anything) once it's done, instead of just leaving it stopped."""
    ps_cmd = (
        "Get-CimInstance Win32_Process -Filter \"Name='winws2.exe'\" "
        "| Select-Object CommandLine,ExecutablePath | ConvertTo-Json -Compress"
    )
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, timeout=10, text=True,
        )
        out = res.stdout.strip()
        if not out:
            return []
        data = json.loads(out)
        if isinstance(data, dict):
            data = [data]
        return data
    except Exception:
        return []


def restore_winws2(snapshot):
    if not snapshot:
        return
    for p in snapshot:
        exe = p.get("ExecutablePath")
        cmdline = p.get("CommandLine") or ""
        if not exe:
            continue
        args = cmdline
        quoted = f'"{exe}"'
        if args.startswith(quoted):
            args = args[len(quoted):].strip()
        elif args.startswith(exe):
            args = args[len(exe):].strip()
        try:
            subprocess.Popen(
                f'"{exe}" {args}',
                cwd=str(Path(exe).parent),
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            pass


def launch_profile(cmd_path: Path, engine_dir: Path):
    """Stop any running winws2 and start this profile's cmd in the
    foreground. Mirrors zapret_tester.launch_strategy for winws.exe."""
    kill_winws2()
    _ensure_windivert_free()
    time.sleep(1)
    subprocess.Popen(
        ["cmd", "/c", str(cmd_path)],
        cwd=str(engine_dir),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
