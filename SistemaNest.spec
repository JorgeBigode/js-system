# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['login_app.py'],
    pathex=[],
    binaries=[],
    datas=[('img', 'img'), ('etiqueta_config.json', '.'), ('PEDIDO.docx', '.')],
    hiddenimports=['pymysql', 'PIL._tkinter_finder', 'babel.numbers', 'win32timezone', 'win32api', 'win32print', 'win32con', 'win32ui', 'win32gui', 'trilhadeira_app'],
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
    a.binaries,
    a.datas,
    [],
    name='SistemaNest',
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
    icon=['img\\icon-SILO.ico'],
)
