"""The teacher's editor: type a sentence, watch the pictures appear over the words.

    python tools/serve.py
    # then open http://127.0.0.1:8000

Standard library only, and bound to the loopback interface. Nothing is added to
requirements.txt, because the whole point of a rule parser is that a classroom machine can
run it without a model download or an account.

Images are fetched by the browser straight from ARASAAC's CDN. Nothing is written to disk
except a teacher's own choices, in lexicon/overrides.json.

Endpoints:

  POST /api/strip        {text}                  -> the strip, one cell per span
  GET  /api/alternatives ?concept=dog            -> every pictogram that could stand for it
  POST /api/override     {concept, pictogram}    -> remember a choice, or null to forget it
  POST /api/approve      {text}                  -> one frozen, approved sentence
  GET  /api/sets                                 -> every saved set
  GET  /api/sets?name=x                          -> one saved set
  POST /api/sets         {name, title, sentences}-> save a set

  GET  /                                         -> the teacher's editor
  GET  /read?set=x                               -> the student view, read only

ARASAAC pictograms: author Sergio Palao, origin ARASAAC (https://arasaac.org), owned by
the Government of Aragon, licensed CC BY-NC-SA.
"""

import http.server
import json
import pathlib
import socketserver
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

sys.path.insert(0, str(ROOT / "tools"))

from build_lexicon import alternatives as alternatives_for  # noqa: E402
from build_lexicon import search_term  # noqa: E402
from check_coverage import classify, fetch, keywords_of  # noqa: E402
from parser.rules import parse  # noqa: E402
from renderer import sets as sets_module  # noqa: E402
from renderer import strip as strip_module  # noqa: E402

PAGE = ROOT / "editor" / "index.html"
READER = ROOT / "editor" / "read.html"
HOST, PORT = "127.0.0.1", 8000

LEXICON = strip_module.load_lexicon()


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        """Quiet. A keystroke is a request here, so the default log is unreadable."""

    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_page(self, path):
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            return {}

    # --- GET ---------------------------------------------------------------
    def do_GET(self):
        route = urllib.parse.urlparse(self.path)
        if route.path in ("/", "/index.html", "/read"):
            # /read is the student view. It reads a saved set and nothing else -- no
            # parser, no lexicon -- because the pictures were frozen on approval.
            self.send_page(READER if route.path == "/read" else PAGE)
            return

        if route.path == "/api/alternatives":
            concept = urllib.parse.parse_qs(route.query).get("concept", [""])[0]
            entry = LEXICON.get(concept) or {}
            if not entry.get("alternatives") and entry.get("match") != "structural":
                # A teacher types words the lexicon has never seen -- the gold set is 87
                # sentences, not a vocabulary. Without a live lookup a missing symbol is
                # simply unfixable, which would make the editor useless the first time it
                # met an ordinary noun. The result is cached, so it is asked once ever.
                entry = live_lookup(concept)
            overrides = strip_module.load_overrides()
            options = []
            for option in entry.get("alternatives") or []:
                options.append(
                    {
                        **option,
                        "url": strip_module.picture_url(option["pictogram"]),
                        "current": overrides.get(concept) == option["pictogram"]
                        or (concept not in overrides
                            and entry.get("pictogram") == option["pictogram"]),
                    }
                )
            self.send_json(
                {
                    "concept": concept,
                    "match": entry.get("match", "unknown"),
                    "note": entry.get("structural") or entry.get("note"),
                    "overridden": concept in overrides,
                    "options": options,
                }
            )
            return

        if route.path == "/api/sets":
            name = urllib.parse.parse_qs(route.query).get("name", [""])[0]
            if not name:
                self.send_json({"sets": sets_module.listing()})
                return
            data = sets_module.load(name)
            if data is None:
                self.send_json({"error": "no such set"}, status=404)
                return
            self.send_json(data)
            return

        self.send_json({"error": "not found"}, status=404)

    # --- POST --------------------------------------------------------------
    def do_POST(self):
        route = urllib.parse.urlparse(self.path)

        if route.path == "/api/strip":
            text = (self.read_json().get("text") or "").strip()
            if not text:
                self.send_json({"text": "", "cells": [], "tokens": []})
                return
            try:
                graph = parse(text)
            except Exception as exc:  # noqa: BLE001 - a half-typed sentence is not a crash
                self.send_json({"text": text, "cells": [], "tokens": [],
                                "error": f"{type(exc).__name__}: {exc}"})
                return
            payload = strip_module.build(graph, LEXICON, strip_module.load_overrides())
            payload["graph"] = graph
            self.send_json(payload)
            return

        if route.path == "/api/approve":
            # Approval freezes the strip as it stands, so a later parser change or lexicon
            # rebuild cannot quietly redraw a sentence the teacher already signed off.
            text = (self.read_json().get("text") or "").strip()
            if not text:
                self.send_json({"error": "text required"}, status=400)
                return
            graph = parse(text)
            strip = strip_module.build(graph, LEXICON, strip_module.load_overrides())
            sentence = sets_module.approved_sentence(strip, graph)
            sentence["to_check"] = sets_module.flags_in(sentence)
            self.send_json(sentence)
            return

        if route.path == "/api/sets":
            data = self.read_json()
            name = (data.get("name") or "").strip()
            if not name:
                self.send_json({"error": "name required"}, status=400)
                return
            try:
                saved = sets_module.save(name, data.get("sentences") or [], data.get("title"))
            except ValueError as exc:
                self.send_json({"error": str(exc)}, status=400)
                return
            print(f"  saved set {saved['name']!r}: {len(saved['sentences'])} sentences")
            self.send_json({"ok": True, "name": saved["name"], "title": saved["title"],
                            "sentences": len(saved["sentences"])})
            return

        if route.path == "/api/override":
            data = self.read_json()
            concept = data.get("concept")
            if not concept:
                self.send_json({"error": "concept required"}, status=400)
                return
            strip_module.save_override(concept, data.get("pictogram"))
            self.send_json({"ok": True, "concept": concept})
            return

        self.send_json({"error": "not found"}, status=404)


def live_lookup(concept):
    """Ask ARASAAC about a concept the built lexicon does not hold, and remember it.

    This writes to the same cache `tools/check_coverage.py` fills, so a rebuild of the
    lexicon picks up everything a teacher has looked at. Failure is not fatal: a machine
    with no network gets an empty picker and the sentence still renders.
    """
    term = search_term(concept)
    try:
        results, _ = fetch(term)
    except Exception as exc:  # noqa: BLE001 - offline is a normal state, not an error
        print(f"  lookup failed for {term!r}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return {"match": "unknown", "alternatives": []}
    status, best = classify(term, results)
    entry = {"match": status, "search_term": term, "alternatives": alternatives_for(term, results)}
    if best is not None:
        entry["pictogram"] = best.get("_id")
        entry["keywords"] = keywords_of(best)[:4]
    LEXICON[concept] = entry  # so the next keystroke does not ask again
    return entry


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    print(f"lexicon: {len(LEXICON)} concepts")
    print(f"teacher  http://{HOST}:{port}")
    print(f"students http://{HOST}:{port}/read")
    with Server((HOST, port), Handler) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
