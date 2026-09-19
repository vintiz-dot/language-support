"""Turn an AMR graph into a scene graph fragment, for use where the rules find nothing.

The benchmark in `holdout3/AMR-BENCHMARK.md` set the design. On unseen text the two parsers
get the same number of events right, but by opposite routes: AMR finds more predicates (74%
against 67%) and the rules are more precise on what they find (94% against 85%). So AMR
fills gaps and never overrides. Trading the rules' precision for AMR's coverage would be the
wrong way round for a teacher-first product, where drawing the wrong picture costs more than
drawing none.

The other half of the benchmark is the reason this is worth doing at all: AMR deliberately
discards number, definiteness and tense, and those are exactly the fields spaCy hands over
for free. So AMR supplies the structure and the existing rule machinery supplies the
features, which is a division of labour rather than a fallback.

Nothing here is imported by `parser.rules` at module level and amrlib is not in
requirements.txt. The rendering path must never need a 516 MB model.
"""

import re

from . import lexicon as lex

# AMR reifications that stand for something the scene graph says with a field instead.
ROLE_FOR_ARG = {":ARG0": "agent", ":ARG1": "patient", ":ARG2": "recipient"}

# Nodes AMR adds as scaffolding rather than content.
SCAFFOLD = {"and", "or", "amr-unknown", "have-degree-91", "have-rel-role-91", "have-org-role-91"}

SENSE = re.compile(r"^(.*?)-\d+$")


def lemma_of(concept):
    """give-01 -> give. Leaves have-rel-role-91 and other reifications alone."""
    match = SENSE.match(concept or "")
    if not match:
        return concept
    base = match.group(1)
    return concept if base.endswith("-role") or base.endswith("-degree") else base


class AmrBridge:
    """Builds scene graph nodes from one AMR graph, against one spaCy doc."""

    def __init__(self, penman_text, doc, builder, entity_props, read_tense_aspect):
        import penman

        self.doc = doc
        self.builder = builder
        self.entity_props = entity_props
        self.read_tense_aspect = read_tense_aspect
        self.graph = penman.decode(penman_text)
        self.concepts = {i.source: i.target for i in self.graph.instances()}
        self.nodes = {}
        self.used_tokens = set()

        self.children = {}
        for edge in self.graph.edges():
            self.children.setdefault(edge.source, []).append((edge.role, edge.target))
        self.attributes = {}
        for attribute in self.graph.attributes():
            self.attributes.setdefault(attribute.source, []).append(
                (attribute.role, attribute.target)
            )

    # --- alignment -------------------------------------------------------------------
    def peek_token(self, concept):
        """Like token_for but consumes nothing, for deciding before committing."""
        stem = (lemma_of(concept) or "")[:4].lower()
        if len(stem) < 3:
            return None
        for token in self.doc:
            if token.is_punct:
                continue
            if token.lower_.startswith(stem) or token.lemma_.lower().startswith(stem):
                return token
        return None

    def token_for(self, concept):
        """The token a concept came from, matched on its first four characters.

        AMR carries no token alignment, so this is a string match and it is approximate.
        It is good enough to give a renderer something to highlight, and every node built
        here is flagged for review anyway.
        """
        stem = (lemma_of(concept) or "")[:4].lower()
        if len(stem) < 3:
            return None
        for token in self.doc:
            if token.i in self.used_tokens or token.is_punct:
                continue
            if token.lower_.startswith(stem) or token.lemma_.lower().startswith(stem):
                self.used_tokens.add(token.i)
                return token
        return None

    # --- entities --------------------------------------------------------------------
    def proper_name(self, variable):
        for role, target in self.children.get(variable, []):
            if role != ":name":
                continue
            parts = [
                value.strip('"')
                for name_role, value in sorted(self.attributes.get(target, []))
                if name_role.startswith(":op")
            ]
            if parts:
                return " ".join(parts)
        return None

    def entity(self, variable):
        if variable in self.nodes:
            return self.nodes[variable]
        concept = self.concepts.get(variable)
        if concept is None:
            return None

        # A coordinated argument is an and/or node whose :opN children are its members.
        if concept in ("and", "or"):
            members = [
                self.entity(target)
                for role, target in sorted(self.children.get(variable, []))
                if role.startswith(":op")
            ]
            members = [m for m in members if m]
            if len(members) < 2:
                return members[0] if members else None
            node = self.builder.entity(
                {"members": members, "coordination": concept,
                 "number": "pl" if concept == "and" else None},
                set(),
            )
            self.nodes[variable] = node
            return node

        token = self.token_for(concept)
        props = dict(self.entity_props(token)) if token is not None else {}
        props["concept"] = lemma_of(concept)

        name = self.proper_name(variable)
        if name:
            props["concept"] = "person"
            props["proper_name"] = name

        for role, target in self.children.get(variable, []):
            if role == ":mod" and target in self.concepts:
                modifier = lemma_of(self.concepts[target])
                existing = props.setdefault("modifiers", [])
                # spaCy may already have found the same word as an amod, so the two
                # sources are merged rather than concatenated.
                seen = {m if isinstance(m, str) else m.get("concept") for m in existing}
                if modifier not in SCAFFOLD and modifier not in seen:
                    existing.append(modifier)
            elif role in (":poss", ":part-of") and target in self.concepts:
                owner = self.entity(target)
                if owner:
                    props["possessor"] = owner

        if not props.get("modifiers"):
            props.pop("modifiers", None)
        node = self.builder.entity(
            props, {token.i} if token is not None else set()
        )
        self.nodes[variable] = node
        self.builder.flag(node, "parse_uncertain", "Recovered from AMR, not from the rules.")
        return node

    # --- events ----------------------------------------------------------------------
    def role_name(self, predicate, arg):
        base = ROLE_FOR_ARG[arg]
        if base == "agent" and predicate in lex.EXPERIENCER_VERBS:
            return "experiencer"
        if base == "patient" and predicate in lex.THEME_OBJECT_VERBS:
            return "theme"
        return base

    def is_predicate(self, variable):
        """A sense-numbered concept is a predicate, arguments or not.

        twinkle-01 in "Twinkle, twinkle, all the night" has no :ARG at all -- requiring one
        was why that sentence still came out as a bare existence rather than the imperative
        it is, which is the case the fallback exists for.
        """
        concept = self.concepts.get(variable, "")
        if concept in SCAFFOLD or lemma_of(concept) in SCAFFOLD:
            return False
        return bool(SENSE.match(concept))

    def event(self, variable):
        concept = self.concepts[variable]
        predicate = lemma_of(concept)
        token = self.token_for(concept)

        args = {
            role: target
            for role, target in self.children.get(variable, [])
            if role in ROLE_FOR_ARG and target in self.concepts
        }
        roles, attribute = {}, None
        if ":ARG0" not in args and list(args) == [":ARG1"]:
            # gray-02 :ARG1 streak is an adjective, not an action. The scene graph says
            # that with be.attribute, which is also how the rules write it.
            filler = self.entity(args[":ARG1"])
            if filler:
                roles["theme"] = filler
            attribute, predicate = predicate, lex.COPULA_ATTRIBUTE
        else:
            for role, target in args.items():
                filler = self.entity(target)
                if filler:
                    roles[self.role_name(predicate, role)] = filler

        props = {"predicate": predicate, "roles": roles or None, "attribute": attribute}
        if token is not None:
            tense, aspect = self.read_tense_aspect(token)
            props["tense"], props["aspect"] = tense, aspect
        props.setdefault("aspect", "simple")

        values = dict(self.attributes.get(variable, []))
        props["polarity"] = "negative" if values.get(":polarity") == "-" else "positive"
        props["mood"] = self.mood(values)
        if props["mood"] == "interrogative":
            props["question"] = {"type": "yes-no"}

        node = self.builder.event(props, {token.i} if token is not None else set())
        self.builder.flag(node, "parse_uncertain", "Recovered from AMR, not from the rules.")
        return node

    def mood(self, values=None):
        values = values or {}
        if values.get(":mode") == "imperative":
            return "imperative"
        if any(token.text == "?" for token in self.doc):
            return "interrogative"
        if any(token.text == "!" for token in self.doc):
            # A bare verb with no subject is an order, not an exclamation, whatever the
            # mark says -- the same precedence the rules use.
            root = self.doc[0]
            if root.tag_ == "VB" and not any(t.dep_.startswith("nsubj") for t in self.doc):
                return "imperative"
            return "exclamative"
        return "declarative"

    def content_top(self):
        """The thing the sentence is about, skipping AMR's scaffolding.

        "What cunning, little eggs!" arrives as say-01 wrapping cunning and egg. Taking the
        first node that is not scaffolding picks cunning, which is a property of the thing
        rather than the thing, so a noun is preferred where one can be found.
        """
        candidates = []
        for variable in [self.graph.top] + list(self.concepts):
            if variable in candidates:
                continue
            concept = self.concepts.get(variable, "")
            if concept in SCAFFOLD or lemma_of(concept) in SCAFFOLD or lemma_of(concept) == "say":
                continue
            candidates.append(variable)
        if not candidates:
            return None
        nominal = [
            v for v in candidates
            if (lambda tok: tok is not None and tok.pos_ in ("NOUN", "PROPN"))(
                self.peek_token(self.concepts.get(v, ""))
            )
        ]
        return (nominal or candidates)[0]

    def setting(self):
        out = {}
        for role, target in self.children.get(self.graph.top, []):
            if role == ":time" and target in self.concepts:
                out["time"] = lemma_of(self.concepts[target])
        return out or None

    def build(self):
        """Populate the builder. Returns True if anything usable came out."""
        predicates = [v for v in self.concepts if self.is_predicate(v)]

        # "What cunning, little eggs!" arrives as say-01 :mode expressive wrapping the
        # content, which is AMR's exclamative and not a speech act to be drawn.
        predicates = [
            v for v in predicates
            if not (lemma_of(self.concepts[v]) == "say"
                    and dict(self.attributes.get(v, [])).get(":mode") == "expressive")
        ]

        for variable in predicates:
            self.event(variable)

        if not self.builder.events:
            # No predicate survived. If AMR found a thing at all, say that it exists --
            # the same move the annotator had to make by hand for an exclamative noun
            # phrase, and better than returning an empty graph.
            variable = self.content_top()
            top = self.entity(variable) if variable else None
            if top is None:
                return False
            mood = self.mood()
            # An invented predicate has no word of its own, and a node with no span can
            # never be matched to anything. A fronted What or How is the closest thing the
            # sentence has to a marker of the assertion, which is where the gold for these
            # puts it too.
            marker = {
                token.i for token in self.doc[:1] if token.lower_ in ("what", "how")
            }
            node = self.builder.event(
                {
                    "predicate": lex.EXISTENTIAL,
                    "roles": {"theme": top},
                    "tense": "present",
                    "aspect": "simple",
                    "polarity": "positive",
                    "mood": mood,
                    "question": {"type": "yes-no"} if mood == "interrogative" else None,
                },
                marker,
            )
            self.builder.flag(node, "parse_uncertain", "Recovered from AMR, not from the rules.")
        return bool(self.builder.events)


def build(penman_text, doc, builder, entity_props, read_tense_aspect):
    """Entry point. Returns True if the builder now holds something worth rendering."""
    if not penman_text:
        return False
    try:
        return AmrBridge(penman_text, doc, builder, entity_props, read_tense_aspect).build()
    except Exception:
        # A malformed AMR graph is a reason to fall back to nothing, not to crash the
        # whole parse. The caller already has an empty graph in that case.
        return False
