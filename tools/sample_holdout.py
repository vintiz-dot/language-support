"""Draw held-out sentences from public-domain early readers.

The point of a held-out set is that nobody chose the sentences to suit the parser, so
sampling is systematic rather than hand-picked: candidates are filtered by shape alone,
then taken at a fixed stride. Re-running this produces the same 50 sentences.

A second set is drawn from the same corpus with set one's sentences removed from the
candidate pool first, then strided the same way. Holding the corpus fixed is deliberate:
set two exists to test whether the parser's fixes generalise, and changing the source at
the same time would confound that with a change in difficulty.

Disjointness is enforced by text rather than by index arithmetic, because set one is not
reproducible from this file any more -- the sentence splitter changed afterwards, and only
8 of its 50 sentences are redrawn by the current code. Set one's sentences survive in
holdout/sentences.json and its annotations are hashed, so the set itself is intact; what
was lost is the ability to regenerate it. Reading the exclusion list from that file is
therefore the only reliable way to guarantee the two sets do not overlap.

Source: McGuffey's First and Second Eclectic Readers (Project Gutenberg, public domain).
They are genuine Grade 1-2 reading material, with the caveat that they are nineteenth
century, so the vocabulary skews older and more rural than a contemporary classroom.
That makes them harder than modern text in one specific way — more unseen words — which
is worth knowing when reading the score.

    python tools/sample_holdout.py                  # set one, holdout/
    python tools/sample_holdout.py --set 2          # set two, holdout2/
    python tools/sample_holdout.py --set 3          # set three, holdout3/, Grade 1-3
"""

import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "holdout"
CACHE = OUT_DIR / ".source-cache"

SOURCES = {
    "mcguffey-1": "https://www.gutenberg.org/cache/epub/14640/pg14640.txt",
    "mcguffey-2": "https://www.gutenberg.org/cache/epub/14668/pg14668.txt",
}

# Sets one and two were drawn when the target was Grade 1-2, so they use the two readers
# above and must keep using exactly those to stay reproducible. The target is now Grade
# 1-3, and neither of those books reaches Grade 3, so set three adds the Third Reader and
# a wider sentence-length window: twelve tokens was chosen for Grade 1-2 text and would
# systematically drop the longer sentences that make Grade 3 harder.
THIRD_READER = {"mcguffey-3": "https://www.gutenberg.org/cache/epub/14766/pg14766.txt"}

TARGET = 50
MIN_TOKENS, MAX_TOKENS = 4, 12
MAX_TOKENS_GRADE_3 = 16


def fetch(name, url):
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"{name}.txt"
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    request = urllib.request.Request(url, headers={"User-Agent": "holdout-sourcing/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        text = response.read().decode("utf-8", "replace")
    cached.write_text(text, encoding="utf-8")
    return text


def strip_boilerplate(text):
    start = text.find("*** START OF")
    if start != -1:
        text = text[text.find("\n", start) + 1 :]
    end = text.find("*** END OF")
    if end != -1:
        text = text[:end]
    return text


def sentences_from(text):
    """Split into sentences, joining wrapped lines but keeping paragraph breaks."""
    text = strip_boilerplate(text)
    paragraphs = re.split(r"\n\s*\n", text)
    found = []
    for paragraph in paragraphs:
        flat = re.sub(r"\s+", " ", paragraph).strip()
        if not flat:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z\"])", flat):
            found.append(sentence.strip())
    return found


def acceptable(sentence, max_tokens=MAX_TOKENS):
    """Shape filters only. Nothing here looks at what the sentence means."""
    if not sentence.endswith((".", "!", "?")):
        return False
    if len(sentence) < 15:
        return False
    if re.search(r"[0-9_\[\]{}*]", sentence):
        return False
    if '"' in sentence or "'" in sentence or "“" in sentence or "’" in sentence:
        return False  # dialogue and contractions complicate tokenisation comparisons
    if not sentence[0].isupper():
        return False
    words = sentence.rstrip(".!?").split()
    if not (MIN_TOKENS - 1 <= len(words) <= max_tokens - 1):
        return False
    if any(word.isupper() and len(word) > 1 for word in words):
        return False  # lesson headings and word lists
    if not all(re.fullmatch(r"[A-Za-z]+[,;:]?", word) for word in words):
        return False
    return True


def main():
    which = 1
    if "--set" in sys.argv:
        which = int(sys.argv[sys.argv.index("--set") + 1])
    if which not in (1, 2, 3):
        raise SystemExit(f"--set must be 1, 2 or 3, not {which}")
    out_dir = ROOT / {1: "holdout", 2: "holdout2", 3: "holdout3"}[which]

    sources = dict(SOURCES)
    max_tokens = MAX_TOKENS
    if which == 3:
        sources.update(THIRD_READER)
        max_tokens = MAX_TOKENS_GRADE_3

    already = set()
    for earlier in ("holdout", "holdout2")[: which - 1]:
        for name in ("sentences.json", "excluded.json"):
            path = ROOT / earlier / name
            if path.exists():
                already |= {item["text"] for item in json.loads(path.read_text(encoding="utf-8"))}

    candidates = []
    seen = set()
    for name, url in sources.items():
        for index, sentence in enumerate(sentences_from(fetch(name, url))):
            if sentence in already:
                continue
            if acceptable(sentence, max_tokens) and sentence.lower() not in seen:
                seen.add(sentence.lower())
                candidates.append({"source": name, "index": index, "text": sentence})

    if len(candidates) < TARGET:
        raise SystemExit(f"only {len(candidates)} candidates; loosen the filters")

    stride = len(candidates) / TARGET
    sample = [candidates[int(i * stride)] for i in range(TARGET)]

    overlap = {item["text"] for item in sample} & already
    if overlap:
        raise SystemExit(f"set two overlaps set one on {len(overlap)}: {sorted(overlap)[:3]}")

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "sentences.json"
    payload = [
        {"id": f"{ {1: 'h', 2: 'j', 3: 'k'}[which] }{i + 1:03d}", "text": item["text"],
         "source": item["source"]}
        for i, item in enumerate(sample)
    ]
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"set {which}: {len(candidates)} candidates "
          f"({len(already)} excluded as already drawn), stride {stride:.1f}, "
          f"max {max_tokens} tokens, sampled {len(sample)}")
    print(f"written to {out.relative_to(ROOT)}")
    print()
    for item in payload[:10]:
        print(f"  {item['id']}  {item['text']}")
    print("  ...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
