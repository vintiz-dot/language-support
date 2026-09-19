"""Approved sentence sets: what a teacher has checked and is willing to show a class.

**Approval freezes the pictures, not the sentence.** A set stores the resolved strip --
which pictogram sits over which words -- rather than only the text. If it stored the text
and re-parsed on opening, a parser change or a lexicon rebuild would silently alter a set a
teacher had already approved, and the approval would mean nothing. This is the same
principle as the held-out locks: the record of what was agreed has to survive the thing
that produced it.

The scene graph is kept alongside as provenance, so a later renderer can compose a scene
rather than a strip. It is explicitly not the authority for what gets drawn. The cells are.

A set is one JSON file under `sets/`. Nothing here is a database, because a teacher should
be able to read, copy, mail or delete their own work without this project's help.
"""

import datetime
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SETS = ROOT / "sets"

SLUG = re.compile(r"[^a-z0-9]+")
SET_VERSION = "1.0.0"


def slugify(name):
    """A set name becomes a filename, so it has to be reduced to something safe.

    Strict allow-list rather than an escape: the name arrives over HTTP and a set called
    `../../etc/passwd` must not be able to address anything outside `sets/`.
    """
    slug = SLUG.sub("-", (name or "").strip().lower()).strip("-")
    return slug[:64] or "untitled"


def path_for(name):
    path = (SETS / (slugify(name) + ".json")).resolve()
    if path.parent != SETS.resolve():
        raise ValueError("set name escapes the sets directory")
    return path


def approved_sentence(strip, graph=None):
    """One approved sentence: the frozen strip, plus what produced it."""
    return {
        "text": strip.get("text", ""),
        "tokens": strip.get("tokens") or [],
        "cells": strip.get("cells") or [],
        "approved": datetime.date.today().isoformat(),
        "provenance": {
            "schema_version": (graph or {}).get("schema_version"),
            "note": "The cells above are what was approved. This graph is how they were "
                    "produced, kept so a later renderer can compose a scene.",
            "graph": graph,
        },
    }


def flags_in(sentence):
    """Anything the teacher was asked to check, so a set can say whether it is clean."""
    out = []
    for cell in sentence.get("cells") or []:
        if cell.get("kind") == "word" or cell.get("continues"):
            continue
        if cell.get("match") == "fuzzy":
            out.append(f"{cell.get('concept')}: no exact symbol")
        elif not cell.get("url") and cell.get("match") != "structural":
            out.append(f"{cell.get('concept')}: no symbol at all")
        if cell.get("uncertain"):
            out.append(f"{cell.get('concept')}: the parser was unsure")
    return out


def save(name, sentences, title=None):
    SETS.mkdir(exist_ok=True)
    path = path_for(name)
    payload = {
        "set_version": SET_VERSION,
        "name": slugify(name),
        "title": title or name,
        "saved": datetime.date.today().isoformat(),
        "sentences": sentences,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def load(name):
    path = path_for(name)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def listing():
    """Every saved set, newest first, with enough to choose between them."""
    if not SETS.exists():
        return []
    out = []
    for path in SETS.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        sentences = data.get("sentences") or []
        out.append(
            {
                "name": data.get("name", path.stem),
                "title": data.get("title") or path.stem,
                "saved": data.get("saved"),
                "sentences": len(sentences),
                "to_check": sum(len(flags_in(s)) for s in sentences),
            }
        )
    return sorted(out, key=lambda row: (row.get("saved") or "", row["title"]), reverse=True)
