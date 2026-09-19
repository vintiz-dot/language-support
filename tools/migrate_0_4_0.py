"""Migrate gold graphs from schema 0.3.0 to 0.4.0.

Unlike the 0.2.0 to 0.3.0 migration, this one is purely additive: `members` and
`coordination` on an entity, `focus` and `measure` on an event. Nothing that was valid at
0.3.0 becomes invalid, so the migration is a version bump and the interesting work is in
the annotations that follow it.

The held-out sets are deliberately NOT migrated. Set one is locked at 0.2.0 and set two at
0.3.0, and rewriting either would damage the record of what was scored against it.

    python tools/migrate_0_4_0.py           # report what would change
    python tools/migrate_0_4_0.py --write   # write it
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GOLD_DIR = ROOT / "gold"

FROM, TO = "0.3.0", "0.4.0"


def main():
    write = "--write" in sys.argv
    touched = 0
    for path in sorted(GOLD_DIR.glob("*.json")):
        graphs = json.loads(path.read_text(encoding="utf-8"))
        changed = 0
        for graph in graphs:
            if graph.get("schema_version") == FROM:
                graph["schema_version"] = TO
                changed += 1
        if not changed:
            continue
        touched += changed
        if write:
            path.write_text(
                json.dumps(graphs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        print(f"  {path.name}: {changed} graphs {FROM} -> {TO}")

    print()
    print(f"{touched} graphs {'migrated' if write else 'would migrate'}")
    if not write:
        print("re-run with --write to apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
