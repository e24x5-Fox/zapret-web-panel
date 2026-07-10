#!/usr/bin/env python3
"""
Zapret strategy tester.

Lets you pick one of the installed zapret-discord-youtube versions in this
folder, run its bypass strategies (general*.bat) one by one, and see which
strategy actually gets through to Discord / YouTube / Cloudflare.

Must be run as Administrator (winws.exe needs the WinDivert driver).
"""

import ctypes
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Folder to scan for zapret-discord-youtube-* releases. Defaults to this
# script's own folder (so it works if you drop it next to your existing
# versions, as before); set ZAPRET_BASE_DIR to point elsewhere if you keep
# this tool in its own separate folder/repo checkout.
BASE_DIR = Path(os.environ["ZAPRET_BASE_DIR"]) if os.environ.get("ZAPRET_BASE_DIR") \
    else Path(__file__).resolve().parent
RESULTS_DIR = Path(__file__).resolve().parent / "test_results"
TARGETS_FILE = Path(__file__).resolve().parent / "targets.json"

# Default service -> hosts catalog, written to targets.json on first run so
# it's user-editable (add/remove services or hosts) without touching code —
# this is what lets anyone pick their own set of services to test, not just
# the Discord/YouTube/Cloudflare set this tool started with.
_DEFAULT_TARGETS = {
    "Discord": [
        {"host": "discord.com", "kind": "http"},
        {"host": "gateway.discord.gg", "kind": "http"},
        {"host": "cdn.discordapp.com", "kind": "http"},
        {"host": "updates.discord.com", "kind": "http"},
    ],
    "YouTube": [
        {"host": "www.youtube.com", "kind": "http"},
        {"host": "youtu.be", "kind": "http"},
        {"host": "i.ytimg.com", "kind": "http"},
        {"host": "redirector.googlevideo.com", "kind": "http"},
    ],
    "Cloudflare": [
        {"host": "www.cloudflare.com", "kind": "http"},
        {"host": "cdnjs.cloudflare.com", "kind": "http"},
        {"host": "1.1.1.1", "kind": "tcp443"},
        {"host": "1.0.0.1", "kind": "tcp443"},
    ],
    "Telegram": [
        {"host": "telegram.org", "kind": "http"},
        {"host": "web.telegram.org", "kind": "http"},
        {"host": "core.telegram.org", "kind": "http"},
    ],
    "Twitter / X": [
        {"host": "x.com", "kind": "http"},
        {"host": "twitter.com", "kind": "http"},
        {"host": "abs.twimg.com", "kind": "http"},
    ],
    "Instagram": [
        {"host": "www.instagram.com", "kind": "http"},
        {"host": "scontent.cdninstagram.com", "kind": "http"},
    ],
    "Facebook": [
        {"host": "www.facebook.com", "kind": "http"},
        {"host": "static.xx.fbcdn.net", "kind": "http"},
    ],
    "TikTok": [
        {"host": "www.tiktok.com", "kind": "http"},
        {"host": "tiktok.com", "kind": "http"},
    ],
    "Steam": [
        {"host": "store.steampowered.com", "kind": "http"},
        {"host": "steamcommunity.com", "kind": "http"},
        {"host": "cdn.akamai.steamstatic.com", "kind": "http"},
    ],
    "Spotify": [
        {"host": "open.spotify.com", "kind": "http"},
        {"host": "api.spotify.com", "kind": "http"},
    ],
    "Twitch": [
        {"host": "www.twitch.tv", "kind": "http"},
        {"host": "static.twitchcdn.net", "kind": "http"},
    ],
    "Reddit": [
        {"host": "www.reddit.com", "kind": "http"},
    ],
}


def _to_tuples(catalog: dict) -> dict:
    return {name: [(h["host"], h["kind"]) for h in hosts] for name, hosts in catalog.items()}


def load_targets() -> dict:
    """Service -> [(host, kind), ...] catalog, loaded from targets.json
    (created with defaults on first run). kind is "http" or "tcp443"."""
    if not TARGETS_FILE.exists():
        TARGETS_FILE.write_text(
            json.dumps(_DEFAULT_TARGETS, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return _to_tuples(_DEFAULT_TARGETS)
    try:
        return _to_tuples(json.loads(TARGETS_FILE.read_text(encoding="utf-8")))
    except Exception:
        return _to_tuples(_DEFAULT_TARGETS)


TARGETS = load_targets()

CURL_TIMEOUT = 6
STRATEGY_WARMUP_SECONDS = 5


# --------------------------------------------------------------------------- #
# Admin / environment checks
# --------------------------------------------------------------------------- #

def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    print("Этот скрипт должен быть запущен от имени администратора")
    print("(winws.exe требует прав администратора для работы драйвера WinDivert).")
    answer = input("Перезапустить с правами администратора сейчас? [Y/n]: ").strip().lower()
    if answer not in ("", "y", "yes", "д", "да"):
        print("Отменено пользователем.")
        sys.exit(1)

    params = " ".join(f'"{a}"' for a in sys.argv)
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, str(BASE_DIR), 1)
    if rc <= 32:
        print("Не удалось запросить права администратора. Запустите вручную от админа.")
        sys.exit(1)
    sys.exit(0)


def check_curl() -> bool:
    try:
        subprocess.run(["curl.exe", "--version"], capture_output=True, timeout=5, check=False)
        return True
    except Exception:
        return False


def check_zapret_service_installed() -> bool:
    try:
        res = subprocess.run(["sc", "query", "zapret"], capture_output=True, timeout=5, text=True)
        return res.returncode == 0
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Discovering versions / strategies
# --------------------------------------------------------------------------- #

def natural_key(name: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def find_versions(base_dir: Path):
    versions = []
    for entry in sorted(base_dir.iterdir()):
        if not entry.is_dir():
            continue
        if (entry / "bin" / "winws.exe").exists():
            versions.append(entry)
    versions.sort(key=lambda p: natural_key(p.name))
    return versions


def find_strategies(version_dir: Path):
    bats = [
        f for f in version_dir.glob("*.bat")
        if not f.name.lower().startswith("service")
    ]
    bats.sort(key=lambda p: natural_key(p.name))
    return bats


# --------------------------------------------------------------------------- #
# winws process control
# --------------------------------------------------------------------------- #

def kill_winws():
    subprocess.run(
        ["taskkill", "/IM", "winws.exe", "/F", "/T"],
        capture_output=True, timeout=10,
    )


def snapshot_winws():
    ps_cmd = (
        "Get-CimInstance Win32_Process -Filter \"Name='winws.exe'\" "
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


def restore_winws(snapshot):
    if not snapshot:
        return
    print("Восстанавливаю ваш запущенный до теста winws...")
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


def run_strategy_bat(bat_path: Path, version_dir: Path):
    subprocess.Popen(
        ["cmd", "/c", str(bat_path)],
        cwd=str(version_dir),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def winws_running() -> bool:
    res = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq winws.exe"],
        capture_output=True, timeout=10, text=True,
    )
    return "winws.exe" in res.stdout.lower()


# --------------------------------------------------------------------------- #
# Connectivity checks
# --------------------------------------------------------------------------- #

def check_http(host: str, timeout=CURL_TIMEOUT):
    t0 = time.time()
    try:
        res = subprocess.run(
            ["curl.exe", "-I", "-s", "-m", str(timeout), "-o", "NUL",
             "-w", "%{http_code}", f"https://{host}"],
            capture_output=True, timeout=timeout + 3, text=True,
        )
        elapsed = time.time() - t0
        code = res.stdout.strip()
        ok = res.returncode == 0 and code.isdigit() and code != "000"
        return ok, code or "ERR", elapsed
    except Exception:
        return False, "ERR", time.time() - t0


def check_tcp443(host: str, timeout=CURL_TIMEOUT):
    t0 = time.time()
    try:
        with socket.create_connection((host, 443), timeout=timeout):
            return True, "OPEN", time.time() - t0
    except Exception:
        return False, "TIMEOUT", time.time() - t0


def check_target(host: str, kind: str):
    if kind == "tcp443":
        return check_tcp443(host)
    return check_http(host)


# --------------------------------------------------------------------------- #
# Interactive selection
# --------------------------------------------------------------------------- #

def pick_version(versions):
    print("\nНайденные версии zapret:")
    for i, v in enumerate(versions, 1):
        print(f"  [{i}] {v.name}")
    while True:
        choice = input("Выберите версию (номер): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(versions):
            return versions[int(choice) - 1]
        print("Некорректный ввод, попробуйте ещё раз.")


def pick_strategies(bats):
    print("\nДоступные стратегии:")
    for i, b in enumerate(bats, 1):
        print(f"  [{i}] {b.name}")
    print("Введите номера через запятую/диапазоны (напр. 1,3,5-8) или 0 для всех.")
    while True:
        choice = input("Выбор: ").strip()
        if choice == "0" or choice == "":
            return bats
        parts = re.split(r"[,\s]+", choice)
        indices = set()
        valid = True
        for part in parts:
            m = re.match(r"^(\d+)-(\d+)$", part)
            if m:
                a, b_ = int(m.group(1)), int(m.group(2))
                indices.update(range(a, b_ + 1))
            elif part.isdigit():
                indices.add(int(part))
            elif part:
                valid = False
        indices = {i for i in indices if 1 <= i <= len(bats)}
        if not valid or not indices:
            print("Некорректный ввод, попробуйте ещё раз.")
            continue
        return [bats[i - 1] for i in sorted(indices)]


def pick_services(catalog):
    names = list(catalog.keys())
    print("\nДоступные сервисы:")
    for i, name in enumerate(names, 1):
        hosts = ", ".join(h for h, _ in catalog[name][:2])
        print(f"  [{i}] {name} ({hosts}{', ...' if len(catalog[name]) > 2 else ''})")
    print("Введите номера через запятую/диапазоны (напр. 1,3) или 0 для всех.")
    while True:
        choice = input("Выбор: ").strip()
        if choice == "0" or choice == "":
            return catalog
        parts = re.split(r"[,\s]+", choice)
        indices = set()
        valid = True
        for part in parts:
            m = re.match(r"^(\d+)-(\d+)$", part)
            if m:
                indices.update(range(int(m.group(1)), int(m.group(2)) + 1))
            elif part.isdigit():
                indices.add(int(part))
            elif part:
                valid = False
        indices = {i for i in indices if 1 <= i <= len(names)}
        if not valid or not indices:
            print("Некорректный ввод, попробуйте ещё раз.")
            continue
        return {names[i - 1]: catalog[names[i - 1]] for i in sorted(indices)}


# --------------------------------------------------------------------------- #
# Main test loop
# --------------------------------------------------------------------------- #

def launch_strategy(bat_path: Path, version_dir: Path):
    """Stop any running winws and start this strategy's bat in the foreground."""
    kill_winws()
    time.sleep(1)
    run_strategy_bat(bat_path, version_dir)


def test_one_strategy(bat_path: Path, version_dir: Path, targets=None, log=lambda msg: None):
    targets = TARGETS if targets is None else targets
    launch_strategy(bat_path, version_dir)

    waited = 0.0
    while waited < STRATEGY_WARMUP_SECONDS + 5:
        if winws_running():
            break
        time.sleep(0.5)
        waited += 0.5
    time.sleep(STRATEGY_WARMUP_SECONDS)

    if not winws_running():
        log("    [WARN] winws.exe не запустился для этой стратегии — пропуск.")
        return None

    service_results = {}
    for service, hosts in targets.items():
        hits = 0
        detail = []
        for host, kind in hosts:
            ok, info, elapsed = check_target(host, kind)
            detail.append((host, ok, info, elapsed))
            if ok:
                hits += 1
        service_results[service] = {
            "score": hits,
            "total": len(hosts),
            "detail": detail,
        }

    kill_winws()
    return service_results


def run_tests(version_dir: Path, bats, targets=None, log=print, should_stop=lambda: False):
    """Run every bat in `bats` against `targets` (a {service: [(host, kind)]}
    subset of TARGETS, or all of TARGETS if omitted), restoring the user's
    prior winws state afterwards. Returns {bat_name: service_results}."""
    original_snapshot = snapshot_winws()
    all_results = {}
    try:
        for i, bat in enumerate(bats, 1):
            if should_stop():
                log("Остановлено пользователем.")
                break
            log(f"[{i}/{len(bats)}] {bat.name}")
            res = test_one_strategy(bat, version_dir, targets=targets, log=log)
            if res is None:
                continue
            all_results[bat.name] = res
            for service, data in res.items():
                log(f"    {service:<10} {data['score']}/{data['total']}")
    finally:
        kill_winws()
        restore_winws(original_snapshot)
    return all_results


def summarize(all_results):
    """Return (best_per_service, overall_best) from run_tests() output.
    Derives the tested service names from the results themselves, so it
    works with whatever subset of TARGETS was actually tested."""
    if not all_results:
        return {}, None

    services = {svc for res in all_results.values() for svc in res}
    best_per_service = {}
    for service in services:
        candidates = {k: v for k, v in all_results.items() if service in v}
        if not candidates:
            continue
        best_per_service[service] = max(
            candidates.items(), key=lambda kv: kv[1][service]["score"]
        )

    def overall_score(res):
        return sum(d["score"] for d in res.values())

    overall_best = max(all_results.items(), key=lambda kv: overall_score(kv[1]))
    return best_per_service, overall_best


def save_report(version_dir: Path, all_results, best_per_service, overall_best) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_file = RESULTS_DIR / f"results_{version_dir.name}_{ts}.txt"
    total_targets = sum(d["total"] for d in next(iter(all_results.values())).values()) if all_results else 0

    def overall_score(res):
        return sum(d["score"] for d in res.values())

    with out_file.open("w", encoding="utf-8") as f:
        f.write(f"Zapret version: {version_dir.name}\n")
        f.write(f"Date: {ts}\n\n")
        for bat_name, res in all_results.items():
            f.write(f"=== {bat_name} ===\n")
            for service, data in res.items():
                f.write(f"  {service}: {data['score']}/{data['total']}\n")
                for host, ok, info, elapsed in data["detail"]:
                    f.write(f"    {host:<30} ok={ok} info={info} time={elapsed:.2f}s\n")
            f.write("\n")
        f.write("=== BEST PER SERVICE ===\n")
        for service, (bat_name, res) in best_per_service.items():
            f.write(f"  {service}: {bat_name} ({res[service]['score']}/{res[service]['total']})\n")
        if overall_best:
            f.write(f"\nBest overall: {overall_best[0]} "
                    f"({overall_score(overall_best[1])}/{total_targets})\n")
    return out_file


def main():
    if not is_admin():
        relaunch_as_admin()
        return

    print("=" * 60)
    print(" ZAPRET STRATEGY TESTER")
    print("=" * 60)

    if not check_curl():
        print("[ERROR] curl.exe не найден в PATH. Установите curl и повторите.")
        sys.exit(1)

    if check_zapret_service_installed():
        print("[ERROR] В системе установлена служба 'zapret'.")
        print("        Удалите её перед тестами: откройте service.bat нужной версии")
        print("        и выберите 'Remove Services'.")
        sys.exit(1)

    versions = find_versions(BASE_DIR)
    if not versions:
        print(f"[ERROR] В {BASE_DIR} не найдено ни одной папки версии zapret (bin/winws.exe).")
        sys.exit(1)

    version_dir = pick_version(versions)
    bats = find_strategies(version_dir)
    if not bats:
        print("[ERROR] В этой версии не найдено general*.bat стратегий.")
        sys.exit(1)

    selected = pick_strategies(bats)
    selected_targets = pick_services(TARGETS)

    print(f"\nВерсия: {version_dir.name}")
    print(f"Стратегий к тесту: {len(selected)}")
    print(f"Сервисов к тесту: {', '.join(selected_targets)}")
    print("Тесты займут несколько минут, не переключайтесь на VPN/другой zapret в это время.\n")

    try:
        all_results = run_tests(version_dir, selected, targets=selected_targets, log=print)
    except KeyboardInterrupt:
        print("\nПрервано пользователем.")
        kill_winws()
        return

    if not all_results:
        print("\nНи одна стратегия не дала результатов.")
        return

    print("\n" + "=" * 60)
    print(" ИТОГ")
    print("=" * 60)

    best_per_service, overall_best = summarize(all_results)
    total_targets = sum(len(v) for v in selected_targets.values())

    for service, (bat_name, res) in best_per_service.items():
        score = res[service]["score"]
        total = res[service]["total"]
        print(f"  {service:<10}: {bat_name}  ({score}/{total})")

    overall_score = sum(d["score"] for d in overall_best[1].values())
    print(f"\n  Лучшая стратегия в целом: {overall_best[0]} ({overall_score}/{total_targets})")

    out_file = save_report(version_dir, all_results, best_per_service, overall_best)

    print(f"\nПодробный отчёт сохранён: {out_file}")
    print("\nЧтобы включить лучшую стратегию — просто запустите нужный .bat вручную")
    print(f"из папки: {version_dir}")


if __name__ == "__main__":
    main()
