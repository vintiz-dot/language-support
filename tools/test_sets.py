"""Approved sets: what a teacher signed off, and whether it stays signed off.

The load-bearing test here is `test_a_saved_set_does_not_change_when_the_lexicon_does`.
Approval only means something if it freezes the pictures; a set that re-resolves its
symbols on opening would let a parser change or a lexicon rebuild quietly redraw work a
teacher had already checked, and nobody would be told. That is the same reason the held-out
sets carry hashes.

    pytest tools/test_sets.py
"""

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from renderer import sets as sets_module  # noqa: E402
from renderer.strip import LEXICON, build, load_lexicon  # noqa: E402
from score import load_gold  # noqa: E402

if not LEXICON.exists():
    pytest.skip("run tools/build_lexicon.py first", allow_module_level=True)

GOLD = load_gold()
LEX = load_lexicon()


@pytest.fixture
def sets_dir(tmp_path, monkeypatch):
    """Point the module at a scratch directory; a test must never touch real work."""
    monkeypatch.setattr(sets_module, "SETS", tmp_path / "sets")
    return tmp_path / "sets"


def approved(graph_id="g001", overrides=None):
    graph = GOLD[graph_id]
    strip = build(graph, LEX, overrides or {})
    return sets_module.approved_sentence(strip, graph)


# --- a set name becomes a filename ------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Week 1 animals", "week-1-animals"),
        ("  Spaced  Out  ", "spaced-out"),
        ("Ünïcode!!", "n-code"),   # a filename stays ASCII; the title does not
        ("", "untitled"),
        ("---", "untitled"),
    ],
)
def test_slugify(name, expected):
    assert sets_module.slugify(name) == expected


@pytest.mark.parametrize(
    "name", ["../../etc/passwd", "..\\..\\windows", "/absolute/path", "a/b/c"]
)
def test_a_set_name_cannot_escape_the_sets_directory(name, sets_dir):
    """The name arrives over HTTP, so this is an allow-list and not an escape."""
    path = sets_module.path_for(name)
    assert path.parent == sets_module.SETS.resolve()
    assert ".." not in path.parts


# --- approval freezes the pictures --------------------------------------------------


def test_approval_stores_the_resolved_pictures_not_just_the_text():
    sentence = approved("g001")
    pictograms = [c["pictogram"] for c in sentence["cells"] if c.get("pictogram")]
    assert pictograms, "nothing was frozen; the set stores only text"
    assert sentence["text"] == "The dog chased the cat."
    assert sentence["approved"]


def test_the_scene_graph_is_kept_as_provenance():
    """Kept so a later renderer can compose a scene -- but the cells are the authority."""
    sentence = approved("g001")
    assert sentence["provenance"]["graph"]["id"] == "g001"
    assert sentence["provenance"]["schema_version"] == GOLD["g001"]["schema_version"]


def test_a_saved_set_does_not_change_when_the_lexicon_does(sets_dir):
    """The whole point of approving. If this fails, approval means nothing."""
    sets_module.save("frozen", [approved("g001")])
    before = sets_module.load("frozen")
    original = [c.get("pictogram") for c in before["sentences"][0]["cells"]]

    # The teacher changes their mind about dog, or the lexicon is rebuilt.
    changed = approved("g001", overrides={"dog": 99999})
    assert 99999 in [c.get("pictogram") for c in changed["cells"]], "the override did nothing"

    after = sets_module.load("frozen")
    assert [c.get("pictogram") for c in after["sentences"][0]["cells"]] == original
    assert 99999 not in [c.get("pictogram") for c in after["sentences"][0]["cells"]]


# --- what a set knows about itself ----------------------------------------------------


def test_a_flagged_picture_is_reported_on_the_set():
    """A teacher should be able to see which saved sets still want checking."""
    sentence = approved("g001")
    for cell in sentence["cells"]:
        if cell.get("concept") == "dog":
            cell["match"] = "fuzzy"
    flags = sets_module.flags_in(sentence)
    assert any("dog" in f for f in flags)


def test_an_unflagged_sentence_reports_nothing():
    assert sets_module.flags_in(approved("g001")) == []


def test_a_plain_word_is_not_reported_as_a_missing_symbol():
    """Function words have no picture by design, not by failure."""
    sentence = approved("g001")
    assert any(c["kind"] == "word" for c in sentence["cells"])
    assert sets_module.flags_in(sentence) == []


# --- saving and reading back -----------------------------------------------------------


def test_save_and_load_round_trip(sets_dir):
    sets_module.save("Week 1 animals", [approved("g001"), approved("g008")], "Week 1 animals")
    data = sets_module.load("Week 1 animals")
    assert data["title"] == "Week 1 animals"
    assert data["name"] == "week-1-animals"
    assert [s["text"] for s in data["sentences"]] == [
        GOLD["g001"]["text"], GOLD["g008"]["text"]
    ]


def test_a_non_ascii_title_survives_even_though_the_filename_cannot(sets_dir):
    """Filenames are reduced to ASCII so they stay portable. What the teacher typed is not.

    A set called Niños or Leçons must still read back under its own name, or the
    slugging would quietly rename people's work.
    """
    sets_module.save("Niños primero", [approved("g001")], "Niños primero")
    data = sets_module.load("Niños primero")
    assert data["title"] == "Niños primero"
    assert data["name"] == "ni-os-primero"


def test_loading_a_set_that_does_not_exist_returns_nothing(sets_dir):
    assert sets_module.load("never saved") is None


def test_saving_again_replaces_the_set(sets_dir):
    sets_module.save("week", [approved("g001"), approved("g008")])
    sets_module.save("week", [approved("g001")])
    assert len(sets_module.load("week")["sentences"]) == 1


def test_the_listing_counts_sentences_and_flags(sets_dir):
    flagged = approved("g001")
    for cell in flagged["cells"]:
        if cell.get("concept") == "dog":
            cell["match"] = "fuzzy"
    sets_module.save("one", [approved("g008")])
    sets_module.save("two", [flagged, approved("g008")])

    rows = {row["name"]: row for row in sets_module.listing()}
    assert rows["one"]["sentences"] == 1 and rows["one"]["to_check"] == 0
    assert rows["two"]["sentences"] == 2 and rows["two"]["to_check"] == 1


def test_the_listing_survives_a_corrupt_file(sets_dir):
    """A teacher's directory is theirs; one bad file must not hide the rest."""
    sets_module.save("good", [approved("g001")])
    (sets_module.SETS / "broken.json").write_text("{not json", encoding="utf-8")
    assert [row["name"] for row in sets_module.listing()] == ["good"]


def test_a_set_is_plain_readable_json(sets_dir):
    """A teacher should be able to read, copy or mail their own work without this project."""
    sets_module.save("week", [approved("g001")])
    text = (sets_module.SETS / "week.json").read_text(encoding="utf-8")
    assert json.loads(text)["sentences"][0]["text"] == "The dog chased the cat."
    assert "\n" in text, "written as one line; a teacher cannot read or diff that"
