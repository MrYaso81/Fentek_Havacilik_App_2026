# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for the portable Windows distribution."""
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = Path(SPECPATH).resolve()
VENDOR = ROOT / 'vendor'
sys.path.insert(0, str(VENDOR))

hiddenimports = sorted(set(
    collect_submodules('pymavlink')
    + collect_submodules('serial')
    + ['cv2', 'lxml.etree', 'fastcrc']
))

datas = [
    (str(ROOT / 'assets'), 'assets'),
    (str(ROOT / 'belgeler'), 'belgeler'),
    (str(ROOT / 'okul_logo.png'), '.'),
    (str(ROOT / 'appearance.json'), '.'),
]

binaries = collect_dynamic_libs('cv2')

a = Analysis(
    ['flight_pro.py'],
    pathex=[str(ROOT), str(VENDOR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Fentek Havacilik',
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
    icon=str(ROOT / 'assets' / 'fentek_iha_v4.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Fentek Havacilik',
)
