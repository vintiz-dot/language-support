"""Negative tests for the gold checker.

The gold set passes clean, which is only meaningful if the checker can fail. Each
test breaks one thing and asserts the corresponding complaint appears.

    pytest tools/test_check_gold.py
"""

import copy

import pytest

from check_gold import check_graph

BASE = {
    "schema_version": "0.2.0",
    "id": "t000",
    "text": "The dog chased the cat.",
    "tokens": ["The", "dog", "chased", "the", "cat", "."],
    "entities": {
        "e1": {"concept": "dog", "number": "sg", "animacy": "animal"},
        "e2": {"concept": "cat", "number": "sg", "animacy": "animal"},
    },
    "events": [
        {
            "id": "ev1",
            "predicate": "chase",
            "roles": {"agent": "e1", "patient": "e2"},
            "tense": "past",
            "mood": "declarative",
        }
    ],
    "alignment": [
        {"node": "e1", "tokens": [0, 1]},
        {"node": "ev1", "tokens": [2]},
        {"node": "e2", "tokens": [3, 4]},
    ],
}


def mutate(**changes):
    graph = copy.deepcopy(BASE)
    graph.update(copy.deepcopy(changes))
    return graph


CASES = []


def case(name, graph, *, error=None, warning=None):
    CASES.append((name, graph, error, warning))


case(
    "role points at a missing entity",
    mutate(events=[{"id": "ev1", "predicate": "chase", "roles": {"agent": "e9"}, "mood": "declarative"}]),
    error="missing entity e9",
)

case(
    "alignment index past the end of the tokens",
    mutate(alignment=[{"node": "e1", "tokens": [0, 99]}]),
    error="past the end",
)

case(
    "alignment points at a missing node",
    mutate(alignment=[{"node": "e7", "tokens": [0]}]),
    error="missing entity e7",
)

case(
    "duplicate event ids",
    mutate(
        events=[
            {"id": "ev1", "predicate": "chase", "roles": {"agent": "e1"}, "mood": "declarative"},
            {"id": "ev1", "predicate": "run", "roles": {"agent": "e2"}, "mood": "declarative"},
        ]
    ),
    error="duplicate event id ev1",
)

case(
    "coref cycle",
    mutate(
        entities={
            "e1": {"concept": "dog", "coref": "e2"},
            "e2": {"concept": "cat", "coref": "e1"},
        }
    ),
    error="coref cycle",
)

case(
    "entity corefs itself",
    mutate(entities={"e1": {"concept": "dog", "coref": "e1"}, "e2": {"concept": "cat"}}),
    error="points at itself",
)

case(
    "discourse relation points at a missing event",
    mutate(discourse=[{"type": "sequence", "from": "ev1", "to": "ev4"}]),
    error="missing event ev4",
)

case(
    "interrogative mood with no question",
    mutate(
        events=[
            {"id": "ev1", "predicate": "chase", "roles": {"agent": "e1"}, "mood": "interrogative"}
        ]
    ),
    error="carries no question",
)

case(
    "question on a declarative event",
    mutate(
        events=[
            {
                "id": "ev1",
                "predicate": "chase",
                "roles": {"agent": "e1"},
                "mood": "declarative",
                "question": {"type": "who", "role": "agent", "target": "e1"},
            }
        ]
    ),
    error="mood is not interrogative",
)

case(
    "between with one singular ground",
    mutate(
        events=[
            {
                "id": "ev1",
                "predicate": "be.located",
                "roles": {"theme": "e1"},
                "spatial": {"figure": "e1", "relation": "between", "ground": "e2"},
                "mood": "declarative",
            }
        ]
    ),
    error="between with a single non-plural ground",
)

case(
    "mass noun carrying a quantity",
    mutate(
        entities={
            "e1": {"concept": "water", "number": "mass", "quantity": 3},
            "e2": {"concept": "cat", "number": "sg"},
        }
    ),
    error="mass but carries a quantity",
)

case(
    "complement points at a missing event",
    mutate(
        events=[
            {
                "id": "ev1",
                "predicate": "like",
                "roles": {"experiencer": "e1"},
                "complement": "ev9",
                "mood": "declarative",
            }
        ]
    ),
    error="missing event ev9",
)

case(
    "entity with no alignment span and not implicit",
    mutate(alignment=[{"node": "e1", "tokens": [0, 1]}, {"node": "ev1", "tokens": [2]}]),
    warning="no alignment span",
)

case(
    "orphan entity nothing references",
    mutate(
        entities={
            "e1": {"concept": "dog"},
            "e2": {"concept": "cat"},
            "e3": {"concept": "bird"},
        },
        alignment=[
            {"node": "e1", "tokens": [0]},
            {"node": "e2", "tokens": [3]},
            {"node": "e3", "tokens": [4]},
            {"node": "ev1", "tokens": [2]},
        ],
    ),
    warning="never referenced",
)

case(
    "who-question with no target to draw a gap for",
    mutate(
        events=[
            {
                "id": "ev1",
                "predicate": "chase",
                "roles": {"agent": "e1", "patient": "e2"},
                "mood": "interrogative",
                "question": {"type": "who", "role": "agent"},
            }
        ]
    ),
    warning="without a target",
)


# --- schema 0.2.0 -------------------------------------------------------------

TWO_EVENTS = {
    "events": [
        {"id": "ev1", "predicate": "rain", "mood": "declarative"},
        {"id": "ev2", "predicate": "chase", "roles": {"agent": "e1"}, "mood": "declarative"},
    ],
    "alignment": [
        {"node": "e1", "tokens": [0, 1]},
        {"node": "ev1", "tokens": [2]},
        {"node": "ev2", "tokens": [3]},
        {"node": "e2", "tokens": [4]},
    ],
}

case(
    "degree with nothing to apply it to",
    mutate(
        events=[
            {"id": "ev1", "predicate": "be.attribute", "roles": {"theme": "e1"},
             "degree": "very", "mood": "declarative"}
        ]
    ),
    error="degree with no attribute",
)

case(
    "comparand without a comparative degree",
    mutate(
        events=[
            {"id": "ev1", "predicate": "be.attribute", "roles": {"theme": "e1"},
             "attribute": "big", "degree": "superlative", "comparand": "e2",
             "mood": "declarative"}
        ]
    ),
    error="neither comparative nor equative",
)

case(
    "comparand pointing at a missing entity",
    mutate(
        events=[
            {"id": "ev1", "predicate": "be.attribute", "roles": {"theme": "e1"},
             "attribute": "big", "degree": "comparative", "comparand": "e8",
             "mood": "declarative"}
        ]
    ),
    error="missing entity e8",
)

case(
    "alignment pointing at a missing discourse relation",
    mutate(alignment=[{"node": "e1", "tokens": [0]}, {"node": "d1", "tokens": [2]}]),
    error="missing discourse relation d1",
)

case(
    "duplicate discourse ids",
    mutate(
        **TWO_EVENTS,
        discourse=[
            {"id": "d1", "type": "sequence", "from": "ev1", "to": "ev2"},
            {"id": "d1", "type": "cause", "from": "ev2", "to": "ev1"},
        ],
    ),
    error="duplicate discourse id d1",
)

case(
    "ability not marked irrealis",
    mutate(
        events=[
            {"id": "ev1", "predicate": "swim", "roles": {"agent": "e1"},
             "modality": "can", "mood": "declarative"}
        ]
    ),
    warning="not marked irrealis",
)

case(
    "condition antecedent asserted as fact",
    mutate(
        **TWO_EVENTS,
        discourse=[{"id": "d1", "type": "condition", "from": "ev1", "to": "ev2"}],
    ),
    warning="is not irrealis",
)

case(
    "discourse marker with no alignment span",
    mutate(
        **TWO_EVENTS,
        discourse=[
            {"id": "d1", "type": "sequence", "from": "ev1", "to": "ev2", "marker": "then"}
        ],
    ),
    warning="no alignment span",
)


# --- schema 0.3.0 -------------------------------------------------------------

case(
    "a non-directional relation with no ground",
    mutate(
        events=[
            {"id": "ev1", "predicate": "be.located", "roles": {"theme": "e1"},
             "spatial": [{"figure": "e1", "relation": "on"}], "mood": "declarative"}
        ]
    ),
    error="with no ground",
)

case(
    "no events and no speech act",
    mutate(events=[], alignment=[{"node": "e1", "tokens": [0]}, {"node": "e2", "tokens": [3]}]),
    error="must carry a speech_act",
)

case(
    "address points at a missing entity",
    mutate(address="e9"),
    error="missing entity e9",
)

case(
    "an entity anchored to a missing entity",
    mutate(
        entities={
            "e1": {"concept": "dog", "located": {"relation": "on", "ground": "e9"}},
            "e2": {"concept": "cat"},
        }
    ),
    error="missing entity e9",
)

case(
    "an entity anchored to itself",
    mutate(
        entities={
            "e1": {"concept": "dog", "located": {"relation": "on", "ground": "e1"}},
            "e2": {"concept": "cat"},
        }
    ),
    error="anchors the entity to itself",
)

case(
    "category points at a missing entity",
    mutate(
        events=[
            {"id": "ev1", "predicate": "be.category", "roles": {"theme": "e1"},
             "category": "e9", "mood": "declarative"}
        ]
    ),
    error="missing entity e9",
)

case(
    "modifies points at a missing entity",
    mutate(
        events=[
            {"id": "ev1", "predicate": "bark", "roles": {"agent": "e1"},
             "modifies": "e9", "mood": "declarative"}
        ]
    ),
    error="missing entity e9",
)

case(
    "never with positive polarity",
    mutate(
        events=[
            {"id": "ev1", "predicate": "chase", "roles": {"agent": "e1", "patient": "e2"},
             "frequency": "never", "polarity": "positive", "mood": "declarative"}
        ]
    ),
    warning="one of the two is wrong",
)


@pytest.mark.parametrize(
    "graph,want_error,want_warning",
    [pytest.param(g, e, w, id=name) for name, g, e, w in CASES],
)
def test_checker_catches(graph, want_error, want_warning):
    errors, warnings = check_graph(graph)
    haystack = errors if want_error else warnings
    needle = want_error or want_warning
    assert any(needle in message for message in haystack), (
        f"expected {'error' if want_error else 'warning'} containing {needle!r}\n"
        f"errors:   {errors}\nwarnings: {warnings}"
    )


def test_baseline_graph_is_clean():
    """Every case below mutates this graph, so it has to start clean."""
    errors, warnings = check_graph(copy.deepcopy(BASE))
    assert not errors and not warnings, f"errors={errors} warnings={warnings}"
