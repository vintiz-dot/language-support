"""Which observable properties of a parse predict that the parse is right?

The project is teacher-first, so it does not need to be right about every sentence -- it
needs to know when it is not. At 11% core correct a renderer that draws everything is
unusable; one that draws what it is confident about and flags the rest is a product. That
turns the open question from "how do we raise 11%" into "what can be read off a parse,
without the answer, that tells us this one is safe to draw".

    python tools/confidence.py holdout3/predictions.json holdout3/gold
    python tools/confidence.py holdout2/predictions.json holdout2/gold

Every signal here is computable from the prediction alone. None of them may consult the
gold graph, because at render time there is no gold graph -- that is the whole point.

**These are diagnostics, not measurements.** All three held-out sets are spent, so a
threshold chosen on the numbers below is fitted to the set it was chosen on. Confirming one
needs a fresh draw. The tool reports each set separately so that a signal which works on
only one of them is visible as such.
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from renderer.strip import load_lexicon  # noqa: E402
from score import core_correct, load_gold, match_nodes, match_spanless_entities  # noqa: E402

DOLCH = ROOT / "lexicon" / "wordlists" / "dolch.json"


def carried_words():
    """Words a scene graph carries as a field, so having no picture is correct for them.

    Reusing the project's own classification rather than inventing a stoplist: `handled_by`
    already names the field that carries each one.
    """
    data = json.loads(DOLCH.read_text(encoding="utf-8"))
    return {
        entry["word"].lower()
        for entry in data["service_words"]
        if entry.get("class") in ("function", "gap")
    }


def covered_tokens(graph):
    out = set()
    for span in graph.get("alignment") or []:
        out.update(span["tokens"])
    return out


def signals(graph, carried, lexicon):
    """Everything readable off one predicted graph. No gold, by construction."""
    tokens = graph.get("tokens") or []
    events = graph.get("events") or []
    entities = graph.get("entities") or {}
    covered = covered_tokens(graph)

    missed = [
        token
        for index, token in enumerate(tokens)
        if index not in covered
        and any(c.isalpha() for c in token)
        and token.lower() not in carried
    ]

    concepts = [e.get("concept") for e in entities.values() if e.get("concept")]
    concepts += [e.get("predicate") for e in events if e.get("predicate")]
    unknown = [c for c in concepts if c not in lexicon]

    return {
        "no events": not events,
        "a review flag": bool(graph.get("review")),
        "a content word with no picture": bool(missed),
        "an event with no roles": any(not (e.get("roles") or {}) for e in events),
        "more than one event": len(events) > 1,
        "a discourse relation": bool(graph.get("discourse")),
        "coordination": any(e.get("members") for e in entities.values()),
        "a concept the lexicon lacks": bool(unknown),
        "over 8 words": len(tokens) > 8,
    }


def rate(hits, total):
    return f"{hits}/{total} ({hits / total:.0%})" if total else "     -"


def analyse(predictions, gold_graphs, label):
    carried = carried_words()
    lexicon = load_lexicon()

    rows = []
    for graph_id, gold in gold_graphs.items():
        pred = predictions.get(graph_id)
        if pred is None:
            continue
        entity_map = match_nodes(pred, gold, "e")
        entity_map.update(match_spanless_entities(pred, gold, entity_map))
        event_map = match_nodes(pred, gold, "ev")
        rows.append(
            {
                "id": graph_id,
                "correct": core_correct(pred, gold, entity_map, event_map),
                "signals": signals(pred, carried, lexicon),
            }
        )

    total = len(rows)
    correct = sum(r["correct"] for r in rows)
    print(f"{label}: {total} graphs, {rate(correct, total)} core correct")
    print()
    print(f"  {'signal':<32}{'raised':>10}{'correct when raised':>22}{'when not':>12}")
    names = list(rows[0]["signals"]) if rows else []
    for name in names:
        with_signal = [r for r in rows if r["signals"][name]]
        without = [r for r in rows if not r["signals"][name]]
        print(
            f"  {name:<32}{len(with_signal):>10}"
            f"{rate(sum(r['correct'] for r in with_signal), len(with_signal)):>22}"
            f"{rate(sum(r['correct'] for r in without), len(without)):>12}"
        )

    # A signal is only useful if withholding on it leaves a cleaner remainder. This is the
    # shape a teacher-first renderer actually needs: draw this many, be right this often.
    print()
    print("  withholding on each signal, one at a time:")
    print(f"  {'withhold when':<32}{'drawn':>8}{'of the set':>13}{'right when drawn':>19}")
    for name in names:
        kept = [r for r in rows if not r["signals"][name]]
        if not kept or len(kept) == total:
            continue
        print(
            f"  {name:<32}{len(kept):>8}{len(kept) / total:>12.0%}"
            f"{rate(sum(r['correct'] for r in kept), len(kept)):>19}"
        )

    # Everything at once: the honest ceiling for a rule of this kind.
    strict = [r for r in rows if not any(r["signals"].values())]
    print()
    print(
        f"  withholding on every signal: draws {len(strict)}/{total} "
        f"({len(strict) / total:.0%}), right {rate(sum(r['correct'] for r in strict), len(strict))}"
    )
    return rows


def main():
    if len(sys.argv) < 3:
        raise SystemExit("usage: python tools/confidence.py predictions.json gold_dir")
    predictions = {
        g["id"]: g
        for g in json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    }
    gold_dir = pathlib.Path(sys.argv[2])
    analyse(predictions, load_gold(ROOT / gold_dir), str(gold_dir))
    print()
    print("  Diagnostic, not a measurement: these sets are spent, so a threshold chosen")
    print("  here is fitted to the set it was chosen on. Confirming one needs a fresh draw.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
