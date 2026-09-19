"""The strip renderer: a scene graph laid out as pictures over the words they came from.

These run against the gold graphs rather than the parser, so they test the rendering
decision and not the parse. They need `lexicon/concepts.json`, which
`python tools/build_lexicon.py` regenerates offline from the cache.

The claim under test throughout is the one the whole project rests on: **a picture belongs
to a span, not to a word.** Word-for-word substitution is what this is meant to replace,
and it would pass a naive version of almost every test below.

    pytest tools/test_strip.py
"""

import copy
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from renderer.strip import LEXICON, build, load_lexicon, picture_url, save_override  # noqa: E402
from score import load_gold  # noqa: E402

if not LEXICON.exists():
    pytest.skip("run tools/build_lexicon.py first", allow_module_level=True)

GOLD = load_gold()
LEX = load_lexicon()


def strip_for(graph_id, overrides=None):
    return build(GOLD[graph_id], LEX, overrides or {})


def cells(graph_id, kind=None, **kwargs):
    out = strip_for(graph_id, **kwargs)["cells"]
    return [c for c in out if kind is None or c["kind"] == kind]


def drawn(graph_id, **kwargs):
    return [c for c in cells(graph_id, **kwargs) if c["kind"] != "word"]


def by_text(graph_id, text):
    return next(c for c in cells(graph_id) if c["text"] == text)


# --- a picture belongs to a span ------------------------------------------------


def test_a_noun_phrase_is_one_picture_over_its_words():
    """The dog is one picture over two words, not a determiner nobody can draw."""
    cell = by_text("g001", "The dog")
    assert cell["tokens"] == [0, 1]
    assert cell["concept"] == "dog"
    assert cell["url"]


def test_a_phrasal_verb_is_one_picture_over_two_words():
    """looked after is a single unit. Reading it word by word draws someone standing behind."""
    cell = by_text("g050", "looked after")
    assert cell["tokens"] == [1, 2]
    assert cell["concept"] == "look-after"


def test_every_token_appears_exactly_once():
    """The strip is laid over the sentence, so it has to cover it without overlapping."""
    for graph_id in ("g001", "g050", "g076", "g015"):
        strip = strip_for(graph_id)
        covered = [i for cell in strip["cells"] for i in cell["tokens"]]
        assert sorted(covered) == list(range(len(strip["tokens"]))), graph_id


def test_cells_are_ordered_by_position():
    for graph_id in ("g001", "g076", "g050"):
        starts = [c["start"] for c in cells(graph_id)]
        assert starts == sorted(starts), graph_id


def test_function_words_survive_without_a_picture():
    """48% of the Dolch list is carried by a graph field. Those words still get shown."""
    cell = by_text("g076", "and")
    assert cell["kind"] == "word"
    assert "url" not in cell


# --- what is deliberately not drawn ---------------------------------------------


def test_a_coordinated_group_has_no_picture_of_its_own():
    """A group is drawn by showing its members, so it must not cover them with one cell."""
    texts = {c["text"] for c in drawn("g076")}
    assert "The boy" in texts and "the girl" in texts
    assert "The boy and the girl" not in texts


def test_a_structural_predicate_draws_no_symbol_for_itself():
    """There is no picture of existence; the things themselves are the picture."""
    entry = LEX["exist"]
    assert entry["match"] == "structural"
    assert "pictogram" not in entry


# --- what the graph fields become ------------------------------------------------


def test_plural_becomes_a_url_parameter():
    """ARASAAC renders the plural marker server side, so number costs nothing here."""
    cell = next(c for c in drawn("g003") if c["concept"] == "cat")
    assert "plural=true" in cell["url"]


def test_past_tense_becomes_a_url_parameter():
    cell = next(c for c in drawn("g001") if c["kind"] == "event")
    assert "action=past" in cell["url"]


def test_a_present_tense_singular_uses_the_plain_cdn():
    """No parameters means the static CDN, which is cheaper and cached better."""
    cell = next(c for c in drawn("g008") if c["concept"] == "ball")
    assert cell["url"].startswith("https://static.arasaac.org/")


def test_negation_is_carried_as_a_flag_not_as_an_opposite():
    """not big must not become small: the picture is a crossed claim, drawn by the strip."""
    cell = next(c for c in drawn("g015") if c["negated"])
    assert cell["concept"] == "big"
    assert "small" not in json.dumps(cell)


def test_an_attribute_is_drawn_although_its_predicate_is_structural():
    """be.attribute has no picture, but the attribute it asserts is the whole claim."""
    cell = next(c for c in drawn("g008") if c["kind"] == "event")
    assert cell["concept"] == "red" and cell["predicate"] == "be.attribute"
    assert cell["url"]


# --- the teacher's choice ---------------------------------------------------------


def test_an_override_wins_over_the_lexicon_default():
    default = next(c for c in drawn("g001") if c["concept"] == "dog")
    chosen = next(c for c in drawn("g001", overrides={"dog": 99999}) if c["concept"] == "dog")
    assert default["pictogram"] != 99999
    assert chosen["pictogram"] == 99999
    assert chosen["match"] == "chosen" and chosen["overridden"] is True


def test_an_override_round_trips_through_the_file(tmp_path):
    path = tmp_path / "overrides.json"
    save_override("dog", 12345, path)
    save_override("cat", 54321, path)
    assert json.loads(path.read_text(encoding="utf-8"))["concepts"] == {
        "dog": 12345, "cat": 54321
    }
    save_override("dog", None, path)
    assert json.loads(path.read_text(encoding="utf-8"))["concepts"] == {"cat": 54321}


# --- flags reach the teacher -------------------------------------------------------


def test_a_review_flag_reaches_the_cell():
    """The review machinery existed and nothing read it. This is the thing that reads it."""
    graph = copy.deepcopy(GOLD["g001"])
    graph["review"] = [{"node": "e1", "reason": "parse_uncertain", "note": "test"}]
    strip = build(graph, LEX, {})
    cell = next(c for c in strip["cells"] if c.get("concept") == "dog")
    assert cell["uncertain"] is True
    assert "parse_uncertain" in cell["flags"]


def test_attribution_travels_with_every_strip():
    """CC BY-NC-SA requires it on every export, so it cannot be a property of the page."""
    assert "ARASAAC" in strip_for("g001")["attribution"]


# --- url construction ---------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({}, "https://static.arasaac.org/pictograms/7202/7202_500.png"),
        ({"plural": True}, "https://api.arasaac.org/v1/pictograms/7202?plural=true"),
        ({"action": "past"}, "https://api.arasaac.org/v1/pictograms/7202?action=past"),
        ({"colour": False}, "https://api.arasaac.org/v1/pictograms/7202?color=false"),
        ({"action": "present"}, "https://static.arasaac.org/pictograms/7202/7202_500.png"),
    ],
)
def test_picture_url(kwargs, expected):
    assert picture_url(7202, **kwargs) == expected
