<h1 align="center">TreeKeeper</h1>

<p align="center">
  <b>A simple family tree app for Windows.</b><br>
  Record people, parents and partners, and see your family as a clear, zoomable tree.<br>
  Everything is kept in one plain JSON file that you own.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows-0078D6" alt="Platform: Windows">
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/UI-PySide6%20(Qt%206)-41CD52" alt="PySide6">
  <img src="https://img.shields.io/badge/AI%20access-MCP-8A63D2" alt="MCP server">
  <a href="https://m8ven.ai/mcp/nivre0-treekeeper-fwmbqb?s=readme">
    <img src="https://m8ven.ai/badge/mcp/nivre0-treekeeper-fwmbqb?v=9bd7ab62ab89305f9814448e9574e934" alt="M8ven Score">
  </a>
</p>

<p align="center">
  <img src="docs/images/whole-family.png" alt="TreeKeeper showing a family over four generations" width="900">
</p>

TreeKeeper is for people who want to write down their family history without learning a full
genealogy suite. It does a few things and tries to do them well: names and life dates, father and
mother, marriages and partnerships, and a tree that draws itself.

## Features

- **Two tree views.** *Ancestors & descendants* shows one person's direct line, one row per
  generation. *Whole family* shows everybody who is connected, laid out with
  [Graphviz](https://graphviz.org).
- **Quick editing.** Click a card to focus a person and double-click it to edit. Dashed
  **+ Add father / mother / child** boxes create a relative in one step.
- **Dates that fit real records.** Choose *exact*, *about*, *before* or *after*. Day and month are
  optional, so `1923`, `ca. 03.1880` and `before 1900` all work.
- **Partnerships.** Marriage or partnership, current, divorced, separated or widowed, with from/to
  dates. Former partners are drawn with a dashed line.
- **Readable cards.** Each card shows name, birth name and lifespan ("1928–1999", "born 1985",
  "died 1944"), with † for people who have died and a colour per gender.
- **One JSON file.** Your data lives in one file you choose, with nothing hidden in a database.
  It is easy to back up, put under version control, or read with other tools.
- **AI access (optional).** A built-in [MCP](https://modelcontextprotocol.io) server lets assistants
  like Claude read and edit the open tree. You can watch every change appear in the window.

<table>
  <tr>
    <td width="50%"><img src="docs/images/ancestors.png" alt="Ancestors and descendants view"></td>
    <td width="50%"><img src="docs/images/person-dialog.png" alt="Editing a person"></td>
  </tr>
  <tr>
    <td align="center"><sub>Ancestors &amp; descendants, with the <i>+ Add child</i> box</sub></td>
    <td align="center"><sub>Editing a person: dates, parents and partners</sub></td>
  </tr>
</table>

## Quick start

You need [Python 3.10 or newer](https://www.python.org/downloads/windows/) and, for the
*Whole family* layout, [Graphviz](https://graphviz.org/download/).

```powershell
git clone https://github.com/Nivre0/TreeKeeper.git
cd TreeKeeper
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

Then choose **File › Open sample data** to look around a made-up family of 17 people over four
generations, or **File › New** to start your own.

The **[installation guide](docs/installation.md)** covers every step in detail, including a desktop
shortcut and building a standalone `.exe`.

## Documentation

| Guide | What's inside |
| --- | --- |
| [Installation](docs/installation.md) | Python, Graphviz, running from source, desktop shortcut, building the `.exe`, troubleshooting |
| [User guide](docs/user-guide.md) | A tour of the window, adding people and relationships, dates, views and settings |
| [AI access](docs/ai-access.md) | Connecting Claude Desktop or Claude Code through the built-in MCP server |
| [File format](docs/file-format.md) | The JSON structure, for backups, scripts and other tools |

## Development

```powershell
# Run the tests
.venv\Scripts\python -m unittest discover -s tests
# Regenerate the sample family
.venv\Scripts\python tools\make_sample.py
# Retake the screenshots in docs/images
.venv\Scripts\python tools\docs_screenshots.py
# Build dist\TreeKeeper\TreeKeeper.exe
.\build.ps1
```

The code lives in [`treekeeper/`](treekeeper):

| Module | Purpose |
| --- | --- |
| `model.py` | People, partnerships, loading, saving and repairing the JSON file |
| `dates.py`, `date_edit.py` | Partial dates and the date picker |
| `layout.py`, `tree_view.py` | Tree layouts (own generation layout and Graphviz) and drawing |
| `main_window.py`, `person_dialog.py` | The main window and the person editor |
| `mcp_server.py`, `ai_tools.py`, `ai_dialog.py` | The MCP server, its tools and its window |
