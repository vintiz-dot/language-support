"""Validate scene graphs against the schema, then against the rules the schema cannot express.

JSON Schema checks shape. It cannot check that roles.agent points at an entity that
exists, that alignment indices fall inside the token list, or that a coref chain
terminates. Those are the errors that actually reach a child as a wrong picture, so
they get checked here.

    python tools/check_gold.py validate
    python tools/check_gold.py concepts
"""

import json
import pathlib
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "scene-graph.schema.json"
# Older graphs validate against the version they were written for. The held-out set is
# locked at 0.2.0 and must keep validating without being rewritten.
FROZEN_SCHEMAS = {"0.2.0": ROOT / "schema" / "scene-graph-0.2.0.json"}

# Directions that name a path with no landmark: fall down, Away they marched. Every other
# relation needs a ground, or there is nothing to draw the figure against.
GROUNDLESS_RELATIONS = {"up", "down", "away", "along", "back", "off", "out-of", "through", "around"}
GOLD_DIR = ROOT / "gold"


def load_gold(directory=None):
    """Yield (path, index, graph) for every scene graph in a directory of gold files."""
    for path in sorted((directory or GOLD_DIR).glob("*.json")):
        graphs = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(graphs, list):
            raise SystemExit(f"{path.name}: expected a JSON array of scene graphs")
        for i, graph in enumerate(graphs):
            yield path, i, graph


def modifier_concept(modifier):
    """A modifier is a bare concept id, or an object carrying a degree. One accessor."""
    return modifier if isinstance(modifier, str) else modifier["concept"]


def modifier_degree(modifier):
    return None if isinstance(modifier, str) else modifier.get("degree")


def ground_refs(spatial):
    """spatial.ground is absent, a single ref, or a list of them; normalise to a list."""
    ground = spatial.get("ground")
    if ground is None:
        return []
    return ground if isinstance(ground, list) else [ground]


def spatial_list(event):
    """spatial became an array in 0.3.0; accept either shape so 0.2.0 graphs still read."""
    spatial = event.get("spatial")
    if spatial is None:
        return []
    return spatial if isinstance(spatial, list) else [spatial]


def check_graph(graph):
    """Return (errors, warnings) for one scene graph."""
    errors, warnings = [], []

    entities = graph.get("entities", {})
    events = graph.get("events", [])
    tokens = graph.get("tokens", [])
    n_tokens = len(tokens)

    event_ids = [ev.get("id") for ev in events]
    for event_id, count in Counter(event_ids).items():
        if count > 1:
            errors.append(f"duplicate event id {event_id}")
    event_ids = set(event_ids)

    discourse = graph.get("discourse") or []
    discourse_ids = [rel.get("id") for rel in discourse]
    for rel_id, count in Counter(discourse_ids).items():
        if count > 1:
            errors.append(f"duplicate discourse id {rel_id}")
    discourse_ids = set(discourse_ids)

    def need_entity(ref, where):
        if ref not in entities:
            errors.append(f"{where} references missing entity {ref}")

    def need_event(ref, where):
        if ref not in event_ids:
            errors.append(f"{where} references missing event {ref}")

    def need_node(ref, where):
        if ref is None:
            errors.append(f"{where} has no node reference")
        elif ref.startswith("ev"):
            need_event(ref, where)
        elif ref.startswith("d"):
            if ref not in discourse_ids:
                errors.append(f"{where} references missing discourse relation {ref}")
        else:
            need_entity(ref, where)

    # Track which entities anything points at, to find orphans later.
    referenced = set()

    for ref, entity in entities.items():
        for field in ("possessor", "coref"):
            target = entity.get(field)
            if target is None:
                continue
            need_entity(target, f"{ref}.{field}")
            referenced.add(target)
            if target == ref:
                errors.append(f"{ref}.{field} points at itself")
        anchoring = entity.get("located")
        if anchoring is not None:
            ground = anchoring.get("ground")
            need_entity(ground, f"{ref}.located.ground")
            referenced.add(ground)
            if ground == ref:
                errors.append(f"{ref}.located anchors the entity to itself")

        if entity.get("number") == "mass" and "quantity" in entity:
            errors.append(f"{ref} is mass but carries a quantity")
        if entity.get("quantity") is not None and entity.get("number") == "sg" and entity["quantity"] != 1:
            warnings.append(f"{ref} is singular but quantity is {entity['quantity']}")

    # A coref chain must terminate rather than loop.
    for ref in entities:
        seen, cursor = {ref}, entities[ref].get("coref")
        while cursor in entities:
            if cursor in seen:
                errors.append(f"coref cycle through {ref}")
                break
            seen.add(cursor)
            cursor = entities[cursor].get("coref")

    for event in events:
        event_id = event.get("id", "?")

        for role, ref in (event.get("roles") or {}).items():
            need_entity(ref, f"{event_id}.roles.{role}")
            referenced.add(ref)

        for n, spatial in enumerate(spatial_list(event)):
            where = f"{event_id}.spatial[{n}]"
            figure = spatial.get("figure")
            if figure is not None:
                need_entity(figure, f"{where}.figure")
                referenced.add(figure)
            grounds = ground_refs(spatial)
            for ref in grounds:
                need_entity(ref, f"{where}.ground")
                referenced.add(ref)
            relation = spatial.get("relation")
            if not grounds and relation not in GROUNDLESS_RELATIONS:
                errors.append(
                    f"{where} uses {relation!r} with no ground, and only a bare direction "
                    "may leave one out"
                )
            if relation == "between":
                # between needs two reference points: either two grounds or one plural ground.
                plural_ground = (
                    len(grounds) == 1
                    and entities.get(grounds[0], {}).get("number") == "pl"
                )
                if len(grounds) < 2 and not plural_ground:
                    errors.append(f"{where} uses between with a single non-plural ground")

        if event.get("complement") is not None:
            need_event(event["complement"], f"{event_id}.complement")
            if event["complement"] == event_id:
                errors.append(f"{event_id}.complement points at itself")

        for field in ("category", "modifies"):
            ref = event.get(field)
            if ref is not None:
                need_entity(ref, f"{event_id}.{field}")
                referenced.add(ref)

        if event.get("frequency") == "never" and event.get("polarity") == "positive":
            warnings.append(
                f"{event_id} is never but polarity is positive; one of the two is wrong"
            )

        if event.get("degree") and not event.get("attribute"):
            errors.append(f"{event_id} carries a degree with no attribute to apply it to")

        comparand = event.get("comparand")
        if comparand is not None:
            need_entity(comparand, f"{event_id}.comparand")
            referenced.add(comparand)
            if event.get("degree") not in ("comparative", "equative"):
                errors.append(
                    f"{event_id} has a comparand but its degree is neither comparative nor equative"
                )

        if event.get("modality") in ("can", "may") and not event.get("irrealis"):
            warnings.append(
                f"{event_id} expresses {event['modality']} but is not marked irrealis, "
                "so it may render as an action taking place"
            )

        question = event.get("question")
        if question:
            if event.get("mood") != "interrogative":
                errors.append(f"{event_id} carries a question but mood is not interrogative")
            target = question.get("target")
            if target is not None:
                need_node(target, f"{event_id}.question.target")
                if not target.startswith(("ev", "d")):
                    referenced.add(target)
            if question.get("type") in ("who", "what", "how-many") and target is None:
                warnings.append(
                    f"{event_id} asks {question['type']} without a target, so no gap can be drawn"
                )
        elif event.get("mood") == "interrogative":
            errors.append(f"{event_id} is interrogative but carries no question")

    address = graph.get("address")
    if address is not None:
        need_entity(address, "address")
        referenced.add(address)

    if not events and not graph.get("speech_act"):
        errors.append("a graph with no events must carry a speech_act")

    setting = graph.get("setting") or {}
    if setting.get("location"):
        need_entity(setting["location"], "setting.location")
        referenced.add(setting["location"])

    events_by_id = {ev.get("id"): ev for ev in events}
    for i, relation in enumerate(discourse):
        for field in ("from", "to"):
            need_event(relation.get(field), f"discourse[{i}].{field}")
        if relation.get("from") == relation.get("to"):
            errors.append(f"discourse[{i}] links an event to itself")
        if relation.get("marker") and relation.get("inferred"):
            errors.append(
                f"discourse[{i}] has a marker but is flagged inferred; it is one or the other"
            )
        if not relation.get("marker") and not relation.get("inferred"):
            warnings.append(
                f"discourse[{i}] has no marker and is not flagged inferred, so it is unclear "
                "whether a parser could ever find it"
            )
        if relation.get("type") == "condition":
            antecedent = events_by_id.get(relation.get("from"))
            if antecedent is not None and not antecedent.get("irrealis"):
                warnings.append(
                    f"discourse[{i}] is a condition but {relation.get('from')} is not irrealis, "
                    "so a hypothetical may render as fact"
                )

    aligned = defaultdict(list)
    for i, span in enumerate(graph.get("alignment") or []):
        node = span.get("node")
        need_node(node, f"alignment[{i}].node")
        for index in span.get("tokens", []):
            if index >= n_tokens:
                errors.append(
                    f"alignment[{i}] token index {index} is past the end of {n_tokens} tokens"
                )
            else:
                aligned[node].append(index)

    for ref, entity in entities.items():
        if ref not in aligned and not entity.get("implicit"):
            warnings.append(f"{ref} has no alignment span and is not marked implicit")
        if ref not in referenced:
            warnings.append(f"{ref} is never referenced by any event, relation or other entity")

    for event in events:
        if event.get("id") not in aligned:
            warnings.append(f"{event.get('id')} has no alignment span")

    for relation in discourse:
        if relation.get("marker") and relation.get("id") not in aligned:
            warnings.append(
                f"{relation.get('id')} has the marker {relation['marker']!r} but no alignment span"
            )

    for flag in graph.get("review") or []:
        need_node(flag.get("node"), "review.node")

    return errors, warnings


def collect_concepts(graph):
    """Every concept id the graph asks the lexicon for, tagged by where it came from."""
    found = []
    for entity in graph.get("entities", {}).values():
        found.append((entity["concept"], "entity"))
        for modifier in entity.get("modifiers") or []:
            found.append((modifier_concept(modifier), "modifier"))
    for event in graph.get("events", []):
        found.append((event["predicate"], "predicate"))
        if event.get("attribute"):
            found.append((event["attribute"], "attribute"))
    setting = graph.get("setting") or {}
    for field in ("time", "weather"):
        if setting.get(field):
            found.append((setting[field], field))
    return found


def cmd_validate(directory=None):
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        raise SystemExit("jsonschema is required: pip install jsonschema")

    validators = {}

    def validator_for(version):
        if version not in validators:
            path = FROZEN_SCHEMAS.get(version, SCHEMA_PATH)
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            validators[version] = Draft202012Validator(schema)
        return validators[version]

    total = 0
    failed = 0
    warned = 0
    seen_ids = {}

    for path, index, graph in load_gold(directory):
        total += 1
        label = f"{path.name}[{index}] {graph.get('id', '?')}"

        validator = validator_for(graph.get("schema_version"))
        errors = [
            f"schema: {'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in sorted(validator.iter_errors(graph), key=lambda e: list(e.absolute_path))
        ]
        warnings = []

        if not errors:
            ref_errors, warnings = check_graph(graph)
            errors.extend(ref_errors)

        graph_id = graph.get("id")
        if graph_id in seen_ids:
            errors.append(f"duplicate gold id, already used by {seen_ids[graph_id]}")
        else:
            seen_ids[graph_id] = label

        if errors:
            failed += 1
            print(f"FAIL {label}")
            for message in errors:
                print(f"       {message}")
        elif warnings:
            warned += 1
            print(f"WARN {label}")
            for message in warnings:
                print(f"       {message}")

    print()
    print(f"{total} graphs, {failed} failed, {warned} with warnings only")
    return 1 if failed else 0


def cmd_concepts():
    counts = Counter()
    sources = defaultdict(set)
    for _, _, graph in load_gold():
        for concept, kind in collect_concepts(graph):
            counts[concept] += 1
            sources[concept].add(kind)

    out = ROOT / "lexicon" / "concepts-required.json"
    payload = [
        {"concept": concept, "count": count, "roles": sorted(sources[concept])}
        for concept, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"{len(counts)} distinct concepts across {sum(counts.values())} uses")
    print(f"written to {out.relative_to(ROOT)}")
    print()
    print("most frequent:")
    for concept, count in counts.most_common(12):
        print(f"  {count:>3}  {concept:<16} {','.join(sorted(sources[concept]))}")
    return 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "validate"
    target = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else None
    if command == "validate":
        sys.exit(cmd_validate(target))
    elif command == "concepts":
        sys.exit(cmd_concepts())
    else:
        raise SystemExit(f"unknown command {command!r}; expected validate or concepts")
