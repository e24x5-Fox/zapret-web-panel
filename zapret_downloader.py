#!/usr/bin/env python3
"""
Downloads original zapret1/zapret2 releases straight from their upstream
GitHub repos into BASE_DIR/zapret/{zapret1,zapret2} — an alternative to
manually downloading+extracting a release zip yourself.

Two different repos, two different shapes, because that's what upstream
actually offers:

- zapret1: Flowseal/zapret-discord-youtube has normal tagged GitHub
  Releases, each with a zip asset already laid out exactly like the panel
  expects (bin/winws.exe, service.bat, general*.bat, ...). Straightforward
  "pick a release, download it" flow, and GitHub publishes a sha256 digest
  per asset that gets verified before extracting — see
  zapret_binary_security_verification in project memory for why that
  matters here.

- zapret2: bol-van/zapret2's own releases only ship source + bare per-arch
  binaries (binaries/windows-x86_64/winws2.exe with no lua/, presets, or
  WinDivert alongside it) — confirmed by hand while integrating zapret2
  support, not something this module needs to rediscover. The actual
  ready-to-run Windows bundle (winws2.exe + lua/ + files/ +
  windivert.filter/ + preset*.cmd, matching zapret2_engine.find_engine_dir)
  lives in the separate bol-van/zapret-win-bundle repo — which has no
  Releases or tags at all, just a rolling master branch. So there's no
  version to pick for zapret2: only "download the current master snapshot",
  labeled by commit date + short SHA since that's all upstream gives us.
  No published digest exists for a branch archive, so this path is
  transparency (surface the commit SHA) rather than verification.
"""

import hashlib
import http.client
import json
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import zapret_tester as zt  # reuse BASE_DIR
from i18n import t

GITHUB_API = "https://api.github.com"
ZAPRET1_REPO = "Flowseal/zapret-discord-youtube"
ZAPRET2_BUNDLE_REPO = "bol-van/zapret-win-bundle"

DOWNLOAD_ROOT = zt.BASE_DIR / "zapret"
ZAPRET1_DIR = DOWNLOAD_ROOT / "zapret1"
ZAPRET2_DIR = DOWNLOAD_ROOT / "zapret2"

_USER_AGENT = "zapret-web-panel"

# Explicitly bypass any system/environment proxy for these requests.
# urllib.request.urlopen() auto-detects HTTP_PROXY/HTTPS_PROXY (env vars or,
# on Windows, the registry-configured system proxy) by default — if that's
# ever misconfigured (seen firsthand: a stray HTTPS_PROXY env var with a
# trailing CR that broke curl.exe too), every GitHub call here would fail
# with a confusing "no connection" error unrelated to the user's actual
# internet access. This app has no reason to route its own GitHub API
# calls through a system proxy it doesn't control.
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


# --------------------------------------------------------------------------- #
# GitHub API
# --------------------------------------------------------------------------- #

def _api_get(path: str, lang="ru"):
    req = urllib.request.Request(
        f"{GITHUB_API}{path}",
        headers={"User-Agent": _USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    try:
        with _opener.open(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise RuntimeError(t(lang, "err_download_rate_limited")) from e
        if e.code == 404:
            raise RuntimeError(t(lang, "err_download_not_found")) from e
        raise RuntimeError(t(lang, "err_download_network")) from e
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as e:
        raise RuntimeError(t(lang, "err_download_network")) from e


def list_zapret1_releases(lang="ru", limit=15):
    data = _api_get(f"/repos/{ZAPRET1_REPO}/releases?per_page={limit}", lang)
    out = []
    for rel in data:
        asset = next((a for a in rel.get("assets", []) if a["name"].lower().endswith(".zip")), None)
        if not asset:
            continue
        out.append({
            "tag": rel["tag_name"],
            "published_at": rel.get("published_at"),
            "size": asset["size"],
            "prerelease": bool(rel.get("prerelease")),
        })
    return out


def _get_zapret1_release(tag: str, lang="ru"):
    rel = _api_get(f"/repos/{ZAPRET1_REPO}/releases/tags/{tag}", lang)
    asset = next((a for a in rel.get("assets", []) if a["name"].lower().endswith(".zip")), None)
    if not asset:
        raise RuntimeError(t(lang, "err_download_no_asset"))
    digest = asset.get("digest") or ""
    sha256 = digest.split(":", 1)[1] if digest.startswith("sha256:") else None
    return {
        "tag": tag,
        "asset_name": asset["name"],
        "download_url": asset["browser_download_url"],
        "sha256": sha256,
    }


def zapret2_bundle_info(lang="ru"):
    commit = _api_get(f"/repos/{ZAPRET2_BUNDLE_REPO}/commits/master", lang)
    sha = commit["sha"]
    short = sha[:7]
    date = commit["commit"]["committer"]["date"]
    return {
        "sha": sha,
        "short_sha": short,
        "date": date,
        "download_url": f"https://codeload.github.com/{ZAPRET2_BUNDLE_REPO}/zip/refs/heads/master",
        "folder_name": f"zapret-win-bundle-{date[:10]}-{short}",
    }


# --------------------------------------------------------------------------- #
# download + extract
# --------------------------------------------------------------------------- #

def _download_to_file(url: str, dest: Path, lang="ru") -> str:
    """Streams url to dest, returns the sha256 hex digest of what was
    written (used for optional verification against a published digest)."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    hasher = hashlib.sha256()
    try:
        with _opener.open(req, timeout=30) as resp, open(dest, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                hasher.update(chunk)
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as e:
        raise RuntimeError(t(lang, "err_download_network")) from e
    return hasher.hexdigest()


def _safe_extractall(zf: zipfile.ZipFile, dest: Path):
    """extractall() that refuses archive members which would land outside
    dest ("zip slip").

    zipfile does not check this itself: a member named "../../evil.bat", or
    one with an absolute path, is written wherever it says. This app
    extracts archives downloaded over the network while running elevated,
    and the zapret2 bundle in particular publishes no sha256 to verify the
    download against, so the archive's own claims are all we have.
    """
    dest_resolved = dest.resolve()
    for member in zf.infolist():
        target = (dest_resolved / member.filename).resolve()
        if target != dest_resolved and dest_resolved not in target.parents:
            raise RuntimeError(f"unsafe path in archive: {member.filename}")
    zf.extractall(dest)


def _extract_flatten(zip_path: Path, dest_parent: Path, folder_name: str, lang="ru") -> Path:
    """Extracts zip_path, flattening a single top-level directory (GitHub's
    convention for both release assets and branch archives) so the result
    lands directly at dest_parent/folder_name with no extra nesting."""
    target = dest_parent / folder_name
    if target.exists():
        raise RuntimeError(t(lang, "err_download_already_exists", name=folder_name))

    dest_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(zip_path) as zf:
            _safe_extractall(zf, tmp_path)
        entries = list(tmp_path.iterdir())
        content_root = entries[0] if len(entries) == 1 and entries[0].is_dir() else tmp_path
        shutil.move(str(content_root), str(target))
    return target


def download_zapret1(tag: str, lang="ru") -> Path:
    release = _get_zapret1_release(tag, lang)
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / release["asset_name"]
        actual_sha256 = _download_to_file(release["download_url"], zip_path, lang)
        if release["sha256"] and actual_sha256 != release["sha256"]:
            raise RuntimeError(t(lang, "err_download_hash_mismatch"))
        # Not derived from the zip's own internal layout: some tags ship a
        # flat archive (bin/, general*.bat directly at the root, no wrapping
        # folder — confirmed by hand against 1.9.8c), others may wrap
        # everything in one folder. _extract_flatten handles both; this name
        # is just what the resulting folder is called on disk, chosen to
        # match the "zapret-discord-youtube-X.Y.Z" naming the existing
        # scan logic (and every other release folder) already expects.
        return _extract_flatten(zip_path, ZAPRET1_DIR, f"zapret-discord-youtube-{tag}", lang)


def download_zapret2_bundle(lang="ru") -> Path:
    info = zapret2_bundle_info(lang)
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "zapret-win-bundle.zip"
        _download_to_file(info["download_url"], zip_path, lang)
        return _extract_flatten(zip_path, ZAPRET2_DIR, info["folder_name"], lang)
