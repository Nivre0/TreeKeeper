# TreeKeeper

A deliberately simple genealogy desktop app for Windows (Python 3 + PySide6).
All data lives in one JSON file that you choose via *File › Open / Save as*.

## Run from source

```
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py [optional\path\to\file.json]
```

*File › Open sample data* loads 17 invented persons over 4 generations
(including a divorce, half-siblings, cousins and a separated unmarried couple).

## Usage

- **Left:** person list with name search (all words must match first/middle/last/birth name).
  Double-click edits, right-click shows quick actions.
- **Toolbar / Person menu:** New person, Edit, *Add child*, *Add parent*, *Add partner* – these act on
  the focus person.
- **Tree:** mouse wheel zooms, drag pans. Click a card to make it the focus person, double-click to edit.
  - *Ancestors & descendants*: direct ancestors above, descendants below, one row per generation.
  - *Whole family*: everybody connected through parents, children or partners; laid out with
    Graphviz `dot` (bundled in the .exe), falling back to a built-in layout if dot is missing.
- **Lines:** double line = marriage, single line = partnership, dashed grey = divorced/separated,
  dotted grey = two parents without a recorded relationship.

Dates are picked, not typed: choose *exact / about / before / after*, then day, month and year from
drop-downs (day and month are optional, so `1923` or `ca. 03.1880` work), or click 📅 for a calendar.
They are stored as text such as `12.03.1923`, `03.1923`, `ca. 1880`, `before 1900`; older free-text
dates are kept unchanged until you edit them. Tick *Deceased* for persons who have died – the date of
death may stay empty if it is unknown (stored as `?`).

## Data file

```json
{
  "format": "treekeeper",
  "version": 1,
  "persons": [
    {
      "id": "uuid", "first_name": "", "middle_name": "", "last_name": "", "birth_name": "",
      "gender": "male | female | diverse | unknown",
      "birth_date": "", "birth_place": "", "death_date": "", "death_place": "",
      "parents": ["uuid", "uuid"],
      "partnerships": [{"partner": "uuid", "type": "marriage | partnership | unknown",
                        "status": "current | divorced | separated | widowed",
                        "from": "", "to": ""}],
      "notes": ""
    }
  ]
}
```

Children are not stored; they are derived from `parents`. Partnerships are stored on both partners and
kept mirrored automatically; deleting a person removes every reference to them. On loading, broken
references are repaired and reported.

## Build the Windows .exe

Requires Graphviz installed (`winget install Graphviz.Graphviz`) so it can be bundled.

```
.\build.ps1            # -> dist\TreeKeeper\TreeKeeper.exe (folder, fast start)
.\build.ps1 -OneFile   # -> dist\TreeKeeper.exe (single file, slower start)
```

## Development

```
.venv\Scripts\python -m unittest discover -s tests
.venv\Scripts\python tools\make_sample.py          # regenerate the sample file
.venv\Scripts\python tools\screenshot.py OUT_DIR   # render both views to PNG
```
