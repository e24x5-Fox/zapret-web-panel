#!/usr/bin/env python3
"""Regression tests for the security fixes described in SECURITY_NOTES.md.

These exist because that file once described all six fixes as done while
none of them were in the code: notes drift, tests do not. Run with:

    python -m unittest test_security -v

Nothing here touches the real system — the two tests that would otherwise
run `net stop` / `sc delete` replace subprocess.run first.
"""

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import zapret_downloader as zd
import zapret_generator as zg
import zapret_service as zs
import zapret_web as zw
import zapret2_generator as zg2


def _make_version_dir(root: Path, *bat_names) -> Path:
    """A folder that looks like an unpacked zapret release."""
    version_dir = root / "zapret-discord-youtube-1.9.9d"
    (version_dir / "bin").mkdir(parents=True)
    (version_dir / "bin" / "winws.exe").write_text("")
    for name in bat_names:
        (version_dir / name).write_text("@echo off\n")
    return version_dir


class StrategyPathTest(unittest.TestCase):
    """Fix #1 — a strategy name must never become an arbitrary path.

    The panel runs elevated and hands the result to `cmd /c` or registers
    it as a service binPath, so an escape here is arbitrary code execution
    as administrator.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.version_dir = _make_version_dir(
            Path(self._tmp.name), "general.bat", "general (ALT).bat", "service.bat"
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_accepts_a_discovered_strategy(self):
        self.assertEqual(
            zw._strategy_path(self.version_dir, "general.bat"),
            self.version_dir / "general.bat",
        )

    def test_rejects_relative_traversal(self):
        with self.assertRaises(ValueError):
            zw._strategy_path(self.version_dir, "../../../Windows/System32/calc.exe")

    def test_rejects_absolute_path(self):
        # This is the one that really bites: pathlib lets an absolute path
        # on the right of `/` replace the left side entirely, so the old
        # .exists() check passed happily.
        with self.assertRaises(ValueError):
            zw._strategy_path(self.version_dir, r"C:\Windows\System32\calc.exe")

    def test_rejects_service_bat(self):
        # find_strategies() filters these out, so they are not launchable.
        with self.assertRaises(ValueError):
            zw._strategy_path(self.version_dir, "service.bat")

    def test_rejects_empty_and_non_string(self):
        for bad in ("", None, 42, ["general.bat"]):
            with self.assertRaises(ValueError):
                zw._strategy_path(self.version_dir, bad)


class SaveCandidateTest(unittest.TestCase):
    """Fix #2 — the generator's save_as name must stay inside the folder."""

    def test_zapret1_strips_directory_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            texts = {"cand": "@echo off\n"}

            for attempt in ("../../evil", r"C:\Windows\Temp\evil", "sub/dir/evil"):
                out = zg.save_candidate(version_dir, texts, "cand", attempt)
                self.assertEqual(out.parent, version_dir, f"escaped with {attempt!r}")

    def test_zapret2_strips_directory_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine_dir = Path(tmp) / "engine"
            engine_dir.mkdir()
            texts = {"cand": "@echo off\n"}

            for attempt in ("../../evil", r"C:\Windows\Temp\evil", "sub/dir/evil"):
                out = zg2.save_candidate(engine_dir, texts, "cand", attempt)
                self.assertEqual(out.parent, engine_dir, f"escaped with {attempt!r}")


class ServiceNameAllowlistTest(unittest.TestCase):
    """Fix #3 — `net stop` / `sc delete` only accept names we derived."""

    def test_stop_services_ignores_names_outside_the_vpn_set(self):
        calls = []

        def fake_run(cmd, *a, **kw):
            calls.append(cmd)
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch.object(zs, "vpn_service_names", return_value={"MyVPNService"}), \
             mock.patch.object(zs.subprocess, "run", side_effect=fake_run):
            zs.stop_services(["MyVPNService", "WinDefend", "Dnscache"])

        stopped = [c[2] for c in calls if c[:2] == ["net", "stop"]]
        self.assertEqual(stopped, ["MyVPNService"])

    def test_remove_conflicting_ignores_unknown_names(self):
        calls = []

        def fake_run(cmd, *a, **kw):
            calls.append(cmd)
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch.object(zs.subprocess, "run", side_effect=fake_run):
            zs.remove_conflicting_services(["GoodbyeDPI", "WinDefend", "Dnscache"])

        deleted = [c[2] for c in calls if c[:2] == ["sc", "delete"]]
        # GoodbyeDPI is on the built-in list; WinDivert is always cleaned up
        # afterwards by design. Nothing else may appear.
        self.assertEqual(deleted, ["GoodbyeDPI", "WinDivert"])

    def test_allowlist_is_exact_not_substring(self):
        calls = []

        def fake_run(cmd, *a, **kw):
            calls.append(cmd)
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch.object(zs.subprocess, "run", side_effect=fake_run):
            zs.remove_conflicting_services(["GoodbyeDPI2", "winws", "winws1x"])

        deleted = [c[2] for c in calls if c[:2] == ["sc", "delete"]]
        self.assertEqual(deleted, ["WinDivert"])


class ZipSlipTest(unittest.TestCase):
    """Fix #4 — an archive member may not write outside the target folder."""

    def _extract(self, member_name):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            zip_path = tmp_path / "payload.zip"
            dest = tmp_path / "dest"
            dest.mkdir()

            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr(member_name, "payload")

            with zipfile.ZipFile(zip_path) as zf:
                zd._safe_extractall(zf, dest)

    def test_rejects_traversal_member(self):
        with self.assertRaises(RuntimeError):
            self._extract("../escaped.txt")

    def test_rejects_deep_traversal_member(self):
        with self.assertRaises(RuntimeError):
            self._extract("a/b/../../../escaped.txt")

    def test_allows_an_ordinary_member(self):
        self._extract("bin/winws.exe")  # must not raise


class BodySizeCapTest(unittest.TestCase):
    """Fix #6 — a forged Content-Length may not allocate unbounded memory."""

    def test_cap_is_defined_and_sane(self):
        self.assertGreater(zw._MAX_BODY_BYTES, 1024 * 1024)
        self.assertLessEqual(zw._MAX_BODY_BYTES, 64 * 1024 * 1024)

    def test_read_json_refuses_an_oversized_body(self):
        handler = zw.Handler.__new__(zw.Handler)
        handler.headers = {"Content-Length": str(zw._MAX_BODY_BYTES + 1)}
        # rfile is deliberately absent: the size check must reject the
        # request before anything tries to read from the socket.
        with self.assertRaises(ValueError):
            handler._read_json()


if __name__ == "__main__":
    unittest.main(verbosity=2)
