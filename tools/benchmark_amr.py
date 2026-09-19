"""Compare the rule parser's role assignment against an off-the-shelf AMR parser.

The question this answers is narrow on purpose. AMR cannot be the target representation --
it deliberately discards number, definiteness and tense, and has no figure/ground -- so this
is not a bake-off between two candidate systems. It asks one thing: on the dimension a
trained parser is most likely to win, **who did what to whom**, does it actually win?

Both systems are judged by the same deliberately crude yardstick, which is what makes the
comparison fair even though the yardstick is poor:

  for every gold event that has a doer and a done-to, is the same pair of concepts in the
  same two slots?

AMR's :ARG0 is read as the doer and :ARG1 as the done-to. That mapping is right for ordinary
transitive verbs and wrong for some PropBank rolesets, so a few percent of the disagreement
here is the yardstick rather than either parser. Copular clauses are skipped entirely,
because gold writes them as be.attribute and AMR does not write them as predicates at all.

    pip install amrlib penman unidecode
    # then download a parse model into amrlib/data/model_stog
    python tools/benchmark_amr.py holdout3/gold
"""

import json
import pathlib
import sys
import warnings

warnings.filterwarnings("ignore")

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DOER = ("agent", "experiencer")
DONE_TO = ("patient", "theme")

COPULAS = {"be.attribute", "be.located", "be.category", "exist"}

# Gold normalises pronouns to speaker/addressee/person; AMR keeps the surface form or uses
# person. Neither is wrong, so both sides are widened to a set and compared for overlap.
EQUIVALENT = {
    "speaker": {"speaker", "i", "we", "person"},
    "addressee": {"addressee", "you", "person"},
    "person": {"person", "he", "she", "they", "them", "it", "man", "woman"},
    "thing": {"thing", "it", "that", "this", "one", "they", "them", "amr-unknown"},
}


def normalise(concept):
    """Strip the notational differences that are not disagreements about meaning.

    Gold writes give and bat.animal; AMR writes give-01 and person. Counting a PropBank
    sense suffix or an unlemmatised plural as a wrong role would measure the notation
    rather than either parser, and the first run of this benchmark did exactly that.
    """
    base = concept.split(".")[0].lower()
    head, _, tail = base.rpartition("-")
    if head and tail.isdigit():
        base = head
    if base.endswith("s") and not base.endswith("ss") and len(base) > 3:
        base = base[:-1]
    return base


def widen(concept):
    if concept is None:
        return set()
    base = normalise(concept)
    return EQUIVALENT.get(base, {base})


def same(a, b):
    if a is None or b is None:
        return False
    if isinstance(a, (list, set, tuple)) or isinstance(b, (list, set, tuple)):
        left = a if isinstance(a, (list, set, tuple)) else [a]
        right = b if isinstance(b, (list, set, tuple)) else [b]
        return any(same(x, y) for x in left for y in right)
    return bool(widen(a) & widen(b))


def gold_triples(graph):
    """(predicate, doer concept, done-to concept) for each gold event that has both."""
    entities = graph.get("entities", {})

    def concept(ref):
        node = entities.get(ref, {})
        if node.get("members"):
            return [concept(m) for m in node["members"]]
        return node.get("concept")

    out = []
    for event in graph.get("events", []):
        if event["predicate"] in COPULAS:
            continue
        roles = event.get("roles") or {}
        doer = next((roles[r] for r in DOER if r in roles), None)
        done = next((roles[r] for r in DONE_TO if r in roles), None)
        if doer and done:
            out.append((event["predicate"], concept(doer), concept(done)))
    return out


def amr_triples(penman_text):
    """(predicate lemma, :ARG0 concept, :ARG1 concept) for each predicate with both."""
    import penman

    try:
        graph = penman.decode(penman_text)
    except Exception:
        return []
    concepts = {i.source: i.target for i in graph.instances()}

    # AMR writes a coordinated argument as an and/or node whose :opN children are the
    # members. Gold approximates a group by its first member, so the fair comparison is a
    # list that matches if any member does -- the same allowance on both sides.
    members = {}
    for edge in graph.edges():
        if edge.role.startswith(":op") and concepts.get(edge.source) in ("and", "or"):
            members.setdefault(edge.source, []).append(concepts.get(edge.target, edge.target))

    def value(node):
        if node in members:
            return members[node]
        return concepts.get(node, node)

    args = {}
    for source, role, target in graph.edges():
        if role in (":ARG0", ":ARG1"):
            args.setdefault(source, {})[role] = value(target)

    out = []
    for node, slots in args.items():
        if ":ARG0" in slots and ":ARG1" in slots:
            out.append((concepts.get(node, ""), slots[":ARG0"], slots[":ARG1"]))
    return out


def score(predicted, gold):
    """Returns (matched predicate, both roles right, roles reversed) counts."""
    found = reversed_count = right = 0
    remaining = list(predicted)
    for predicate, doer, done in gold:
        hit = next((p for p in remaining if same(p[0], predicate)), None)
        if hit is None:
            continue
        remaining.remove(hit)
        found += 1
        if same(hit[1], doer) and same(hit[2], done):
            right += 1
        elif same(hit[1], done) and same(hit[2], doer):
            reversed_count += 1
    return found, right, reversed_count


def main():
    gold_dir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "holdout3/gold")
    from tools.score import load_gold
    from parser.rules import parse

    gold = load_gold(ROOT / gold_dir)
    ids = sorted(gold)
    sentences = [gold[i]["text"] for i in ids]

    print(f"{gold_dir}: {len(ids)} sentences")
    print("loading the AMR model (cpu)...")
    import amrlib

    stog = amrlib.load_stog_model(device="cpu", batch_size=4, num_beams=1)
    graphs = stog.parse_sents(sentences)

    totals = {"gold": 0, "rule": [0, 0, 0], "amr": [0, 0, 0]}
    rows = []
    for graph_id, penman_text in zip(ids, graphs):
        want = gold_triples(gold[graph_id])
        if not want:
            continue
        totals["gold"] += len(want)

        rule = parse(gold[graph_id]["text"], tokens=gold[graph_id]["tokens"])
        rule_got = gold_triples(rule)
        amr_got = amr_triples(penman_text or "")

        for name, got in (("rule", rule_got), ("amr", amr_got)):
            found, right, rev = score(got, want)
            totals[name][0] += found
            totals[name][1] += right
            totals[name][2] += rev
        rows.append((graph_id, want, rule_got, amr_got))

    print()
    print(f"gold events with both a doer and a done-to: {totals['gold']}")
    print()
    print(f"{'':6} {'predicate found':>16} {'both roles right':>18} {'reversed':>10}")
    for name in ("rule", "amr"):
        found, right, rev = totals[name]
        pct_found = f"{found}/{totals['gold']} ({round(100 * found / max(totals['gold'], 1))}%)"
        pct_right = f"{right}/{found} ({round(100 * right / max(found, 1))}%)" if found else "-"
        print(f"{name:6} {pct_found:>16} {pct_right:>18} {rev:>10}")

    out = ROOT / gold_dir.parent / "amr-benchmark.json"
    out.write_text(
        json.dumps(
            {
                "gold_triples": totals["gold"],
                "rule": dict(zip(("found", "right", "reversed"), totals["rule"])),
                "amr": dict(zip(("found", "right", "reversed"), totals["amr"])),
                "detail": [
                    {"id": i, "gold": w, "rule": r, "amr": a} for i, w, r, a in rows
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print()
    print(f"written to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
