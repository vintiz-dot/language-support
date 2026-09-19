"""Phase 1d: the fixes the second held-out set called for, plus two bugs found beside them.

Every sentence here is written for the test and belongs to no gold set. Set three has been
drawn but not annotated, and nothing in this file is taken from it.

    pytest tools/test_parser_fixes.py
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from parser.rules import parse, _nlp  # noqa: E402


def run(text):
    return parse(text, tokens=[t.text for t in _nlp().tokenizer(text)])


def event(graph, predicate):
    return next((e for e in graph["events"] if e["predicate"] == predicate), None)


def concept_of(graph, ref):
    return graph["entities"].get(ref, {}).get("concept")


# --- a preposition may be spent once -------------------------------------------------
# A verb that absorbs its preposition was still emitting it as a spatial relation, so
# "look at the man" produced the predicate look-at AND a spatial at. The suppression was
# written but never worked: it compared spaCy Token objects with `is`, and spaCy builds a
# fresh proxy on every access, so doc[1] is doc[1] is False.


@pytest.mark.parametrize(
    "text,predicate",
    [
        ("Look at the bird.", "look-at"),
        ("She looked for her shoe.", "look-for"),
        ("Please pick up the toy.", "pick-up"),
        ("He put on his coat.", "put-on"),
    ],
)
def test_a_swallowed_preposition_is_not_also_a_spatial(text, predicate):
    graph = run(text)
    found = event(graph, predicate)
    assert found is not None, f"{predicate} not recognised"
    assert not found.get("spatial"), f"{predicate} also emitted {found.get('spatial')}"


def test_a_real_spatial_still_survives():
    """The fix must not silence prepositions that are doing spatial work."""
    graph = run("She put the cup on the shelf.")
    spatial = graph["events"][0]["spatial"][0]
    assert spatial["relation"] == "on"
    assert concept_of(graph, spatial["ground"]) == "shelf"


# --- phrasal verbs and idioms the held-out set named ----------------------------------


@pytest.mark.parametrize(
    "text,predicate",
    [
        ("Listen to the bell.", "listen-to"),
        ("He drove off the crows.", "drive-off"),
        ("Take care of your coat.", "look-after"),
        ("They made fun of the boy.", "mock"),
        ("She put the room in order.", "tidy"),
    ],
)
def test_multiword_predicates_resolve(text, predicate):
    assert event(run(text), predicate) is not None


def test_an_idiom_does_not_leave_its_parts_as_entities():
    """take care of should not leave care standing as a thing that was taken."""
    graph = run("Take care of your coat.")
    assert "care" not in [e["concept"] for e in graph["entities"].values()]


def test_an_idiom_keeps_its_real_object():
    graph = run("Take care of your coat.")
    roles = graph["events"][0].get("roles") or {}
    assert concept_of(graph, roles.get("patient")) == "coat"


# --- a discourse relation needs two events --------------------------------------------
# Same Token identity bug: `head.head is not head` is True even at the root, so a sentence
# opening with And, But or Then related its only event to itself.


@pytest.mark.parametrize("text", ["And the birds sang.", "But the cup fell.", "Then he slept."])
def test_a_lone_clause_gets_no_self_referential_relation(text):
    for relation in run(text).get("discourse", []):
        assert relation["from"] != relation["to"], f"{text} relates an event to itself"


def test_a_real_two_clause_relation_still_works():
    """Clause-level and is a sequence, per g042; the point here is that it links two events."""
    graph = run("The boy ran and the girl walked.")
    relation = graph["discourse"][0]
    assert relation["from"] != relation["to"]
    assert {relation["from"], relation["to"]} == {e["id"] for e in graph["events"]}


# --- exclamative mood without a fronted degree word -----------------------------------


@pytest.mark.parametrize("text", ["He broke the window!", "The cake is lovely!"])
def test_an_exclamation_mark_makes_an_exclamative(text):
    assert run(text)["events"][0]["mood"] == "exclamative"


def test_an_imperative_with_an_exclamation_mark_stays_imperative():
    assert run("Shut the door!")["events"][0]["mood"] == "imperative"


def test_a_question_is_not_made_exclamative():
    assert run("Can you swim?")["events"][0]["mood"] == "interrogative"


# --- who performs an embedded clause ---------------------------------------------------
# The metric said zero argument swaps while the parser was handing the embedded clause to
# the wrong person, because swaps only counts agent and patient inverted inside one event.


def test_object_control_gives_the_clause_to_the_object():
    graph = run("Mum told Sam to wash the cup.")
    assert concept_of(graph, event(graph, "wash")["roles"]["agent"]) == "person"
    told = event(graph, "tell")["roles"]
    assert event(graph, "wash")["roles"]["agent"] != told["agent"]


def test_object_control_with_two_people_of_the_same_kind():
    """Both are 'person', so this has to compare references rather than concepts."""
    graph = run("She asked him to sit down.")
    asked = event(graph, "ask")["roles"]
    washer = event(graph, "sit-down")["roles"]["agent"]
    assert washer != asked["agent"], "the asker was made the sitter"
    assert washer == asked.get("patient") or washer == asked.get("theme")


def test_subject_control_still_gives_the_clause_to_the_subject():
    graph = run("He wanted to go home.")
    assert event(graph, "go")["roles"]["agent"] == event(graph, "want")["roles"]["experiencer"]


def test_a_purpose_clause_keeps_the_subject():
    graph = run("She stood up to see the parade.")
    assert event(graph, "see")["roles"]["experiencer"] == event(graph, "stand-up")["roles"]["agent"]


# --- a complement is not a question ----------------------------------------------------
# Found by making run_parser validate its own output: the question marker was landing on
# the embedded clause too, which the validator had always rejected in gold.


def test_a_question_marks_only_the_clause_it_asks_about():
    graph = run("Did you watch the dog run away?")
    asking = event(graph, "watch")
    embedded = event(graph, "run")
    assert asking["question"]["type"] == "yes-no"
    assert "question" not in embedded
    assert embedded.get("mood") is None
