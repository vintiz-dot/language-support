"""The editor's HTTP surface, over a real socket.

Everything else in this project is tested as a function call. The server is the one place
where input arrives from outside, so it is the one place worth testing the way it is
actually used: a real request to a real port. The path-traversal case in particular is not
meaningful as a unit test, because what is being checked is that a hostile name cannot
reach the filesystem *through the endpoint*.

The server is started once for the module on an ephemeral port and torn down after.

    pytest tools/test_serve.py
"""

import json
import pathlib
import socket
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

pytest.importorskip("spacy", reason="the server loads the parser at import")

from renderer.strip import LEXICON  # noqa: E402

if not LEXICON.exists():
    pytest.skip("run tools/build_lexicon.py first", allow_module_level=True)

import serve  # noqa: E402
from renderer import sets as sets_module  # noqa: E402


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    """A live server on a free port, writing sets into a scratch directory."""
    sets_module.SETS = tmp_path_factory.mktemp("sets")

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    server = serve.Server(("127.0.0.1", port), serve.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=30) as response:
        return response.status, response.read().decode("utf-8")


def post(base, path, payload):
    request = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


# --- the two pages -------------------------------------------------------------


def test_the_teacher_page_is_served(base):
    status, body = get(base, "/")
    assert status == 200 and "Sentence pictures" in body


def test_the_student_page_is_served(base):
    status, body = get(base, "/read")
    assert status == 200 and "Choose a set to read" in body


def test_the_student_page_never_mentions_the_parser_or_the_flags(base):
    """A child is not shown that the parser was unsure; that is the teacher's business."""
    _, body = get(base, "/read")
    for word in ("/api/strip", "/api/approve", "parse_uncertain", "fuzzy"):
        assert word not in body, f"the student view references {word}"


def test_an_unknown_path_is_a_404(base):
    with pytest.raises(urllib.error.HTTPError) as caught:
        get(base, "/api/nothing")
    assert caught.value.code == 404


# --- parsing -------------------------------------------------------------------


def test_a_sentence_becomes_a_strip(base):
    status, data = post(base, "/api/strip", {"text": "The dog chased the cat."})
    assert status == 200
    concepts = [c.get("concept") for c in data["cells"]]
    assert "dog" in concepts and "cat" in concepts
    assert data["attribution"].startswith("ARASAAC")


def test_empty_text_is_not_an_error(base):
    """A teacher clearing the box is a normal thing to do, not a failure."""
    status, data = post(base, "/api/strip", {"text": "   "})
    assert status == 200 and data["cells"] == []


def test_half_typed_text_does_not_crash_the_server(base):
    status, data = post(base, "/api/strip", {"text": "The dog ch"})
    assert status == 200 and "cells" in data


# --- approving and saving --------------------------------------------------------


def test_approving_freezes_the_pictures(base):
    status, sentence = post(base, "/api/approve", {"text": "The dog chased the cat."})
    assert status == 200
    assert [c["pictogram"] for c in sentence["cells"] if c.get("pictogram")]
    assert sentence["approved"] and sentence["to_check"] == []


def test_approving_nothing_is_refused(base):
    status, data = post(base, "/api/approve", {"text": ""})
    assert status == 400 and "error" in data


def test_a_set_saves_and_reads_back(base):
    _, sentence = post(base, "/api/approve", {"text": "The dog chased the cat."})
    status, result = post(
        base, "/api/sets", {"name": "Week 1", "title": "Week 1", "sentences": [sentence]}
    )
    assert status == 200 and result["name"] == "week-1"

    _, body = get(base, "/api/sets?name=week-1")
    data = json.loads(body)
    assert data["title"] == "Week 1"
    assert data["sentences"][0]["text"] == "The dog chased the cat."


def test_a_set_appears_in_the_listing(base):
    _, sentence = post(base, "/api/approve", {"text": "The ball is red."})
    post(base, "/api/sets", {"name": "Colours", "sentences": [sentence]})
    _, body = get(base, "/api/sets")
    names = [row["name"] for row in json.loads(body)["sets"]]
    assert "colours" in names


def test_saving_without_a_name_is_refused(base):
    status, data = post(base, "/api/sets", {"sentences": []})
    assert status == 400 and "error" in data


def test_reading_a_set_that_does_not_exist_is_a_404(base):
    with pytest.raises(urllib.error.HTTPError) as caught:
        get(base, "/api/sets?name=never-saved")
    assert caught.value.code == 404


# --- the hostile case ------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["../../../evil", "..\\..\\evil", "/etc/passwd", "....//....//evil"]
)
def test_a_set_name_cannot_write_outside_the_sets_directory(base, name):
    """The one input that reaches the filesystem. An allow-list, not an escape."""
    before = {p.name for p in sets_module.SETS.glob("*")}
    status, result = post(base, "/api/sets", {"name": name, "sentences": []})
    assert status == 200

    written = {p.name for p in sets_module.SETS.glob("*")} - before
    for path in written:
        assert (sets_module.SETS / path).resolve().parent == sets_module.SETS.resolve()
    assert not (ROOT / "evil.json").exists()
    assert ".." not in result["name"] and "/" not in result["name"]
