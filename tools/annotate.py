"""Working tools for annotating a held-out set by hand.

Set three is drawn but unannotated. This builds the scaffold to type into, shows one
sentence at a time with its token indices, reports progress, validates what is finished so
far, and locks the set when it is done.

    python tools/annotate.py scaffold      # create the files, never overwriting work
    python tools/annotate.py status        # how many are done
    python tools/annotate.py show k004     # one sentence with its token indices
    python tools/annotate.py check         # validate the finished ones
    python tools/annotate.py lock          # hash, once check is clean

The set directory defaults to holdout3 and can be given as a second argument.
"""

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TODO = "TODO"
PER_FILE = 25


def paths(name):
    base = ROOT / name
    return base, base / "gold", base / "sentences.json"


def load_sentences(sentences_path):
    if not sentences_path.exists():
        raise SystemExit(f"no {sentences_path.relative_to(ROOT)}; draw the set first")
    return json.loads(sentences_path.read_text(encoding="utf-8"))


def tokenise(text):
    # The tokeniser only. This does not parse, and must not: the annotations are written
    # before the parser is ever run on these sentences.
    from parser.rules import _nlp

    return [token.text for token in _nlp().tokenizer(text)]


def load_gold(gold_dir):
    graphs = {}
    for path in sorted(gold_dir.glob("*.json")):
        for graph in json.loads(path.read_text(encoding="utf-8")):
            graphs[graph["id"]] = graph
    return graphs


def is_done(graph):
    return graph.get("notes") != TODO


def cmd_scaffold(name):
    base, gold_dir, sentences_path = paths(name)
    sentences = load_sentences(sentences_path)
    excluded = set()
    excluded_path = base / "excluded.json"
    if excluded_path.exists():
        excluded = {item["id"] for item in json.loads(excluded_path.read_text(encoding="utf-8"))}

    gold_dir.mkdir(parents=True, exist_ok=True)
    existing = load_gold(gold_dir)
    kept = [s for s in sentences if s["id"] not in excluded]

    written = 0
    for index in range(0, len(kept), PER_FILE):
        chunk = kept[index : index + PER_FILE]
        letter = "abcdefgh"[index // PER_FILE]
        out = gold_dir / f"gold-{letter}.json"
        graphs = []
        for item in chunk:
            if item["id"] in existing:
                graphs.append(existing[item["id"]])  # never overwrite work in progress
                continue
            graphs.append(
                {
                    "schema_version": "0.4.0",
                    "id": item["id"],
                    "text": item["text"],
                    "tokens": tokenise(item["text"]),
                    "entities": {},
                    "events": [],
                    "alignment": [],
                    "notes": TODO,
                }
            )
            written += 1
        out.write_text(json.dumps(graphs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  {out.relative_to(ROOT)}: {len(chunk)} sentences")

    print()
    print(f"{written} new stubs, {len(existing)} left untouched")
    print("Replace the TODO in notes when a graph is finished; anything still TODO is skipped.")
    return 0


def cmd_show(name, wanted):
    _, gold_dir, sentences_path = paths(name)
    for item in load_sentences(sentences_path):
        if item["id"] != wanted:
            continue
        tokens = tokenise(item["text"])
        print(item["id"], "|", item["text"])
        print()
        for i, token in enumerate(tokens):
            print(f"  {i:>2}  {token}")
        graph = load_gold(gold_dir).get(wanted)
        if graph is not None and is_done(graph):
            print()
            print("annotated:")
            print(json.dumps(graph, indent=2, ensure_ascii=False))
        return 0
    raise SystemExit(f"no sentence {wanted!r}")


def cmd_status(name):
    base, gold_dir, sentences_path = paths(name)
    sentences = load_sentences(sentences_path)
    graphs = load_gold(gold_dir)
    excluded_path = base / "excluded.json"
    excluded = (
        {item["id"] for item in json.loads(excluded_path.read_text(encoding="utf-8"))}
        if excluded_path.exists()
        else set()
    )

    done = [g for g in graphs.values() if is_done(g)]
    todo = [g for g in graphs.values() if not is_done(g)]
    total = len(sentences) - len(excluded)

    print(f"{name}: {len(done)}/{total} annotated, {len(excluded)} excluded")
    if todo:
        bar_done = len(done) * 30 // max(total, 1)
        print(f"  [{'#' * bar_done}{'.' * (30 - bar_done)}]")
        print()
        print("  next:", " ".join(sorted(g["id"] for g in todo)[:8]))
    gaps = [g["id"] for g in done if "GAP" in (g.get("notes") or "")]
    if gaps:
        print()
        print(f"  {len(gaps)} recorded a schema gap: {' '.join(gaps)}")
    return 0


def cmd_check(name):
    from tools.check_gold import check_graph, validator_for

    _, gold_dir, _ = paths(name)
    graphs = load_gold(gold_dir)
    done = {k: v for k, v in graphs.items() if is_done(v)}
    if not done:
        print("nothing annotated yet")
        return 0

    failed = 0
    for graph_id, graph in sorted(done.items()):
        problems = []
        try:
            validator_for(graph.get("schema_version")).validate(graph)
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            problems.append(str(exc).split("\n")[0])
        errors, warnings = check_graph(graph)
        problems += errors
        if problems:
            failed += 1
            print(f"FAIL {graph_id}")
            for message in problems:
                print(f"       {message}")
        elif warnings:
            print(f"WARN {graph_id}")
            for message in warnings:
                print(f"       {message}")

    print()
    print(f"{len(done)} annotated, {failed} failed")
    return 1 if failed else 0


def cmd_lock(name):
    base, gold_dir, sentences_path = paths(name)
    graphs = load_gold(gold_dir)
    todo = [g["id"] for g in graphs.values() if not is_done(g)]
    if todo:
        raise SystemExit(f"{len(todo)} still TODO; finish them before locking")
    if cmd_check(name) != 0:
        raise SystemExit("validation failed; nothing locked")

    files = {}
    for path in sorted(gold_dir.glob("*.json")):
        files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    lock = {
        "locked": __import__("datetime").date.today().isoformat(),
        "note": (
            "Annotations were written by hand and validated before the parser was run on "
            "any of these sentences. Scored once; the parser must not be tuned against "
            "this set."
        ),
        "files": files,
    }
    (base / "LOCK.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print()
    print(f"locked {len(files)} files")
    for filename, digest in files.items():
        print(f"  {filename}  {digest}")
    return 0


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command == "show":
        wanted = sys.argv[2] if len(sys.argv) > 2 else None
        name = sys.argv[3] if len(sys.argv) > 3 else "holdout3"
        if wanted is None:
            raise SystemExit("show needs a sentence id, e.g. show k004")
        return cmd_show(name, wanted)

    name = sys.argv[2] if len(sys.argv) > 2 else "holdout3"
    if command == "scaffold":
        return cmd_scaffold(name)
    if command == "status":
        return cmd_status(name)
    if command == "check":
        return cmd_check(name)
    if command == "lock":
        return cmd_lock(name)
    raise SystemExit(f"unknown command {command!r}; expected scaffold, show, status, check or lock")


if __name__ == "__main__":
    sys.exit(main())
