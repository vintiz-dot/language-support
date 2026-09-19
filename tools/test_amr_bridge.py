"""The AMR bridge, tested against hand-written penman rather than a 516 MB model.

The bridge is a pure function from an AMR graph to scene graph nodes, so the model is only
needed to produce the input. Writing the penman by hand keeps these tests fast, offline and
deterministic, and lets them cover shapes a model might not produce on demand.

    pytest tools/test_amr_bridge.py
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

pytest.importorskip("penman", reason="penman is a benchmark dependency, not a runtime one")

from parser import amr_bridge  # noqa: E402
from parser.rules import Builder, _doc, _nlp, entity_props, parse, read_tense_aspect  # noqa: E402


def build(text, penman_text):
    tokens = [t.text for t in _nlp().tokenizer(text)]
    doc = _doc(tokens)
    builder = Builder(text, tokens)
    ok = amr_bridge.build(penman_text, doc, builder, entity_props, read_tense_aspect)
    return ok, builder.graph()


def concepts(graph):
    return {e.get("concept") for e in graph["entities"].values()}


def roles_as_concepts(graph, index=0):
    entities = graph["entities"]
    return {
        role: entities[ref].get("concept")
        for role, ref in (graph["events"][index].get("roles") or {}).items()
    }


# --- the architectural guarantee ---------------------------------------------------------
# The benchmark says the rules are more precise than AMR on what they find, so AMR must
# never get to overrule one. This is the test that keeps that true.


def test_the_fallback_is_not_consulted_when_the_rules_succeed():
    calls = []

    def fallback(text):
        calls.append(text)
        return "(d / dog)"

    tokens = [t.text for t in _nlp().tokenizer("The dog chased the cat.")]
    graph = parse("The dog chased the cat.", tokens=tokens, fallback=fallback)
    assert calls == [], "the fallback ran even though the rules produced events"
    assert roles_as_concepts(graph) == {"agent": "dog", "patient": "cat"}


def test_a_broken_amr_graph_does_not_crash_the_parse():
    ok, graph = build("Twinkle, twinkle.", "(this is not penman")
    assert ok is False
    assert graph["events"] == []


# --- predicate and argument structure ------------------------------------------------------


def test_arg0_and_arg1_become_agent_and_patient():
    _, graph = build(
        "The dog chased the cat.",
        "(c / chase-01 :ARG0 (d / dog) :ARG1 (c2 / cat))",
    )
    assert graph["events"][0]["predicate"] == "chase"
    assert roles_as_concepts(graph) == {"agent": "dog", "patient": "cat"}


def test_the_verb_class_decides_the_role_name():
    """see takes an experiencer and a theme, matching how the rules write it."""
    _, graph = build(
        "The boy saw the bird.",
        "(s / see-01 :ARG0 (b / boy) :ARG1 (b2 / bird))",
    )
    assert set(roles_as_concepts(graph)) == {"experiencer", "theme"}


def test_arg2_is_a_recipient():
    _, graph = build(
        "The girl gave the boy a book.",
        "(g / give-01 :ARG0 (g2 / girl) :ARG1 (b / book) :ARG2 (b2 / boy))",
    )
    assert roles_as_concepts(graph)["recipient"] == "boy"


def test_an_arg1_only_predicate_becomes_an_attribute():
    """gray-02 :ARG1 streak is an adjective, not an action."""
    _, graph = build(
        "The streaks are gray.",
        "(g / gray-02 :ARG1 (s / streak))",
    )
    event = graph["events"][0]
    assert event["predicate"] == "be.attribute"
    assert event["attribute"] == "gray"
    assert roles_as_concepts(graph) == {"theme": "streak"}


def test_a_predicate_with_no_arguments_still_becomes_an_event():
    """twinkle-01 has no :ARG at all, and is the whole content of its sentence."""
    ok, graph = build("Twinkle, twinkle.", "(t / twinkle-01)")
    assert ok
    assert graph["events"][0]["predicate"] == "twinkle"


# --- what AMR brings that the rules do not ----------------------------------------------


def test_a_coordinated_argument_becomes_a_group():
    _, graph = build(
        "The boy and the girl ran.",
        "(r / run-02 :ARG0 (a / and :op1 (b / boy) :op2 (g / girl)))",
    )
    agent = graph["events"][0]["roles"]["agent"]
    group = graph["entities"][agent]
    assert group["coordination"] == "and"
    assert {graph["entities"][m]["concept"] for m in group["members"]} == {"boy", "girl"}


def test_a_name_becomes_a_proper_name():
    _, graph = build(
        "Kate sang.",
        '(s / sing-01 :ARG0 (p / person :name (n / name :op1 "Kate")))',
    )
    agent = graph["entities"][graph["events"][0]["roles"]["agent"]]
    assert agent["concept"] == "person" and agent["proper_name"] == "Kate"


def test_negative_polarity_is_carried():
    _, graph = build(
        "The dog did not bark.",
        "(b / bark-01 :ARG0 (d / dog) :polarity -)",
    )
    assert graph["events"][0]["polarity"] == "negative"


# --- the features AMR throws away, recovered from spaCy ------------------------------------


def test_number_and_definiteness_come_from_spacy_not_amr():
    """AMR writes cat for both cat and cats; the bridge fills that back in."""
    _, graph = build(
        "The cats slept.",
        "(s / sleep-01 :ARG0 (c / cat))",
    )
    cat = next(e for e in graph["entities"].values() if e["concept"] == "cat")
    assert cat["number"] == "pl"
    assert cat["definite"] is True


# --- no predicate at all --------------------------------------------------------------------


def test_a_verbless_exclamation_becomes_an_existence():
    ok, graph = build(
        "What little eggs!",
        "(s / say-01 :mode expressive :ARG2 (e / egg :mod (l / little)))",
    )
    assert ok
    event = graph["events"][0]
    assert event["predicate"] == "exist" and event["mood"] == "exclamative"
    assert "egg" in concepts(graph)
    assert "say" not in concepts(graph), "AMR's expressive wrapper leaked into the scene"


def test_a_modifier_is_not_duplicated_when_both_sources_find_it():
    _, graph = build(
        "What little eggs!",
        "(s / say-01 :mode expressive :ARG2 (e / egg :mod (l / little)))",
    )
    egg = next(e for e in graph["entities"].values() if e["concept"] == "egg")
    assert egg["modifiers"].count("little") == 1


# --- everything it builds is flagged ----------------------------------------------------------


def test_every_node_from_the_fallback_is_flagged_for_review():
    _, graph = build(
        "The dog chased the cat.",
        "(c / chase-01 :ARG0 (d / dog) :ARG1 (c2 / cat))",
    )
    flagged = {flag["node"] for flag in graph["review"]}
    nodes = set(graph["entities"]) | {e["id"] for e in graph["events"]}
    assert nodes <= flagged, "a fallback node reached the renderer unflagged"
    assert all(flag["reason"] == "parse_uncertain" for flag in graph["review"])
