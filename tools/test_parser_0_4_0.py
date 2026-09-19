"""Schema 0.4.0: coordinated noun phrases, focus particles, measure phrases.

Every sentence here belongs to no gold set. Set three is drawn but unannotated and nothing
in this file is taken from it.

    pytest tools/test_parser_0_4_0.py
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from parser.rules import parse, _nlp  # noqa: E402


def run(text):
    return parse(text, tokens=[t.text for t in _nlp().tokenizer(text)])


def concepts(graph, refs):
    return {graph["entities"][r].get("concept") for r in refs}


def group_of(graph):
    return next((e for e in graph["entities"].values() if e.get("members")), None)


# --- coordinated noun phrases ----------------------------------------------------------
# At 0.3.0 these became duplicate events sharing a verb token. Harmless for a distributive
# verb, wrong for a collective one.


def test_a_coordinated_subject_is_one_group():
    graph = run("The cup and the plate broke.")
    group = group_of(graph)
    assert group is not None, "no group entity built"
    assert concepts(graph, group["members"]) == {"cup", "plate"}
    assert group["coordination"] == "and"


def test_the_group_fills_the_role_not_its_members():
    graph = run("The cup and the plate broke.")
    agent = graph["events"][0]["roles"]["agent"]
    assert graph["entities"][agent].get("members"), "the role points at a member, not the group"


def test_one_event_not_two():
    assert len(run("The cup and the plate broke.")["events"]) == 1


def test_a_coordinated_object_is_a_group():
    graph = run("She washed the cup and the plate.")
    patient = graph["events"][0]["roles"]["patient"]
    assert concepts(graph, graph["entities"][patient]["members"]) == {"cup", "plate"}


def test_or_is_not_and():
    graph = run("He eats apples or pears.")
    group = group_of(graph)
    assert group["coordination"] == "or"


def test_an_alternative_is_not_a_plurality():
    """You get one of them, so the group is not plural."""
    assert group_of(run("He eats apples or pears.")).get("number") is None


def test_three_members():
    graph = run("Ann, Ben and Sam sang.")
    group = group_of(graph)
    assert group is not None and len(group["members"]) == 3


def test_a_collective_predicate_keeps_one_event():
    """Tom and Ben are friends is not Tom being a friend and Ben being a friend."""
    graph = run("The men and the women are farmers.")
    assert len(graph["events"]) == 1
    theme = graph["events"][0]["roles"]["theme"]
    assert graph["entities"][theme].get("members")


def test_two_clauses_are_still_two_events():
    """The guard: coordinating clauses is not coordinating noun phrases."""
    graph = run("The boy ran and the girl walked.")
    assert len(graph["events"]) == 2
    assert group_of(graph) is None


# --- focus particles --------------------------------------------------------------------


def test_only_is_recorded_against_the_thing_it_narrows():
    graph = run("Only Ben came.")
    focus = graph["events"][0]["focus"]
    assert focus["particle"] == "only"
    assert graph["entities"][focus["target"]].get("proper_name") == "Ben"


@pytest.mark.parametrize(
    "text,particle", [("Even the cat slept.", "even"), ("She too can read.", "too")]
)
def test_other_particles(text, particle):
    assert run(text)["events"][0]["focus"]["particle"] == particle


def test_too_as_a_degree_is_not_a_focus():
    """The guard that matters: 'too big' is a degree, not a focus particle."""
    graph = run("The cup is too big.")
    assert "focus" not in graph["events"][0]
    assert graph["events"][0]["degree"] == "too"


def test_a_plain_sentence_carries_no_focus():
    assert "focus" not in run("The dog barked.")["events"][0]


# --- measure phrases ---------------------------------------------------------------------
# Without these, "he is nine years old" reduces to "he is old", which is inverted rather
# than merely lossy.


@pytest.mark.parametrize(
    "text,quantity,unit",
    [
        ("He is nine years old.", 9, "year"),
        ("The box is three metres wide.", 3, "metre"),
    ],
)
def test_a_measure_is_kept(text, quantity, unit):
    measure = run(text)["events"][0]["measure"]
    assert measure == {"quantity": quantity, "unit": unit}


def test_a_bare_attribute_carries_no_measure():
    assert "measure" not in run("He is old.")["events"][0]
