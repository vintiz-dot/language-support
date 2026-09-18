"""One-shot migration of the gold set from schema 0.1.0 to 0.2.0.

Three mechanical changes, applied everywhere:

  - bump schema_version
  - give every discourse relation an id, so it can carry an alignment span
  - move connective tokens off the event span and onto the relation span

and one judgement call applied by id: irrealis on events that are not asserted to
happen. Ability is the case that matters most, because "she can swim" must not render
as a swimming scene.

Kept in the repository rather than thrown away: it is the record of what changed and
why, and re-running it on migrated files is a no-op.

    python tools/migrate_0_2_0.py
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GOLD = ROOT / "gold"

# Events not asserted to occur. Ability and the antecedent of a condition; future tense
# is excluded on purpose, being asserted to happen later rather than merely possible.
IRREALIS = {
    ("g005", "ev1"): "ability, not an action in progress",
    ("g017", "ev1"): "denied ability, still not an action",
    ("g025", "ev1"): "ability under question",
    ("g046", "ev1"): "antecedent of a condition",
}

# Connective tokens currently sitting on an event span that belong to the relation.
# graph id -> (tokens for the relation, {event id: replacement span})
MARKER_SPANS = {
    "g042": ([3], {}),
    "g043": ([0, 6], {"ev1": [2], "ev2": [8]}),
    "g044": ([3], {}),
    "g045": ([3], {}),
    "g046": ([0], {"ev1": [1, 2]}),
}


def migrate(graph):
    changed = False

    if graph.get("schema_version") != "0.2.0":
        graph["schema_version"] = "0.2.0"
        changed = True

    graph_id = graph.get("id")

    for i, relation in enumerate(graph.get("discourse") or [], start=1):
        if "id" not in relation:
            # Rebuild so id leads, matching how events are written.
            ordered = {"id": f"d{i}"}
            ordered.update(relation)
            relation.clear()
            relation.update(ordered)
            changed = True

    if graph_id in MARKER_SPANS:
        marker_tokens, replacements = MARKER_SPANS[graph_id]
        alignment = graph.setdefault("alignment", [])
        relation_id = graph["discourse"][0]["id"]

        if not any(span["node"] == relation_id for span in alignment):
            for span in alignment:
                if span["node"] in replacements:
                    span["tokens"] = replacements[span["node"]]
            alignment.append({"node": relation_id, "tokens": marker_tokens})
            changed = True

    for event in graph.get("events", []):
        key = (graph_id, event.get("id"))
        if key in IRREALIS and "irrealis" not in event:
            event["irrealis"] = True
            changed = True

    return changed


def main():
    touched = 0
    for path in sorted(GOLD.glob("*.json")):
        graphs = json.loads(path.read_text(encoding="utf-8"))
        if any([migrate(graph) for graph in graphs]):
            path.write_text(json.dumps(graphs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            touched += 1
            print(f"migrated {path.name}")
    print(f"{touched} files changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
