"""Parser tests for the failure classes the held-out run exposed.

The taxonomy came from held-out data, so the fixes have to be general rather than
sentence-by-sentence. Every sentence here is written for the test and appears in neither
the tuning set nor the held-out set: if a fix only works on the sentence that revealed
the problem, these fail.

    pytest tools/test_parser_coverage.py
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from parser.rules import parse, _nlp  # noqa: E402


def run(text):
    return parse(text, tokens=[t.text for t in _nlp().tokenizer(text)])


def concept_of(graph, ref):
    return graph["entities"].get(ref, {}).get("concept")


def role(graph, role_name, event_index=0):
    ref = (graph["events"][event_index].get("roles") or {}).get(role_name)
    return concept_of(graph, ref) if ref else None


def first(graph, field, event_index=0):
    return graph["events"][event_index].get(field)


# --- noun-phrase head selection ------------------------------------------------------
# The largest single cause in the held-out run: the parser took a determiner or a
# quantifier as the head noun, producing concepts like "some" and "mine".


def test_partitive_takes_the_noun_not_the_quantifier():
    g = run("I ate some of the cakes.")
    assert role(g, "patient") == "cake"


def test_partitive_keeps_the_quantifier_on_the_entity():
    g = run("I ate some of the cakes.")
    ref = g["events"][0]["roles"]["patient"]
    assert g["entities"][ref].get("quantifier") == "some"


def test_a_standalone_demonstrative_is_a_thing():
    g = run("She likes this.")
    ref = g["events"][0]["roles"]["theme"]
    assert g["entities"][ref]["concept"] == "thing"
    assert g["entities"][ref].get("deixis") == "proximal"


def test_a_possessive_pronoun_is_a_thing_with_an_owner():
    g = run("He took mine.")
    ref = g["events"][0]["roles"]["patient"]
    assert g["entities"][ref]["concept"] == "thing"
    assert concept_of(g, g["entities"][ref].get("possessor")) == "speaker"


def test_a_prepositional_dative_recipient_is_the_noun():
    """spaCy labels the "to" itself as the dative, which made the recipient "to"."""
    g = run("The boy gave the book to his sister.")
    assert role(g, "recipient") == "sister"


def test_a_prepositional_dative_still_follows_a_partitive():
    g = run("He showed the picture to some of the children.")
    assert role(g, "recipient") == "child"


def test_a_relative_pronoun_is_not_an_entity():
    g = run("The bird that sang flew away.")
    assert "that" not in [e["concept"] for e in g["entities"].values()]


# --- non-finite clauses ---------------------------------------------------------------
# 0.2.0 only recognised xcomp, so purpose infinitives, perception complements and
# participials were given a tense and a mood the text never asserts.


@pytest.mark.parametrize(
    "text,predicate",
    [
        ("She bought bread to eat.", "eat"),
        ("I saw him run.", "run"),
        ("He sat, waiting for the bus.", "wait"),
    ],
)
def test_a_non_finite_clause_carries_no_tense_or_mood(text, predicate):
    g = run(text)
    event = next(e for e in g["events"] if e["predicate"] == predicate)
    assert event.get("tense") is None, f"{predicate} was given a tense it does not assert"
    assert event.get("mood") is None


# --- coordination -----------------------------------------------------------------------


def test_coordinated_adjectives_become_two_events():
    g = run("The apple is red and sweet.")
    attributes = {e.get("attribute") for e in g["events"]}
    assert {"red", "sweet"} <= attributes


def test_coordinated_adjectives_are_linked():
    g = run("The apple is red and sweet.")
    assert any(r["type"] == "addition" for r in g.get("discourse", []))


# --- spatial figure ----------------------------------------------------------------------


def test_the_figure_is_the_thing_that_moves():
    g = run("He threw the ball into the box.")
    spatial = g["events"][0]["spatial"][0]
    assert concept_of(g, spatial["figure"]) == "ball"


# --- mood from grammar, not punctuation ---------------------------------------------------


def test_inversion_makes_a_question_even_without_a_question_mark():
    g = run("Can you help me.")
    assert first(g, "mood") == "interrogative"


# --- fields 0.3.0 added --------------------------------------------------------------------


def test_a_vocative_becomes_the_address():
    g = run("Sit down, Tom.")
    assert concept_of(g, g.get("address")) is not None
    assert g["entities"][g["address"]].get("proper_name") == "Tom"


def test_a_vocative_is_the_agent_of_an_imperative():
    """Tom is who is being told to sit, not a bystander beside an anonymous addressee."""
    g = run("Sit down, Tom.")
    assert g["events"][0]["roles"]["agent"] == g["address"]
    assert len(g["entities"]) == 1


def test_a_bare_greeting_is_a_speech_act_with_no_events():
    g = run("Thank you.")
    assert g.get("speech_act") == "thanks"
    assert g["events"] == []


def test_manner_is_recorded():
    assert first(run("He ran quickly."), "manner") == "quickly"


def test_frequency_is_recorded():
    g = run("She never cries.")
    assert first(g, "frequency") == "never"
    assert first(g, "polarity") == "negative"


def test_phase_is_recorded():
    assert first(run("I am still hungry."), "phase") == "still"


def test_comitative_is_recorded():
    g = run("He played with his brother.")
    assert role(g, "comitative") == "brother"


def test_simultaneous_relation_is_recorded():
    g = run("She sang while she worked.")
    assert any(r["type"] == "simultaneous" for r in g.get("discourse", []))


def test_a_relative_clause_modifies_its_entity():
    g = run("The boy who fell is crying.")
    modifier = next((e for e in g["events"] if e.get("modifies")), None)
    assert modifier is not None and modifier["predicate"] == "fall"
    assert concept_of(g, modifier["modifies"]) == "boy"


def test_nominal_predication_uses_category():
    g = run("My dad is a farmer.")
    event = g["events"][0]
    assert concept_of(g, event.get("category")) == "farmer"


def test_exclamative_mood():
    assert first(run("How sad it is!"), "mood") == "exclamative"


def test_equative_degree_carries_a_comparand():
    g = run("He is as tall as me.")
    event = g["events"][0]
    assert event.get("degree") == "equative"
    assert concept_of(g, event.get("comparand")) == "speaker"


def test_would_is_a_modality():
    g = run("They would come.")
    assert first(g, "modality") == "would"
    assert first(g, "irrealis") is True


def test_a_bare_direction_needs_no_ground():
    g = run("The dog ran away.")
    spatial = g["events"][0]["spatial"][0]
    assert spatial["relation"] == "away"
    assert "ground" not in spatial


def test_an_entity_can_be_located_without_an_event():
    g = run("The cup on the table is full.")
    cup = next(e for e in g["entities"].values() if e["concept"] == "cup")
    assert cup.get("located", {}).get("relation") == "on"
