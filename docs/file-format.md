# File format

A TreeKeeper file is a UTF-8 JSON file with one entry per person. It is meant to be easy to read,
back up, compare in Git, or process with your own scripts.

```json
{
  "format": "treekeeper",
  "version": 1,
  "persons": [
    {
      "id": "6f1c2a9e-0b5d-5c1e-9a57-3d2b8c4e7f10",
      "first_name": "Walter",
      "middle_name": "",
      "last_name": "Keller",
      "birth_name": "",
      "gender": "male",
      "birth_date": "12.03.1928",
      "birth_place": "Zürich",
      "death_date": "1999",
      "death_place": "Bern",
      "parents": ["<id of father>", "<id of mother>"],
      "partnerships": [
        {
          "partner": "<id of Elisabeth>",
          "type": "marriage",
          "status": "divorced",
          "from": "1952",
          "to": "1963"
        }
      ],
      "notes": ""
    }
  ]
}
```

## Fields

| Field | Values |
| --- | --- |
| `id` | Any unique string. TreeKeeper creates UUIDs. |
| `first_name`, `middle_name`, `last_name`, `birth_name` | Text. `birth_name` is the surname at birth, if different. |
| `gender` | `male`, `female`, `diverse` or `unknown` |
| `birth_date`, `death_date` | A date as text (see below), or empty |
| `birth_place`, `death_place` | Text |
| `parents` | Up to two person ids |
| `partnerships` | A list of `{partner, type, status, from, to}` |
| `partnerships[].type` | `marriage`, `partnership` or `unknown` |
| `partnerships[].status` | `current`, `divorced`, `separated` or `widowed` |
| `notes` | Free text |

## Dates

Dates are stored as text, so incomplete dates are possible:

| Example | Meaning |
| --- | --- |
| `12.03.1923` | 12 March 1923 |
| `03.1923` | March 1923 |
| `1923` | Sometime in 1923 |
| `ca. 1880` | About 1880 |
| `before 1900` / `after 1750` | Before or after a date. Day and month are allowed too. |
| `?` | Death date only: died, date unknown |

ISO dates (`1923-03-12`) are also understood when reading. Dates TreeKeeper doesn't understand are
kept as they are and shown unchanged until you edit them.

## Rules

- **Children are not stored.** They follow from the `parents` of other people.
- **Partnerships are mirrored.** Each partnership appears on both partners. If only one side has
  it, TreeKeeper adds the other side when the file is opened.
- **No dangling links.** Deleting a person removes them from every `parents` list and every
  partnership.
- **Repair on open.** Links to missing people, more than two parents, a person who is their own
  ancestor, and one-sided partnerships are fixed
  when a file is opened, and TreeKeeper lists what it changed. The fix is written back the next
  time you save.
- **Safe saving.** Files are written to a temporary file first and then swapped in, so a crash
  while saving can't leave you with a half-written file.
