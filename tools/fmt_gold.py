"""Canonical formatting for the gold files.

json.dumps with an indent puts every token and every alignment index on its own line,
which turns a readable 200-line file into 1200 lines of scaffolding. The gold set is
maintained by hand and reviewed in diffs, so short scalar arrays stay inline.

Run after anything that rewrites a gold file, so diffs stay about content.

    python tools/fmt_gold.py
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GOLD = ROOT / "gold"
INLINE_WIDTH = 96


def is_scalar(value):
    return value is None or isinstance(value, (str, int, float, bool))


def dumps(value, indent=0):
    pad = "  " * indent
    inner = "  " * (indent + 1)

    if isinstance(value, list):
        if not value:
            return "[]"
        if all(is_scalar(item) for item in value):
            inline = "[" + ", ".join(json.dumps(item, ensure_ascii=False) for item in value) + "]"
            if len(inline) + len(pad) <= INLINE_WIDTH:
                return inline
        items = [inner + dumps(item, indent + 1) for item in value]
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"

    if isinstance(value, dict):
        if not value:
            return "{}"
        # Alignment spans are {node, tokens}: a scalar plus a short list. Keeping those
        # on one line is most of the readability win, so a scalar list counts as inlineable.
        def inlineable(v):
            return is_scalar(v) or (isinstance(v, list) and all(is_scalar(i) for i in v))

        if all(inlineable(v) for v in value.values()):
            parts = [
                f"{json.dumps(k, ensure_ascii=False)}: {dumps(v, indent + 1)}"
                for k, v in value.items()
            ]
            inline = "{ " + ", ".join(parts) + " }"
            if len(inline) + len(pad) <= INLINE_WIDTH and "\n" not in inline:
                return inline
        items = [
            f"{inner}{json.dumps(k, ensure_ascii=False)}: {dumps(v, indent + 1)}"
            for k, v in value.items()
        ]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"

    return json.dumps(value, ensure_ascii=False)


def main():
    changed = 0
    for path in sorted(GOLD.glob("*.json")):
        original = path.read_text(encoding="utf-8")
        formatted = dumps(json.loads(original)) + "\n"
        if formatted != original:
            path.write_text(formatted, encoding="utf-8")
            changed += 1
            lines = formatted.count("\n")
            print(f"formatted {path.name}  ({lines} lines)")
    print(f"{changed} files reformatted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
