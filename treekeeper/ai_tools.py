"""Operations AI assistants may perform through the MCP server.

Tools run in the GUI thread on the file that is open in the main window, so
every change shows up immediately and is saved like a manual edit (the window
title gets its "unsaved changes" star).
"""

from . import dates
from .model import GENDERS, PARTNERSHIP_STATUSES, PARTNERSHIP_TYPES, Partnership, Person, father_and_mother

DATE_HELP = ("Text date: '12.03.1923' (day.month.year), '03.1923', '1923', optionally prefixed "
             "with 'ca. ', 'before ' or 'after ' (e.g. 'ca. 1880'). Empty string = unknown.")
NAME_FIELDS = ("first_name", "middle_name", "last_name", "birth_name")
TEXT_FIELDS = NAME_FIELDS + ("birth_place", "death_place", "notes")
DATE_FIELDS = ("birth_date", "death_date")

PERSON_PROPERTIES = {
    "first_name": {"type": "string"},
    "middle_name": {"type": "string"},
    "last_name": {"type": "string", "description": "Current surname."},
    "birth_name": {"type": "string", "description": "Surname at birth (maiden name), if different."},
    "gender": {"type": "string", "enum": list(GENDERS)},
    "birth_date": {"type": "string", "description": DATE_HELP},
    "birth_place": {"type": "string"},
    "death_date": {"type": "string", "description": DATE_HELP + " Use '?' if the person died but the date "
                                                                  "is unknown; leave empty for living persons."},
    "death_place": {"type": "string"},
    "parents": {"type": "array", "items": {"type": "string"}, "maxItems": 2,
                "description": "Ids of the person's parents (at most two: father and mother). "
                               "Replaces the current parents; [] removes them."},
    "notes": {"type": "string"},
}
PARTNERSHIP_PROPERTIES = {
    "type": {"type": "string", "enum": list(PARTNERSHIP_TYPES), "default": "marriage"},
    "status": {"type": "string", "enum": list(PARTNERSHIP_STATUSES), "default": "current",
               "description": "current, divorced, separated, or widowed (ended by death)."},
    "from": {"type": "string", "description": "Start date. " + DATE_HELP},
    "to": {"type": "string", "description": "End date. " + DATE_HELP},
}


class ToolError(Exception):
    """A problem the AI should see as a tool error (bad id, invalid value, ...)."""


def _schema(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


class TreeTools:
    def __init__(self, window):
        self.window = window
        self._tools = {
            "get_file_info": (
                "Information about the file open in TreeKeeper: path, number of persons, "
                "whether there are unsaved changes, and the person currently in focus.",
                _schema({}), self.get_file_info),
            "list_persons": (
                "List persons (id, name, lifespan, gender), sorted by last name. "
                "Optional query: every word must occur in first, middle, last or birth name.",
                _schema({"query": {"type": "string"}}), self.list_persons),
            "get_person": (
                "All details of one person, including parents, children and partnerships with names.",
                _schema({"id": {"type": "string"}}, ["id"]), self.get_person),
            "create_person": (
                "Create a new person. At least first_name or last_name is required. "
                "Returns the new person including its id.",
                _schema(PERSON_PROPERTIES), self.create_person),
            "update_person": (
                "Change fields of an existing person. Only the given fields change. "
                "Use set_partnership / remove_partnership for partners.",
                _schema({"id": {"type": "string"}, **PERSON_PROPERTIES}, ["id"]), self.update_person),
            "delete_person": (
                "Delete a person. References to them (as parent or partner) are removed from everyone else.",
                _schema({"id": {"type": "string"}}, ["id"]), self.delete_person),
            "set_partnership": (
                "Create or update the partnership between two persons. It is stored on both automatically.",
                _schema({"person_id": {"type": "string"}, "partner_id": {"type": "string"},
                         **PARTNERSHIP_PROPERTIES}, ["person_id", "partner_id"]), self.set_partnership),
            "remove_partnership": (
                "Remove the partnership between two persons (from both sides).",
                _schema({"person_id": {"type": "string"}, "partner_id": {"type": "string"}},
                        ["person_id", "partner_id"]), self.remove_partnership),
            "show_person": (
                "Make a person the focus of the tree view in the app, optionally switching the view.",
                _schema({"id": {"type": "string"},
                         "view": {"type": "string", "enum": ["ancestors_and_descendants", "whole_family"]}},
                        ["id"]), self.show_person),
            "save_file": (
                "Save all changes to the open file. Fails if the file has never been saved; "
                "then ask the user to use File › Save as in TreeKeeper.",
                _schema({}), self.save_file),
        }

    @property
    def tree(self):
        return self.window.tree

    def names(self):
        return list(self._tools)

    def definitions(self):
        return [{"name": name, "description": description, "inputSchema": schema}
                for name, (description, schema, _) in self._tools.items()]

    def call(self, name, arguments):
        if not isinstance(arguments, dict):
            raise ToolError("Arguments must be an object.")
        _, schema, fn = self._tools[name]
        unknown = set(arguments) - set(schema["properties"])
        if unknown:
            raise ToolError(f"Unknown argument(s): {', '.join(sorted(unknown))}")
        missing = [key for key in schema["required"] if not arguments.get(key)]
        if missing:
            raise ToolError(f"Missing argument(s): {', '.join(missing)}")
        return fn(**arguments)

    # --- helpers --------------------------------------------------------------------

    def _person(self, pid):
        person = self.tree.get(pid)
        if person is None:
            raise ToolError(f"No person with id {pid!r}. Use list_persons to find ids.")
        return person

    @staticmethod
    def _check_date(field, value, allow_unknown=False):
        if not isinstance(value, str):
            raise ToolError(f"{field} must be a string.")
        value = value.strip()
        if value and not (allow_unknown and value == "?") and dates.parse_date(value) is None:
            raise ToolError(f"{field}: {value!r} is not a valid date. {DATE_HELP}")
        return value

    def _apply_fields(self, person, fields):
        for key, value in fields.items():
            if key in TEXT_FIELDS:
                if not isinstance(value, str):
                    raise ToolError(f"{key} must be a string.")
                setattr(person, key, value.strip())
            elif key in DATE_FIELDS:
                setattr(person, key, self._check_date(key, value, allow_unknown=key == "death_date"))
            elif key == "gender":
                if value not in GENDERS:
                    raise ToolError(f"gender must be one of {', '.join(GENDERS)}.")
                person.gender = value
            elif key == "parents":
                if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                    raise ToolError("parents must be a list of person ids.")
                for pid in value:
                    self._person(pid)
                error = self.tree.check_parents(person.id, value)
                if error:
                    raise ToolError(error)
                if set(value) & {ps.partner for ps in person.partnerships}:
                    raise ToolError("A parent cannot also be a partner of the same person.")
                person.parents = list(value)
        if not (person.first_name or person.last_name):
            raise ToolError("A person needs at least a first_name or last_name.")

    def _changed(self, message, focus=None):
        self.window.refresh_after_external_change(f"AI: {message}", focus)

    def summary(self, person):
        return {"id": person.id, "name": person.full_name, "lifespan": person.lifespan,
                "gender": person.gender, "deceased": person.deceased}

    def details(self, person):
        info = person.to_dict()
        info["name"] = person.full_name
        info["lifespan"] = person.lifespan
        info["deceased"] = person.deceased
        father, mother = father_and_mother(self.tree, person.parents)
        info["father"] = self.summary(self.tree.get(father)) if father else None
        info["mother"] = self.summary(self.tree.get(mother)) if mother else None
        info["children"] = [self.summary(c) for c in self.tree.children_of(person.id)]
        for entry in info["partnerships"]:
            entry["partner_name"] = self.tree.get(entry["partner"]).full_name
        return info

    # --- tools ----------------------------------------------------------------------

    def get_file_info(self):
        tree = self.tree
        return {"path": tree.path, "person_count": len(tree.persons), "unsaved_changes": tree.dirty,
                "focus_person": self.summary(tree.get(self.window.focus_id)) if self.window.focus_id else None}

    def list_persons(self, query=""):
        return [self.summary(p) for p in self.tree.sorted_persons() if not query or p.matches(query)]

    def get_person(self, id):
        return self.details(self._person(id))

    def create_person(self, **fields):
        person = Person()
        self._apply_fields(person, fields)
        try:
            self.tree.add_person(person)
        except ValueError as e:
            raise ToolError(str(e))
        self._changed(f"added {person.full_name}", focus=person.id)
        return self.details(person)

    def update_person(self, id, **fields):
        person = self._person(id).copy()
        self._apply_fields(person, fields)
        try:
            self.tree.update_person(person)
        except ValueError as e:
            raise ToolError(str(e))
        self._changed(f"edited {person.full_name}")
        return self.details(self.tree.get(id))

    def delete_person(self, id):
        person = self._person(id)
        self.tree.delete_person(id)
        self._changed(f"deleted {person.full_name}")
        return {"deleted": self.summary(person)}

    def set_partnership(self, person_id, partner_id, **fields):
        person = self._person(person_id).copy()
        partner = self._person(partner_id)
        if person_id == partner_id:
            raise ToolError("A person cannot be their own partner.")
        if partner_id in person.parents or person_id in partner.parents:
            raise ToolError("A parent cannot also be a partner of the same person.")
        existing = person.partnership_with(partner_id)
        ps = existing or Partnership(partner_id)
        if "type" in fields:
            if fields["type"] not in PARTNERSHIP_TYPES:
                raise ToolError(f"type must be one of {', '.join(PARTNERSHIP_TYPES)}.")
            ps.type = fields["type"]
        if "status" in fields:
            if fields["status"] not in PARTNERSHIP_STATUSES:
                raise ToolError(f"status must be one of {', '.join(PARTNERSHIP_STATUSES)}.")
            ps.status = fields["status"]
        if "from" in fields:
            ps.start = self._check_date("from", fields["from"])
        if "to" in fields:
            ps.end = self._check_date("to", fields["to"])
        if not existing:
            person.partnerships.append(ps)
        self.tree.update_person(person)
        self._changed(f"{'updated' if existing else 'added'} partnership {person.full_name} – {partner.full_name}")
        return self.details(self.tree.get(person_id))

    def remove_partnership(self, person_id, partner_id):
        person = self._person(person_id).copy()
        partner = self._person(partner_id)
        if not person.partnership_with(partner_id):
            raise ToolError(f"{person.full_name} and {partner.full_name} have no partnership.")
        person.partnerships = [ps for ps in person.partnerships if ps.partner != partner_id]
        self.tree.update_person(person)
        self._changed(f"removed partnership {person.full_name} – {partner.full_name}")
        return self.details(self.tree.get(person_id))

    def show_person(self, id, view=None):
        person = self._person(id)
        if view:
            self.window.set_view_mode(view)
        self.window.set_focus(id)
        return {"focus_person": self.summary(person), "view": self.window.view_mode_name()}

    def save_file(self):
        if not self.tree.path:
            raise ToolError("This file has never been saved. Ask the user to use File › Save as in TreeKeeper.")
        if not self.window._save(self.tree.path):
            raise ToolError("Saving failed; TreeKeeper showed the error to the user.")
        return self.get_file_info()
