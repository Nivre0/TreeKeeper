"""Generate sample_family.json: 17 invented persons over 4 generations.

Includes a divorce (Walter & Elisabeth), half-siblings (Thomas / Ruth),
cousins, a widowhood and an unmarried, separated couple.
Run: python tools/make_sample.py
"""

import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from treekeeper.model import TreeKeeper, Partnership, Person  # noqa: E402

NS = uuid.UUID("6f1f6c1e-0b7a-4c55-9a43-3d1d3c2b9a10")


def pid(key):
    return str(uuid.uuid5(NS, key))


PEOPLE = [
    # key, first, middle, last, birth name, gender, birth, birth place, death, death place, parents, notes
    ("heinrich", "Heinrich", "Albert", "Keller", "", "male", "1902", "Zürich", "14.11.1971", "Zürich", [], "Carpenter."),
    ("anna", "Anna", "", "Keller", "Brunner", "female", "ca. 1905", "Winterthur", "1980", "Zürich", [], ""),
    ("josef", "Josef", "", "Meier", "", "male", "1898", "Luzern", "1944", "", [], "Exact date of death unknown."),
    ("rosa", "Rosa", "", "Meier", "Huber", "female", "03.05.1901", "Kriens", "1988", "Luzern", [], ""),
    ("walter", "Walter", "", "Keller", "", "male", "12.03.1928", "Zürich", "1999", "Bern", ["heinrich", "anna"], ""),
    ("margrit", "Margrit", "", "Schmid", "Keller", "female", "1931", "Zürich", "2015", "Basel", ["heinrich", "anna"], ""),
    ("peter", "Peter", "", "Schmid", "", "male", "1929", "Basel", "2001", "Basel", [], ""),
    ("elisabeth", "Elisabeth", "", "Meier", "Meier", "female", "1932", "Luzern", "2010", "Luzern", ["josef", "rosa"],
     "Took back her maiden name after the divorce."),
    ("hedwig", "Hedwig", "", "Keller", "Frei", "female", "1938", "Bern", "", "", [], ""),
    ("thomas", "Thomas", "Walter", "Keller", "", "male", "1954", "Luzern", "", "", ["walter", "elisabeth"], ""),
    ("ruth", "Ruth", "", "Keller", "", "female", "1966", "Bern", "", "", ["walter", "hedwig"], "Half-sister of Thomas."),
    ("daniel", "Daniel", "", "Schmid", "", "male", "1958", "Basel", "", "", ["margrit", "peter"], ""),
    ("claudia", "Claudia", "", "Roth", "", "female", "about 1961", "", "", "", [], ""),
    ("sandra", "Sandra", "", "Keller", "Weber", "female", "1957", "Aarau", "", "", [], ""),
    ("lukas", "Lukas", "", "Keller", "", "male", "1985", "Zürich", "", "", ["thomas", "sandra"], ""),
    ("nina", "Nina", "", "Keller", "", "female", "1988", "Zürich", "", "", ["thomas", "sandra"], ""),
    ("lea", "Lea", "", "Schmid", "", "female", "1990", "Basel", "", "", ["daniel", "claudia"], ""),
]

PARTNERSHIPS = [
    ("heinrich", "anna", "marriage", "widowed", "1926", "1971"),
    ("josef", "rosa", "marriage", "widowed", "1925", "1944"),
    ("margrit", "peter", "marriage", "widowed", "1955", "2001"),
    ("walter", "elisabeth", "marriage", "divorced", "1952", "1963"),
    ("walter", "hedwig", "marriage", "widowed", "1965", "1999"),
    ("thomas", "sandra", "marriage", "current", "1983", ""),
    ("daniel", "claudia", "partnership", "separated", "1988", "1994"),
]


def main():
    tree = TreeKeeper()
    for key, first, middle, last, birth_name, gender, born, bplace, died, dplace, parents, notes in PEOPLE:
        tree.add_person(Person(
            id=pid(key), first_name=first, middle_name=middle, last_name=last,
            birth_name=birth_name if birth_name != last else "", gender=gender,
            birth_date=born, birth_place=bplace, death_date=died, death_place=dplace,
            parents=[pid(p) for p in parents], notes=notes))
    for a, b, ptype, status, start, end in PARTNERSHIPS:
        person = tree.get(pid(a)).copy()
        person.partnerships.append(Partnership(pid(b), ptype, status, start, end))
        tree.update_person(person)
    out = os.path.join(os.path.dirname(__file__), "..", "treekeeper", "resources", "sample_family.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tree.save(os.path.abspath(out))
    print(f"Wrote {len(tree.persons)} persons to {os.path.abspath(out)}")


if __name__ == "__main__":
    main()
