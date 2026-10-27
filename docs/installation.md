# Installation

TreeKeeper runs on Windows 10 and 11. You run it from the source code with Python, and you can
optionally build a standalone `.exe`.

- [1. Install Python](#1-install-python)
- [2. Install Graphviz (recommended)](#2-install-graphviz-recommended)
- [3. Download TreeKeeper](#3-download-treekeeper)
- [4. Set it up and start it](#4-set-it-up-and-start-it)
- [5. Add a desktop and Start menu shortcut](#5-add-a-desktop-and-start-menu-shortcut)
- [Updating](#updating)
- [Building a standalone .exe](#building-a-standalone-exe)
- [Troubleshooting](#troubleshooting)

## 1. Install Python

Install **Python 3.10 or newer** from [python.org](https://www.python.org/downloads/windows/), or
in a terminal:

```powershell
winget install Python.Python.3.13
```

The installer also adds the `py` launcher, which is what the commands below use. To check that it
works:

```powershell
py -3 --version
```

## 2. Install Graphviz (recommended)

The *Whole family* view is laid out by [Graphviz](https://graphviz.org). Without it, TreeKeeper
falls back to a simpler built-in layout. The text at the top right, above the tree, shows which one
is in use (`layout: Graphviz dot` or `layout: built-in`).

```powershell
winget install Graphviz.Graphviz
```

TreeKeeper finds Graphviz in `C:\Program Files\Graphviz` or on your `PATH`. You don't need to
configure anything.

## 3. Download TreeKeeper

**With Git:**

```powershell
git clone https://github.com/Nivre0/TreeKeeper.git
cd TreeKeeper
```

**Without Git:** on the [repository page](https://github.com/Nivre0/TreeKeeper), click
**Code › Download ZIP**. Unpack it to a folder such as `C:\Apps\TreeKeeper`, then open a terminal
in that folder.

## 4. Set it up and start it

These commands create a private Python environment in the `.venv` folder and install the only
dependency, [PySide6](https://pypi.org/project/PySide6/) (Qt for Python):

```powershell
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Start TreeKeeper:

```powershell
.venv\Scripts\python main.py
```

You can also open a file directly with `.venv\Scripts\python main.py C:\path\to\family.json`.
TreeKeeper reopens the last file you used.

> **Tip:** use `pythonw` instead of `python` to start TreeKeeper without a console window:
> `.venv\Scripts\pythonw main.py`

## 5. Add a desktop and Start menu shortcut

Run this in PowerShell from the TreeKeeper folder. It creates a **TreeKeeper** shortcut on your
desktop and in the Start menu, and the shortcut starts the app without a console window:

```powershell
$app   = (Get-Location).Path
$shell = New-Object -ComObject WScript.Shell
foreach ($folder in [Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("Programs")) {
    $link = $shell.CreateShortcut((Join-Path $folder "TreeKeeper.lnk"))
    $link.TargetPath       = Join-Path $app ".venv\Scripts\pythonw.exe"
    $link.Arguments        = "`"$(Join-Path $app 'main.py')`""
    $link.WorkingDirectory = $app
    $link.Description      = "TreeKeeper family tree"
    $link.Save()
}
```

To give the shortcut a custom icon, right-click it and choose **Properties › Change Icon…**.

## Updating

If you used Git, run this in the TreeKeeper folder:

```powershell
git pull
.venv\Scripts\pip install -r requirements.txt
```

If you downloaded the ZIP, download the new ZIP and replace the files, but keep your `.venv` folder.
Your family files are not affected either way. They live wherever you saved them, not in the
program folder.

## Building a standalone .exe

You can build an `.exe` that runs without Python, for example for another computer. Graphviz must
be installed (step 2), because the build bundles it, so the `.exe` doesn't need it separately.

```powershell
.\build.ps1            # -> dist\TreeKeeper\TreeKeeper.exe  (a folder, starts fast)
.\build.ps1 -OneFile   # -> dist\TreeKeeper.exe             (a single file, starts slower)
```

The script installs [PyInstaller](https://pyinstaller.org) into `.venv`, runs the tests and then
builds. Close TreeKeeper before rebuilding, because Windows can't replace a running `.exe`.

> **Smart App Control:** on Windows 11 with *Smart App Control* turned on, Windows blocks
> self-built `.exe` files because they are not signed. In that case, use the Python shortcut from
> step 5. It runs the same app.

## Troubleshooting

| Problem | Solution |
| --- | --- |
| `py` is not recognized | Reinstall Python and keep **"py launcher"** ticked, or use the full path to `python.exe`. |
| `pip install` fails with a PySide6 error | Make sure you use a 64-bit Python 3.10 or newer (`py -3 --version`). |
| *Whole family* shows "layout: built-in" | Graphviz is not installed or not found. Install it (step 2) and restart TreeKeeper. |
| The window opens without my data | TreeKeeper reopens the last file. Use **File › Open…** to pick your file. |
| The `.exe` is blocked | See *Smart App Control* above, or start TreeKeeper with the Python shortcut. |
| AI assistant can't connect | See [AI access › Troubleshooting](ai-access.md#troubleshooting). |
