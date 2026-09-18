"""Dependency patterns, written as data rather than control flow.

The rules that decide who acts and who is acted on used to live inside a long loop over
a token's children, mixed in with everything else the parser does. That made them hard
to review and hard to see: the bug where "put the box on the shelf" was read as the
phrasal verb "put on" was invisible because the deciding condition sat three branches
deep. Here each rule names the construction it matches, says what it assigns and says
why, so the rule set can be read by someone who is not reading the parser.

A limitation worth stating rather than hiding: `DependencyMatcher` has no operator for
"this child is absent". Rules that need one carry an explicit `guard`, and that is the
honest shape of the knowledge — the pattern says what to look for, the guard says what
would rule it out.

Order is significant. Rules are tried in the order written, most specific first, and the
first rule to claim a token keeps it.
"""

from . import lexicon as lex

ROLE_RULES = [
    {
        "name": "experiencer_subject",
        "doc": "like, want, see, think: the subject undergoes rather than acts. Drawing "
        "it as an agent puts a person mid-action when the sentence reports a state.",
        "role": "experiencer",
        "pattern": [
            {
                "RIGHT_ID": "verb",
                "RIGHT_ATTRS": {"POS": "VERB", "LEMMA": {"IN": sorted(lex.EXPERIENCER_VERBS)}},
            },
            {
                "LEFT_ID": "verb",
                "REL_OP": ">",
                "RIGHT_ID": "filler",
                "RIGHT_ATTRS": {"DEP": "nsubj"},
            },
        ],
    },
    {
        "name": "agent_subject",
        "doc": "The general case: the subject of a verb is the one doing it. Left-to-right "
        "order is what distinguishes g001 from g001b, so this is the rule the whole "
        "project rests on.",
        "role": "agent",
        "pattern": [
            {"RIGHT_ID": "verb", "RIGHT_ATTRS": {"POS": {"IN": ["VERB", "AUX"]}}},
            {
                "LEFT_ID": "verb",
                "REL_OP": ">",
                "RIGHT_ID": "filler",
                "RIGHT_ATTRS": {"DEP": {"IN": ["nsubj", "nsubjpass"]}},
            },
        ],
    },
    {
        "name": "recipient_dative",
        "doc": "give, send, show: the dative is who receives, not what is given.",
        "role": "recipient",
        "pattern": [
            {"RIGHT_ID": "verb", "RIGHT_ATTRS": {"POS": "VERB"}},
            {
                "LEFT_ID": "verb",
                "REL_OP": ">",
                "RIGHT_ID": "filler",
                "RIGHT_ATTRS": {"DEP": "dative"},
            },
        ],
    },
    {
        "name": "theme_object",
        "doc": "The object of a transfer or a mental state is not acted on. A book that "
        "is given is moved, not changed, and an apple that is liked is untouched.",
        "role": "theme",
        "pattern": [
            {
                "RIGHT_ID": "verb",
                "RIGHT_ATTRS": {
                    "POS": "VERB",
                    "LEMMA": {"IN": sorted(lex.THEME_OBJECT_VERBS | lex.DITRANSITIVE_VERBS)},
                },
            },
            {
                "LEFT_ID": "verb",
                "REL_OP": ">",
                "RIGHT_ID": "filler",
                "RIGHT_ATTRS": {"DEP": "dobj"},
            },
        ],
    },
    {
        "name": "patient_object",
        "doc": "The general case: a direct object is the thing acted on.",
        "role": "patient",
        "pattern": [
            {"RIGHT_ID": "verb", "RIGHT_ATTRS": {"POS": "VERB"}},
            {
                "LEFT_ID": "verb",
                "REL_OP": ">",
                "RIGHT_ID": "filler",
                "RIGHT_ATTRS": {"DEP": "dobj"},
            },
        ],
    },
]


def _has_direct_object(doc, verb_index):
    return any(child.dep_ == "dobj" for child in doc[verb_index].children)


PHRASAL_RULES = [
    {
        "name": "verb_plus_particle",
        "doc": "A particle is always part of the verb. put on, pick up, wake up.",
        "pattern": [
            {"RIGHT_ID": "verb", "RIGHT_ATTRS": {"POS": "VERB"}},
            {
                "LEFT_ID": "verb",
                "REL_OP": ">",
                "RIGHT_ID": "particle",
                "RIGHT_ATTRS": {"DEP": "prt"},
            },
        ],
        "guard": None,
    },
    {
        "name": "verb_plus_bare_preposition",
        "doc": "A preposition belongs to the verb only when the verb has no object of its "
        "own. 'He looked after his sister' is one verb; 'put the box on the shelf' is a "
        "verb with a real prepositional phrase, and merging it makes the shelf the thing "
        "being put.",
        "pattern": [
            {"RIGHT_ID": "verb", "RIGHT_ATTRS": {"POS": "VERB"}},
            {
                "LEFT_ID": "verb",
                "REL_OP": ">",
                "RIGHT_ID": "particle",
                "RIGHT_ATTRS": {"DEP": "prep"},
            },
        ],
        # DependencyMatcher cannot say "and no dobj child", so the exception is explicit.
        "guard": lambda doc, verb_index, _particle: not _has_direct_object(doc, verb_index),
    },
]


def build_matcher(vocab):
    """One matcher holding every rule, keyed so matches can be traced back by name."""
    from spacy.matcher import DependencyMatcher

    matcher = DependencyMatcher(vocab)
    for rule in ROLE_RULES:
        matcher.add(f"role:{rule['name']}", [rule["pattern"]])
    for rule in PHRASAL_RULES:
        matcher.add(f"phrasal:{rule['name']}", [rule["pattern"]])
    return matcher


def _matches_by_rule(doc, matcher):
    """rule name -> list of matched token index tuples, in the order the rules are written."""
    found = {}
    for match_id, token_indices in matcher(doc):
        found.setdefault(doc.vocab.strings[match_id], []).append(token_indices)
    return found


def match_roles(doc, matcher):
    """verb token index -> {filler token index: role}.

    Rules are applied in order and the first to claim a filler keeps it, so a specific
    rule placed above a general one wins without either needing to know about the other.
    """
    found = _matches_by_rule(doc, matcher)
    assigned = {}
    for rule in ROLE_RULES:
        for verb_index, filler_index in found.get(f"role:{rule['name']}", []):
            slots = assigned.setdefault(verb_index, {})
            if filler_index not in slots:
                slots[filler_index] = rule["role"]
    return assigned


def match_phrasal(doc, matcher):
    """verb token index -> (concept, particle token) for recognised phrasal verbs."""
    found = _matches_by_rule(doc, matcher)
    result = {}
    for rule in PHRASAL_RULES:
        for verb_index, particle_index in found.get(f"phrasal:{rule['name']}", []):
            if verb_index in result:
                continue
            guard = rule["guard"]
            if guard is not None and not guard(doc, verb_index, particle_index):
                continue
            verb, particle = doc[verb_index], doc[particle_index]
            key = (verb.lemma_.lower(), particle.lemma_.lower())
            if key in lex.PHRASAL_VERBS:
                result[verb_index] = (lex.PHRASAL_VERBS[key], particle)
    return result
