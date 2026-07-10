#!/usr/bin/env python3
"""
Local web control panel for zapret. Replaces the Tkinter GUI: this process
is only a JSON API + static file server on 127.0.0.1, all actual UI lives in
web/index.html and runs in the browser.

Must run as Administrator (winws.exe needs the WinDivert driver).
"""

import ctypes
import json
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import zapret_tester as zt
import zapret_service as zs
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
EXPECTED_HOST = f"127.0.0.1:{PORT}"


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


def _version_dir(name, lang="ru"):
    if not name:
        raise ValueError(t(lang, "err_version_not_specified"))
    vd = BASE_DIR / name
    if not vd.exists() or not (vd / "bin" / "winws.exe").exists():
        raise ValueError(t(lang, "err_unknown_version", name=name))
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
        return self.headers.get("Host", "") == EXPECTED_HOST

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
                versions = zt.find_versions(BASE_DIR)
                return self._send_json({"versions": [v.name for v in versions]})

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

            if path == "/api/manual/status":
                return self._send_json({"running": zt.winws_running()})

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

            if path == "/api/env":
                return self._send_json({
                    "admin": zt.is_admin(),
                    "curl": zt.check_curl(),
                    "zapret_service_installed": zt.check_zapret_service_installed(),
                })

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

    _POST_ROUTES = {
        "/api/test/start": _test_start,
        "/api/test/stop": _test_stop,
        "/api/manual/launch": _manual_launch,
        "/api/manual/stop": _manual_stop,
        "/api/service/install": _service_install,
        "/api/service/remove": _service_remove,
        "/api/service/settings/game_filter": _settings_game_filter,
        "/api/service/settings/ipset_cycle": _settings_ipset_cycle,
        "/api/service/settings/check_updates": _settings_check_updates,
        "/api/service/update/ipset": _update_ipset,
        "/api/service/update/hosts": _update_hosts,
        "/api/service/update/check": _update_check,
        "/api/diagnostics/run": _diagnostics_run,
        "/api/diagnostics/remove_conflicts": _diagnostics_remove_conflicts,
        "/api/diagnostics/clear_discord_cache": _diagnostics_clear_discord,
        "/api/diagnostics/stop_services": _diagnostics_stop_services,
        "/api/diagnostics/fix_windivert": _diagnostics_fix_windivert,
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
    # No web UI (and so no chosen language) exists yet at this point, so
    # these bootstrap console lines are printed in both languages.
    print("Нужны права администратора, запрашиваю... / Admin rights required, requesting...")
    params = " ".join(f'"{a}"' for a in sys.argv)
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, str(BASE_DIR), 1)
    if rc <= 32:
        print("Не удалось получить права администратора. Запустите вручную от админа. / "
              "Failed to get admin rights. Please run as administrator manually.")
        sys.exit(1)
    sys.exit(0)


def main():
    if not zt.is_admin():
        _relaunch_as_admin()
        return

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}/"
    print("=" * 60)
    print(" ZAPRET WEB PANEL")
    print("=" * 60)
    print(f"Открываю / Opening: {url}")
    print("Закройте это окно, чтобы остановить панель. / Close this window to stop the panel.")

    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
