# PyInstaller spec – build with:  .venv\Scripts\pyinstaller FamilyTree.spec --noconfirm
# Bundles Graphviz (dot.exe + DLLs + plugin config) into a "graphviz" folder.
# Set GRAPHVIZ_BIN to use a Graphviz installation other than the default.
# Set ONEFILE=1 for a single .exe (slower start, it unpacks itself on every launch).

import glob
import os

graphviz_bin = os.environ.get("GRAPHVIZ_BIN", r"C:\Program Files\Graphviz\bin")
graphviz_files = []
if os.path.isfile(os.path.join(graphviz_bin, "dot.exe")):
    for pattern in ("dot.exe", "*.dll", "config*"):
        graphviz_files += [(f, "graphviz") for f in glob.glob(os.path.join(graphviz_bin, pattern))]
else:
    print("WARNING: Graphviz not found - the 'Whole family' view will use the built-in layout.")

onefile = os.environ.get("ONEFILE") == "1"

a = Analysis(
    ["main.py"],
    datas=[("familytree/resources", "familytree/resources")] + graphviz_files,
    excludes=["tkinter", "unittest", "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick",
              "PySide6.QtMultimedia", "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtPdf"],
)
pyz = PYZ(a.pure)

if onefile:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, name="FamilyTree", console=False, upx=False)
else:
    exe = EXE(pyz, a.scripts, exclude_binaries=True, name="FamilyTree", console=False, upx=False)
    coll = COLLECT(exe, a.binaries, a.datas, name="FamilyTree", upx=False)
