# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('uvicorn')
datas = [
    ('app/templates', 'app/templates'),
    ('app/static', 'app/static'),
    ('plugins', 'plugins'),
    ('themes', 'themes'),
    ('user_scripts', 'user_scripts'),
    ('docs', 'docs'),
    ('LICENSE', '.'),
    ('README.md', '.'),
]

a = Analysis(
    ['matrix.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='dashboard-matrix',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
