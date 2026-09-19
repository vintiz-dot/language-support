"""Build the concept-to-pictogram map: the middle link in the rendering chain.

The chain is `concept id` -> **lexicon** -> `pictogram id` -> image URL, and until now the
middle link did not exist. `lexicon/arasaac-coverage-*.json` happened to hold some of the
pairs, but that was a by-product of measuring coverage and nothing read it.

Everything here comes out of the cache `tools/check_coverage.py` already filled, so a
rebuild is offline. Pass --fetch to look up concepts the cache has never seen.

    python tools/build_lexicon.py
    python tools/build_lexicon.py --fetch

Three kinds of entry come out:

  structural  the scene composes it rather than drawing it -- `be.located` is a placement,
              `exist` is just showing the things. No picture, and not a gap.
  exact       a pictogram carries the concept as a keyword. Trustworthy.
  fuzzy       the search returned something but nothing carries the word. This is the
              honest fallback: the top result is offered and marked, so the teacher sees
              amber rather than a confident wrong picture.

ARASAAC pictograms: author Sergio Palao, origin ARASAAC (https://arasaac.org), owned by
the Government of Aragon, licensed CC BY-NC-SA.
"""

import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from check_coverage import (  # noqa: E402
    CACHE_DIR,
    DEICTIC,
    SEARCH_TERM,
    STRUCTURAL,
    classify,
    fetch,
    keywords_of,
)

OUT = ROOT / "lexicon" / "concepts.json"
REQUIRED = ROOT / "lexicon" / "concepts-required.json"
DOLCH = ROOT / "lexicon" / "wordlists" / "dolch.json"

ATTRIBUTION = (
    "ARASAAC pictograms: author Sergio Palao, origin ARASAAC (https://arasaac.org), "
    "owned by the Government of Aragon, licensed CC BY-NC-SA."
)

# Enough for a teacher to find a better picture, few enough that the committed file stays
# small. The cache holds the full search if this ever needs widening.
MAX_ALTERNATIVES = 16


def search_term(concept):
    """The word to ask ARASAAC for. Concept ids are not search terms."""
    if concept in SEARCH_TERM:
        return SEARCH_TERM[concept]
    # bat.animal -> bat, look-after -> look after
    return concept.split(".")[0].replace("-", " ")


def cached_terms():
    return {path.stem for path in CACHE_DIR.glob("*.json")} if CACHE_DIR.exists() else set()


def alternatives(term, results):
    """Every pictogram the search returned, exact keyword matches first.

    The teacher is choosing between pictures, not reading a ranking, so this keeps all of
    them and only sorts. A wrong first choice is a click to fix; a missing option is not.
    """
    wanted = term.strip().lower()
    scored = []
    for pictogram in results:
        keywords = keywords_of(pictogram)
        if not pictogram.get("_id"):
            continue
        scored.append(
            {
                "pictogram": pictogram["_id"],
                "keywords": keywords[:4],
                "exact": wanted in keywords,
            }
        )
    scored.sort(key=lambda row: (not row["exact"], row["pictogram"]))
    return scored[:MAX_ALTERNATIVES]


def entry_for(concept, allow_fetch):
    if concept in STRUCTURAL:
        return {"structural": STRUCTURAL[concept], "match": "structural"}

    term = search_term(concept)
    path = CACHE_DIR / (term.replace(" ", "%20") + ".json")
    if path.exists():
        results = json.loads(path.read_text(encoding="utf-8"))
    elif allow_fetch:
        results, _ = fetch(term)
    else:
        return {"match": "unknown", "search_term": term}

    status, best = classify(term, results)
    entry = {"match": status, "search_term": term, "results": len(results)}
    if best is not None:
        entry["pictogram"] = best.get("_id")
        entry["keywords"] = keywords_of(best)[:6]
    entry["alternatives"] = alternatives(term, results)
    if concept in DEICTIC:
        entry["note"] = "drawn by the character rig; this symbol is a fallback only"
    return entry


def wanted_concepts():
    """Every concept the project has ever asked for, plus anything already cached."""
    concepts = set()
    if REQUIRED.exists():
        data = json.loads(REQUIRED.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else data.get("concepts", [])
        for row in rows:
            concepts.add(row["concept"] if isinstance(row, dict) else row)
    concepts |= STRUCTURAL.keys() | DEICTIC
    concepts |= {t.replace("%20", " ") for t in cached_terms()}
    return sorted(concepts)


def main():
    allow_fetch = "--fetch" in sys.argv
    concepts = wanted_concepts()

    out = {}
    for concept in concepts:
        out[concept] = entry_for(concept, allow_fetch)

    counts = {}
    for entry in out.values():
        counts[entry["match"]] = counts.get(entry["match"], 0) + 1

    OUT.write_text(
        json.dumps(
            {
                "lexicon_version": "1.0.0",
                "generated": datetime.date.today().isoformat(),
                "attribution": ATTRIBUTION,
                "source": "ARASAAC search API, cached under lexicon/.arasaac-cache",
                "concepts": out,
            },
            indent=2,
            sort_keys=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"{len(out)} concepts -> {OUT.relative_to(ROOT)}")
    for status in ("exact", "fuzzy", "structural", "none", "unknown"):
        if counts.get(status):
            print(f"  {status:<11} {counts[status]}")
    if counts.get("unknown"):
        print("  (run with --fetch to look those up)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
