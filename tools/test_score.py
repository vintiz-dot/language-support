"""Tests for the scoring harness.

A scorer that reports success on everything is worse than no scorer, so each test
introduces one specific error into a perfect prediction and asserts the harness both
catches it and attributes it to the right dimension.

The load-bearing case is swap_detected: entities perfect, roles zero. If that one ever
passes silently the harness is not doing its job.

    pytest tools/test_score.py
"""

import copy
from collections import defaultdict

import pytest

from score import load_gold, new_tally, score_pair

GOLD = load_gold()


def score_one(pred, gold):
    tally = new_tally()
    detail = defaultdict(list)
    score_pair(pred, gold, tally, detail)
    return tally, detail


def perfect(graph_id):
    """A prediction identical to gold. Every test starts here and breaks one thing."""
    return copy.deepcopy(GOLD[graph_id]), GOLD[graph_id]


def rename_entities(graph, mapping):
    """Rewrite entity ids everywhere they appear, to prove scoring is id-independent."""
    graph["entities"] = {mapping.get(k, k): v for k, v in graph["entities"].items()}
    for entity in graph["entities"].values():
        for field in ("possessor", "coref"):
            if entity.get(field) in mapping:
                entity[field] = mapping[entity[field]]
    for event in graph["events"]:
        roles = event.get("roles") or {}
        for role, filler in list(roles.items()):
            roles[role] = mapping.get(filler, filler)
        for spatial in event.get("spatial") or []:
            if spatial.get("figure") in mapping:
                spatial["figure"] = mapping[spatial["figure"]]
            ground = spatial.get("ground")
            if isinstance(ground, list):
                spatial["ground"] = [mapping.get(g, g) for g in ground]
            elif ground in mapping:
                spatial["ground"] = mapping[ground]
        if event.get("comparand") in mapping:
            event["comparand"] = mapping[event["comparand"]]
    for span in graph.get("alignment") or []:
        span["node"] = mapping.get(span["node"], span["node"])
    return graph


RESULTS = []


def check(name, condition, note=""):
    RESULTS.append((name, bool(condition), note))


# --- a perfect prediction scores perfectly ------------------------------------

for graph_id in ("g001", "g032", "g044", "g057"):
    pred, gold = perfect(graph_id)
    tally, _ = score_one(pred, gold)
    check(
        f"perfect prediction is perfect ({graph_id})",
        tally["scene_correct"] == 1
        and tally["entities"]["fn"] == 0
        and tally["entities"]["fp"] == 0
        and tally["entities"]["wrong_concept"] == 0
        and tally["roles"]["correct"] == tally["roles"]["total"]
        and tally["alignment"]["exact"] == tally["alignment"]["n"],
    )

# --- the identity property, over the whole gold set ---------------------------
# Every gold graph scored against itself must be perfect. This caught a real bug:
# implicit entities carry no token span, so span matching could not reach them and
# they read as spurious on one side and missing on the other.

identity_failures = []
for _gid, _gold in GOLD.items():
    _tally, _detail = score_one(copy.deepcopy(_gold), _gold)
    if not _tally["scene_correct"]:
        identity_failures.append((_gid, _detail[_gid]))

check(
    f"every gold graph scores perfectly against itself ({len(GOLD)} graphs)",
    not identity_failures,
    "; ".join(f"{gid}: {msgs}" for gid, msgs in identity_failures[:3]),
)

# --- scoring must not depend on entity ids ------------------------------------

pred, gold = perfect("g001")
pred = rename_entities(pred, {"e1": "e77", "e2": "e88"})
tally, _ = score_one(pred, gold)
check(
    "renamed entity ids still score perfectly",
    tally["scene_correct"] == 1 and tally["roles"]["correct"] == tally["roles"]["total"],
    "correspondence comes from token spans, not from ids matching",
)

# --- the failure the harness exists for ---------------------------------------

pred, gold = perfect("g001")
roles = pred["events"][0]["roles"]
roles["agent"], roles["patient"] = roles["patient"], roles["agent"]
tally, detail = score_one(pred, gold)
check(
    "swap detected: entities perfect",
    tally["entities"]["tp"] == 2
    and tally["entities"]["fn"] == 0
    and tally["entities"]["fp"] == 0
    and tally["entities"]["wrong_concept"] == 0,
)
check("swap detected: roles zero", tally["roles"]["correct"] == 0 and tally["roles"]["total"] == 2)
check(
    "swap detected: conditioned score also zero",
    tally["roles_given_entities"]["correct"] == 0
    and tally["roles_given_entities"]["total"] == 2,
    "this is the number that isolates roles from entity recognition",
)
check("swap detected: counted as an argument swap", tally["argument_swaps"] == 1)
check("swap detected: scene marked wrong", tally["scene_correct"] == 0)
check(
    "swap detected: reported in the detail log",
    any("ARGUMENT SWAP" in m for m in detail["g001"]),
)

# --- a sense error is not a segmentation error --------------------------------

pred, gold = perfect("g048")
pred["entities"]["e1"]["concept"] = "bat.sport"
tally, _ = score_one(pred, gold)
check(
    "wrong sense counted apart from a miss",
    tally["entities"]["wrong_concept"] == 1
    and tally["entities"]["fn"] == 0
    and tally["entities"]["fp"] == 0,
)
check(
    "wrong sense excludes the event from the conditioned role score",
    tally["roles"]["total"] > 0 and tally["roles_given_entities"]["total"] == 0,
    "roles are only conditioned on events whose entities were all recognised",
)

# --- a wrong preposition is a spatial error, not a role error -----------------

pred, gold = perfect("g032")
pred["events"][0]["spatial"][0]["relation"] = "in"
tally, _ = score_one(pred, gold)
check(
    "wrong preposition hits spatial only",
    tally["spatial"]["relation"]["correct"] == 0
    and tally["spatial"]["ground"]["correct"] == 1
    and tally["spatial"]["figure"]["correct"] == 1
    and tally["roles"]["correct"] == tally["roles"]["total"],
)
check("wrong preposition marks the scene wrong", tally["scene_correct"] == 0)

# --- discourse direction is scored apart from discourse type ------------------

pred, gold = perfect("g044")
relation = pred["discourse"][0]
relation["from"], relation["to"] = relation["to"], relation["from"]
tally, _ = score_one(pred, gold)
check(
    "reversed arrow: type still correct",
    tally["discourse"]["type"]["correct"] == 1,
)
check(
    "reversed arrow: direction wrong and counted",
    tally["discourse"]["direction"]["correct"] == 0 and tally["discourse"]["reversed"] == 1,
    "because reverses the arrow against text order; this is the g044 hazard",
)

# --- features ------------------------------------------------------------------

pred, gold = perfect("g010")
pred["events"][0]["tense"] = "present"
tally, _ = score_one(pred, gold)
check(
    "wrong tense hits the tense feature only",
    tally["features"]["tense"]["correct"] == 0
    and tally["features"]["aspect"]["correct"] == 1
    and tally["roles"]["correct"] == tally["roles"]["total"],
)

pred, gold = perfect("g060")
del pred["events"][0]["irrealis"]
tally, _ = score_one(pred, gold)
check(
    "dropped irrealis is caught",
    tally["features"]["irrealis"]["correct"] == 0
    and tally["features"]["irrealis"]["total"] == 1,
)

# --- missing and spurious entities --------------------------------------------

pred, gold = perfect("g001")
del pred["entities"]["e2"]
del pred["events"][0]["roles"]["patient"]
pred["alignment"] = [s for s in pred["alignment"] if s["node"] != "e2"]
tally, _ = score_one(pred, gold)
check("missing entity counted as a miss", tally["entities"]["fn"] == 1)

pred, gold = perfect("g001")
pred["entities"]["e9"] = {"concept": "bird", "number": "sg"}
pred["alignment"].append({"node": "e9", "tokens": [5]})
tally, _ = score_one(pred, gold)
check("spurious entity counted as spurious", tally["entities"]["fp"] == 1)

# --- alignment quality ----------------------------------------------------------

pred, gold = perfect("g001")
for span in pred["alignment"]:
    if span["node"] == "e1":
        span["tokens"] = [1]  # gold is [0, 1]: right head, missing determiner
tally, _ = score_one(pred, gold)
check(
    "partial alignment scores below exact but still matches",
    tally["alignment"]["exact"] < tally["alignment"]["n"]
    and tally["roles"]["correct"] == tally["roles"]["total"],
    "a span that overlaps still resolves correspondence, so roles survive",
)


@pytest.mark.parametrize(
    "passed,note",
    [pytest.param(passed, note, id=name) for name, passed, note in RESULTS],
)
def test_harness_behaviour(passed, note):
    assert passed, note or "harness did not report the expected result"
