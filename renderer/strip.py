"""Turn a scene graph into a strip of pictures laid over the words they came from.

A picture sits over a **span**, not over a word. That distinction is the whole project:
*look after his sister* is one picture over two words, not a verb symbol followed by a
preposition symbol, and *the dog* is one picture over two words rather than a determiner
nobody can draw. Function words carry no picture at all because the graph carries them as
fields -- `number`, `definite`, `tense` -- and 48% of the Dolch list is like that.

It also makes the strip an inspection tool. When the parser gets a sentence wrong the
picture sits over the wrong words, so the teacher sees the mistake in the place it
happened rather than being told a score.

Groups and structural concepts are deliberately pictureless. A coordinated group has no
concept of its own -- it is drawn by showing its members -- and `be.located` is a placement
rather than a thing.
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEXICON = ROOT / "lexicon" / "concepts.json"
OVERRIDES = ROOT / "lexicon" / "overrides.json"

STATIC = "https://static.arasaac.org/pictograms/{id}/{id}_500.png"
API = "https://api.arasaac.org/v1/pictograms/{id}"

ATTRIBUTION = (
    "ARASAAC pictograms: author Sergio Palao, origin ARASAAC (https://arasaac.org), "
    "owned by the Government of Aragon, licensed CC BY-NC-SA."
)


def load_lexicon(path=None):
    data = json.loads((path or LEXICON).read_text(encoding="utf-8"))
    return data["concepts"]


def load_overrides(path=None):
    path = path or OVERRIDES
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("concepts", {})


def save_override(concept, pictogram, path=None):
    """Record a teacher's choice. Keyed by concept, so fixing it once fixes it everywhere."""
    path = path or OVERRIDES
    data = {"concepts": load_overrides(path)}
    if pictogram is None:
        data["concepts"].pop(concept, None)
    else:
        data["concepts"][concept] = pictogram
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data["concepts"]


def picture_url(pictogram, plural=False, action=None, colour=True):
    """The static CDN unless a rendering parameter applies, which only the API honours.

    ARASAAC renders plural and tense server side, so several scene graph fields become
    URL parameters rather than image work here.
    """
    params = []
    if plural:
        params.append("plural=true")
    if action in ("past", "future"):
        params.append(f"action={action}")
    if not colour:
        params.append("color=false")
    if not params:
        return STATIC.format(id=pictogram)
    return API.format(id=pictogram) + "?" + "&".join(params)


def runs(span):
    """Split a span into contiguous stretches of tokens.

    An alignment span need not be contiguous. In *Put the box on the shelf* the event owns
    *Put* and *on* with the object between them, and a discourse relation owns *First* and
    *then* a clause apart. Rendering such a span as one cell would print "Put on" and take
    *on* out of its place, so the strip would no longer read as the sentence. The picture
    goes on the first stretch and the rest stay where they belong, tied to the same node.
    """
    out = []
    for index in sorted(span):
        if out and index == out[-1][-1] + 1:
            out[-1].append(index)
        else:
            out.append([index])
    return out


def spans_by_node(graph):
    out = {}
    for span in graph.get("alignment") or []:
        out.setdefault(span["node"], set()).update(span["tokens"])
    return out


def flags_by_node(graph):
    out = {}
    for flag in graph.get("review") or []:
        out.setdefault(flag["node"], []).append(flag.get("reason", "review"))
    return out


def candidates(graph):
    """Every node that could own a picture, as (node id, kind, concept, params)."""
    out = []
    entities = graph.get("entities", {})
    for node_id, entity in entities.items():
        if entity.get("members"):
            continue  # a group is drawn by showing its members
        concept = entity.get("concept")
        if not concept:
            continue
        out.append(
            (
                node_id,
                "entity",
                concept,
                {"plural": entity.get("number") == "pl"},
            )
        )
    for event in graph.get("events", []):
        concept = event.get("predicate")
        if not concept:
            continue
        out.append(
            (
                event["id"],
                "event",
                concept,
                {
                    "action": event.get("tense"),
                    "negated": event.get("polarity") == "negative",
                    "attribute": event.get("attribute"),
                },
            )
        )
    return out


def drawable(concept, params):
    """What the cell should actually show a picture of.

    `be.attribute` is a structural predicate -- there is no picture of attribution -- but
    the attribute it asserts is an ordinary concept and is the whole content of the claim.
    *The dog is not big* with nothing over *is not big* loses the sentence; with `big`
    crossed out it keeps it.
    """
    return params.get("attribute") or concept


def build(graph, lexicon, overrides=None, colour=True):
    """A scene graph plus the lexicon becomes an ordered strip of cells.

    Every token appears exactly once, either inside a picture cell or as a bare word, so
    the strip can be laid directly over the sentence the teacher typed.
    """
    overrides = overrides or {}
    tokens = graph.get("tokens") or []
    spans = spans_by_node(graph)
    flags = flags_by_node(graph)

    # Longest span first, so a phrasal verb wins over anything inside it. Ties break on
    # position, which keeps the result stable rather than merely deterministic.
    ranked = sorted(
        (c for c in candidates(graph) if spans.get(c[0])),
        key=lambda c: (-len(spans[c[0]]), min(spans[c[0]])),
    )

    claimed, cells = set(), []
    for node_id, kind, concept, params in ranked:
        span = spans[node_id]
        if span & claimed:
            continue
        claimed |= span
        for part, run in enumerate(runs(span)):
            cells.append(cell(node_id, kind, concept, params, run, tokens, lexicon,
                              overrides, flags, colour, part))

    for index, token in enumerate(tokens):
        if index not in claimed:
            cells.append(
                {
                    "tokens": [index],
                    "start": index,
                    "text": token,
                    "kind": "word",
                    "carried": True,
                }
            )

    cells.sort(key=lambda c: c["start"])
    return {
        "text": graph.get("text", " ".join(tokens)),
        "tokens": tokens,
        "cells": cells,
        "speech_act": graph.get("speech_act"),
        "attribution": ATTRIBUTION,
    }


def cell(node_id, kind, concept, params, span, tokens, lexicon, overrides, flags, colour,
         part=0):
    shown = drawable(concept, params)
    entry = lexicon.get(shown) or {"match": "unknown"}
    pictogram = entry.get("pictogram")
    match = entry.get("match", "unknown")

    overridden = shown in overrides
    if overridden:
        pictogram = overrides[shown]
        match = "chosen"

    ordered = sorted(span)
    out = {
        "tokens": ordered,
        "start": ordered[0],
        "text": " ".join(tokens[i] for i in ordered),
        "node": node_id,
        "kind": kind,
        "concept": shown,
        "predicate": concept if shown != concept else None,
        "match": match,
        "overridden": overridden,
        "negated": bool(params.get("negated")),
        "uncertain": "parse_uncertain" in flags.get(node_id, []),
        "flags": flags.get(node_id, []),
    }
    if match == "structural":
        out["note"] = entry.get("structural")
    if part:
        # The picture was drawn on the first stretch of this span; this is the rest of it.
        out["continues"] = True
        return out
    if pictogram:
        out["pictogram"] = pictogram
        out["url"] = picture_url(
            pictogram,
            plural=bool(params.get("plural")),
            action=params.get("action"),
            colour=colour,
        )
    return out
