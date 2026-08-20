# Security notes

Notes on the security posture of the web panel's backend. Kept in the repo
(not machine-local memory) so it's visible from any PC this project is
checked out on.

**Every fix listed below is covered by a test in `test_security.py`.** That
is deliberate, and the reason is in the history section at the bottom: an
earlier version of this file described all six of these as done while none
of them were actually in the code. Notes drift; tests do not. Run them with:

```
python -m unittest test_security -v
```

## Threat model

The panel binds a local HTTP server and runs elevated, because `winws.exe`
needs the WinDivert driver. Two consequences follow.

First, anything that can drive the API with a valid token — an XSS in the
page, or any local program that can read `window.ZAPRET_TOKEN` — acts with
administrator rights. So handler input is treated as untrusted even though
it nominally comes from our own page.

Second, "it came from our own UI" is never a reason to skip a check. The UI
offers a fixed set of choices; the request is a separate thing that can say
anything.

## Fixed

1. **Path traversal → arbitrary code execution as administrator**
   `_manual_launch` (`/api/manual/launch`) and `_service_install`
   (`/api/service/install`) joined the client-supplied strategy filename
   straight onto the version folder (`vd / data["strategy"]`) and checked
   only `.exists()`.

   That check does not confine anything. `pathlib` treats an absolute path
   on the right of `/` as replacing the left side entirely, so
   `Path("C:/versions/x") / "C:/Windows/System32/calc.exe"` *is*
   `C:\Windows\System32\calc.exe`, and `.exists()` says yes. A
   `../../../` name resolves out of the folder just as well. The result was
   passed to `cmd /c`, or registered as the auto-start `zapret` service.

   **Fix:** both handlers now resolve the name through `_strategy_path()`
   in `zapret_web.py`, which only returns a path that `zt.find_strategies()`
   actually discovered — the whitelist `_test_start` always used.
   `install_service()` additionally takes `Path(bat_name).name` itself, so
   a future direct caller cannot reintroduce the escape.

2. **Same traversal in `save_candidate`**
   (`zapret_generator.py`, `zapret2_generator.py`) — `save_as` was joined
   onto `version_dir`/`engine_dir` unsanitized, letting a generated .bat be
   written anywhere on disk. **Fix:** the name goes through `Path(...).name`
   before joining, and an empty result is rejected.

3. **Unrestricted service names in the diagnostics endpoints**
   `/api/diagnostics/stop_services` and `/api/diagnostics/remove_conflicts`
   took a client-supplied `names` list and ran `net stop` / `sc delete` on
   whatever was in it. Passing `["WinDefend", "Dnscache"]` deleted Windows
   Defender and the DNS client.

   **Fix:** `stop_services()` intersects the list with `vpn_service_names()`,
   derived server-side from `sc query` at call time; and
   `remove_conflicting_services()` only acts on names in
   `CONFLICTING_BYPASS_SERVICES`. Both matches are exact, not substring.

4. **Zip-slip in the release downloader**
   `_extract_flatten` (`zapret_downloader.py`) called `zf.extractall()` with
   no per-member check, so an archive member named `../../evil.bat` landed
   outside the extraction directory. **Fix:** `_safe_extractall()` resolves
   every member against the destination and refuses the archive before
   extracting anything. Matters most for the zapret2 bundle, which — unlike
   zapret1 releases — publishes no sha256 to verify the download against.

5. **Thread-safety race in the version-scan cache**
   `/api/versions` and `/api/zapret2/versions` iterated `_version_paths` /
   `_zapret2_version_paths` while another request's thread could be inside
   `_do_rescan()` clearing and refilling the same dict (e.g. a background
   download finishing), raising `RuntimeError: dictionary changed size
   during iteration`. The lock existed but covered only the writes.
   **Fix:** both handlers snapshot the dict under the lock and read from the
   snapshot; `_do_rescan()` builds its sorted result inside the lock too.

6. **Unbounded request body size**
   `Handler._read_json()` read `Content-Length` bytes with no cap. Added a
   10 MB ceiling (`_MAX_BODY_BYTES`), generous next to the largest
   legitimate body (a user-list save), which closes a trivial
   memory-exhaustion vector via a forged header.

## Reviewed and left alone

- **CSRF / DNS-rebinding defence** (per-run token plus a `Host` check) —
  sound. Note that the `Host` check is not the real defence; the token is.
  That is why v1.8.0 and v1.9.1 could safely relax how strictly the header
  is parsed when antivirus HTTP filters rewrote it.
- **Frontend** (`web/app.js`) — user-controlled strings consistently go
  through `escapeHtml()` before any `innerHTML` use, and logs go through
  `textContent`. No XSS found.
- **`_test_start` and `_zapret2_launch`** — already whitelisted correctly;
  used as the reference pattern for fix #1.

## History

An earlier revision of this file, dated 2026-07-20, listed fixes 1–6 as
completed. They were not: verified against the code, and against the full
git history, none of the six were ever committed. `_safe_extractall` and
`_MAX_BODY_BYTES` did not appear in any commit on any branch. The file
itself had never been committed either. The likely explanation is a session
whose code edits were lost while the notes survived separately.

The practical lesson is why `test_security.py` now exists alongside this
file. Before the fixes went in, all 15 of those tests failed against the
then-current code; they pass now. A claim in prose can rot silently. A
failing test cannot.

## Build

Note for builds on the original author's machine: the ambient
`HTTP_PROXY`/`HTTPS_PROXY` environment variables have at times been
malformed (a trailing space breaks URL parsing) and made both `pip install`
and `pyinstaller` fail. Build with those cleared if that recurs:

```
HTTP_PROXY= HTTPS_PROXY= http_proxy= https_proxy= python -m PyInstaller zapret-web-panel.spec
```
