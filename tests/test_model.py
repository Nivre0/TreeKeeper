import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from treekeeper import dates, layout  # noqa: E402
from treekeeper.model import TreeKeeper, Partnership, Person  # noqa: E402

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "treekeeper", "resources", "sample_family.json")


def by_name(tree, first):
    return next(p for p in tree.persons.values() if p.first_name == first)


class DatesTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(dates.parse_year("1923"), (1923, ""))
        self.assertEqual(dates.parse_year("12.03.1923"), (1923, ""))
        self.assertEqual(dates.parse_year("1923-03-12"), (1923, ""))
        self.assertEqual(dates.parse_year("ca. 1880"), (1880, "c."))
        self.assertEqual(dates.parse_year("before 1900"), (1900, "bef."))
        self.assertEqual(dates.parse_year("?"), (None, ""))

    def test_lifespan(self):
        self.assertEqual(dates.lifespan("1923", "1998", True), "1923–1998")
        self.assertEqual(dates.lifespan("1950", "", False), "1950–")
        self.assertEqual(dates.lifespan("", "1998", True), "?–1998")
        self.assertEqual(dates.lifespan("ca. 1880", "?", True), "c. 1880–?")
        self.assertEqual(dates.lifespan("", "", False), "")

    def test_parse_date(self):
        self.assertEqual(dates.parse_date("12.03.1923"), ("", 12, 3, 1923))
        self.assertEqual(dates.parse_date("1923-03-12"), ("", 12, 3, 1923))
        self.assertEqual(dates.parse_date("03.1923"), ("", None, 3, 1923))
        self.assertEqual(dates.parse_date("about 1961"), ("c.", None, None, 1961))
        self.assertEqual(dates.parse_date("before 1900"), ("bef.", None, None, 1900))
        self.assertEqual(dates.parse_date(""), ("", None, None, None))
        self.assertIsNone(dates.parse_date("spring 1923"))
        self.assertIsNone(dates.parse_date("31.02.1923"))

    def test_format_date_roundtrip(self):
        for parts in (("", 12, 3, 1923), ("c.", None, 3, 1880), ("aft.", None, None, 1900)):
            self.assertEqual(dates.parse_date(dates.format_date(*parts)), parts)
        self.assertEqual(dates.format_date("c.", None, None, 1880), "ca. 1880")
        self.assertEqual(dates.format_date("", None, None, None), "")

    def test_date_error(self):
        self.assertIsNone(dates.date_error(29, 2, 1924))
        self.assertIsNotNone(dates.date_error(29, 2, 1923))
        self.assertIsNotNone(dates.date_error(5, None, 1923))
        self.assertIsNotNone(dates.date_error(None, 4, None))


class DateEditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def make(self, text):
        from treekeeper.date_edit import DateEdit
        edit = DateEdit()
        edit.set_text(text)
        return edit

    def test_roundtrip_and_edit(self):
        edit = self.make("ca. 03.1880")
        self.assertEqual(edit.text(), "ca. 03.1880")
        edit.day.setCurrentIndex(15)
        edit.qualifier.setCurrentIndex(0)
        self.assertEqual(edit.text(), "15.03.1880")

    def test_legacy_text_kept_until_changed(self):
        edit = self.make("spring 1923")
        self.assertEqual(edit.text(), "spring 1923")
        self.assertEqual(edit.year.value(), 1923)
        edit.month.setCurrentIndex(4)
        self.assertEqual(edit.text(), "04.1923")

    def test_calendar_pick_and_errors(self):
        from PySide6.QtCore import QDate
        edit = self.make("")
        self.assertEqual(edit.text(), "")
        edit._pick_from_calendar(QDate(1950, 7, 4))
        self.assertEqual(edit.text(), "04.07.1950")
        edit.month.setCurrentIndex(0)
        self.assertIsNotNone(edit.error())
        edit.year.setValue(0)
        edit.year.stepBy(1)
        self.assertEqual(edit.year.value(), 1900)


class ModelTest(unittest.TestCase):
    def setUp(self):
        self.tree = TreeKeeper()
        self.a = self.tree.add_person(Person(first_name="A", gender="male"))
        self.b = self.tree.add_person(Person(first_name="B", gender="female"))
        self.c = self.tree.add_person(Person(first_name="C", parents=[self.a.id, self.b.id]))

    def test_children_derived(self):
        self.assertEqual([p.id for p in self.tree.children_of(self.a.id)], [self.c.id])

    def test_partnership_mirrored_and_removed(self):
        a = self.a.copy()
        a.partnerships.append(Partnership(self.b.id, "marriage", "divorced", "1950", "1960"))
        self.tree.update_person(a)
        mirror = self.tree.get(self.b.id).partnership_with(self.a.id)
        self.assertEqual((mirror.status, mirror.start, mirror.end), ("divorced", "1950", "1960"))
        # editing from the other side updates the first side
        b = self.tree.get(self.b.id).copy()
        b.partnerships[0].status = "separated"
        self.tree.update_person(b)
        self.assertEqual(self.tree.get(self.a.id).partnerships[0].status, "separated")
        # removing on one side removes on both
        a = self.tree.get(self.a.id).copy()
        a.partnerships = []
        self.tree.update_person(a)
        self.assertEqual(self.tree.get(self.b.id).partnerships, [])

    def test_delete_removes_references(self):
        a = self.a.copy()
        a.partnerships.append(Partnership(self.b.id))
        self.tree.update_person(a)
        self.tree.delete_person(self.b.id)
        self.assertEqual(self.tree.get(self.c.id).parents, [self.a.id])
        self.assertEqual(self.tree.get(self.a.id).partnerships, [])

    def test_cycles_rejected(self):
        a = self.a.copy()
        a.parents = [self.c.id]
        with self.assertRaises(ValueError):
            self.tree.update_person(a)
        self.assertIsNotNone(self.tree.check_parents(self.a.id, [self.a.id]))
        self.assertIsNotNone(self.tree.check_parents(self.c.id, [self.a.id, self.b.id, self.a.id]))

    def test_load_repairs(self):
        raw = [
            {"id": "1", "first_name": "X", "parents": ["missing", "1"],
             "partnerships": [{"partner": "2", "type": "marriage", "status": "current"}]},
            {"id": "2", "first_name": "Y"},
        ]
        tree = TreeKeeper.from_json_data(raw)
        self.assertEqual(tree.get("1").parents, [])
        self.assertIsNotNone(tree.get("2").partnership_with("1"))
        self.assertTrue(tree.warnings)

    def test_save_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.json")
            self.tree.save(path)
            loaded = TreeKeeper.load(path)
        self.assertEqual({p.id: p.to_dict() for p in loaded.persons.values()},
                         {p.id: p.to_dict() for p in self.tree.persons.values()})
        self.assertFalse(loaded.warnings)


class SampleAndLayoutTest(unittest.TestCase):
    def setUp(self):
        self.tree = TreeKeeper.load(SAMPLE)

    def test_sample_is_consistent(self):
        self.assertFalse(self.tree.warnings)
        self.assertGreaterEqual(len(self.tree.persons), 15)
        walter = by_name(self.tree, "Walter")
        self.assertEqual(len(self.tree.children_of(walter.id)), 2)
        statuses = {ps.status for ps in walter.partnerships}
        self.assertIn("divorced", statuses)

    def assert_no_overlap(self, positions):
        items = list(positions.items())
        for i, (a, (ax, ay)) in enumerate(items):
            for b, (bx, by) in items[i + 1:]:
                overlap = abs(ax - bx) < layout.CARD_W and abs(ay - by) < layout.CARD_H
                self.assertFalse(overlap, f"cards overlap: {self.tree.get(a).full_name} / {self.tree.get(b).full_name}")

    def test_direct_layout(self):
        thomas = by_name(self.tree, "Thomas")
        result = layout.layout_direct(self.tree, thomas.id)
        names = {self.tree.get(p).first_name for p in result.positions}
        self.assertEqual(names, {"Thomas", "Walter", "Elisabeth", "Heinrich", "Anna", "Josef", "Rosa", "Lukas", "Nina"})
        y = {self.tree.get(p).first_name: xy[1] for p, xy in result.positions.items()}
        self.assertLess(y["Heinrich"], y["Walter"])
        self.assertLess(y["Walter"], y["Thomas"])
        self.assertLess(y["Thomas"], y["Lukas"])
        self.assertEqual(y["Heinrich"], y["Rosa"])
        self.assert_no_overlap(result.positions)

    def _check_all_layout(self, result):
        self.assertEqual(len(result.positions), len(self.tree.persons))
        self.assert_no_overlap(result.positions)
        y = {self.tree.get(p).first_name: xy[1] for p, xy in result.positions.items()}
        self.assertLess(y["Walter"], y["Thomas"])
        self.assertEqual(y["Thomas"], y["Ruth"])
        self.assertEqual(y["Walter"], y["Hedwig"])

    def test_all_layout_builtin(self):
        result = layout.layout_all(self.tree, by_name(self.tree, "Thomas").id, use_graphviz=False)
        self.assertEqual(result.engine, "built-in")
        self._check_all_layout(result)

    @unittest.skipUnless(layout.find_dot(), "Graphviz not installed")
    def test_all_layout_graphviz(self):
        result = layout.layout_all(self.tree, by_name(self.tree, "Thomas").id)
        self.assertEqual(result.engine, "Graphviz dot")
        self._check_all_layout(result)


if __name__ == "__main__":
    unittest.main()
