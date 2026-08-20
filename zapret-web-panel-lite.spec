# -*- mode: python ; coding: utf-8 -*-

# Smaller variant of zapret-web-panel.spec: the same app, minus a few stdlib
# C-extensions it never reaches at runtime (see the excludes below). Kept as
# a SEPARATE spec/output so it never overwrites the normal build.
#
# HISTORY, because the release notes got this wrong for two versions: this
# spec was originally written to also compress the result with UPX, and
# v1.9.0's notes described the lite build that way and warned users about
# UPX's reputation for antivirus false positives. In reality upx.exe was
# never installed on the build machine, so PyInstaller skipped the step in
# silence and every published lite build has been an ordinary uncompressed
# exe — verified against the v1.9.2 binaries by their PE section names.
# The warning therefore scared people away from a file that was no
# different in that respect from the recommended one. UPX is now off
# explicitly (see the EXE block) and the size difference comes purely from
# the excludes, which is about a megabyte.
#
# The upx_exclude list below is retained for anyone reviving the UPX
# variant. It intentionally protects every Microsoft-signed / .NET-managed
# binary the app depends on (WebView2 loader/assemblies, pythonnet's CLR
# runtime DLLs, the VC++/UCRT system DLLs) — UPX has known issues repacking
# .NET assemblies and signed system DLLs, and breaking WebView2Loader.dll
# specifically would break the whole app window. Only plain CPython
# extension modules (.pyd) and the OpenSSL/python3xx DLLs are compressed.
#
# Extra excludes below drop stdlib C-extensions that PyInstaller's static
# analysis pulls in defensively but that this app never actually reaches at
# runtime: bz2/lzma are only used by zipfile.py's own optional (try/except
# ImportError-guarded) codec support, and the only zip files this app ever
# opens are plain-DEFLATE GitHub release archives (zapret_downloader.py);
# decimal isn't used anywhere in this codebase or its dependencies.
# NOTE: xml/pyexpat looked unused too (only textual hit was clr_loader's
# `if __name__ == "__main__"` corerror.xml script) but is NOT safe to drop —
# pkg_resources (pulled in by pythonnet/webview via the pyi_rth_pkgres
# runtime hook, which runs unconditionally on every launch) imports
# plistlib at its own top level, which unconditionally imports xml. Verified
# by trying it: excluding xml/pyexpat produced an immediate
# "ModuleNotFoundError: No module named 'xml'" crash at startup via
# pyi_rth_pkgres -> pkg_resources -> plistlib. Don't re-add them without
# re-testing a real launch.
# optimize=2 strips docstrings/asserts from the bundled bytecode (this
# codebase has no asserts used for real control flow, so that's a free win).
a = Analysis(
    ['zapret_web.py'],
    pathex=[],
    binaries=[],
    datas=[('web', 'web')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'gi', 'AppKit', 'Cocoa', 'objc',
        'bz2', 'lzma', 'decimal', '_decimal',
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='zapret-web-panel-lite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # Off, deliberately — see the note at the top of this file. The
    # upx_exclude list below is kept intact so the UPX variant can be
    # revived by flipping this one flag, but it must stay a conscious
    # decision rather than something that switches itself on depending on
    # whether the build machine happens to have upx.exe.
    upx=False,
    upx_exclude=[
        'ucrtbase.dll', 'vcruntime140.dll', 'vcruntime140_1.dll',
        'WebView2Loader.dll', 'Microsoft.Web.WebView2.*.dll',
        '*.Runtime.dll', 'System.*.dll', 'netstandard.dll', 'mscorlib.dll',
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
    icon='icon.ico',
)
