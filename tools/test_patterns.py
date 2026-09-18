"""Tests for the declarative rule set, exercised on its own.

These go at the patterns rather than through the parser, which is the point of moving
the rules into data: a rule can now be checked without running everything around it, and
a failure names the rule rather than the sentence.

    pytest tools/test_patterns.py
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from parser import patterns  # noqa: E402
from parser.rules import _doc, _nlp  # noqa: E402


def analyse(text):
    tokens = [token.text for token in _nlp().tokenizer(text)]
    doc = _doc(tokens)
    return doc, patterns.build_matcher(doc.vocab)


def roles_by_word(text):
    """{verb: {word: role}} so assertions read like the sentence."""
    doc, matcher = analyse(text)
    return {
        doc[verb].lower_: {doc[filler].lower_: role for filler, role in slots.items()}
        for verb, slots in patterns.match_roles(doc, matcher).items()
    }


def phrasal_by_word(text):
    doc, matcher = analyse(text)
    return {
        doc[verb].lower_: concept
        for verb, (concept, _particle) in patterns.match_phrasal(doc, matcher).items()
    }


# --- role rules ---------------------------------------------------------------------


def test_subject_and_object_follow_word_order():
    assert roles_by_word("The dog chased the cat.")["chased"] == {
        "dog": "agent",
        "cat": "patient",
    }


def test_reversing_the_sentence_reverses_the_roles():
    assert roles_by_word("The cat chased the dog.")["chased"] == {
        "cat": "agent",
        "dog": "patient",
    }


def test_experiencer_rule_beats_the_general_agent_rule():
    """Rule order is load-bearing: experiencer_subject is written above agent_subject."""
    assert roles_by_word("I like apples.")["like"]["i"] == "experiencer"


def test_a_liked_thing_is_a_theme_not_a_patient():
    assert roles_by_word("I like apples.")["like"]["apples"] == "theme"


def test_ditransitive_splits_recipient_from_theme():
    assert roles_by_word("Mum gave me a book.")["gave"] == {
        "mum": "agent",
        "me": "recipient",
        "book": "theme",
    }


def test_a_transitive_object_is_a_patient():
    assert roles_by_word("The girl opened the door.")["opened"]["door"] == "patient"


# --- phrasal rules -------------------------------------------------------------------


def test_a_particle_merges_into_the_verb():
    assert phrasal_by_word("Put on your coat.") == {"put": "put-on"}


def test_a_bare_preposition_merges_when_the_verb_has_no_object():
    assert phrasal_by_word("He looked after his sister.") == {"looked": "look-after"}


def test_a_preposition_does_not_merge_when_the_verb_has_an_object():
    """The guard that DependencyMatcher cannot express.

    Without it, "put the box on the shelf" reads as the phrasal verb "put on" and the
    shelf becomes the thing being put — a plausible picture with nothing to flag it.
    """
    assert phrasal_by_word("Put the box on the shelf.") == {}


def test_an_unlisted_combination_does_not_merge():
    assert phrasal_by_word("She walked to the shop.") == {}


# --- the rule set as a whole ----------------------------------------------------------


@pytest.mark.parametrize(
    "rule",
    patterns.ROLE_RULES + patterns.PHRASAL_RULES,
    ids=[rule["name"] for rule in patterns.ROLE_RULES + patterns.PHRASAL_RULES],
)
def test_every_rule_explains_itself(rule):
    """A rule set is only auditable if each rule says what it is for."""
    assert rule["doc"].strip(), f"{rule['name']} has no explanation"
    assert rule["pattern"], f"{rule['name']} has no pattern"


def test_rule_names_are_unique():
    names = [rule["name"] for rule in patterns.ROLE_RULES + patterns.PHRASAL_RULES]
    assert len(names) == len(set(names))
