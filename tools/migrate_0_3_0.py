"""Migrate the tuning gold set from schema 0.2.0 to 0.3.0.

Two mechanical changes. Nothing here adds meaning: the 0.3.0 fields that hold what
0.2.0 could not — address, manner, frequency, located and the rest — are filled in by
hand where they apply, not guessed at by a script.

The held-out set is deliberately NOT migrated. It is locked at 0.2.0, and rewriting it
would break the record of what was scored. `check_gold` validates each graph against the
version it declares, so both sets coexist.

    python tools/migrate_0_3_0.py
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GOLD = ROOT / "gold"


def migrate(graph):
    changed = False

    if graph.get("schema_version") != "0.3.0":
        graph["schema_version"] = "0.3.0"
        changed = True

    for event in graph.get("events", []):
        spatial = event.get("spatial")
        if isinstance(spatial, dict):
            # One event can carry more than one figure-ground relation, so the field is
            # a list. Existing single relations become one-element lists.
            event["spatial"] = [spatial]
            changed = True

    return changed


def main():
    touched = 0
    for path in sorted(GOLD.glob("*.json")):
        graphs = json.loads(path.read_text(encoding="utf-8"))
        if any([migrate(graph) for graph in graphs]):
            path.write_text(
                json.dumps(graphs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            touched += 1
            print(f"migrated {path.name}")
    print(f"{touched} files changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
