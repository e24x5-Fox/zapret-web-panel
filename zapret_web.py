#!/usr/bin/env python3
"""
Local web control panel for zapret. Replaces the Tkinter GUI: this process
is only a JSON API + static file server on 127.0.0.1, all actual UI lives in
web/index.html and runs in the browser.

Must run as Administrator (winws.exe needs the WinDivert driver).
"""

import ctypes
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
import webbrowser
import winreg
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Packaged as a windowed (console=False) exe: there is no console, so
# sys.stdout/stderr are None. Anything that still calls print() (including
# in the imported modules below) would otherwise crash with
# "AttributeError: 'NoneType' object has no attribute 'write'" the first
# time it runs. Redirect to a null sink instead of hunting down every print.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# zapret_tester/zapret_service/zapret_generator all shell out to console
# tools (tasklist, sc, net, taskkill, curl, powershell...) via subprocess,
# none of them passing CREATE_NO_WINDOW. With a console-subsystem parent
# that's invisible (this is a windowed app now), Windows would otherwise pop
# a brand new console window for every single one of those — most visibly
# the winws-status poll the UI runs every 2 seconds. Patching Popen.__init__
# once here (subprocess.run()/check_output()/etc. all construct a Popen
# internally, so this covers every call site in every module) is far less
# error-prone than adding the flag to ~40 individual call sites.
if sys.platform == "win32":
    _popen_init = subprocess.Popen.__init__

    def _popen_init_no_window(self, *args, **kwargs):
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | subprocess.CREATE_NO_WINDOW
        _popen_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _popen_init_no_window

import zapret_tester as zt
import zapret_service as zs
import zapret_generator as zg
import zapret2_engine as z2
import zapret2_generator as zg2
import zapret_downloader as zd
from i18n import t

def _resource_dir() -> Path:
    """Where bundled read-only assets (web/) live: PyInstaller's onefile
    temp extraction dir when packaged, this script's folder otherwise."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


BASE_DIR = zt.BASE_DIR
WEB_DIR = _resource_dir() / "web"
PORT = 8756

# Fresh per-run secret. This server runs elevated and can install/remove
# Windows services and kill processes, so every /api/* call must carry this
# token in an X-Zapret-Token header. Two things make that an actual defense
# rather than security theater:
#   - a page on another origin cannot read this process's window.ZAPRET_TOKEN
#     (browser same-origin policy), so it cannot forge the header;
#   - setting a *custom* header forces a CORS preflight, and since we never
#     send Access-Control-Allow-* headers, the browser blocks the real
#     request before it reaches us — this also defeats plain <form> CSRF,
#     which can't set custom headers at all, and DNS-rebinding attacks,
#     which don't help an attacker who still can't read or set the token.
# The token is embedded into index.html at serve time (see _serve_static)
# and attached to every request by web/app.js.
SECRET_TOKEN = secrets.token_urlsafe(32)
# Some WebView2 Runtime builds send "Host: localhost:PORT" instead of
# "Host: 127.0.0.1:PORT" for a plain loopback navigation (observed on a
# tester's machine — the panel's own window got a raw {"error": "forbidden"}
# JSON body instead of the UI). Both names resolve to the same loopback
# interface, and this check is defense-in-depth on top of the token above
# (the actual CSRF/DNS-rebinding defense), so accepting any loopback name
# on our own port doesn't weaken anything real.
_LOOPBACK_HOSTNAMES = {"127.0.0.1", "localhost", "[::1]"}


# --------------------------------------------------------------------------- #
# background test session (single test can run at a time)
# --------------------------------------------------------------------------- #

class TestSession:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.stop_requested = False
        self.log = []
        self.progress = {"done": 0, "total": 0}
        self.results = {}
        self.best = None
        self.version = None
        self.report_path = None

    def reset(self, version_name, total):
        with self.lock:
            self.running = True
            self.stop_requested = False
            self.log = []
            self.progress = {"done": 0, "total": total}
            self.results = {}
            self.best = None
            self.version = version_name
            self.report_path = None

    def append_log(self, msg):
        with self.lock:
            self.log.append(msg)
            if msg.startswith("["):
                self.progress["done"] += 1

    def finish(self, results, best, report_path):
        with self.lock:
            self.results = results
            self.best = best
            self.report_path = report_path
            self.running = False

    def snapshot(self, since=0):
        with self.lock:
            out = {
                "running": self.running,
                "log": self.log[since:],
                "log_len": len(self.log),
                "progress": dict(self.progress),
                "version": self.version,
            }
            if not self.running and self.results:
                out["results"] = self.results
                out["best"] = self.best
                out["report_path"] = self.report_path
            return out


test_session = TestSession()


# --------------------------------------------------------------------------- #
# background generator session (single run at a time, mirrors TestSession) —
# also keeps `texts` (candidate name -> generated .bat content) around after
# a run finishes, since that's what /api/generator/save persists to disk.
# --------------------------------------------------------------------------- #

class GeneratorSession:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.stop_requested = False
        self.log = []
        self.progress = {"done": 0, "total": 0}
        self.results = {}
        self.best = None
        self.version = None
        self.texts = {}
        self.baseline = None
        self.inconclusive = False

    def reset(self, version_name, total):
        with self.lock:
            self.running = True
            self.stop_requested = False
            self.log = []
            self.progress = {"done": 0, "total": total}
            self.results = {}
            self.best = None
            self.version = version_name
            self.texts = {}
            self.baseline = None
            self.inconclusive = False

    def append_log(self, msg):
        with self.lock:
            self.log.append(msg)
            if msg.startswith("["):
                self.progress["done"] += 1

    def finish(self, results, best, texts, baseline, inconclusive):
        with self.lock:
            self.results = results
            self.best = best
            self.texts = texts
            self.baseline = baseline
            self.inconclusive = inconclusive
            self.running = False

    def snapshot(self, since=0):
        with self.lock:
            out = {
                "running": self.running,
                "log": self.log[since:],
                "log_len": len(self.log),
                "progress": dict(self.progress),
                "version": self.version,
            }
            if not self.running and self.results:
                out["results"] = self.results
                out["best"] = self.best
                out["baseline"] = self.baseline
                out["inconclusive"] = self.inconclusive
                out["candidates"] = list(self.texts.keys())
            return out


generator_session = GeneratorSession()

# Separate instance for the zapret2 generator — GeneratorSession's state
# machine doesn't reference zapret1 anywhere, so it's reused as-is; only a
# distinct instance is needed so the two searches can't clobber each other's
# progress/results if a user somehow triggered both.
zapret2_generator_session = GeneratorSession()


# --------------------------------------------------------------------------- #
# version scan cache — name -> absolute Path, populated by _do_rescan().
# Versions can now live anywhere on disk (global scan) or in a
# user-configured folder (custom scan), not just under BASE_DIR, so every
# lookup by name goes through this cache instead of assuming BASE_DIR/name.
# --------------------------------------------------------------------------- #

_version_paths = {}
_scan_lock = threading.Lock()


def _do_rescan(lang="ru"):
    settings = zt.load_scan_settings()
    if settings["mode"] == "custom" and settings.get("custom_dir"):
        found = zt.find_versions_in_dir(Path(settings["custom_dir"]))
    else:
        found = zt.find_versions_global()
    with _scan_lock:
        _version_paths.clear()
        _version_paths.update(found)
    return sorted(_version_paths.keys(), key=zt.natural_key)


def _version_dir(name, lang="ru"):
    if not name:
        raise ValueError(t(lang, "err_version_not_specified"))
    if not _version_paths:
        _do_rescan(lang)
    vd = _version_paths.get(name)
    if not vd or not vd.exists() or not (vd / "bin" / "winws.exe").exists():
        raise ValueError(t(lang, "err_unknown_version", name=name))
    return vd


# zapret2 (alternative engine) version scan cache — same shape as the
# zapret1 cache above, always whole-computer (zapret2 installs have no
# reliable naming convention to support a "custom folder" mode against).
_zapret2_version_paths = {}
_zapret2_scan_lock = threading.Lock()


def _do_rescan_zapret2():
    found = z2.find_versions_global()
    with _zapret2_scan_lock:
        _zapret2_version_paths.clear()
        _zapret2_version_paths.update(found)
    return sorted(_zapret2_version_paths.keys(), key=zt.natural_key)


def _zapret2_version_dir(name, lang="ru"):
    if not name:
        return None
    if not _zapret2_version_paths:
        _do_rescan_zapret2()
    vd = _zapret2_version_paths.get(name)
    if not vd or not z2.find_engine_dir(vd):
        return None
    return vd


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #

class Handler(BaseHTTPRequestHandler):
    server_version = "ZapretWeb/1.0"

    def log_message(self, fmt, *args):
        pass

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message, status=400):
        self._send_json({"error": message}, status)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8")) if raw else {}

    def _host_ok(self) -> bool:
        header = self.headers.get("Host", "")
        host, sep, port = header.rpartition(":")
        if not sep:
            # No ":" at all (e.g. some local security-suite/proxy layer
            # rewrites "Host: 127.0.0.1:8756" down to a bare "Host:
            # localhost"): str.rpartition() with no match puts the whole
            # header in `port` and leaves `host` empty, which used to reject
            # every one of these as forbidden. The connection already landed
            # on our own PORT-only listening socket, so the bare hostname is
            # enough on its own.
            host, port = port, str(PORT)
        ok = host.lower() in _LOOPBACK_HOSTNAMES and port == str(PORT)
        if not ok:
            print(f"[host-check] rejected Host header: {header!r}", file=sys.stderr)
        return ok

    def _token_ok(self) -> bool:
        return secrets.compare_digest(self.headers.get("X-Zapret-Token", ""), SECRET_TOKEN)

    def _lang(self) -> str:
        lang = self.headers.get("X-Zapret-Lang", "ru")
        return lang if lang in ("ru", "en") else "ru"

    # -- routing ----------------------------------------------------- #

    def do_GET(self):
        if not self._host_ok():
            return self._send_error_json("forbidden", 403)

        parsed = urlparse(self.path)
        path, qs = parsed.path, parse_qs(parsed.query)
        lang = self._lang()

        if path.startswith("/api/") and not self._token_ok():
            return self._send_error_json("unauthorized", 401)

        try:
            if path == "/api/versions":
                if qs.get("rescan", ["0"])[0] == "1" or not _version_paths:
                    names = _do_rescan(lang)
                else:
                    names = sorted(_version_paths.keys(), key=zt.natural_key)
                return self._send_json({
                    "versions": names,
                    "paths": {name: str(p) for name, p in _version_paths.items()},
                })

            if path == "/api/scan/settings":
                return self._send_json(zt.load_scan_settings())

            if path == "/api/strategies":
                vd = _version_dir(qs.get("version", [None])[0], lang)
                return self._send_json({"strategies": [b.name for b in zt.find_strategies(vd)]})

            if path == "/api/services":
                return self._send_json({
                    "services": {name: [h for h, _ in hosts] for name, hosts in zt.TARGETS.items()}
                })

            if path == "/api/test/status":
                since = int(qs.get("since", ["0"])[0])
                return self._send_json(test_session.snapshot(since))

            if path == "/api/generator/status":
                since = int(qs.get("since", ["0"])[0])
                return self._send_json(generator_session.snapshot(since))

            if path == "/api/zapret2/generator/status":
                since = int(qs.get("since", ["0"])[0])
                return self._send_json(zapret2_generator_session.snapshot(since))

            if path == "/api/manual/status":
                return self._send_json({"running": zt.winws_running()})

            if path == "/api/zapret2/versions":
                if qs.get("rescan", ["0"])[0] == "1" or not _zapret2_version_paths:
                    names = _do_rescan_zapret2()
                else:
                    names = sorted(_zapret2_version_paths.keys(), key=zt.natural_key)
                return self._send_json({
                    "versions": names,
                    "paths": {name: str(p) for name, p in _zapret2_version_paths.items()},
                })

            if path == "/api/zapret2/state":
                vd = _zapret2_version_dir(qs.get("version", [None])[0], lang)
                profiles = [p.name for p in z2.find_profiles(vd)] if vd else []
                return self._send_json({
                    "valid": vd is not None,
                    "profiles": profiles,
                    "running": z2.winws2_running(),
                })

            if path == "/api/service/status":
                vd = _version_dir(qs.get("version", [None])[0], lang)
                return self._send_json({"text": zs.service_status(vd, lang)})

            if path == "/api/service/settings":
                vd = _version_dir(qs.get("version", [None])[0], lang)
                return self._send_json({
                    "game_filter": zs.game_filter_status(vd),
                    "ipset": zs.ipset_status(vd),
                    "check_updates": zs.check_updates_enabled(vd),
                })

            if path == "/api/service/lists":
                vd = _version_dir(qs.get("version", [None])[0], lang)
                return self._send_json(zs.read_user_lists(vd))

            if path == "/api/env":
                return self._send_json({
                    "admin": zt.is_admin(),
                    "curl": zt.check_curl(),
                    "zapret_service_installed": zt.check_zapret_service_installed(),
                })

            if path == "/api/download/zapret1/releases":
                return self._send_json({"releases": zd.list_zapret1_releases(lang)})

            if path == "/api/download/zapret2/info":
                return self._send_json(zd.zapret2_bundle_info(lang))

            if path.startswith("/api/"):
                return self._send_error_json("not found", 404)

            return self._serve_static(path)
        except ValueError as e:
            self._send_error_json(str(e), 400)
        except Exception as e:
            self._send_error_json(str(e), 500)

    def do_POST(self):
        if not self._host_ok():
            return self._send_error_json("forbidden", 403)

        path = urlparse(self.path).path
        if not self._token_ok():
            return self._send_error_json("unauthorized", 401)

        try:
            data = self._read_json()
            handler = self._POST_ROUTES.get(path)
            if handler is None:
                return self._send_error_json("not found", 404)
            return handler(self, data, self._lang())
        except KeyError as e:
            self._send_error_json(f"missing field: {e}", 400)
        except ValueError as e:
            self._send_error_json(str(e), 400)
        except Exception as e:
            self._send_error_json(str(e), 500)

    # -- POST action implementations ---------------------------------- #

    def _test_start(self, data, lang):
        if test_session.running:
            return self._send_error_json(t(lang, "err_test_already_running"))
        vd = _version_dir(data["version"], lang)
        names = data.get("strategies") or []
        all_bats = {b.name: b for b in zt.find_strategies(vd)}
        bats = [all_bats[n] for n in names if n in all_bats]
        if not bats:
            return self._send_error_json(t(lang, "err_strategies_not_found"))

        service_names = data.get("services") or []
        targets = {k: v for k, v in zt.TARGETS.items() if k in service_names} or zt.TARGETS
        if not targets:
            return self._send_error_json(t(lang, "err_services_not_found"))

        test_session.reset(vd.name, len(bats))

        def worker():
            results = zt.run_tests(
                vd, bats, targets=targets, log=test_session.append_log,
                should_stop=lambda: test_session.stop_requested, lang=lang,
            )
            best = None
            report_path = None
            if results:
                best_per_service, overall_best = zt.summarize(results)
                total_targets = sum(len(v) for v in targets.values())
                best = {
                    "per_service": {
                        svc: {"strategy": name, "score": res[svc]["score"], "total": res[svc]["total"]}
                        for svc, (name, res) in best_per_service.items()
                    },
                    "overall": {
                        "strategy": overall_best[0],
                        "score": sum(d["score"] for d in overall_best[1].values()),
                        "total": total_targets,
                    } if overall_best else None,
                }
                report_path = str(zt.save_report(vd, results, best_per_service, overall_best))
            test_session.finish(results, best, report_path)

        threading.Thread(target=worker, daemon=True).start()
        return self._send_json({"ok": True})

    def _test_stop(self, data, lang):
        test_session.stop_requested = True
        return self._send_json({"ok": True})

    def _generator_start(self, data, lang):
        if generator_session.running:
            return self._send_error_json(t(lang, "err_generator_already_running"))
        if test_session.running:
            return self._send_error_json(t(lang, "err_test_already_running"))
        vd = _version_dir(data["version"], lang)
        mode = data.get("mode")
        if mode not in ("simple", "advanced"):
            return self._send_error_json(t(lang, "err_bad_generator_mode"))

        service_names = data.get("services") or []
        targets = {k: v for k, v in zt.TARGETS.items() if k in service_names} or zt.TARGETS
        if not targets:
            return self._send_error_json(t(lang, "err_services_not_found"))

        total = len(zg.SIMPLE_SPACE) if mode == "simple" else len(zg.ADV_METHODS) ** 2 + 12
        generator_session.reset(vd.name, total)

        def worker():
            all_results, best_per_service, overall_best, texts, baseline, inconclusive = zg.run_generator(
                vd, mode, targets=targets, log=generator_session.append_log,
                should_stop=lambda: generator_session.stop_requested, lang=lang,
            )
            best = None
            if all_results:
                total_targets = sum(len(v) for v in targets.values())
                best = {
                    "per_service": {
                        svc: {"strategy": name, "score": res[svc]["score"], "total": res[svc]["total"]}
                        for svc, (name, res) in best_per_service.items()
                    },
                    "overall": {
                        "strategy": overall_best[0],
                        "score": sum(d["score"] for d in overall_best[1].values()),
                        "total": total_targets,
                    } if overall_best else None,
                }
            baseline_out = {
                svc: {"score": d["score"], "total": d["total"]} for svc, d in (baseline or {}).items()
            } if baseline else None
            generator_session.finish(all_results, best, texts, baseline_out, inconclusive)

        threading.Thread(target=worker, daemon=True).start()
        return self._send_json({"ok": True})

    def _generator_stop(self, data, lang):
        generator_session.stop_requested = True
        return self._send_json({"ok": True})

    def _generator_save(self, data, lang):
        vd = _version_dir(data["version"], lang)
        candidate = data["candidate"]
        if generator_session.version != vd.name or candidate not in generator_session.texts:
            raise ValueError(t(lang, "err_generator_candidate_not_found"))
        out_path = zg.save_candidate(vd, generator_session.texts, candidate, data.get("save_as") or candidate)
        return self._send_json({"ok": True, "path": str(out_path)})

    def _zapret2_generator_start(self, data, lang):
        if zapret2_generator_session.running:
            return self._send_error_json(t(lang, "err_generator_already_running"))
        engine_dir = _zapret2_version_dir(data.get("version"), lang)
        if not engine_dir:
            return self._send_error_json(t(lang, "err_zapret2_no_version"))
        mode = data.get("mode")
        if mode not in ("simple", "advanced"):
            return self._send_error_json(t(lang, "err_bad_generator_mode"))

        service_names = data.get("services") or []
        targets = {k: v for k, v in zt.TARGETS.items() if k in service_names} or zt.TARGETS
        if not targets:
            return self._send_error_json(t(lang, "err_services_not_found"))

        total = (
            len(zg2.SIMPLE_SPACE) if mode == "simple"
            else len(zg2.TLS_METHODS) * len(zg2.HTTP_METHODS) + 12
        )
        version_name = data.get("version")
        zapret2_generator_session.reset(version_name, total)

        def worker():
            all_results, best_per_service, overall_best, texts, baseline, inconclusive = zg2.run_generator(
                engine_dir, mode, targets=targets, log=zapret2_generator_session.append_log,
                should_stop=lambda: zapret2_generator_session.stop_requested, lang=lang,
            )
            best = None
            if all_results:
                total_targets = sum(len(v) for v in targets.values())
                best = {
                    "per_service": {
                        svc: {"strategy": name, "score": res[svc]["score"], "total": res[svc]["total"]}
                        for svc, (name, res) in best_per_service.items()
                    },
                    "overall": {
                        "strategy": overall_best[0],
                        "score": sum(d["score"] for d in overall_best[1].values()),
                        "total": total_targets,
                    } if overall_best else None,
                }
            baseline_out = {
                svc: {"score": d["score"], "total": d["total"]} for svc, d in (baseline or {}).items()
            } if baseline else None
            zapret2_generator_session.finish(all_results, best, texts, baseline_out, inconclusive)

        threading.Thread(target=worker, daemon=True).start()
        return self._send_json({"ok": True})

    def _zapret2_generator_stop(self, data, lang):
        zapret2_generator_session.stop_requested = True
        return self._send_json({"ok": True})

    def _zapret2_generator_save(self, data, lang):
        engine_dir = _zapret2_version_dir(data.get("version"), lang)
        if not engine_dir:
            raise ValueError(t(lang, "err_zapret2_no_version"))
        candidate = data["candidate"]
        if zapret2_generator_session.version != data.get("version") or candidate not in zapret2_generator_session.texts:
            raise ValueError(t(lang, "err_generator_candidate_not_found"))
        out_path = zg2.save_candidate(
            engine_dir, zapret2_generator_session.texts, candidate, data.get("save_as") or candidate
        )
        return self._send_json({"ok": True, "path": str(out_path)})

    def _manual_launch(self, data, lang):
        vd = _version_dir(data["version"], lang)
        bat = vd / data["strategy"]
        if not bat.exists():
            raise ValueError(t(lang, "err_strategy_not_found", strategy=data["strategy"]))
        zt.launch_strategy(bat, vd)
        return self._send_json({"ok": True})

    def _manual_stop(self, data, lang):
        zt.kill_winws()
        return self._send_json({"ok": True})

    def _zapret2_launch(self, data, lang):
        engine_dir = _zapret2_version_dir(data.get("version"), lang)
        if not engine_dir:
            raise ValueError(t(lang, "err_zapret2_no_version"))
        profile_name = data.get("profile")
        all_profiles = {p.name: p for p in z2.find_profiles(engine_dir)}
        profile = all_profiles.get(profile_name)
        if not profile:
            raise ValueError(t(lang, "err_zapret2_profile_not_found"))
        z2.launch_profile(profile, engine_dir)
        return self._send_json({"ok": True})

    def _zapret2_stop(self, data, lang):
        z2.kill_winws2()
        return self._send_json({"ok": True})

    def _service_install(self, data, lang):
        vd = _version_dir(data["version"], lang)
        out = zs.install_service(vd, data["strategy"], lang)
        return self._send_json({"ok": True, "output": out})

    def _service_remove(self, data, lang):
        out = zs.remove_service(lang)
        return self._send_json({"ok": True, "output": out})

    def _settings_game_filter(self, data, lang):
        vd = _version_dir(data["version"], lang)
        zs.set_game_filter(vd, data["mode"])
        return self._send_json({"ok": True})

    def _settings_ipset_cycle(self, data, lang):
        vd = _version_dir(data["version"], lang)
        return self._send_json({"ok": True, "status": zs.cycle_ipset(vd, lang)})

    def _settings_check_updates(self, data, lang):
        vd = _version_dir(data["version"], lang)
        zs.set_check_updates_enabled(vd, bool(data.get("enabled")))
        return self._send_json({"ok": True})

    def _service_lists_save(self, data, lang):
        vd = _version_dir(data["version"], lang)
        zs.write_user_list(vd, data["key"], data.get("content", ""), lang)
        return self._send_json({"ok": True})

    def _update_ipset(self, data, lang):
        vd = _version_dir(data["version"], lang)
        return self._send_json({"ok": True, "output": zs.update_ipset_list(vd, lang)})

    def _update_hosts(self, data, lang):
        return self._send_json({"ok": True, "output": zs.check_hosts_file(lang)})

    def _update_check(self, data, lang):
        vd = _version_dir(data["version"], lang)
        return self._send_json(zs.check_for_updates(vd, lang))

    def _diagnostics_run(self, data, lang):
        vd = _version_dir(data["version"], lang)
        results, conflicts, windivert_conflict = zs.run_diagnostics(vd, lang)
        return self._send_json({
            "results": results, "conflicts": conflicts, "windivert_conflict": windivert_conflict,
        })

    def _diagnostics_remove_conflicts(self, data, lang):
        out = zs.remove_conflicting_services(data.get("names") or [], lang)
        return self._send_json({"ok": True, "output": out})

    def _diagnostics_clear_discord(self, data, lang):
        return self._send_json({"ok": True, "output": zs.clear_discord_cache(lang)})

    def _diagnostics_stop_services(self, data, lang):
        names = data.get("names") or []
        if not names:
            raise ValueError(t(lang, "err_no_service_selected"))
        return self._send_json({"ok": True, "output": zs.stop_services(names, lang)})

    def _diagnostics_fix_windivert(self, data, lang):
        return self._send_json({"ok": True, "output": zs.fix_windivert_conflict(lang)})

    def _scan_settings_save(self, data, lang):
        mode = data.get("mode")
        if mode not in ("global", "custom"):
            raise ValueError(t(lang, "err_bad_scan_mode"))
        custom_dir = data.get("custom_dir") or None
        if mode == "custom" and not custom_dir:
            raise ValueError(t(lang, "err_no_custom_dir"))
        zt.save_scan_settings(mode, custom_dir)
        return self._send_json({"ok": True})

    def _scan_pick_folder(self, data, lang):
        return self._send_json({"path": zt.pick_folder_dialog()})

    def _open_folder(self, data, lang):
        vd = _version_dir(data.get("name"), lang)
        os.startfile(str(vd))
        return self._send_json({"ok": True})

    def _delete_folder(self, data, lang):
        name = data.get("name")
        vd = _version_dir(name, lang)
        shutil.rmtree(vd)
        with _scan_lock:
            _version_paths.pop(name, None)
        return self._send_json({"ok": True})

    def _download_zapret1_start(self, data, lang):
        tag = data.get("tag")
        if not tag:
            raise ValueError(t(lang, "err_version_not_specified"))
        path = zd.download_zapret1(tag, lang)
        _do_rescan(lang)
        # A same-named release folder may already exist elsewhere on disk
        # (this app's users tend to have old copies scattered around) — the
        # whole-computer rescan's first-match-wins collision handling could
        # otherwise silently point the just-downloaded name at that old
        # copy instead. The one just fetched is what the user asked for,
        # so it always wins the naming slot right after a download.
        with _scan_lock:
            _version_paths[path.name] = path
        return self._send_json({"ok": True, "path": str(path), "name": path.name})

    def _download_zapret2_start(self, data, lang):
        path = zd.download_zapret2_bundle(lang)
        _do_rescan_zapret2()
        engine_dir = z2.find_engine_dir(path) or path
        with _zapret2_scan_lock:
            _zapret2_version_paths[path.name] = engine_dir
        return self._send_json({"ok": True, "path": str(engine_dir), "name": path.name})

    _POST_ROUTES = {
        "/api/test/start": _test_start,
        "/api/test/stop": _test_stop,
        "/api/generator/start": _generator_start,
        "/api/generator/stop": _generator_stop,
        "/api/generator/save": _generator_save,
        "/api/manual/launch": _manual_launch,
        "/api/manual/stop": _manual_stop,
        "/api/zapret2/launch": _zapret2_launch,
        "/api/zapret2/stop": _zapret2_stop,
        "/api/zapret2/generator/start": _zapret2_generator_start,
        "/api/zapret2/generator/stop": _zapret2_generator_stop,
        "/api/zapret2/generator/save": _zapret2_generator_save,
        "/api/service/install": _service_install,
        "/api/service/remove": _service_remove,
        "/api/service/settings/game_filter": _settings_game_filter,
        "/api/service/settings/ipset_cycle": _settings_ipset_cycle,
        "/api/service/settings/check_updates": _settings_check_updates,
        "/api/service/lists/save": _service_lists_save,
        "/api/service/update/ipset": _update_ipset,
        "/api/service/update/hosts": _update_hosts,
        "/api/service/update/check": _update_check,
        "/api/diagnostics/run": _diagnostics_run,
        "/api/diagnostics/remove_conflicts": _diagnostics_remove_conflicts,
        "/api/diagnostics/clear_discord_cache": _diagnostics_clear_discord,
        "/api/diagnostics/stop_services": _diagnostics_stop_services,
        "/api/diagnostics/fix_windivert": _diagnostics_fix_windivert,
        "/api/scan/settings": _scan_settings_save,
        "/api/scan/pick_folder": _scan_pick_folder,
        "/api/open_folder": _open_folder,
        "/api/delete_folder": _delete_folder,
        "/api/download/zapret1/start": _download_zapret1_start,
        "/api/download/zapret2/start": _download_zapret2_start,
    }

    # -- static files -------------------------------------------------- #

    _CONTENT_TYPES = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
    }

    def _serve_static(self, path):
        if path == "/":
            path = "/index.html"
        file_path = (WEB_DIR / path.lstrip("/")).resolve()
        if WEB_DIR not in file_path.parents:
            return self._send_error_json("forbidden", 403)
        if not file_path.is_file():
            return self._send_error_json("not found", 404)

        data = file_path.read_bytes()
        if file_path.name == "index.html":
            token_tag = f'<script>window.ZAPRET_TOKEN = "{SECRET_TOKEN}";</script>\n'.encode("utf-8")
            data = data.replace(b'<script src="app.js">', token_tag + b'<script src="app.js">')

        self.send_response(200)
        self.send_header("Content-Type", self._CONTENT_TYPES.get(file_path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


# --------------------------------------------------------------------------- #

def _relaunch_as_admin():
    # No console exists to print to (windowed build) — the UAC prompt itself
    # is the only feedback the user gets here, which is expected.
    print("Нужны права администратора, запрашиваю... / Admin rights required, requesting...")
    params = " ".join(f'"{a}"' for a in sys.argv)
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, str(BASE_DIR), 1)
    if rc <= 32:
        print("Не удалось получить права администратора. Запустите вручную от админа. / "
              "Failed to get admin rights. Please run as administrator manually.")
        sys.exit(1)
    sys.exit(0)


# Windows 11 ships WebView2 Runtime built in; Windows 10 doesn't, so on a
# fresh Windows 10 machine the "real app window" path below silently falls
# back to opening a browser tab instead — confirmed the hard way by a
# tester whose stray Ctrl+P triggered a broken-looking WebView2 print
# overlay, which turned out to only be reachable if WebView2 is present at
# all (i.e. their box already had *some* copy of it). Proactively installing
# it here means the fallback essentially never triggers on a normal
# Windows 10 install instead of silently degrading to browser mode.
_WEBVIEW2_CLIENT_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
_WEBVIEW2_BOOTSTRAPPER_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"


def _webview2_installed() -> bool:
    """Checks the same registry keys Microsoft's own detection guidance
    uses — machine-wide (32- and 64-bit view) and per-user WebView2
    Runtime installs all register an EdgeUpdate client key with a
    non-empty product version ('pv')."""
    key_paths = [
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_CLIENT_GUID}"),
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_CLIENT_GUID}"),
        (winreg.HKEY_CURRENT_USER, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_CLIENT_GUID}"),
    ]
    for hive, path in key_paths:
        try:
            with winreg.OpenKey(hive, path) as key:
                value, _ = winreg.QueryValueEx(key, "pv")
            if value:
                return True
        except OSError:
            continue
    return False


def _install_webview2_runtime() -> bool:
    """Downloads and silently runs Microsoft's official WebView2 Runtime
    Evergreen Bootstrapper (the same small installer Microsoft's own docs
    point third-party apps at for exactly this). Returns True on apparent
    success. Explicitly bypasses any system/env proxy, same reasoning as
    zapret_downloader — this shouldn't fail just because of an unrelated
    misconfigured proxy."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        tmp_path = Path(tempfile.gettempdir()) / "MicrosoftEdgeWebView2Setup.exe"
        req = urllib.request.Request(_WEBVIEW2_BOOTSTRAPPER_URL, headers={"User-Agent": "zapret-web-panel"})
        with opener.open(req, timeout=120) as resp, open(tmp_path, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
        res = subprocess.run([str(tmp_path), "/silent", "/install"], timeout=300)
        return res.returncode == 0
    except Exception:
        return False


def _ensure_webview2_runtime():
    if _webview2_installed():
        return
    ctypes.windll.user32.MessageBoxW(
        None,
        "Компонент WebView2 Runtime не найден и будет автоматически установлен "
        "(нужен интернет, может занять до минуты).\n\n"
        "The WebView2 Runtime component wasn't found and will be installed "
        "automatically (needs an internet connection, may take up to a minute).",
        "Zapret Control Panel",
        0x40,  # MB_ICONINFORMATION
    )
    if not _install_webview2_runtime():
        ctypes.windll.user32.MessageBoxW(
            None,
            "Не удалось установить WebView2 Runtime — панель откроется в браузере "
            "вместо отдельного окна.\n\n"
            "Couldn't install the WebView2 Runtime — the panel will open in your "
            "browser instead of its own window.",
            "Zapret Control Panel",
            0x30,  # MB_ICONWARNING
        )


def main():
    if not zt.is_admin():
        _relaunch_as_admin()
        return

    _ensure_webview2_runtime()

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    url = f"http://127.0.0.1:{PORT}/"

    # Normal path: a real app window (no browser chrome, no console) via
    # pywebview, wrapping WebView2 (auto-installed above if missing). Falls
    # back to opening the system browser only if that install didn't work
    # out (e.g. no internet) — the panel still works, just as a browser tab
    # instead of a window.
    try:
        import webview
        webview.create_window(
            "Zapret Control Panel", url,
            width=520, height=840, min_size=(440, 680),
            background_color="#05070a",
        )
        webview.start()
    except Exception:
        webbrowser.open(url)
        try:
            server_thread.join()
        except KeyboardInterrupt:
            pass
        return

    server.shutdown()


if __name__ == "__main__":
    main()
