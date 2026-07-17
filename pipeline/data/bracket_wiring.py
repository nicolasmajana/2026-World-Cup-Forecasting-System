"""The fixed 2026 knockout bracket wiring (FIFA structure, via openfootball).

This is hardcoded on purpose: the live feed replaces slot refs ("1E", "W74")
with real team names as the tournament resolves, so anything that needs the
STRUCTURE (the simulation, the resolver) must not depend on the feed's
current labels. Slot refs: 1A = winner of Group A, 2B = runner-up,
3A/B/C/D/F = a qualifying third-place team from one of those groups,
W74 / L101 = winner / loser of that match number. The feed numbers the
Final and third-place match itself (confirmed from the live 2026 feed):
103 = third-place match, 104 = Final. The round-label fallback below only
applies if a future feed omits "num" for these two matches.
"""

WIRES = [
    {"num": 73, "round": "r32", "ref1": "2A", "ref2": "2B"},
    {"num": 74, "round": "r32", "ref1": "1E", "ref2": "3A/B/C/D/F"},
    {"num": 75, "round": "r32", "ref1": "1F", "ref2": "2C"},
    {"num": 76, "round": "r32", "ref1": "1C", "ref2": "2F"},
    {"num": 77, "round": "r32", "ref1": "1I", "ref2": "3C/D/F/G/H"},
    {"num": 78, "round": "r32", "ref1": "2E", "ref2": "2I"},
    {"num": 79, "round": "r32", "ref1": "1A", "ref2": "3C/E/F/H/I"},
    {"num": 80, "round": "r32", "ref1": "1L", "ref2": "3E/H/I/J/K"},
    {"num": 81, "round": "r32", "ref1": "1D", "ref2": "3B/E/F/I/J"},
    {"num": 82, "round": "r32", "ref1": "1G", "ref2": "3A/E/H/I/J"},
    {"num": 83, "round": "r32", "ref1": "2K", "ref2": "2L"},
    {"num": 84, "round": "r32", "ref1": "1H", "ref2": "2J"},
    {"num": 85, "round": "r32", "ref1": "1B", "ref2": "3E/F/G/I/J"},
    {"num": 86, "round": "r32", "ref1": "1J", "ref2": "2H"},
    {"num": 87, "round": "r32", "ref1": "1K", "ref2": "3D/E/I/J/L"},
    {"num": 88, "round": "r32", "ref1": "2D", "ref2": "2G"},
    {"num": 89, "round": "r16", "ref1": "W74", "ref2": "W77"},
    {"num": 90, "round": "r16", "ref1": "W73", "ref2": "W75"},
    {"num": 91, "round": "r16", "ref1": "W76", "ref2": "W78"},
    {"num": 92, "round": "r16", "ref1": "W79", "ref2": "W80"},
    {"num": 93, "round": "r16", "ref1": "W83", "ref2": "W84"},
    {"num": 94, "round": "r16", "ref1": "W81", "ref2": "W82"},
    {"num": 95, "round": "r16", "ref1": "W86", "ref2": "W88"},
    {"num": 96, "round": "r16", "ref1": "W85", "ref2": "W87"},
    {"num": 97, "round": "qf", "ref1": "W89", "ref2": "W90"},
    {"num": 98, "round": "qf", "ref1": "W93", "ref2": "W94"},
    {"num": 99, "round": "qf", "ref1": "W91", "ref2": "W92"},
    {"num": 100, "round": "qf", "ref1": "W95", "ref2": "W96"},
    {"num": 101, "round": "sf", "ref1": "W97", "ref2": "W98"},
    {"num": 102, "round": "sf", "ref1": "W99", "ref2": "W100"},
    {"num": 103, "round": "3p", "ref1": "L101", "ref2": "L102"},
    {"num": 104, "round": "f", "ref1": "W101", "ref2": "W102"},
]

FINAL_NUM = 104
THIRD_PLACE_NUM = 103

# Third-place slots: "num:side" -> set of groups that slot may receive
THIRD_SLOTS = [
    (f"{w['num']}:{side}", set(w[ref][1:].split("/")))
    for w in WIRES
    for side, ref in (("1", "ref1"), ("2", "ref2"))
    if w[ref].startswith("3") and "/" in w[ref]
]


def feed_num(match: dict) -> int | None:
    """Stable match number for an openfootball match entry (group or KO)."""
    num = match.get("num")
    if num is not None:
        return int(num)
    rnd = match.get("round", "")
    if rnd == "Final":
        return FINAL_NUM
    if "third" in rnd.lower():
        return THIRD_PLACE_NUM
    return None
