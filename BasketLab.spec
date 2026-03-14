# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for BasketLab
Builds a standalone executable for Windows and macOS
"""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all hidden imports needed
hiddenimports = [
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'pymongo',
    'requests',
    'beautifulsoup4',
    'bs4',
    'matplotlib',
    'matplotlib.backends.backend_qt5agg',
    'numpy',
    'scipy',
    'pandas',
    'fpdf2',
    'docx',
    'PIL',
    'PIL.Image',
    'certifi',
    'charset_normalizer',
    'idna',
    'urllib3',
    'lxml',
    'scipy.special.cython_special',
]

# Collect matplotlib data files
matplotlib_datas = collect_data_files('matplotlib', include_py_files=False)

# Collect certifi certificates for HTTPS requests
certifi_datas = collect_data_files('certifi')

# Define data files to include
datas = [
    ('resources/BasketLab.ico', 'resources'),
    ('resources/BasketLab.png', 'resources'),
    ('src/JSON_samples', 'JSON_samples'),
    ('src/database/db_credentials.txt', 'database'),  # Include DB credentials in distribution
]

# Add collected data files
datas += matplotlib_datas
datas += certifi_datas

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',  # Exclude Tkinter to reduce size
        '_tkinter',
        'distutils',
        # Exclude heavy ML/DL libraries not used by the app
        'torch',
        'torchvision',
        'torchaudio',
        'tensorflow',
        'tensorboard',
        'transformers',
        'jax',
        'flax',
        'onnx',
        'onnxruntime',
        'triton',
        'sentencepiece',
        'tokenizers',
        # Exclude testing frameworks (but keep unittest itself)
        'pytest',
        'hypothesis',
        # Exclude IPython and Jupyter
        'IPython',
        'jupyter',
        'notebook',
        # Exclude other unnecessary packages
        'setuptools',
        'pip',
        'wheel',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BasketLab',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/BasketLab.ico' if sys.platform == 'win32' else 'resources/BasketLab.png',
)

# For macOS: Create .app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='BasketLab.app',
        icon='resources/BasketLab.png',
        bundle_identifier='com.basketlab.app',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': 'True',
        },
    )
