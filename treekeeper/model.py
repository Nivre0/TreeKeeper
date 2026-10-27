"""Data model: a flat list of persons stored in one JSON file.

Children are never stored; they are derived from the persons' parent lists.
Partnerships are stored on both partners and kept mirrored by TreeKeeper.
"""

import json
import os
import uuid
from dataclasses import dataclass, field

from . import dates

FILE_FORMAT = "treekeeper"
FILE_VERSION = 1

GENDERS = ("male", "female", "diverse", "unknown")
PARTNERSHIP_TYPES = ("marriage", "partnership", "unknown")
PARTNERSHIP_STATUSES = ("current", "divorced", "separated", "widowed")
FORMER_STATUSES = ("divorced", "separated")


def new_id():
    return str(uuid.uuid4())


@dataclass
class Partnership:
    partner: str
    type: str = "marriage"
    status: str = "current"
    start: str = ""
    end: str = ""

    @property
    def is_former(self):
        return self.status in FORMER_STATUSES

    def mirrored(self, own_id):
        """The same partnership as seen from the partner's side."""
        return Partnership(own_id, self.type, self.status, self.start, self.end)

    def to_dict(self):
        return {"partner": self.partner, "type": self.type, "status": self.status,
                "from": self.start, "to": self.end}

    @classmethod
    def from_dict(cls, d):
        ptype = d.get("type", "unknown")
        status = d.get("status", "current")
        return cls(
            partner=str(d.get("partner", "")),
            type=ptype if ptype in PARTNERSHIP_TYPES else "unknown",
            status=status if status in PARTNERSHIP_STATUSES else "current",
            start=str(d.get("from") or ""),
            end=str(d.get("to") or ""),
        )


@dataclass
class Person:
    id: str = field(default_factory=new_id)
    first_name: str = ""
    middle_name: str = ""
    last_name: str = ""
    birth_name: str = ""
    gender: str = "unknown"
    birth_date: str = ""
    birth_place: str = ""
    death_date: str = ""
    death_place: str = ""
    parents: list = field(default_factory=list)
    partnerships: list = field(default_factory=list)
    notes: str = ""

    # --- derived display helpers -------------------------------------------------

    @property
    def deceased(self):
        return bool(self.death_date.strip() or self.death_place.strip())

    @property
    def given_names(self):
        return " ".join(n for n in (self.first_name, self.middle_name) if n.strip())

    @property
    def full_name(self):
        name = " ".join(n for n in (self.given_names, self.last_name) if n.strip())
        return name or "(no name)"

    @property
    def short_name(self):
        name = " ".join(n for n in (self.first_name, self.last_name) if n.strip())
        return name or "(no name)"

    @property
    def lifespan(self):
        return dates.lifespan(self.birth_date, self.death_date, self.deceased)

    @property
    def list_label(self):
        """'Last, First Middle (1923–1998)' for lists and pickers."""
        if self.last_name.strip():
            name = self.last_name
            if self.given_names:
                name += ", " + self.given_names
        else:
            name = self.given_names or "(no name)"
        if self.birth_name.strip() and self.birth_name != self.last_name:
            name += f" (née {self.birth_name})"
        span = self.lifespan
        return f"{name}  {span}" if span else name

    def sort_key(self):
        return (self.last_name.lower(), self.first_name.lower(), dates.sort_year(self.birth_date))

    def matches(self, query):
        """True if every word of the query occurs in one of the names."""
        haystack = " ".join((self.first_name, self.middle_name, self.last_name, self.birth_name)).lower()
        return all(word in haystack for word in query.lower().split())

    def partnership_with(self, other_id):
        return next((p for p in self.partnerships if p.partner == other_id), None)

    # --- serialisation ------------------------------------------------------------

    def copy(self):
        return Person.from_dict(self.to_dict())

    def to_dict(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "middle_name": self.middle_name,
            "last_name": self.last_name,
            "birth_name": self.birth_name,
            "gender": self.gender,
            "birth_date": self.birth_date,
            "birth_place": self.birth_place,
            "death_date": self.death_date,
            "death_place": self.death_place,
            "parents": list(self.parents),
            "partnerships": [p.to_dict() for p in self.partnerships],
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d):
        gender = d.get("gender", "unknown")
        return cls(
            id=str(d.get("id") or new_id()),
            first_name=str(d.get("first_name") or ""),
            middle_name=str(d.get("middle_name") or ""),
            last_name=str(d.get("last_name") or ""),
            birth_name=str(d.get("birth_name") or ""),
            gender=gender if gender in GENDERS else "unknown",
            birth_date=str(d.get("birth_date") or ""),
            birth_place=str(d.get("birth_place") or ""),
            death_date=str(d.get("death_date") or ""),
            death_place=str(d.get("death_place") or ""),
            parents=[str(p) for p in (d.get("parents") or []) if p],
            partnerships=[Partnership.from_dict(p) for p in (d.get("partnerships") or [])
                          if isinstance(p, dict)],
            notes=str(d.get("notes") or ""),
        )


class TreeKeeper:
    """All persons of one file plus the operations that keep references consistent."""

    def __init__(self):
        self.persons = {}
        self.path = None
        self.dirty = False

    # --- file I/O -----------------------------------------------------------------

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        tree = cls.from_json_data(raw)
        tree.path = path
        return tree

    @classmethod
    def from_json_data(cls, raw):
        # Accept both {"persons": [...]} and a bare list of persons.
        entries = raw.get("persons", []) if isinstance(raw, dict) else raw
        if not isinstance(entries, list):
            raise ValueError("The file does not contain a list of persons.")
        tree = cls()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            person = Person.from_dict(entry)
            if person.id in tree.persons:
                person.id = new_id()
            tree.persons[person.id] = person
        tree.warnings = tree._repair()
        tree.dirty = False
        return tree

    def save(self, path=None):
        path = path or self.path
        data = {
            "format": FILE_FORMAT,
            "version": FILE_VERSION,
            "persons": [p.to_dict() for p in sorted(self.persons.values(), key=Person.sort_key)],
        }
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        self.path = path
        self.dirty = False

    def _repair(self):
        """Remove dangling references and make partnerships symmetric. Returns warnings."""
        warnings = []
        for person in self.persons.values():
            parents = []
            for pid in person.parents:
                if pid in self.persons and pid != person.id and pid not in parents:
                    parents.append(pid)
                else:
                    warnings.append(f"{person.full_name}: removed invalid parent reference.")
            if len(parents) > 2:
                warnings.append(f"{person.full_name}: more than two parents, kept the first two.")
                parents = parents[:2]
            person.parents = parents
        for person in self.persons.values():
            if self.is_ancestor(person.id, person.id):
                warnings.append(f"{person.full_name}: is their own ancestor, removed parents.")
                person.parents = []
        for person in list(self.persons.values()):
            valid = []
            for ps in person.partnerships:
                if ps.partner in self.persons and ps.partner != person.id \
                        and not any(v.partner == ps.partner for v in valid):
                    valid.append(ps)
                else:
                    warnings.append(f"{person.full_name}: removed invalid partner reference.")
            person.partnerships = valid
        for person in self.persons.values():
            for ps in person.partnerships:
                other = self.persons[ps.partner]
                if other.partnership_with(person.id) is None:
                    other.partnerships.append(ps.mirrored(person.id))
                    warnings.append(f"{other.full_name}: added missing mirrored partnership.")
        return warnings

    # --- queries ------------------------------------------------------------------

    def get(self, pid):
        return self.persons.get(pid)

    def sorted_persons(self):
        return sorted(self.persons.values(), key=Person.sort_key)

    def parents_of(self, pid):
        person = self.persons.get(pid)
        if not person:
            return []
        parents = [self.persons[p] for p in person.parents if p in self.persons]
        # Conventional order: father left, mother right.
        order = {"male": 0, "unknown": 1, "diverse": 1, "female": 2}
        return sorted(parents, key=lambda p: order.get(p.gender, 1))

    def children_of(self, pid):
        kids = [p for p in self.persons.values() if pid in p.parents]
        return sorted(kids, key=lambda p: (dates.sort_year(p.birth_date), p.first_name.lower()))

    def partners_of(self, pid):
        person = self.persons.get(pid)
        if not person:
            return []
        return [(self.persons[ps.partner], ps) for ps in person.partnerships if ps.partner in self.persons]

    def is_ancestor(self, ancestor_id, person_id):
        """True if ancestor_id is a (strict) ancestor of person_id."""
        stack = list(self.persons[person_id].parents) if person_id in self.persons else []
        seen = set()
        while stack:
            pid = stack.pop()
            if pid == ancestor_id:
                return True
            if pid in seen or pid not in self.persons:
                continue
            seen.add(pid)
            stack.extend(self.persons[pid].parents)
        return False

    def check_parents(self, person_id, parent_ids):
        """Return an error message if parent_ids are not valid for person_id, else None."""
        parent_ids = [p for p in parent_ids if p]
        if len(parent_ids) > 2:
            return "A person can have at most two parents."
        if len(set(parent_ids)) != len(parent_ids):
            return "The same person was selected twice as parent."
        for pid in parent_ids:
            if pid == person_id:
                return "A person cannot be their own parent."
            if pid not in self.persons:
                return "Unknown parent selected."
            if person_id in self.persons and self.is_ancestor(person_id, pid):
                return f"{self.persons[pid].full_name} is a descendant of this person and cannot be a parent."
        return None

    # --- mutations ----------------------------------------------------------------

    def add_person(self, person):
        error = self.check_parents(person.id, person.parents)
        if error:
            raise ValueError(error)
        self.persons[person.id] = person
        self._sync_partnerships(person)
        self.dirty = True
        return person

    def update_person(self, person):
        """Replace the stored person with this (edited) version."""
        if person.id not in self.persons:
            raise KeyError(person.id)
        error = self.check_parents(person.id, person.parents)
        if error:
            raise ValueError(error)
        self.persons[person.id] = person
        self._sync_partnerships(person)
        self.dirty = True

    def add_parent(self, child_id, parent_id):
        child = self.persons[child_id]
        new_parents = child.parents + [parent_id]
        error = self.check_parents(child_id, new_parents)
        if error:
            raise ValueError(error)
        child.parents = new_parents
        self.dirty = True

    def delete_person(self, pid):
        if pid not in self.persons:
            return
        del self.persons[pid]
        for other in self.persons.values():
            other.parents = [p for p in other.parents if p != pid]
            other.partnerships = [ps for ps in other.partnerships if ps.partner != pid]
        self.dirty = True

    def reference_count(self, pid):
        """(children, partners) that refer to this person - shown before deleting."""
        children = sum(1 for p in self.persons.values() if pid in p.parents)
        person = self.persons.get(pid)
        return children, len(person.partnerships) if person else 0

    def _sync_partnerships(self, person):
        """Make every partner's list mirror this person's partnerships."""
        clean = []
        for ps in person.partnerships:
            if ps.partner == person.id or ps.partner not in self.persons:
                continue
            if any(c.partner == ps.partner for c in clean):
                continue
            clean.append(ps)
        person.partnerships = clean
        for other in self.persons.values():
            if other.id == person.id:
                continue
            mine = person.partnership_with(other.id)
            theirs = other.partnership_with(person.id)
            if mine and theirs:
                other.partnerships[other.partnerships.index(theirs)] = mine.mirrored(person.id)
            elif mine:
                other.partnerships.append(mine.mirrored(person.id))
            elif theirs:
                other.partnerships.remove(theirs)
