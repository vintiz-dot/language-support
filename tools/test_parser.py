"""Behavioural tests for the rule parser.

These are not a score. Scoring happens against the gold set, and the gold set is what
the rules were tuned on, so it cannot tell you whether a rule generalises. These lock in
specific behaviours — mostly ones that were wrong at some point — using sentences that
are not in the gold set.

    pytest tools/test_parser.py
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from parser.rules import parse, _nlp  # noqa: E402

RESULTS = []


def run(text):
    tokens = [token.text for token in _nlp().tokenizer(text)]
    return parse(text, tokens=tokens)


def concepts(graph):
    return {ref: entity.get("concept") for ref, entity in graph["entities"].items()}


def role_concept(graph, event, role):
    ref = (event.get("roles") or {}).get(role)
    return graph["entities"].get(ref, {}).get("concept") if ref else None


def check(name, condition, note=""):
    RESULTS.append((name, bool(condition), note))


# --- word order decides who does what ------------------------------------------

a = run("The girl fed the rabbit.")
check(
    "agent and patient follow word order",
    role_concept(a, a["events"][0], "agent") == "girl"
    and role_concept(a, a["events"][0], "patient") == "rabbit",
)

b = run("The rabbit fed the girl.")
check(
    "reversing the sentence reverses the roles",
    role_concept(b, b["events"][0], "agent") == "rabbit"
    and role_concept(b, b["events"][0], "patient") == "girl",
    "if this ever matches the previous case, the parser has stopped reading word order",
)

# --- a particle is part of the verb; a preposition is not -----------------------
# "put on your coat" is one verb. "put the box on the shelf" is a verb and a real
# prepositional phrase, and reading it as phrasal made the shelf the thing being put.

c = run("Put this box on the shelf.")
event = c["events"][0]
check(
    "a real prepositional phrase is not swallowed as a particle",
    event["predicate"] == "put"
    and role_concept(c, event, "patient") == "box"
    and event["spatial"][0]["relation"] == "on",
)
check(
    "the figure is the thing moved, not the destination",
    c["entities"].get(event["spatial"][0]["figure"], {}).get("concept") == "box",
)

d = run("Put on your coat.")
check("a genuine particle still merges into the verb", d["events"][0]["predicate"] == "put-on")

e = run("The teacher looked after the class.")
check(
    "a phrasal verb with no object still merges",
    e["events"][0]["predicate"] == "look-after"
    and role_concept(e, e["events"][0], "patient") == "class",
    "read as look plus after, this draws someone standing behind a class",
)

# --- idioms must not render literally -------------------------------------------

f = run("It is raining cats and dogs.")
check(
    "an idiom keeps its predicate and drops the literal participants",
    f["events"][0]["predicate"] == "rain"
    and "cat" not in concepts(f).values()
    and "dog" not in concepts(f).values(),
)
check(
    "an idiom is flagged for review",
    any(flag["reason"] == "idiom_suspected" for flag in f.get("review", [])),
)

# --- ability is not action --------------------------------------------------------

g = run("He can run fast.")
check(
    "ability is marked irrealis so it is not drawn as happening",
    g["events"][0].get("irrealis") is True and g["events"][0].get("modality") == "can",
)

h = run("We are going to visit the farm.")
check(
    "going to is a future marker, not motion",
    h["events"][0]["predicate"] == "visit" and h["events"][0].get("tense") == "future",
    "reading going as the predicate draws people already travelling",
)
check("an asserted future is not irrealis", h["events"][0].get("irrealis") is None)

# --- conditionals are hypothetical -------------------------------------------------

i = run("If it snows, we will stay inside.")
antecedents = [e for e in i["events"] if e.get("irrealis")]
check(
    "the antecedent of a condition is irrealis",
    len(antecedents) == 1 and antecedents[0]["predicate"] == "snow",
)
check(
    "the condition relation runs from antecedent to consequent",
    any(r["type"] == "condition" for r in i.get("discourse", [])),
)

# --- because reverses the arrow against text order ---------------------------------

j = run("She was happy because her dog came home.")
relations = [r for r in j.get("discourse", []) if r["type"] == "cause"]
by_id = {event["id"]: event for event in j["events"]}
check(
    "because points from the cause to the effect",
    len(relations) == 1 and by_id[relations[0]["from"]]["predicate"] == "come",
    "a left-to-right reading gets this backwards and orders the panels wrongly",
)

# --- quantity and number ------------------------------------------------------------

k = run("Three frogs sat on a log.")
frog = next(e for e in k["entities"].values() if e.get("concept") == "frog")
check("an explicit count becomes a quantity", frog.get("quantity") == 3 and frog.get("number") == "pl")

m = run("The ball is between the boxes.")
ground = m["events"][0]["spatial"][0]["ground"]
check(
    "between infers the two reference points it needs",
    m["entities"][ground].get("quantity") == 2,
)

# --- negation ------------------------------------------------------------------------

n = run("The dog did not eat the bone.")
check("negation is on the event, not the entity", n["events"][0].get("polarity") == "negative")

# --- mental states are flagged as undrawable -------------------------------------------

p = run("She thinks about her friend.")
check(
    "a mental state is flagged rather than drawn",
    any(flag["reason"] == "not_depictable" for flag in p.get("review", [])),
)
check(
    "a possessive resolves onto its antecedent rather than inventing a person",
    len(p["entities"]) == 2,
)


@pytest.mark.parametrize(
    "passed,note",
    [pytest.param(passed, note, id=name) for name, passed, note in RESULTS],
)
def test_parser_behaviour(passed, note):
    assert passed, note or "parser did not behave as expected"
