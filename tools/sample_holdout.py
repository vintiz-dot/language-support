"""Draw held-out sentences from public-domain early readers.

The point of a held-out set is that nobody chose the sentences to suit the parser, so
sampling is systematic rather than hand-picked: candidates are filtered by shape alone,
then taken at a fixed stride. Re-running this produces the same 50 sentences.

Source: McGuffey's First and Second Eclectic Readers (Project Gutenberg, public domain).
They are genuine Grade 1-2 reading material, with the caveat that they are nineteenth
century, so the vocabulary skews older and more rural than a contemporary classroom.
That makes them harder than modern text in one specific way — more unseen words — which
is worth knowing when reading the score.

    python tools/sample_holdout.py
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

TARGET = 50
MIN_TOKENS, MAX_TOKENS = 4, 12


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


def acceptable(sentence):
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
    if not (MIN_TOKENS - 1 <= len(words) <= MAX_TOKENS - 1):
        return False
    if any(word.isupper() and len(word) > 1 for word in words):
        return False  # lesson headings and word lists
    if not all(re.fullmatch(r"[A-Za-z]+[,;:]?", word) for word in words):
        return False
    return True


def main():
    candidates = []
    seen = set()
    for name, url in SOURCES.items():
        for index, sentence in enumerate(sentences_from(fetch(name, url))):
            if acceptable(sentence) and sentence.lower() not in seen:
                seen.add(sentence.lower())
                candidates.append({"source": name, "index": index, "text": sentence})

    if len(candidates) < TARGET:
        raise SystemExit(f"only {len(candidates)} candidates; loosen the filters")

    stride = len(candidates) / TARGET
    sample = [candidates[int(i * stride)] for i in range(TARGET)]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "sentences.json"
    payload = [
        {"id": f"h{i + 1:03d}", "text": item["text"], "source": item["source"]}
        for i, item in enumerate(sample)
    ]
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"{len(candidates)} candidates, stride {stride:.1f}, sampled {len(sample)}")
    print(f"written to {out.relative_to(ROOT)}")
    print()
    for item in payload[:10]:
        print(f"  {item['id']}  {item['text']}")
    print("  ...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
