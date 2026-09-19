"""Run the rule parser over every gold sentence and write predictions for scoring.

    python tools/run_parser.py
    python tools/run_parser.py holdout3/gold out.json --amr   # with the AMR fallback
    python tools/score.py predictions.json --detail
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from parser.rules import parse  # noqa: E402
from tools.check_gold import check_graph, validator_for  # noqa: E402

GOLD_DIR = ROOT / "gold"
OUT = ROOT / "predictions.json"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    gold_dir = pathlib.Path(args[0]) if args else GOLD_DIR
    out = pathlib.Path(args[1]) if len(args) > 1 else OUT

    fallback = None
    if "--amr" in sys.argv:
        from tools.amr_fallback import amr_fallback, prefill

        texts = [
            g["text"]
            for path in sorted(gold_dir.glob("*.json"))
            for g in json.loads(path.read_text(encoding="utf-8"))
        ]
        print(f"pre-parsing {len(texts)} sentences with AMR (this is the slow part)...")
        fallback = amr_fallback(cache=prefill({}, texts))

    predictions, failures, invalid = [], [], []
    for path in sorted(gold_dir.glob("*.json")):
        for gold in json.loads(path.read_text(encoding="utf-8")):
            try:
                graph = parse(gold["text"], tokens=gold["tokens"], fallback=fallback)
            except Exception as exc:
                failures.append((gold["id"], f"{type(exc).__name__}: {exc}"))
                continue
            graph["id"] = gold["id"]
            predictions.append(graph)
            # The gold annotations have always been validated; the parser's own output
            # never was, which is how it shipped discourse relations pointing at their own
            # event. The validator already rejected that shape -- nothing was asking it.
            errors, _warnings = check_graph(graph)
            errors += [
                f"{'.'.join(str(x) for x in e.path) or 'graph'}: {e.message}"
                for e in validator_for(graph.get("schema_version")).iter_errors(graph)
            ]
            invalid.extend((gold["id"], message) for message in errors)

    out.write_text(json.dumps(predictions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"parsed {len(predictions)} sentences -> {out.name}")
    if failures:
        print(f"{len(failures)} crashed:")
        for graph_id, message in failures:
            print(f"  {graph_id}  {message}")
    if invalid:
        print(f"{len(invalid)} schema or reference violations in the parser's own output:")
        for graph_id, message in invalid:
            print(f"  {graph_id}  {message}")
    return 1 if invalid or failures else 0


if __name__ == "__main__":
    sys.exit(main())
