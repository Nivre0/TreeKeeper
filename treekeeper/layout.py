"""Positions for the tree view.

A layout returns a Layout: card centres for every shown person plus the
"family units" (shown parents -> shown children) and couples that the view
draws as lines. Coordinates are scene pixels, y grows downwards.

- layout_direct: ancestors and descendants of the focus person, built as two
  tidy trees (ancestors upwards, descendants downwards) on generation rows.
- layout_all: the whole connected family, laid out by Graphviz dot when it is
  available, otherwise by a small built-in layered layout.
"""

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

from . import dates
from .model import father_and_mother

CARD_W = 180
CARD_H = 64
H_GAP = 36          # between unrelated cards / siblings
COUPLE_GAP = 40     # between partners (room for the partnership line)
V_GAP = 90
ROW_H = CARD_H + V_GAP


@dataclass
class FamilyUnit:
    parents: tuple          # 1 or 2 shown parent ids
    children: list          # shown child ids
    origin_x: float = None  # optional x where the line to the children starts


@dataclass
class Layout:
    positions: dict = field(default_factory=dict)   # person id -> (x, y) card centre
    units: list = field(default_factory=list)
    engine: str = ""
    placeholders: dict = field(default_factory=dict)  # "father"/"mother" -> (x, y): missing parents of the focus


def add_parent_placeholders(tree, layout, focus_id):
    """Reserve a free spot above the focus person for each missing father/mother card."""
    focus = tree.get(focus_id)
    father, mother = father_and_mother(tree, focus.parents)
    missing = [role for role, pid in (("father", father), ("mother", mother)) if pid is None]
    if not missing:
        return layout
    fx, fy = layout.positions[focus_id]
    y = fy - ROW_H
    taken = [x for x, yy in layout.positions.values() if abs(yy - y) < CARD_H]
    step = CARD_W + COUPLE_GAP
    if len(missing) == 2:
        offsets, start = (-step / 2, step / 2), fx
    else:
        present = father or mother
        offsets = (0,)
        if present in layout.positions and abs(layout.positions[present][1] - y) < 1:
            px = layout.positions[present][0]
            start = px + step if missing[0] == "mother" else px - step
        else:
            start = fx

    def free(cx):
        return all(abs(cx + off - x) >= CARD_W + COUPLE_GAP for off in offsets for x in taken)

    # Nearest free position, searching outwards from the preferred one.
    for shift in range(0, 60):
        for cx in ((start + shift * step, start - shift * step) if shift else (start,)):
            if free(cx):
                for role, off in zip(missing, offsets):
                    layout.placeholders[role] = (cx + off, y)
                return layout
    return layout


def family_units(tree, shown):
    """Group shown children by their shown parents."""
    units = {}
    for pid in shown:
        person = tree.get(pid)
        parents = tuple(sorted(p for p in person.parents if p in shown))
        if parents:
            units.setdefault(parents, []).append(pid)
    result = []
    for parents, kids in units.items():
        kids.sort(key=lambda k: dates.sort_year(tree.get(k).birth_date))
        result.append(FamilyUnit(parents, kids))
    return result


# --- Mode 1: direct ancestors and descendants ----------------------------------------

def layout_direct(tree, focus_id):
    pos = {}

    def anc_width(pid, seen):
        if pid in seen:
            return CARD_W
        seen = seen | {pid}
        parents = [p.id for p in tree.parents_of(pid)]
        if not parents:
            return CARD_W
        total = sum(anc_width(p, seen) for p in parents) + H_GAP * (len(parents) - 1)
        return max(CARD_W, total)

    def place_ancestors(pid, cx, row, seen):
        pos[pid] = (cx, row * ROW_H)
        seen.add(pid)
        parents = [p.id for p in tree.parents_of(pid) if p.id not in seen and p.id not in pos]
        if not parents:
            return
        widths = [anc_width(p, set(seen)) for p in parents]
        total = sum(widths) + H_GAP * (len(parents) - 1)
        x = cx - total / 2
        for parent, w in zip(parents, widths):
            place_ancestors(parent, x + w / 2, row - 1, seen)
            x += w + H_GAP

    def desc_width(pid, seen):
        if pid in seen:
            return CARD_W
        seen = seen | {pid}
        kids = [c.id for c in tree.children_of(pid)]
        if not kids:
            return CARD_W
        total = sum(desc_width(k, seen) for k in kids) + H_GAP * (len(kids) - 1)
        return max(CARD_W, total)

    def place_descendants(pid, cx, row, seen):
        if pid != focus_id:
            pos[pid] = (cx, row * ROW_H)
        seen.add(pid)
        kids = [c.id for c in tree.children_of(pid) if c.id not in seen and c.id not in pos]
        if not kids:
            return
        widths = [desc_width(k, set(seen)) for k in kids]
        total = sum(widths) + H_GAP * (len(kids) - 1)
        x = cx - total / 2
        for kid, w in zip(kids, widths):
            place_descendants(kid, x + w / 2, row + 1, seen)
            x += w + H_GAP

    place_ancestors(focus_id, 0, 0, set())
    place_descendants(focus_id, 0, 0, {p for p in pos if p != focus_id})
    return add_parent_placeholders(tree, Layout(pos, family_units(tree, set(pos)), "generations"), focus_id)


# --- Mode 2: everyone connected to the focus person ----------------------------------

def connected_relatives(tree, focus_id):
    """All persons reachable via parent, child and partner links."""
    children = {}
    for person in tree.persons.values():
        for parent in person.parents:
            children.setdefault(parent, []).append(person.id)
    seen = {focus_id}
    stack = [focus_id]
    while stack:
        person = tree.get(stack.pop())
        neighbours = list(person.parents) + children.get(person.id, []) + [ps.partner for ps in person.partnerships]
        for n in neighbours:
            if n not in seen and tree.get(n):
                seen.add(n)
                stack.append(n)
    return seen


def couples(tree, shown):
    """Unordered partner pairs (a, b) with both shown, plus parent pairs without partnership."""
    pairs = set()
    for pid in shown:
        for ps in tree.get(pid).partnerships:
            if ps.partner in shown:
                pairs.add(tuple(sorted((pid, ps.partner))))
    for unit in family_units(tree, shown):
        if len(unit.parents) == 2:
            pairs.add(tuple(unit.parents))
    return sorted(pairs)

_GENDER_ORDER = {"male": 0, "unknown": 1, "diverse": 1, "female": 2}


def partner_blocks(tree, shown, linked=lambda a, b: True):
    """Groups of persons connected as couples, each as a left-to-right sequence.

    A person with several partners is placed between them (first partner left,
    later ones right), so every couple line runs between neighbouring cards.
    """
    adjacency = {pid: [] for pid in shown}
    for a, b in couples(tree, shown):
        if linked(a, b):
            adjacency[a].append(b)
            adjacency[b].append(a)

    def partner_order(pid):
        def key(other):
            ps = tree.get(pid).partnership_with(other)
            return (dates.sort_year(ps.start if ps else ""), dates.sort_year(tree.get(other).birth_date), other)
        return sorted(adjacency[pid], key=key)

    blocks, placed = [], set()
    for start in sorted(shown, key=lambda p: tree.get(p).sort_key()):
        if start in placed:
            continue
        component, stack = set(), [start]
        while stack:
            cur = stack.pop()
            if cur not in component:
                component.add(cur)
                stack.extend(adjacency[cur])
        hub = max(sorted(component), key=lambda m: len(adjacency[m]))
        seq, queue = [hub], [hub]
        placed.add(hub)
        while queue:
            cur = queue.pop(0)
            new = [p for p in partner_order(cur) if p not in placed]
            for i, partner in enumerate(new):
                idx = seq.index(cur)
                left_free, right_free = idx == 0, idx == len(seq) - 1
                if left_free and (not right_free or (i == 0 and len(new) > 1)):
                    seq.insert(0, partner)
                elif right_free:
                    seq.append(partner)
                else:
                    seq.insert(idx + 1, partner)
                placed.add(partner)
                queue.append(partner)
        if len(seq) == 2:
            a, b = (tree.get(p) for p in seq)
            if (_GENDER_ORDER.get(a.gender, 1), dates.sort_year(a.birth_date)) > \
                    (_GENDER_ORDER.get(b.gender, 1), dates.sort_year(b.birth_date)):
                seq.reverse()
        blocks.append(seq)
    return blocks


def block_width(block):
    return len(block) * CARD_W + (len(block) - 1) * COUPLE_GAP


def place_block(block, left, y, positions):
    for i, pid in enumerate(block):
        positions[pid] = (left + i * (CARD_W + COUPLE_GAP) + CARD_W / 2, y)


def find_dot():
    """Path to Graphviz dot: bundled copy first, then PATH, then default install dir."""
    candidates = []
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        candidates.append(os.path.join(base, "graphviz", "dot.exe"))
    found = shutil.which("dot")
    if found:
        candidates.append(found)
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(env):
            candidates.append(os.path.join(os.environ[env], "Graphviz", "bin", "dot.exe"))
    return next((c for c in candidates if os.path.isfile(c)), None)


def layout_all(tree, focus_id, use_graphviz=True):
    shown = connected_relatives(tree, focus_id)
    dot = find_dot() if use_graphviz else None
    result = None
    if dot:
        try:
            result = _layout_graphviz(tree, shown, dot)
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    if result is None:
        result = _layout_builtin(tree, shown, focus_id)
    return add_parent_placeholders(tree, result, focus_id)


def _dot_source(tree, shown, blocks):
    """One dot node per partner block: an HTML table with a port per card and per gap."""
    where = {}
    lines = [
        "digraph family {",
        f"  graph [rankdir=TB, nodesep={H_GAP / 72:.3f}, ranksep={V_GAP / 72:.3f}, splines=false];",
        "  node [shape=none, margin=0, width=0, height=0];",
        "  edge [arrowhead=none];",
    ]
    for bi, block in enumerate(blocks):
        cells = []
        for mi, pid in enumerate(block):
            if mi:
                cells.append(f'<TD WIDTH="{COUPLE_GAP}" HEIGHT="{CARD_H}" FIXEDSIZE="TRUE" PORT="u{mi}"></TD>')
            cells.append(f'<TD WIDTH="{CARD_W}" HEIGHT="{CARD_H}" FIXEDSIZE="TRUE" PORT="p{mi}"></TD>')
            where[pid] = (bi, mi)
        table = ('<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="0"><TR>'
                 + "".join(cells) + "</TR></TABLE>")
        lines.append(f"  b{bi} [label=<{table}>];")
    for unit in family_units(tree, shown):
        spots = sorted(where[p] for p in unit.parents)
        if len(spots) == 2 and spots[0][0] == spots[1][0] and spots[1][1] - spots[0][1] == 1:
            tail_block, tail = spots[0][0], f"b{spots[0][0]}:u{spots[1][1]}:s"
        else:
            tail_block, tail = spots[0][0], f"b{spots[0][0]}:p{spots[0][1]}:s"
        for kid in unit.children:
            kb, km = where[kid]
            if kb != tail_block:
                lines.append(f"  {tail} -> b{kb}:p{km}:n;")
    lines.append("}")
    return "\n".join(lines)


def _layout_graphviz(tree, shown, dot):
    blocks = partner_blocks(tree, shown)
    source = _dot_source(tree, shown, blocks)
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    result = subprocess.run([dot, "-Tplain"], input=source.encode("utf-8"), capture_output=True,
                            timeout=30, creationflags=flags)
    if result.returncode != 0:
        raise ValueError(result.stderr.decode("utf-8", "replace"))
    positions = {}
    height = 0.0
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if parts and parts[0] == "graph":
            height = float(parts[3])
        elif parts and parts[0] == "node":
            block = blocks[int(parts[1].strip('"')[1:])]
            cx, cy = float(parts[2]) * 72, (height - float(parts[3])) * 72
            place_block(block, cx - block_width(block) / 2, cy, positions)
    if set(positions) != shown:
        raise ValueError("Graphviz output incomplete")
    return Layout(positions, family_units(tree, shown), "Graphviz dot")


def _layout_builtin(tree, shown, focus_id):
    """Fallback: generation rows + barycenter ordering of partner blocks."""
    gen = {focus_id: 0}
    queue = [focus_id]
    children = {}
    for pid in shown:
        for parent in tree.get(pid).parents:
            children.setdefault(parent, []).append(pid)
    while queue:
        pid = queue.pop(0)
        person = tree.get(pid)
        steps = [(p, -1) for p in person.parents] + [(c, 1) for c in children.get(pid, [])] \
            + [(ps.partner, 0) for ps in person.partnerships]
        for other, delta in steps:
            if other in shown and other not in gen:
                gen[other] = gen[pid] + delta
                queue.append(other)

    blocks = partner_blocks(tree, shown, linked=lambda a, b: gen[a] == gen[b])
    rows = {}
    for i, block in enumerate(blocks):
        rows.setdefault(gen[block[0]], []).append(i)
    xpos = {}

    def assign_x():
        for row in rows.values():
            x = 0
            for b in row:
                for m in blocks[b]:
                    xpos[m] = x
                    x += 1

    def barycenter(b):
        linked = []
        for m in blocks[b]:
            linked += [p for p in tree.get(m).parents if p in xpos]
            linked += [c for c in children.get(m, []) if c in xpos]
        if not linked:
            return sum(xpos[m] for m in blocks[b]) / len(blocks[b])
        return sum(xpos[p] for p in linked) / len(linked)

    assign_x()
    for _ in range(6):
        for g in sorted(rows):
            rows[g].sort(key=barycenter)
            assign_x()

    positions = {}
    for g, row in rows.items():
        total = sum(block_width(blocks[b]) for b in row) + H_GAP * (len(row) - 1)
        left = -total / 2
        for b in row:
            place_block(blocks[b], left, g * ROW_H, positions)
            left += block_width(blocks[b]) + H_GAP
    return Layout(positions, family_units(tree, shown), "built-in")
