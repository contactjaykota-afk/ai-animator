# PyInstaller spec - builds "dist/AI Animator/AI Animator.exe" (one-folder build:
# starts faster and is less often flagged by antivirus than one-file builds).
# Build:  pyinstaller --noconfirm packaging/ai_animator.spec
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
ICON = str(ROOT / "ai_animator" / "resources" / "icon.ico")

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "ai_animator" / "resources"), "resources")],
    hiddenimports=[
        "keyring.backends.Windows",       # Windows Credential Manager
        "win32ctypes.core",
        "mss.windows",
    ],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.Qt3DCore", "PySide6.QtQuick3D", "PySide6.QtMultimedia", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="AI Animator",
    icon=ICON,
    console=False,          # no terminal window
    version=str(ROOT / "packaging" / "version_info.txt") if sys.platform == "win32" else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="AI Animator")
