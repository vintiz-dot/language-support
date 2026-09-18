"""Run the rule parser over every gold sentence and write predictions for scoring.

    python tools/run_parser.py
    python tools/score.py predictions.json --detail
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from parser.rules import parse  # noqa: E402

GOLD_DIR = ROOT / "gold"
OUT = ROOT / "predictions.json"


def main():
    gold_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else GOLD_DIR
    out = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else OUT
    predictions, failures = [], []
    for path in sorted(gold_dir.glob("*.json")):
        for gold in json.loads(path.read_text(encoding="utf-8")):
            try:
                graph = parse(gold["text"], tokens=gold["tokens"])
            except Exception as exc:
                failures.append((gold["id"], f"{type(exc).__name__}: {exc}"))
                continue
            graph["id"] = gold["id"]
            predictions.append(graph)

    out.write_text(json.dumps(predictions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"parsed {len(predictions)} sentences -> {out.name}")
    if failures:
        print(f"{len(failures)} crashed:")
        for graph_id, message in failures:
            print(f"  {graph_id}  {message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
