# -*- mode: python ; coding: utf-8 -*-


# Windows-only app (see README): pywebview only ever needs its edgechromium
# (WebView2) backend here, with mshtml as pywebview's own built-in fallback.
# Excluding the other GUI toolkits it *could* use on other platforms keeps
# the build from accidentally dragging in something huge like PyQt5/GTK just
# because it happens to be installed in the build machine's environment.
a = Analysis(
    ['zapret_web.py'],
    pathex=[],
    binaries=[],
    datas=[('web', 'web')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'gi', 'AppKit', 'Cocoa', 'objc'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='zapret-web-panel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
)
