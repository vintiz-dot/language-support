"""Measure how much Grade 1-2 vocabulary ARASAAC can actually draw.

A search returning results is not coverage. ARASAAC's search is fuzzy, so asking for
"hungry" can return food pictograms. Coverage here means a returned pictogram carries
the search term as an exact keyword; anything else is a near miss a human has to judge.

Two sources:

    python tools/check_coverage.py gold     concepts the gold set actually asks for
    python tools/check_coverage.py dolch    a standard Grade 1-2 sight word list

The gold run is a floor check on a sample this project chose itself, so it is biased
toward concrete nouns. The Dolch run is the real measurement, and it splits the list
into words that need a picture and words the scene graph carries structurally.

Responses are cached under lexicon/.arasaac-cache so re-runs are offline and the API
gets hit once per term.

ARASAAC pictograms: author Sergio Palao, origin ARASAAC (https://arasaac.org),
owned by the Government of Aragon, licensed CC BY-NC-SA.
"""

import json
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONCEPTS = ROOT / "lexicon" / "concepts-required.json"
DOLCH = ROOT / "lexicon" / "wordlists" / "dolch.json"
CACHE_DIR = ROOT / "lexicon" / ".arasaac-cache"

API = "https://api.arasaac.org/v1/pictograms/en/search/"
DELAY_SECONDS = 0.25

# Concepts the scene composes rather than draws. Excluded from the coverage denominator.
STRUCTURAL = {
    "be.located": "locative relation, drawn by placing the figure against the ground",
    "be.attribute": "attribution, drawn by applying the attribute to the figure",
    "exist": "existential, drawn by showing the things themselves",
    "thing": "coreference placeholder, resolves to its antecedent's concept",
    "location": "deictic placeholder for here and there, drawn as a position relative to the reader",
}

# Concepts drawn by the character rig rather than fetched as a symbol. Looked up anyway,
# because a fallback symbol is still wanted when no avatar is configured.
DEICTIC = {"speaker", "addressee", "person"}

# Where the search term differs from the concept id.
SEARCH_TERM = {
    "bat.animal": "bat",
    "look-after": "look after",
    "speaker": "me",
    "addressee": "you",
    "indoors": "inside",
}


def fetch(term):
    """Return (results, was_cached) for a term. An empty list means the API has none."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = CACHE_DIR / (urllib.parse.quote(term, safe="") + ".json")
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8")), True

    request = urllib.request.Request(
        API + urllib.parse.quote(term),
        headers={"User-Agent": "language-support-coverage/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        data = []
    if not isinstance(data, list):
        data = []
    cached.write_text(json.dumps(data), encoding="utf-8")
    time.sleep(DELAY_SECONDS)
    return data, False


def keywords_of(pictogram):
    return [
        entry.get("keyword", "").strip().lower()
        for entry in pictogram.get("keywords", [])
        if entry.get("keyword")
    ]


def classify(term, results):
    """exact when some pictogram carries the term as a keyword, else fuzzy or none."""
    wanted = term.strip().lower()
    for pictogram in results:
        if wanted in keywords_of(pictogram):
            return "exact", pictogram
    if results:
        return "fuzzy", results[0]
    return "none", None


def look_up(term):
    results, cached = fetch(term)
    status, best = classify(term, results)
    row = {"search_term": term, "status": status, "results": len(results)}
    if best is not None:
        row["pictogram_id"] = best.get("_id")
        row["pictogram_keywords"] = keywords_of(best)
    return row, cached


def report(rows, label):
    """Print exact/fuzzy/none counts plus the misses, and return the exact count."""
    buckets = defaultdict(list)
    for row in rows:
        buckets[row["status"]].append(row)
    total = len(rows)
    exact = len(buckets["exact"])
    print(f"{label}: {exact}/{total} exact ({exact / total:.0%})")
    print(f"  fuzzy {len(buckets['fuzzy'])}, none {len(buckets['none'])}")

    for status, heading in (("fuzzy", "no exact keyword match"), ("none", "no results at all")):
        if not buckets[status]:
            continue
        print()
        print(f"  {heading}:")
        for row in sorted(buckets[status], key=lambda r: r.get("search_term", "")):
            top = ", ".join(row.get("pictogram_keywords", [])[:4])
            suffix = f"  top: {top}" if top else ""
            print(f"    {row['search_term']:<14}{suffix}")
    return exact


def cmd_gold():
    concepts = json.loads(CONCEPTS.read_text(encoding="utf-8"))
    rows, cached_count = [], 0

    for record in concepts:
        concept, uses = record["concept"], record["count"]
        if concept in STRUCTURAL:
            rows.append(
                {"concept": concept, "uses": uses, "status": "structural", "note": STRUCTURAL[concept]}
            )
            continue
        term = SEARCH_TERM.get(concept, concept.replace("-", " "))
        row, cached = look_up(term)
        cached_count += cached
        row.update(concept=concept, uses=uses)
        if concept in DEICTIC:
            row["note"] = "drawn by the character rig; symbol is a fallback only"
        rows.append(row)

    out = ROOT / "lexicon" / "arasaac-coverage-gold.json"
    out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

    lexical = [r for r in rows if r["status"] != "structural"]
    structural = len(rows) - len(lexical)
    print(f"{len(rows)} concepts from the gold set: {structural} structural, {len(lexical)} needing a symbol")
    print(f"  cached responses reused: {cached_count}")
    print()
    exact = report(lexical, "gold concepts")
    uses_total = sum(r["uses"] for r in lexical)
    uses_exact = sum(r["uses"] for r in lexical if r["status"] == "exact")
    print()
    print(f"  weighted by uses: {uses_exact}/{uses_total} ({uses_exact / uses_total:.0%})")
    print()
    print("  Caveat: this vocabulary was chosen by this project, so it skews concrete.")
    print("  Run the dolch source for a measurement against an external list.")
    print()
    print(f"written to {out.relative_to(ROOT)}")
    return 0


def cmd_dolch():
    data = json.loads(DOLCH.read_text(encoding="utf-8"))
    service = data["service_words"]
    nouns = data["nouns"]

    by_class = Counter(entry["class"] for entry in service)
    handled = Counter(
        entry["handled_by"].split(":")[0] for entry in service if entry["class"] == "function"
    )
    gaps = [entry for entry in service if entry["class"] == "gap"]

    print(f"Dolch: {len(service)} service words + {len(nouns)} nouns = {len(service) + len(nouns)} total")
    print()
    print("service words by class:")
    for name in ("content", "function", "gap"):
        share = by_class[name] / len(service)
        print(f"  {name:<9} {by_class[name]:>3}  ({share:.0%})")
    print()
    print("function words, by the scene graph field that carries them:")
    for field, count in handled.most_common():
        print(f"  {count:>3}  {field}")

    rows, cached_count = [], 0
    content_terms = [
        (entry.get("lemma", entry["word"]), entry["word"])
        for entry in service
        if entry["class"] == "content"
    ]
    for term, word in content_terms:
        row, cached = look_up(term)
        cached_count += cached
        row.update(word=word, source="service")
        rows.append(row)

    noun_rows = []
    for noun in nouns:
        row, cached = look_up(noun)
        cached_count += cached
        row.update(word=noun, source="noun")
        noun_rows.append(row)
    rows.extend(noun_rows)

    out = ROOT / "lexicon" / "arasaac-coverage-dolch.json"
    out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

    print()
    print(f"cached responses reused: {cached_count}")
    print()
    service_content = [r for r in rows if r["source"] == "service"]
    report(service_content, "content service words")
    print()
    report(noun_rows, "nouns")
    print()
    report(rows, "all words needing a symbol")

    print()
    print(f"schema gaps found: {len(gaps)} words with no home in 0.1.0")
    for entry in gaps:
        print(f"  {entry['word']:<10} {entry['handled_by']}")

    print()
    print(f"written to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else "gold"
    if source == "gold":
        sys.exit(cmd_gold())
    elif source == "dolch":
        sys.exit(cmd_dolch())
    else:
        raise SystemExit(f"unknown source {source!r}; expected gold or dolch")
