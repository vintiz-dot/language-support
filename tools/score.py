"""Score predicted scene graphs against the gold set, dimension by dimension.

A single accuracy number is actively misleading here. A parser that finds both animals
in "the dog chased the cat" and then assigns agent and patient backwards draws a
confident, wrong picture — worse for a learner than a parser that fails loudly, because
nothing signals the error. So roles are scored separately from entities, and separately
again conditioned on the entities being right, which is the only way to see that failure.

Entity ids are not comparable across graphs, so correspondence is established through
the alignment: predicted and gold nodes are matched by token-span overlap, and every
role comparison runs through that mapping.

    python tools/score.py predictions.json
    python tools/score.py predictions.json --detail
"""

import json
import pathlib
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
GOLD_DIR = ROOT / "gold"

FEATURES = ("tense", "aspect", "polarity", "mood", "modality", "irrealis", "degree")

# Entity properties that change what gets drawn. quantity is the sharpest: getting it
# wrong draws the wrong number of things and makes counting questions unanswerable.
ENTITY_FEATURES = ("number", "quantity", "definite", "deixis", "quantifier", "gender")


def load_gold(directory=None):
    graphs = {}
    for path in sorted((directory or GOLD_DIR).glob("*.json")):
        for graph in json.loads(path.read_text(encoding="utf-8")):
            graphs[graph["id"]] = graph
    return graphs


def spans(graph):
    """node id -> set of token indices, unioned across however many spans it has."""
    out = defaultdict(set)
    for span in graph.get("alignment") or []:
        out[span["node"]].update(span["tokens"])
    return dict(out)


def iou(a, b):
    if not a and not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def match_nodes(pred, gold, prefix):
    """Greedy highest-overlap matching of predicted nodes to gold nodes.

    Deterministic: candidates are sorted by overlap, then by id, so the same inputs
    always produce the same mapping.
    """
    pred_spans = {k: v for k, v in spans(pred).items() if node_kind(k) == prefix}
    gold_spans = {k: v for k, v in spans(gold).items() if node_kind(k) == prefix}

    candidates = []
    for p_id, p_tokens in pred_spans.items():
        for g_id, g_tokens in gold_spans.items():
            overlap = iou(p_tokens, g_tokens)
            if overlap > 0:
                candidates.append((-overlap, p_id, g_id))
    candidates.sort()

    mapping, used_pred, used_gold = {}, set(), set()
    for _, p_id, g_id in candidates:
        if p_id in used_pred or g_id in used_gold:
            continue
        mapping[p_id] = g_id
        used_pred.add(p_id)
        used_gold.add(g_id)
    return mapping


def match_spanless_entities(pred, gold, matched):
    """Pair up entities that have no token span, by concept.

    An implicit entity — the addressee of an imperative, say — is not in the text at
    all, so overlap cannot identify it and it would otherwise read as spurious on one
    side and missing on the other. There are only ever one or two per graph, so
    matching on concept is safe here in a way it would not be for entities generally.
    """
    pred_spans, gold_spans = spans(pred), spans(gold)
    pred_left = sorted(
        k for k in pred.get("entities", {}) if k not in matched and not pred_spans.get(k)
    )
    gold_left = sorted(
        k
        for k in gold.get("entities", {})
        if k not in set(matched.values()) and not gold_spans.get(k)
    )

    extra, used = {}, set()
    for p_id in pred_left:
        for g_id in gold_left:
            if g_id in used:
                continue
            if pred["entities"][p_id].get("concept") == gold["entities"][g_id].get("concept"):
                extra[p_id] = g_id
                used.add(g_id)
                break
    return extra


def node_kind(node_id):
    if node_id.startswith("ev"):
        return "ev"
    if node_id.startswith("d"):
        return "d"
    return "e"


def events_by_id(graph):
    return {event["id"]: event for event in graph.get("events", [])}


def spatial_list(event):
    """spatial became an array in 0.3.0; accept either shape."""
    spatial = event.get("spatial")
    if spatial is None:
        return []
    return spatial if isinstance(spatial, list) else [spatial]


def ground_list(spatial):
    ground = (spatial or {}).get("ground")
    if ground is None:
        return []
    return list(ground) if isinstance(ground, list) else [ground]


def score_pair(pred, gold, tally, detail):
    """Accumulate one graph's results into tally. detail collects per-graph failures."""
    graph_id = gold["id"]
    scene_ok = True
    entity_map = match_nodes(pred, gold, "e")
    entity_map.update(match_spanless_entities(pred, gold, entity_map))
    event_map = match_nodes(pred, gold, "ev")
    gold_from_pred = entity_map

    pred_entities = pred.get("entities", {})
    gold_entities = gold.get("entities", {})

    # --- entities -------------------------------------------------------------
    # A true positive is a span match whose concept also agrees. A span match with the
    # wrong concept is counted apart, because it is a sense error rather than a
    # segmentation error and the two want different fixes.
    concept_ok = {}
    for p_id, g_id in entity_map.items():
        same = pred_entities[p_id].get("concept") == gold_entities[g_id].get("concept")
        concept_ok[g_id] = same
        if same:
            tally["entities"]["tp"] += 1
            for feature in ENTITY_FEATURES:
                g_value = gold_entities[g_id].get(feature)
                p_value = pred_entities[p_id].get(feature)
                if g_value is None and p_value is None:
                    continue
                tally["entity_features"][feature]["total"] += 1
                ok = g_value == p_value
                tally["entity_features"][feature]["correct"] += ok
                if not ok:
                    scene_ok = False
                    detail[graph_id].append(
                        f"{gold_entities[g_id].get('concept')}.{feature}: "
                        f"predicted {p_value!r}, gold {g_value!r}"
                    )
        else:
            tally["entities"]["wrong_concept"] += 1
            scene_ok = False
            detail[graph_id].append(
                f"entity concept: predicted {pred_entities[p_id].get('concept')!r} "
                f"for gold {gold_entities[g_id].get('concept')!r}"
            )

    matched_gold = set(entity_map.values())
    for g_id in gold_entities:
        if g_id not in matched_gold and not gold_entities[g_id].get("implicit"):
            tally["entities"]["fn"] += 1
            scene_ok = False
            detail[graph_id].append(f"entity missed: {gold_entities[g_id].get('concept')}")
    for p_id in pred_entities:
        if p_id not in entity_map:
            tally["entities"]["fp"] += 1
            scene_ok = False
            detail[graph_id].append(f"entity spurious: {pred_entities[p_id].get('concept')}")

    pred_events = events_by_id(pred)
    gold_events = events_by_id(gold)

    for p_ev_id, g_ev_id in event_map.items():
        p_event, g_event = pred_events[p_ev_id], gold_events[g_ev_id]

        if p_event.get("predicate") != g_event.get("predicate"):
            tally["predicate"]["wrong"] += 1
            detail[graph_id].append(
                f"predicate: predicted {p_event.get('predicate')!r} "
                f"for gold {g_event.get('predicate')!r}"
            )
            scene_ok = False
        tally["predicate"]["total"] += 1

        # --- roles ------------------------------------------------------------
        p_roles = p_event.get("roles") or {}
        g_roles = g_event.get("roles") or {}
        # Translate predicted fillers into gold ids so the two are comparable.
        p_roles_in_gold = {
            role: gold_from_pred.get(filler) for role, filler in p_roles.items()
        }

        # An event qualifies for the conditioned score only if every entity it
        # mentions was itself recognised correctly.
        participants = set(g_roles.values())
        entities_clean = all(concept_ok.get(g_id, False) for g_id in participants)

        for role, g_filler in g_roles.items():
            correct = p_roles_in_gold.get(role) == g_filler
            tally["roles"]["correct"] += correct
            tally["roles"]["total"] += 1
            if entities_clean:
                tally["roles_given_entities"]["correct"] += correct
                tally["roles_given_entities"]["total"] += 1
            if not correct:
                scene_ok = False
                detail[graph_id].append(
                    f"role {role}: predicted {p_roles_in_gold.get(role)}, gold {g_filler}"
                )
        for role in p_roles_in_gold:
            if role not in g_roles:
                tally["roles"]["total"] += 1
                scene_ok = False
                detail[graph_id].append(f"role {role}: spurious")

        # The failure this harness exists to surface.
        if (
            "agent" in g_roles
            and "patient" in g_roles
            and p_roles_in_gold.get("agent") == g_roles["patient"]
            and p_roles_in_gold.get("patient") == g_roles["agent"]
        ):
            tally["argument_swaps"] += 1
            detail[graph_id].append("ARGUMENT SWAP: agent and patient inverted")

        # --- spatial ----------------------------------------------------------
        # An event may carry several figure-ground relations, so the two lists are
        # matched before their fields are compared. Greedy on how many fields agree.
        p_spatials, g_spatials = spatial_list(p_event), spatial_list(g_event)

        def fields_of(spatial, translate):
            ground = {translate(x) for x in ground_list(spatial)}
            figure = translate(spatial.get("figure"))
            return spatial.get("relation"), figure, ground

        remaining = list(range(len(p_spatials)))
        for g_spatial in g_spatials:
            want = fields_of(g_spatial, lambda x: x)
            best, best_score = None, -1
            for i in remaining:
                got = fields_of(p_spatials[i], lambda x: gold_from_pred.get(x))
                agree = sum(a == b for a, b in zip(want, got))
                if agree > best_score:
                    best, best_score = i, agree
            got = fields_of(p_spatials[best], lambda x: gold_from_pred.get(x)) if best is not None else (None, None, set())
            if best is not None:
                remaining.remove(best)
            for field, a, b in zip(("relation", "figure", "ground"), want, got):
                tally["spatial"][field]["total"] += 1
                ok = a == b
                tally["spatial"][field]["correct"] += ok
                if not ok:
                    scene_ok = False
                    detail[graph_id].append(f"spatial {field} wrong")

        for i in remaining:
            tally["spatial"]["spurious"] += 1
            scene_ok = False
            detail[graph_id].append(
                f"spatial spurious: {p_spatials[i].get('relation')}"
            )

        # --- grammatical features ---------------------------------------------
        for feature in FEATURES:
            g_value, p_value = g_event.get(feature), p_event.get(feature)
            if g_value is None and p_value is None:
                continue
            tally["features"][feature]["total"] += 1
            ok = g_value == p_value
            tally["features"][feature]["correct"] += ok
            if not ok:
                scene_ok = False
                detail[graph_id].append(f"{feature}: predicted {p_value!r}, gold {g_value!r}")

    for g_ev_id in gold_events:
        if g_ev_id not in event_map.values():
            tally["events"]["fn"] += 1
            scene_ok = False
            detail[graph_id].append(f"event missed: {gold_events[g_ev_id].get('predicate')}")
    for p_ev_id in pred_events:
        if p_ev_id not in event_map:
            tally["events"]["fp"] += 1
            scene_ok = False
            detail[graph_id].append(f"event spurious: {pred_events[p_ev_id].get('predicate')}")

    # --- discourse ------------------------------------------------------------
    # Type and direction are scored apart: "because" reverses the arrow relative to text
    # order, so a parser can get every relation type right and every arrow backwards.
    g_relations = gold.get("discourse") or []
    p_relations = pred.get("discourse") or []
    p_translated = [
        (
            rel.get("type"),
            event_map.get(rel.get("from")),
            event_map.get(rel.get("to")),
        )
        for rel in p_relations
    ]
    for relation in g_relations:
        want = (relation.get("type"), relation.get("from"), relation.get("to"))
        bucket = "inferred" if relation.get("inferred") else "marked"
        tally["discourse"][bucket]["total"] += 1
        tally["discourse"]["type"]["total"] += 1
        tally["discourse"]["direction"]["total"] += 1
        type_hit = any(p[0] == want[0] for p in p_translated)
        full_hit = any(p == want for p in p_translated)
        reversed_hit = any(
            p[0] == want[0] and p[1] == want[2] and p[2] == want[1] for p in p_translated
        )
        tally["discourse"]["type"]["correct"] += type_hit
        tally["discourse"]["direction"]["correct"] += full_hit
        tally["discourse"][bucket]["correct"] += full_hit
        if type_hit and reversed_hit and not full_hit:
            tally["discourse"]["reversed"] += 1
            detail[graph_id].append(f"discourse {want[0]}: arrow reversed")
        elif not full_hit and bucket == "marked":
            scene_ok = False
            detail[graph_id].append(f"discourse {want[0]}: not recovered")

    # --- alignment ------------------------------------------------------------
    p_spans, g_spans = spans(pred), spans(gold)
    full_map = {**entity_map, **event_map, **match_nodes(pred, gold, "d")}
    for p_id, g_id in full_map.items():
        if not p_spans.get(p_id) and not g_spans.get(g_id):
            continue
        overlap = iou(p_spans.get(p_id, set()), g_spans.get(g_id, set()))
        tally["alignment"]["iou_sum"] += overlap
        tally["alignment"]["n"] += 1
        tally["alignment"]["exact"] += p_spans.get(p_id) == g_spans.get(g_id)

    tally["scene_correct"] += scene_ok
    tally["graphs"] += 1


def new_tally():
    return {
        "graphs": 0,
        "scene_correct": 0,
        "argument_swaps": 0,
        "entities": Counter(),
        "events": Counter(),
        "predicate": Counter(),
        "roles": Counter(),
        "roles_given_entities": Counter(),
        "spatial": {k: Counter() for k in ("relation", "figure", "ground")} | {"spurious": 0},
        "features": {k: Counter() for k in FEATURES},
        "entity_features": {k: Counter() for k in ENTITY_FEATURES},
        "discourse": {
            "type": Counter(),
            "direction": Counter(),
            "marked": Counter(),
            "inferred": Counter(),
            "reversed": 0,
        },
        "alignment": Counter(),
    }


def pct(correct, total):
    return f"{correct}/{total} ({correct / total:.0%})" if total else "-"


def render(tally):
    lines = []
    e = tally["entities"]
    precision_denom = e["tp"] + e["fp"] + e["wrong_concept"]
    recall_denom = e["tp"] + e["fn"] + e["wrong_concept"]

    lines.append(f"graphs scored: {tally['graphs']}")
    lines.append(f"scene correct: {pct(tally['scene_correct'], tally['graphs'])}")
    lines.append("  every entity, role, relation and feature right; the picture would be right")
    lines.append("")
    lines.append("entities")
    lines.append(f"  precision      {pct(e['tp'], precision_denom)}")
    lines.append(f"  recall         {pct(e['tp'], recall_denom)}")
    lines.append(f"  wrong concept  {e['wrong_concept']}   (span found, sense wrong)")
    lines.append(f"  missed         {e['fn']}")
    lines.append(f"  spurious       {e['fp']}")
    lines.append("")
    lines.append("entity properties (on correctly identified entities)")
    for feature in ENTITY_FEATURES:
        counter = tally["entity_features"][feature]
        if counter["total"]:
            lines.append(f"  {feature:<11} {pct(counter['correct'], counter['total'])}")
    lines.append("")
    lines.append("roles")
    lines.append(f"  overall            {pct(tally['roles']['correct'], tally['roles']['total'])}")
    lines.append(
        f"  given right entities {pct(tally['roles_given_entities']['correct'], tally['roles_given_entities']['total'])}"
    )
    lines.append(f"  argument swaps     {tally['argument_swaps']}   (agent and patient inverted)")
    lines.append("")
    lines.append("predicates")
    lines.append(
        f"  correct  {pct(tally['predicate']['total'] - tally['predicate']['wrong'], tally['predicate']['total'])}"
    )
    lines.append(f"  events missed {tally['events']['fn']}, spurious {tally['events']['fp']}")
    lines.append("")
    lines.append("spatial")
    for field in ("relation", "figure", "ground"):
        counter = tally["spatial"][field]
        lines.append(f"  {field:<9} {pct(counter['correct'], counter['total'])}")
    lines.append(f"  spurious  {tally['spatial']['spurious']}")
    lines.append("")
    lines.append("features")
    for feature in FEATURES:
        counter = tally["features"][feature]
        if counter["total"]:
            lines.append(f"  {feature:<9} {pct(counter['correct'], counter['total'])}")
    lines.append("")
    lines.append("discourse")
    lines.append(f"  type      {pct(tally['discourse']['type']['correct'], tally['discourse']['type']['total'])}")
    lines.append(
        f"  direction {pct(tally['discourse']['direction']['correct'], tally['discourse']['direction']['total'])}"
    )
    lines.append(f"  reversed  {tally['discourse']['reversed']}   (right relation, arrow backwards)")
    lines.append(
        f"  marked    {pct(tally['discourse']['marked']['correct'], tally['discourse']['marked']['total'])}"
        "   (a connective realises it; a rule parser can reach these)"
    )
    lines.append(
        f"  inferred  {pct(tally['discourse']['inferred']['correct'], tally['discourse']['inferred']['total'])}"
        "   (reader supplies it; not counted against the scene)"
    )
    lines.append("")
    a = tally["alignment"]
    mean_iou = a["iou_sum"] / a["n"] if a["n"] else 0.0
    lines.append("alignment")
    lines.append(f"  mean overlap {mean_iou:.2f}")
    lines.append(f"  exact spans  {pct(a['exact'], a['n'])}")
    return "\n".join(lines)


def score_all(predictions, gold_graphs):
    tally = new_tally()
    detail = defaultdict(list)
    missing = []
    for graph_id, gold in gold_graphs.items():
        pred = predictions.get(graph_id)
        if pred is None:
            missing.append(graph_id)
            continue
        score_pair(pred, gold, tally, detail)
    return tally, detail, missing


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: python tools/score.py predictions.json [--detail]")
    path = pathlib.Path(sys.argv[1])
    show_detail = "--detail" in sys.argv

    predictions = {g["id"]: g for g in json.loads(path.read_text(encoding="utf-8"))}
    gold_dir = None
    for arg in sys.argv[2:]:
        if not arg.startswith("--"):
            gold_dir = pathlib.Path(arg)
    gold_graphs = load_gold(gold_dir)
    tally, detail, missing = score_all(predictions, gold_graphs)

    print(render(tally))
    if missing:
        print()
        print(f"no prediction for {len(missing)} graphs: {', '.join(sorted(missing)[:8])}")

    if show_detail and detail:
        print()
        print("failures by graph:")
        for graph_id in sorted(detail):
            print(f"  {graph_id}  {gold_graphs[graph_id]['text']}")
            for message in detail[graph_id]:
                print(f"      {message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
