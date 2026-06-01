# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the AppImage / EXE bundle.
# Bundles the whole package (so resources/ - i18n, icon, fonts - ship with it)
# and the crypto/http deps that PyInstaller cannot trace through dynamic imports.
from PyInstaller.utils.hooks import collect_all

datas = [("easy_scsmodmanager", "easy_scsmodmanager")]
binaries = []
hiddenimports = [
    "Crypto",
    "Crypto.Cipher",
    "Crypto.Cipher.AES",
    "vdf",
    "httpx",
]
for _pkg in ("Crypto", "httpx"):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h


a = Analysis(
    ["easy_scsmodmanager/__main__.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EasySCSModManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="EasySCSModManager",
)
