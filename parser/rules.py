"""Rule-based scene graph parser over a spaCy dependency parse.

Deliberately not a model. The target is Grade 1-3 syntax, which is short and regular
enough that rules cover it, and rules can say when they do not apply — a model cannot,
and a confidently wrong picture is the worst output this system can produce.

Order matters in one place especially: multi-word units are resolved before roles are
assigned. Read left to right, "looked after his sister" gives a verb plus a preposition
and a plausible, wrong picture of someone standing behind a girl.

    from parser.rules import parse
    graph = parse("The dog chased the cat.", tokens=[...])
"""

import functools
import pathlib

from . import lexicon as lex
from . import patterns

CLAUSE_DEPS = {"ROOT", "conj", "advcl", "ccomp", "xcomp", "relcl"}
RELATIVE_PRONOUNS = {"that", "which", "who", "whom", "whose"}
SUBJECT_DEPS = {"nsubj", "nsubjpass", "expl"}
NP_CHILD_DEPS = {"det", "amod", "nummod", "poss", "compound", "predet", "quantmod", "nmod"}
NOMINAL_POS = {"NOUN", "PROPN", "PRON"}
WH_WORDS = {"who", "what", "where", "when", "why", "how", "which"}


@functools.lru_cache(maxsize=1)
def _schema_version():
    """The version the schema currently declares.

    Hardcoding this drifted: the parser said 0.2.0 for two schema releases while emitting
    members, focus and measure, and nothing caught it because the only gate on parser
    output was the referential checker, not the schema itself.
    """
    import json

    path = pathlib.Path(__file__).resolve().parent.parent / "schema" / "scene-graph.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))["properties"]["schema_version"]["const"]


SCHEMA_VERSION = _schema_version()


def _nlp():
    import spacy

    return spacy.load("en_core_web_sm")


def _doc(tokens):
    """Parse a fixed token list.

    The tokenisation is supplied rather than derived, because alignment indices are only
    meaningful against the tokens the rest of the system uses.
    """
    from spacy.tokens import Doc

    nlp = _nlp()
    doc = Doc(nlp.vocab, words=list(tokens))
    for _, component in nlp.pipeline:
        doc = component(doc)
    return doc


class Builder:
    def __init__(self, text, tokens):
        self.text = text
        self.tokens = list(tokens)
        self.entities = {}
        self.events = []
        self.discourse = []
        self.alignment = []
        self.review = []
        self.address = None
        self.speech_act = None
        self._counts = {"e": 0, "ev": 0, "d": 0}

    def _next(self, kind):
        self._counts[kind] += 1
        return f"{kind}{self._counts[kind]}"

    def entity(self, props, span=None):
        node = self._next("e")
        self.entities[node] = {k: v for k, v in props.items() if v is not None}
        if span:
            self.align(node, span)
        return node

    def event(self, props, span=None):
        node = self._next("ev")
        event = {"id": node}
        event.update({k: v for k, v in props.items() if v is not None})
        self.events.append(event)
        if span:
            self.align(node, span)
        return node

    def relation(self, props, span=None):
        node = self._next("d")
        relation = {"id": node}
        relation.update({k: v for k, v in props.items() if v is not None})
        self.discourse.append(relation)
        if span:
            self.align(node, span)
        return node

    def align(self, node, span):
        tokens = sorted({i for i in span if 0 <= i < len(self.tokens)})
        if tokens:
            self.alignment.append({"node": node, "tokens": tokens})

    def span_of(self, node):
        """Every token index aligned to a node, across however many spans it has."""
        found = set()
        for entry in self.alignment:
            if entry["node"] == node:
                found.update(entry["tokens"])
        return found

    def flag(self, node, reason, message=None, options=None, score=None):
        entry = {"node": node, "reason": reason}
        if message:
            entry["message"] = message
        if options:
            entry["options"] = options
        if score is not None:
            entry["score"] = score
        self.review.append(entry)

    def graph(self, pattern=None):
        out = {
            "schema_version": SCHEMA_VERSION,
            "text": self.text,
            "tokens": self.tokens,
            "entities": self.entities,
            "events": self.events,
            "alignment": self.alignment,
        }
        if pattern:
            out["pattern"] = pattern
        if self.address:
            out["address"] = self.address
        if self.speech_act:
            out["speech_act"] = self.speech_act
        if self.discourse:
            out["discourse"] = self.discourse
        if self.review:
            out["review"] = self.review
        return out


# --- multi-word units, resolved before roles ---------------------------------------


def _match_lemma_run(doc, table):
    """Find a contiguous run of lemmas from table; return (value, token indices) or None."""
    lemmas = [token.lemma_.lower() for token in doc]
    for key, value in table.items():
        width = len(key)
        for start in range(len(lemmas) - width + 1):
            if tuple(lemmas[start : start + width]) == key:
                return value, set(range(start, start + width))
    return None


def find_idiom(doc):
    """Return (predicate, token indices) for an idiom that consumes the clause, else None."""
    return _match_lemma_run(doc, lex.IDIOMS)


def find_predicate_idiom(doc):
    """Return (predicate, token indices) for an idiom that is only the verb, else None.

    Unlike find_idiom the clause keeps its participants, so the caller has to suppress the
    idiom's own noun and pick up the object hanging under the idiom's preposition.
    """
    return _match_lemma_run(doc, lex.PREDICATE_IDIOMS)


def preposition_relation(prep_token):
    """Map a preposition to a spatial relation, preferring multi-word matches."""
    words = [prep_token.lower_]
    cursor = prep_token
    for _ in range(2):
        nxt = cursor.nbor(1) if cursor.i + 1 < len(cursor.doc) else None
        if nxt is None:
            break
        words.append(nxt.lower_)
        cursor = nxt
        phrase = tuple(words)
        if phrase in lex.PREPOSITION_PHRASES:
            return lex.PREPOSITION_PHRASES[phrase], set(range(prep_token.i, cursor.i + 1))
    relation = lex.PREPOSITIONS.get(prep_token.lower_)
    return (relation, {prep_token.i}) if relation else (None, set())


# --- entities -----------------------------------------------------------------------


def nominal_head(token):
    """Follow a partitive to the noun it quantifies.

    "some of the cakes" arrives with some as the object and cakes buried under a
    preposition. Taking some as the head produced the concept "some", which no lexicon
    can draw. The quantifier is kept; only the head moves.
    """
    # A preposition is never a nominal head. spaCy labels the "to" of a prepositional
    # dative as the dative itself, so "gave the book to his sister" made the recipient
    # the concept "to" -- a nonsense concept in an argument position.
    if token.pos_ == "ADP":
        pobj = next((c for c in token.children if c.dep_ == "pobj"), None)
        if pobj is not None:
            return nominal_head(pobj)

    if token.pos_ != "PRON" or token.lower_ not in lex.QUANTIFIERS | {"all", "none", "one"}:
        return token, None
    for child in token.children:
        if child.dep_ == "prep" and child.lower_ == "of":
            for pobj in child.children:
                if pobj.dep_ == "pobj":
                    return pobj, token
    return token, None


def noun_span(token):
    """Token indices of the noun phrase headed by token, excluding attached PPs."""
    span = {token.i}
    for child in token.children:
        if child.dep_ in NP_CHILD_DEPS:
            span.update(sub.i for sub in child.subtree)
    return span


def entity_props(token):
    """Read an entity's properties off a nominal head."""
    word = token.lower_

    # A demonstrative standing alone is a thing at a distance, not the word "this".
    if token.pos_ == "PRON" and word in lex.DEMONSTRATIVES:
        return {
            "concept": "thing",
            "number": "pl" if word in ("these", "those") else "sg",
            "definite": True,
            "deixis": lex.DEMONSTRATIVES[word],
        }

    # mine, yours, theirs: the concept is unknown, only the owner is recoverable.
    if word in lex.POSSESSIVE_NOMINALS:
        return {"concept": "thing", "number": "sg", "person": lex.POSSESSIVE_NOMINALS[word]}

    if word in lex.PRONOUNS:
        props = dict(lex.PRONOUNS[word])
        if word in lex.POSSESSIVE_PRONOUNS:
            props["definite"] = None
        return props

    if token.pos_ == "PROPN":
        concept = lex.KINSHIP_PROPER.get(token.lower_, "person")
        props = {
            "concept": concept,
            "proper_name": token.text,
            "number": "sg",
            "animacy": "person",
        }
        if concept != "person":
            props["gender"] = lex.GENDERED_NOUNS.get(concept)
        return {k: v for k, v in props.items() if v is not None}

    if word in WH_WORDS:
        return {"concept": "person" if word == "who" else "thing", "number": "sg"}

    lemma = token.lemma_.lower()
    # An ambiguous word takes its first listed sense as a default. entity_for flags it.
    props = {"concept": lex.AMBIGUOUS[lemma][0] if lemma in lex.AMBIGUOUS else lemma}

    if lemma in lex.MASS_NOUNS:
        props["number"] = "mass"
    else:
        props["number"] = "pl" if token.morph.get("Number") == ["Plur"] else "sg"

    props["animacy"] = lex.ANIMACY_LOOKUP.get(lemma, "object")
    if lemma in lex.GENDERED_NOUNS:
        props["gender"] = lex.GENDERED_NOUNS[lemma]

    modifiers = []
    for child in token.children:
        if child.dep_ == "det":
            det = child.lower_
            if det in lex.DEMONSTRATIVES:
                props["deixis"] = lex.DEMONSTRATIVES[det]
                props["definite"] = True
            elif det in lex.QUANTIFIERS:
                props["quantifier"] = det
                props["definite"] = False
            elif det == "the":
                props["definite"] = True
            elif det in ("a", "an"):
                props["definite"] = False
        elif child.dep_ == "poss":
            props["definite"] = True
        elif child.dep_ == "nummod":
            value = lex.NUMBER_WORDS.get(child.lower_)
            if value is None and child.like_num:
                try:
                    value = int(child.text)
                except ValueError:
                    value = None
            if value is not None:
                props["quantity"] = value
                props["number"] = "pl" if value != 1 else "sg"
        elif child.dep_ == "amod":
            degree = None
            for grandchild in child.children:
                if grandchild.dep_ == "advmod" and grandchild.lower_ == "as":
                    span.add(grandchild.i)
                elif grandchild.dep_ == "advmod" and grandchild.lower_ in lex.DEGREE_ADVERBS:
                    degree = lex.DEGREE_ADVERBS[grandchild.lower_]
            if any(g.lower_ == "how" for g in child.children):
                continue  # "how many": the count is the question, not a quantifier
            if child.lower_ in WH_WORDS or child.lower_ in lex.QUANTIFIERS:
                props.setdefault("quantifier", child.lower_)
                continue
            modifiers.append({"concept": child.lemma_.lower(), "degree": degree} if degree else child.lemma_.lower())

    if modifiers:
        props["modifiers"] = modifiers
    if "definite" not in props and props.get("number") in ("pl", "mass"):
        props["definite"] = False  # bare plurals and mass nouns carry no article
    return {k: v for k, v in props.items() if v is not None}


class Context:
    """Per-sentence state: the doc, the builder, and the token-to-entity cache."""

    def __init__(self, doc, builder):
        self.doc = doc
        self.builder = builder
        self.entity_cache = {}
        self.idiom = find_idiom(doc)
        self.predicate_idiom = find_predicate_idiom(doc)
        matcher = patterns.build_matcher(doc.vocab)
        self.phrasal = {
            verb_index: (concept, {particle.i}, particle)
            for verb_index, (concept, particle) in patterns.match_phrasal(doc, matcher).items()
        }
        # verb token index -> {filler token index: role}, from the declarative rules.
        self.roles = patterns.match_roles(doc, matcher)
        # speaker and addressee are fixed by the speech situation, so every mention is
        # the same referent and gets one entity with several spans. Third person is not
        # reused: he needs a fresh entity carrying coref, which this parser leaves open.
        self.singletons = {}

    def entity_for(self, token):
        original = token
        token, quantifier = nominal_head(token)
        if original.i in self.entity_cache:
            return self.entity_cache[original.i]
        if token.i in self.entity_cache:
            return self.entity_cache[token.i]

        props = entity_props(token)
        if quantifier is not None:
            props.setdefault("quantifier", quantifier.lower_)

        concept = props.get("concept")
        is_pronoun = token.lower_ in lex.PRONOUNS
        key = (concept, props.get("person"), props.get("gender"))
        if is_pronoun:
            existing = self.singletons.get(key)
            if existing is not None:
                if token.lower_ not in lex.POSSESSIVE_PRONOUNS:
                    self.builder.align(existing, noun_span(token))
                self.entity_cache[token.i] = existing
                return existing

        span = noun_span(token)
        if quantifier is not None:
            span |= {quantifier.i}
            span |= {c.i for c in quantifier.children if c.dep_ == "prep"}
        node = self.builder.entity(props, span)
        self.entity_cache[original.i] = node
        if is_pronoun:
            self.singletons[key] = node
        self.entity_cache[token.i] = node

        # A possessive nominal names its owner by person, so resolve it the same way a
        # pronoun would: mine is the speaker's, yours is the addressee's.
        person = props.get("person") if props.get("concept") == "thing" else None
        if token.lower_ in lex.POSSESSIVE_NOMINALS:
            owner_concept = {"1sg": "speaker", "1pl": "speaker", "2sg": "addressee"}.get(person)
            if owner_concept:
                owner = self.singletons.get((owner_concept, person, None))
                if owner is None:
                    owner = self.builder.entity(
                        {"concept": owner_concept, "person": person, "number": "sg",
                         "animacy": "person", "implicit": True}
                    )
                    self.singletons[(owner_concept, person, None)] = owner
                self.builder.entities[node]["possessor"] = owner

        # A preposition hanging off a noun locates that noun rather than the event:
        # "the cup on the table is full" identifies which cup.
        for child in token.children:
            if child.dep_ != "prep" or child.lower_ == "of":
                continue
            relation, _ = preposition_relation(child)
            grounds = [g for g in child.children if g.dep_ == "pobj"]
            if relation and grounds:
                self.builder.entities[node]["located"] = {
                    "relation": relation,
                    "ground": self.entity_for(grounds[0]),
                }
                self.builder.align(node, {child.i})

        lemma = token.lemma_.lower()
        if lemma in lex.AMBIGUOUS:
            self.builder.flag(
                node,
                "sense_ambiguous",
                f"{lemma} has more than one sense and context did not settle it",
                lex.AMBIGUOUS[lemma],
                0.5,
            )
        for child in token.children:
            if child.dep_ == "poss":
                self.builder.entities[node]["possessor"] = self.entity_for(child)
        return node

    def conjuncts(self, token):
        """token plus everything coordinated with it, in text order."""
        found = [token]
        cursor = token
        while True:
            nxt = next((c for c in cursor.children if c.dep_ == "conj" and c.pos_ in NOMINAL_POS), None)
            if nxt is None:
                break
            found.append(nxt)
            cursor = nxt
        return found

    def entity_or_group(self, tokens):
        """One entity, or a group entity when the noun phrase is coordinated.

        0.3.0 had nowhere to put "the boy and the girl", so the clause was duplicated into
        two events sharing a verb token. That is merely clumsy for a distributive verb and
        wrong for a collective one: "Tom and Ben are friends" is not Tom being a friend and
        Ben being a friend.
        """
        members = []
        for token in tokens:
            members += self.conjuncts(token)
        if len(members) == 1:
            return self.entity_for(members[0])

        nodes = [self.entity_for(token) for token in members]
        marker = None
        for token in members:
            marker = next((c for c in token.children if c.dep_ == "cc"), marker)
        coordination = "or" if marker is not None and marker.lower_ == "or" else "and"

        props = {"members": nodes, "coordination": coordination}
        # An alternative is not a plurality: you get one of milk or water, not both.
        if coordination == "and":
            props["number"] = "pl"
        animacies = {self.builder.entities[n].get("animacy") for n in nodes}
        if len(animacies) == 1 and None not in animacies:
            props["animacy"] = animacies.pop()

        spans = [self.builder.span_of(n) for n in nodes]
        covered = set().union(*spans) if spans else set()
        if covered:
            # The group covers the whole phrase, connectors included, so a renderer can
            # highlight it; the members keep their own spans inside it.
            covered = set(range(min(covered), max(covered) + 1))
        return self.builder.entity(props, covered)

    def deictic_location(self, adverb):
        node = self.builder.entity(
            {
                "concept": "location",
                "number": "sg",
                "deixis": lex.DEICTIC_ADVERBS[adverb.lower_],
                "animacy": "place",
            },
            {adverb.i},
        )
        return node


# --- events -------------------------------------------------------------------------


def clause_heads(doc):
    return [
        token
        for token in doc
        if token.pos_ in ("VERB", "AUX") and token.dep_ in CLAUSE_DEPS
    ]


def future_periphrasis(head):
    """Detect 'is going to VERB', which is a future marker rather than motion."""
    if head.lemma_.lower() != "go" or head.tag_ != "VBG":
        return None
    if not any(child.dep_ == "aux" and child.lemma_.lower() == "be" for child in head.children):
        return None
    for child in head.children:
        if child.dep_ == "xcomp" and child.pos_ == "VERB":
            return child
    return None


def read_tense_aspect(head):
    auxes = [c for c in head.children if c.dep_ in ("aux", "auxpass")]
    lemmas = [a.lemma_.lower() for a in auxes]

    tense = "present"
    if "will" in lemmas or "shall" in lemmas:
        tense = "future"
    elif any(a.morph.get("Tense") == ["Past"] for a in auxes):
        tense = "past"
    elif head.morph.get("Tense") == ["Past"]:
        tense = "past"

    aspect = "simple"
    if "be" in lemmas and head.tag_ == "VBG":
        aspect = "progressive"
    elif "have" in lemmas and head.tag_ == "VBN":
        aspect = "perfect"
    return tense, aspect


def read_modality(head):
    for child in head.children:
        if child.dep_ in ("aux", "advmod"):
            word = child.lower_
            if word == "cannot":
                return "can"
            if word in lex.MODALS:
                return lex.MODALS[word]
    return None


def is_negated(head):
    for child in head.children:
        if child.dep_ == "neg":
            return True
        if child.lower_ in ("cannot", "never"):
            return True
        if child.dep_ == "det" and child.lower_ == "no":
            return True
    for child in head.children:
        for grandchild in child.children:
            if grandchild.dep_ == "det" and grandchild.lower_ == "no":
                return True
    return False


def sentence_mood(doc, head):
    """Read mood off the grammar, falling back to punctuation.

    Held-out data had a question written with a full stop and an imperative written with
    a question mark, so inversion is checked before the mark is trusted.
    """
    subjects = [child for child in head.children if child.dep_ in SUBJECT_DEPS]
    auxes = [child for child in head.children if child.dep_ in ("aux", "auxpass")]

    exclaimed = any(token.text == "!" for token in doc)

    # "How fine he looks!" — an exclamative degree word plus an exclamation mark.
    if exclaimed and any(
        token.lower_ in ("how", "what") and token.dep_ in ("advmod", "det") for token in doc
    ):
        return "exclamative"

    # Subject-auxiliary inversion: the auxiliary comes before the subject.
    if auxes and subjects and min(a.i for a in auxes) < min(s.i for s in subjects):
        return "interrogative"

    if any(token.text == "?" for token in doc):
        # A verse imperative can end in a question mark; the verb form decides.
        if head.dep_ == "ROOT" and head.tag_ == "VB" and not subjects:
            return "imperative"
        return "interrogative"

    if head.dep_ == "ROOT" and head.tag_ == "VB" and not subjects:
        return "imperative"

    # Nothing fronted, but the mark is still doing work: "He broke the window!" is not a
    # statement read flatly. Checked last so that an imperative ending in ! stays one.
    if exclaimed and subjects:
        return "exclamative"
    return "declarative"


def list_prefix(head, subjects):
    """Names at the front of a list that spaCy read as something other than the subject.

    "Ann, Ben and Sam sang" arrives with Ann as an npadvmod, which the vocative rule would
    otherwise claim -- the same label a trailing vocative carries. The two are told apart by
    position: a list member is FOLLOWED by a comma and precedes the subject, where a
    vocative is preceded by one and usually ends the clause.
    """
    if not subjects:
        return []
    first = min(s.i for s in subjects)
    found = []
    for child in head.children:
        if child.dep_ not in ("npadvmod", "dep") or child.pos_ not in NOMINAL_POS:
            continue
        if child.i >= first:
            continue
        following = child.doc[child.i + 1] if child.i + 1 < len(child.doc) else None
        if following is not None and following.text == ",":
            found.append(child)
    return sorted(found, key=lambda c: c.i)


def control_subject(head):
    """Who performs an embedded clause: the matrix object if it has one, else its subject.

    "Mum told Sam to wash the cup" is Sam washing. Borrowing the matrix subject whatever the
    clause looked like handed it to Mum, and the swap counter never saw it because that
    counts agent and patient inverted inside one event, not the wrong person carried into
    another one. Held out j047.
    """
    matrix = head.head
    if matrix.lemma_.lower() not in lex.SUBJECT_CONTROL_VERBS:
        objects = [c for c in matrix.children if c.dep_ in ("dobj", "dative")]
        if objects:
            return objects[:1]
    return [c for c in matrix.children if c.dep_ in ("nsubj", "nsubjpass")]


def build_event(ctx, head, mood):
    """Build one event from a clause head. Returns its id, or None if skipped."""
    builder = ctx.builder
    doc = ctx.doc
    span = {head.i}

    # A future periphrasis moves the event onto the lexical verb it introduces.
    target = future_periphrasis(head)
    going_to = target is not None
    if going_to:
        span.update(child.i for child in head.children if child.dep_ == "aux")
        span.add(head.i)
        span.update(child.i for child in target.children if child.dep_ == "aux")
        subject_source = head
        head = target
        span.add(head.i)
    else:
        subject_source = head

    children = list(head.children)
    if going_to:
        children += [c for c in subject_source.children if c.dep_ in SUBJECT_DEPS]

    span.update(
        child.i
        for child in head.children
        if child.dep_ in ("aux", "auxpass", "neg", "prt", "expl")
    )
    span.update(
        child.i for child in head.children if child.dep_ == "advmod" and child.lower_ == "cannot"
    )
    span.update(child.i for child in head.children if child.lower_ in WH_WORDS and child.dep_ == "advmod")

    predicate = head.lemma_.lower()
    # A list: one event can carry more than one figure-ground relation, and 0.2.0 kept
    # only the last, which silently dropped half of "on the bank, under the rock".
    spatials = []
    coordinated = []
    manner = None
    measure = None
    focus = None
    frequency = None
    phase = None
    category = None
    vocative = None
    # An xcomp is non-finite: tense, polarity and mood belong to the matrix clause, and
    # its subject is not expressed, so it is inherited.
    # 0.2.0 only recognised xcomp, so purpose infinitives ("bread to eat"), perception
    # complements ("saw him run") and participials ("sat, waiting") were given a tense
    # and a mood the text never asserts.
    has_infinitive_to = any(c.dep_ == "aux" and c.lower_ == "to" for c in head.children)
    has_finite_aux = any(
        c.dep_ in ("aux", "auxpass") and c.lower_ not in ("to",) for c in head.children
    )
    is_complement = not going_to and (
        head.dep_ == "xcomp"
        or has_infinitive_to
        or (head.dep_ == "ccomp" and head.tag_ == "VB" and not has_finite_aux)
        or (head.dep_ == "advcl" and head.tag_ == "VBG" and not has_finite_aux)
    )
    borrowed = set()
    if is_complement and not any(c.dep_ in ("nsubj", "nsubjpass") for c in children):
        controllers = control_subject(head)
        children += controllers
        borrowed = {c.i for c in controllers}
    props = {}
    roles = {}
    spatial = None
    attribute = None
    degree = None
    comparand = None
    question = None

    # --- idiom: keep the predicate, drop the literal participants ---------------
    if ctx.idiom and head.i in ctx.idiom[1]:
        predicate = ctx.idiom[0]
        span.update(ctx.idiom[1])
        node = builder.event(
            {
                "predicate": predicate,
                "tense": read_tense_aspect(head)[0],
                "aspect": read_tense_aspect(head)[1],
                "polarity": "negative" if is_negated(head) else "positive",
                "mood": mood,
            },
            span,
        )
        builder.flag(node, "idiom_suspected", "Recognised idiom. Do not render literally.", score=0.3)
        return node

    # --- predicate idiom: the verb is replaced, the participants stay -----------
    idiom_span = set()
    idiomatic = False
    if ctx.predicate_idiom and head.i == min(ctx.predicate_idiom[1]):
        predicate, idiom_span = ctx.predicate_idiom
        idiomatic = True
        span.update(idiom_span)
        # "take care of your coat": the object hangs under the idiom's own preposition,
        # two levels down from the verb, so the role loop over head.children never sees it.
        for token in head.doc:
            if token.dep_ == "pobj" and token.head.i in idiom_span:
                roles["patient"] = ctx.entity_for(token)

    # --- phrasal verb: the swallowed preposition is not a spatial relation ------
    swallowed = None
    if head.i in ctx.phrasal:
        predicate, extra, swallowed = ctx.phrasal[head.i]
        span.update(extra)

    if predicate == "be" or head.lemma_.lower() == "be":
        predicate = lex.COPULA_ATTRIBUTE

    # A past participle under a passive auxiliary may be a state rather than an action.
    stative_participle = head.lower_ in lex.ADJECTIVAL_PARTICIPLES and any(
        c.dep_ == "auxpass" for c in head.children
    )
    if stative_participle:
        predicate = lex.COPULA_ATTRIBUTE
        attribute = head.lower_

    # spaCy sometimes labels a second conjunct as another subject rather than a conj, so
    # same-dep siblings are merged into one group alongside the conj chain.
    coordinated_args, skip_children, list_members = {}, set(), set()
    for dep_name in ("nsubj", "nsubjpass", "dobj"):
        same = [
            c
            for c in children
            if c.dep_ == dep_name and c.pos_ in NOMINAL_POS and c.i not in borrowed
        ]
        if dep_name.startswith("nsubj"):
            prefix = list_prefix(head, same)
            list_members.update(c.i for c in prefix)
            same = prefix + same
        if len(same) > 1:
            coordinated_args[same[0].i] = same
            skip_children.update(c.i for c in same[1:])

    def argument(child):
        """The entity filling an argument slot, which may be a coordinated group."""
        return ctx.entity_or_group(coordinated_args.get(child.i, [child]))

    for child in children:
        if child.i in skip_children:
            continue
        # A borrowed controller keeps its own dependency label -- Sam is still the object
        # of told -- but it is the subject of this clause, so it is read as one. A name at
        # the head of a list arrives mislabelled and is read the same way.
        dep = "nsubj" if child.i in borrowed or child.i in list_members else child.dep_
        if child.i in idiom_span:
            continue

        # A relative pronoun is not a participant; it stands for the noun the clause
        # modifies, so the role is filled by that noun instead.
        if (
            dep in ("nsubj", "nsubjpass", "dobj")
            and child.lower_ in RELATIVE_PRONOUNS
            and head.dep_ == "relcl"
        ):
            roles["agent" if dep.startswith("nsubj") else "patient"] = ctx.entity_for(head.head)
            span.add(child.i)
            continue

        if dep in ("nsubj", "nsubjpass") or (dep == "expl" and predicate != lex.EXISTENTIAL):
            if child.lower_ == "it" and head.lemma_.lower() in ("rain", "snow"):
                span.add(child.i)
                continue
            if dep == "expl":
                predicate = lex.EXISTENTIAL
                span.add(child.i)
                continue
            role = ctx.roles.get(head.i, {}).get(child.i, "agent")
            # A borrowed controller is not a child of this verb, so no declarative rule can
            # match it and the default lands on agent. The verb's own class decides instead.
            if role == "agent" and child.i in borrowed and head.lemma_.lower() in lex.EXPERIENCER_VERBS:
                role = "experiencer"
            # Construction overrides the verb's lexical class: a copula has no agent
            # whatever the verb would otherwise take.
            if predicate in (lex.COPULA_ATTRIBUTE, lex.COPULA_LOCATED, lex.EXISTENTIAL):
                role = "theme"
            if dep == "nsubjpass":
                role = "theme" if stative_participle else "patient"
            if child.lower_ in WH_WORDS:
                node = ctx.entity_for(child)
                roles[role] = node
                question = {"type": child.lower_, "role": role, "target": node}
            else:
                roles[role] = argument(child)

        elif dep in ("dobj", "attr", "oprd"):
            if dep == "attr" and child.pos_ in ("NOUN", "PROPN") and not any(
                c.dep_ == "expl" for c in head.children
            ):
                # "My dad is a farmer": the complement is a class, not a property, and it
                # is an entity so a great storyteller keeps great.
                category = ctx.entity_for(child)
                predicate = "be.category"
                continue

            if dep in ("attr", "oprd") and (
                child.pos_ == "ADJ" or child.morph.get("Degree") in (["Cmp"], ["Sup"])
            ):
                attribute = child.lemma_.lower()
                span.add(child.i)
                span.update(c.i for c in child.children if c.dep_ == "det")
                if child.morph.get("Degree") == ["Sup"]:
                    degree = "superlative"
                elif child.morph.get("Degree") == ["Cmp"]:
                    degree = "comparative"
                continue
            if dep == "attr" and any(c.dep_ == "expl" for c in head.children):
                predicate = lex.EXISTENTIAL
                roles["theme"] = ctx.entity_for(child)
            elif child.lower_ in WH_WORDS:
                node = ctx.entity_for(child)
                roles["theme"] = node
                question = {"type": child.lower_, "role": "theme", "target": node}
            else:
                role = ctx.roles.get(head.i, {}).get(child.i, "patient")
                roles[role] = argument(child)

        elif dep == "dative":
            roles[ctx.roles.get(head.i, {}).get(child.i, "recipient")] = ctx.entity_for(child)

        elif dep == "acomp":
            phrase_prep = next(
                (
                    g
                    for g in child.children
                    if g.dep_ == "prep" and (child.lower_, g.lower_) in lex.PREPOSITION_PHRASES
                ),
                None,
            )
            if phrase_prep is not None:
                relation = lex.PREPOSITION_PHRASES[(child.lower_, phrase_prep.lower_)]
                grounds = [ctx.entity_for(g) for g in phrase_prep.children if g.dep_ == "pobj"]
                if grounds:
                    span.update({child.i, phrase_prep.i})
                    spatials.append({"relation": relation, "ground": grounds[0]})
                    continue
            attribute = child.lemma_.lower()
            span.add(child.i)
            # "seven years old": the noun phrase measures the attribute rather than
            # participating in anything. Without it the graph says only that she was old.
            unit = next(
                (
                    g
                    for g in child.children
                    if g.dep_ == "npadvmod" and g.lemma_.lower() in lex.MEASURE_UNITS
                ),
                None,
            )
            if unit is not None:
                number = next((n for n in unit.children if n.dep_ == "nummod"), None)
                value = lex.NUMBER_WORDS.get(number.lower_) if number is not None else None
                if value is None and number is not None and number.like_num:
                    try:
                        value = int(number.text)
                    except ValueError:
                        value = None
                if value is not None:
                    measure = {"quantity": value, "unit": unit.lemma_.lower()}
                    span.update({unit.i, number.i})
            # "red and sweet" asserts two things about one apple, so it is two events.
            coordinated += [c for c in child.children if c.dep_ == "conj" and c.pos_ == "ADJ"]
            if child.morph.get("Degree") == ["Cmp"]:
                degree = "comparative"
            elif child.morph.get("Degree") == ["Sup"]:
                degree = "superlative"
            for grandchild in child.children:
                if grandchild.dep_ == "advmod" and grandchild.lower_ in lex.DEGREE_ADVERBS:
                    degree = lex.DEGREE_ADVERBS[grandchild.lower_]
                    span.add(grandchild.i)
                elif grandchild.dep_ == "prep" and grandchild.lower_ in ("than", "as"):
                    for great in grandchild.children:
                        if great.dep_ == "pobj":
                            comparand = ctx.entity_for(great)
                            span.add(grandchild.i)
                            if grandchild.lower_ == "as":
                                degree = "equative"
                            else:
                                degree = degree if degree == "comparative" else "comparative"

        elif dep == "prep" and (swallowed is None or child.i != swallowed.i):
            if child.lower_ == "with":
                for pobj in child.children:
                    if pobj.dep_ == "pobj":
                        roles["comitative"] = ctx.entity_for(pobj)
                        span.add(child.i)
                continue

            pobj = next((c for c in child.children if c.dep_ == "pobj"), None)
            if pobj is not None and (
                head.lemma_.lower(), child.lower_, pobj.lemma_.lower()
            ) in lex.VERB_PP_IDIOMS:
                predicate = lex.VERB_PP_IDIOMS[
                    (head.lemma_.lower(), child.lower_, pobj.lemma_.lower())
                ]
                idiomatic = True
                span.update({child.i, pobj.i})
                continue

            relation, prep_span = preposition_relation(child)
            if relation is None or (
                child.lower_ in lex.ABOUT_PREPOSITIONS
                and head.lemma_.lower() in lex.EXPERIENCER_VERBS
            ):
                if child.lower_ in lex.ABOUT_PREPOSITIONS:
                    for pobj in child.children:
                        if pobj.dep_ == "pobj":
                            roles.setdefault("theme", ctx.entity_for(pobj))
                            span.add(child.i)
                continue
            grounds = []
            for pobj in child.children:
                if pobj.dep_ != "pobj":
                    continue
                grounds.append(ctx.entity_for(pobj))
                grounds += [
                    ctx.entity_for(conj) for conj in pobj.children if conj.dep_ == "conj"
                ]
            if not grounds:
                continue
            span.update(prep_span)
            spatials.append({
                "relation": relation,
                "ground": grounds[0] if len(grounds) == 1 else grounds,
            })

        elif dep in ("advmod", "neg") and child.lower_ in lex.FREQUENCY_ADVERBS:
            frequency = lex.FREQUENCY_ADVERBS[child.lower_]
            span.add(child.i)

        elif dep == "advmod" and child.lower_ in lex.PHASE_ADVERBS:
            phase = lex.PHASE_ADVERBS[child.lower_]
            span.add(child.i)

        elif (
            dep in ("advmod", "prt")
            and child.lower_ in lex.DIRECTIONAL_ADVERBS
            and (swallowed is None or child.i != swallowed.i)
        ):
            spatials.append({"relation": lex.DIRECTIONAL_ADVERBS[child.lower_]})
            span.add(child.i)

        elif (
            dep == "advmod"
            and child.pos_ == "ADV"
            and child.lower_ not in lex.NON_MANNER_ADVERBS
            and child.lower_ not in WH_WORDS
            and child.lower_.endswith("ly")
        ):
            manner = child.lemma_.lower()
            span.add(child.i)

        elif dep == "advmod" and child.lower_ in lex.LOCATIVE_ADVERBS:
            concept, relation = lex.LOCATIVE_ADVERBS[child.lower_]
            ground = builder.entity(
                {"concept": concept, "number": "sg", "animacy": "place"}, {child.i}
            )
            spatials.append({"relation": relation, "ground": ground})

        elif dep == "advmod" and child.lower_ in lex.DEICTIC_ADVERBS:
            # "there" after be is existential; elsewhere it is a place.
            if child.lower_ == "there" and head.lemma_.lower() in ("be", "exist"):
                span.add(child.i)
                predicate = lex.EXISTENTIAL
            else:
                spatials.append({"relation": "at", "ground": ctx.deictic_location(child)})

        elif dep in ("npadvmod", "vocative", "dep") and child.pos_ == "PROPN":
            vocative = ctx.entity_for(child)

        elif dep == "xcomp" and child.pos_ == "VERB" and not going_to:
            props["complement_token"] = child

    # A focus particle sits on whatever it narrows, which may be a noun deep in the clause
    # rather than a child of the verb, so this runs once the entities exist.
    for token in head.doc:
        if token.lower_ not in lex.FOCUS_PARTICLES or token.dep_ != "advmod":
            continue
        anchor = token.head
        if anchor.pos_ == "ADJ":
            continue  # "too big" is a degree, not a focus
        target = ctx.entity_cache.get(anchor.i)
        if target is None and anchor.i == head.i:
            # Attached to the verb: it focuses the subject, which is the reading in
            # "He too can swim". Focusing the predicate itself is not distinguished.
            target = roles.get("agent") or roles.get("theme") or roles.get("experiencer")
        if target is not None:
            focus = {"particle": token.lower_, "target": target}
            span.add(token.i)
            break

    if swallowed is not None:
        for child in swallowed.children:
            if child.dep_ == "pobj":
                roles["patient"] = ctx.entity_for(child)

    if spatials and predicate == lex.COPULA_ATTRIBUTE and attribute is None:
        predicate = lex.COPULA_LOCATED
    if predicate == lex.EXISTENTIAL and "theme" not in roles and "agent" in roles:
        roles["theme"] = roles.pop("agent")

    tense, aspect = read_tense_aspect(head)
    modality = read_modality(head)
    if going_to:
        tense, modality = "future", "going-to"

    # A non-finite complement carries no mood, so it cannot carry a question either:
    # "Did you see that boy fall down?" asks about the seeing, not about the falling.
    if mood == "interrogative" and question is None and not is_complement:
        for token in doc:
            if token.lower_ in WH_WORDS and token.dep_ == "advmod":
                question = {"type": token.lower_, "role": "location" if token.lower_ == "where" else None}
                break
        else:
            question = {"type": "yes-no"}
        if question.get("role") is None:
            question.pop("role", None)

    if question and question.get("type") == "where" and predicate == lex.COPULA_ATTRIBUTE:
        predicate = lex.COPULA_LOCATED

    # between needs two reference points; a single plural ground supplies them.
    for spatial in spatials:
        if spatial.get("relation") != "between":
            continue
        ground = spatial["ground"]
        if isinstance(ground, str):
            entity = builder.entities[ground]
            if entity.get("number") == "pl" and "quantity" not in entity:
                entity["quantity"] = 2

    if mood == "imperative" and vocative is not None:
        # "Come here, Ben" addresses Ben, so the vocative is the agent rather than an
        # anonymous addressee standing beside the person actually named.
        roles["agent"] = vocative
    elif mood == "imperative":
        addressee = ctx.singletons.get(("addressee", "2sg", None))
        if addressee is None:
            addressee = builder.entity(
                {
                    "concept": "addressee",
                    "person": "2sg",
                    "number": "sg",
                    "animacy": "person",
                    "implicit": True,
                }
            )
            ctx.singletons[("addressee", "2sg", None)] = addressee
        roles["agent"] = addressee

    if is_complement:
        tense = modality = None
        if head.tag_ == "VBG":
            aspect = "progressive"

    # After the imperative block, because that is where a vocative becomes the agent and
    # the figure is read off the roles.
    figure = roles.get("agent") or roles.get("theme") or roles.get("patient")
    moved = roles.get("patient") or roles.get("theme")
    if moved and head.lemma_.lower() in lex.MOTION_TRANSFER_VERBS:
        figure = moved
    if figure:
        for spatial in spatials:
            spatial["figure"] = figure

    event_props = {
        "predicate": predicate,
        "roles": roles or None,
        "attribute": attribute,
        "measure": measure,
        "focus": focus,
        "category": category,
        "manner": manner,
        "frequency": frequency,
        "phase": phase,
        "modifies": ctx.entity_for(head.head) if head.dep_ == "relcl" else None,
        "degree": degree,
        "comparand": comparand,
        "spatial": spatials or None,
        "tense": tense,
        "aspect": aspect,
        "polarity": None if is_complement else ("negative" if is_negated(head) else "positive"),
        "mood": None if is_complement else mood,
        "modality": modality,
        "question": question if mood == "interrogative" else None,
    }
    if modality in lex.IRREALIS_MODALS:
        event_props["irrealis"] = True
    if frequency == "never":
        event_props["polarity"] = "negative"

    node = builder.event(event_props, span)
    if vocative is not None:
        builder.address = vocative

    for extra in coordinated:
        sibling = builder.event(
            {
                "predicate": predicate,
                "roles": dict(roles) or None,
                "attribute": extra.lemma_.lower(),
                "tense": tense,
                "aspect": aspect,
                "polarity": event_props.get("polarity"),
                "mood": mood,
            },
            {extra.i},
        )
        marker = next(
            (c for c in extra.children if c.dep_ == "cc" and c.lower_ in lex.DISCOURSE_MARKERS),
            None,
        )
        builder.relation(
            {
                "type": "addition",
                "from": node,
                "to": sibling,
                "marker": marker.lower_ if marker is not None else None,
            },
            {marker.i} if marker is not None else None,
        )

    if predicate in lex.NOT_DEPICTABLE:
        builder.flag(node, "not_depictable", f"{predicate} is a mental state with no depiction", score=0.6)
    if head.i in ctx.phrasal:
        builder.flag(
            node,
            "parse_uncertain",
            "Phrasal verb: the particle was absorbed into the predicate, not read as a preposition",
            score=0.5,
        )
    return node


# --- discourse ----------------------------------------------------------------------


def build_discourse(ctx, head_to_event):
    """Link clause events using explicit connectives only.

    Relations the reader infers are deliberately not emitted. A rule parser cannot find
    them, and asserting one the text does not mark would put an inference into the data.
    """
    builder = ctx.builder
    doc = ctx.doc

    for head, event_id in head_to_event.items():
        marker = None
        candidates = list(head.children)
        if head.dep_ == "conj":
            # spaCy attaches the coordinator to the first conjunct, not the second.
            candidates += [c for c in head.head.children if c.dep_ == "cc"]
        for child in candidates:
            if child.dep_ in ("mark", "cc") and child.lower_ in lex.DISCOURSE_MARKERS:
                marker = child
                break
            if child.dep_ == "advmod" and child.lower_ in ("then", "first"):
                marker = child
        if marker is None:
            continue

        relation_type, direction = lex.DISCOURSE_MARKERS.get(
            marker.lower_, ("sequence", "forward")
        )

        # spaCy builds a fresh Token proxy on each access, so `head.head is not head` is
        # true even at the root. Comparing indices is the only reliable identity test, and
        # getting it wrong related every And-, But- and Then-initial clause to itself.
        other_head = head.head if head.head.i != head.i else None
        if head.dep_ == "conj":
            other_head = head.head
        if other_head is None or other_head not in head_to_event:
            continue
        other_id = head_to_event[other_head]

        if direction == "backward":
            source, target = event_id, other_id
        else:
            source, target = other_id, event_id

        span = {marker.i}
        if relation_type == "sequence":
            # First X, then Y marks one relation twice.
            span.update(
                token.i
                for token in doc
                if token.lower_ in ("first", "then") and token.dep_ == "advmod"
            )
        builder.relation(
            {"type": relation_type, "from": source, "to": target, "marker": marker.lower_},
            span,
        )


# --- entry point ---------------------------------------------------------------------


def find_speech_act(doc):
    """Match a leading interactional phrase, and say whether it is the whole utterance.

    "Thank you." describes no scene at all. "Yes, if you will sit still." opens with one
    and then describes something, so the act is recorded and the clause still parsed.
    """
    lemmas = [token.lemma_.lower() for token in doc]
    for width in (3, 2, 1):
        key = tuple(lemmas[:width])
        if key in lex.SPEECH_ACT_PHRASES:
            rest = [token for token in doc[width:] if not token.is_punct]
            return lex.SPEECH_ACT_PHRASES[key], not rest
    return None, False


def parse(text, tokens=None, fallback=None):
    """Parse text into a scene graph. tokens fixes the tokenisation alignment refers to.

    fallback is an optional callable taking the text and returning an AMR graph in penman
    notation. It is consulted only when the rules produce no events at all -- roughly one
    sentence in nine on held-out set three, where spaCy's tagger reads the verb as a noun
    and there is no verbal root to build from. It never overrides a rule that fired,
    because the rules are the more precise of the two and precision is what a teacher-first
    renderer needs. See holdout3/AMR-BENCHMARK.md.
    """
    if tokens is None:
        tokens = [token.text for token in _nlp().tokenizer(text)]
    doc = _doc(tokens)
    builder = Builder(text, tokens)
    ctx = Context(doc, builder)

    act, standalone = find_speech_act(doc)
    if act is not None:
        builder.speech_act = act
        if standalone:
            return builder.graph()

    heads = clause_heads(doc)
    head_to_event = {}
    skip = set()

    for head in heads:
        if head in skip:
            continue
        target = future_periphrasis(head)
        if target is not None:
            skip.add(target)
        mood = sentence_mood(doc, head)
        event_id = build_event(ctx, head, mood)
        if event_id:
            head_to_event[head] = event_id

    # Resolve xcomp complements now that every clause has an id.
    for event in builder.events:
        token = event.pop("complement_token", None)
        if token is not None and token in head_to_event:
            event["complement"] = head_to_event[token]

    build_discourse(ctx, head_to_event)

    # A condition makes its antecedent hypothetical. Nothing on the clause itself says
    # so, so this can only be set once the relation exists.
    by_id = {event["id"]: event for event in builder.events}
    for relation in builder.discourse:
        if relation.get("type") == "condition":
            antecedent = by_id.get(relation.get("from"))
            if antecedent is not None:
                antecedent["irrealis"] = True

    # Gaps only. An empty graph is a blank page where a picture was expected, which is the
    # one outcome worse than a flagged approximate one.
    if fallback is not None and not builder.events and builder.speech_act is None:
        from . import amr_bridge

        spare = Builder(text, tokens)
        if amr_bridge.build(fallback(text), doc, spare, entity_props, read_tense_aspect):
            spare.address, spare.speech_act = builder.address, builder.speech_act
            # No pattern is set: that field names a sentence shape, not a provenance. Every
            # node the bridge builds carries a parse_uncertain flag instead, which is what a
            # teacher-facing review queue should be reading anyway.
            return spare.graph()

    return builder.graph()
