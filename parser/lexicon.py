"""Data the rules read: concept mapping, verb classes, prepositions, multi-word units.

Kept apart from the rules so the linguistic knowledge is inspectable and editable by
someone who is not reading the parser, and so the multi-word pass has one obvious home.
"""

# Pronouns resolve to the special concepts documented in the README. he and she become
# person because they denote a human; it and they become thing because the concept is
# genuinely unknown until coreference resolves it.
PRONOUNS = {
    "i": {"concept": "speaker", "person": "1sg", "number": "sg", "animacy": "person"},
    "me": {"concept": "speaker", "person": "1sg", "number": "sg", "animacy": "person"},
    "my": {"concept": "speaker", "person": "1sg", "number": "sg", "animacy": "person"},
    "we": {"concept": "speaker", "person": "1pl", "number": "pl", "animacy": "person"},
    "us": {"concept": "speaker", "person": "1pl", "number": "pl", "animacy": "person"},
    "our": {"concept": "speaker", "person": "1pl", "number": "pl", "animacy": "person"},
    "you": {"concept": "addressee", "person": "2sg", "number": "sg", "animacy": "person"},
    "your": {"concept": "addressee", "person": "2sg", "number": "sg", "animacy": "person"},
    "he": {"concept": "person", "person": "3sg", "gender": "male", "number": "sg", "animacy": "person"},
    "him": {"concept": "person", "person": "3sg", "gender": "male", "number": "sg", "animacy": "person"},
    "his": {"concept": "person", "person": "3sg", "gender": "male", "number": "sg", "animacy": "person"},
    "she": {"concept": "person", "person": "3sg", "gender": "female", "number": "sg", "animacy": "person"},
    "her": {"concept": "person", "person": "3sg", "gender": "female", "number": "sg", "animacy": "person"},
    "it": {"concept": "thing", "person": "3sg", "number": "sg"},
    "its": {"concept": "thing", "person": "3sg", "number": "sg"},
    "they": {"concept": "thing", "person": "3pl", "number": "pl"},
    "them": {"concept": "thing", "person": "3pl", "number": "pl"},
    "their": {"concept": "thing", "person": "3pl", "number": "pl"},
}

POSSESSIVE_PRONOUNS = {"my", "your", "his", "her", "our", "their", "its"}

DEMONSTRATIVES = {"this": "proximal", "these": "proximal", "that": "distal", "those": "distal"}
DEICTIC_ADVERBS = {"here": "proximal", "there": "distal"}

QUANTIFIERS = {"some", "many", "few", "all", "no", "any", "every", "both"}

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

# Verbs whose subject undergoes rather than acts. Drawing an experiencer as an agent
# puts a person mid-action when the sentence describes a mental state.
EXPERIENCER_VERBS = {
    "like", "love", "hate", "want", "see", "hear", "think", "know", "feel", "need", "wish",
}

# Experiencer verbs whose object is a theme rather than a patient.
THEME_OBJECT_VERBS = EXPERIENCER_VERBS | {"have", "exist"}

PREPOSITIONS = {
    "at": "at", "on": "on", "in": "in", "under": "under", "underneath": "under",
    "over": "over", "above": "above", "below": "below", "behind": "behind",
    "beside": "next-to", "near": "near", "between": "between", "into": "into",
    "onto": "onto", "off": "off", "up": "up", "down": "down", "through": "through",
    "across": "across", "around": "around", "round": "around", "to": "to",
    "from": "from", "inside": "in", "outside": "out-of", "by": "next-to",
}

# Multi-word prepositions, matched before the single-word table.
PREPOSITION_PHRASES = {
    ("next", "to"): "next-to",
    ("in", "front", "of"): "in-front-of",
    ("out", "of"): "out-of",
    ("on", "top", "of"): "on",
}

# Phrasal verbs whose meaning is not the sum of their parts. This pass has to run before
# role assignment: read as a verb plus a preposition, "looked after his sister" produces
# a plausible, wrong picture of someone standing behind a girl, and nothing flags it.
PHRASAL_VERBS = {
    ("look", "after"): "look-after",
    ("look", "for"): "look-for",
    ("look", "at"): "look-at",
    ("pick", "up"): "pick-up",
    ("put", "on"): "put-on",
    ("take", "off"): "take-off",
    ("get", "up"): "get-up",
    ("sit", "down"): "sit-down",
    ("stand", "up"): "stand-up",
    ("wake", "up"): "wake-up",
    ("give", "up"): "give-up",
    ("run", "away"): "run-away",
}

# Idioms must never render literally. The value is the predicate to use instead.
IDIOMS = {
    ("rain", "cat", "and", "dog"): "rain",
    ("piece", "of", "cake"): "easy",
    ("under", "the", "weather"): "ill",
}

MODALS = {
    "can": "can", "could": "can", "must": "must", "may": "may",
    "might": "may", "should": "should", "shall": "should", "would": "would",
}

# Modalities that describe a possibility rather than an occurrence. The event must not be
# drawn as taking place.
IRREALIS_MODALS = {"can", "may", "would"}

DISCOURSE_MARKERS = {
    "first": ("sequence", "backward"),
    "because": ("cause", "backward"),
    "since": ("cause", "backward"),
    "so": ("cause", "forward"),
    "if": ("condition", "backward"),
    "but": ("contrast", "forward"),
    "or": ("disjunction", "forward"),
    "and": ("sequence", "forward"),
    "then": ("sequence", "forward"),
    "while": ("simultaneous", "forward"),
    "as": ("simultaneous", "forward"),
    "after": ("sequence", "backward"),
    "before": ("sequence", "forward"),
}

DEGREE_ADVERBS = {"very": "very", "too": "too", "really": "very", "so": "very"}

# Words whose sense the parser cannot settle from context alone. Flagged for review
# rather than guessed at, because a confidently wrong picture teaches the wrong word.
# The first option is the default the parser takes when context settles nothing. It is
# still flagged: a default is a guess, and the teacher should see it before a child does.
AMBIGUOUS = {
    "bat": ["bat.animal", "bat.sport"],
    "bank": ["bank.money", "bank.river"],
    "light": ["light.lamp", "light.weight"],
    "left": ["left.direction", "left.depart"],
    "watch": ["watch.clock", "watch.look"],
}

# Predicates with no depiction. They need a drawing convention, not a symbol.
NOT_DEPICTABLE = {"think", "know", "want", "need", "believe", "remember", "forget", "hope"}

# Copula readings, chosen by what complements the verb.
COPULA_ATTRIBUTE = "be.attribute"
COPULA_LOCATED = "be.located"
EXISTENTIAL = "exist"


# Animacy is a best-effort lookup. It steers which rig draws the entity, so a miss is
# cosmetic rather than a meaning error, and unknown words fall through to object.
ANIMACY = {
    "person": [
        "boy", "girl", "man", "woman", "men", "women", "child", "children", "baby",
        "mother", "father", "mum", "mom", "dad", "sister", "brother", "friend",
        "teacher", "farmer", "doctor", "nurse", "people", "family", "parent",
    ],
    "animal": [
        "dog", "cat", "bird", "fish", "cow", "pig", "horse", "duck", "sheep", "hen",
        "rabbit", "bear", "chicken", "squirrel", "bat", "frog", "mouse", "robin", "insect",
    ],
    "place": [
        "school", "park", "home", "house", "garden", "farm", "cave", "street", "hill",
        "city", "town", "room", "shop", "zoo", "beach", "forest", "library", "indoors",
        "location", "kitchen", "classroom",
    ],
}

ANIMACY_LOOKUP = {word: kind for kind, words in ANIMACY.items() for word in words}

MASS_NOUNS = {
    "food", "water", "milk", "bread", "rice", "money", "snow", "rain", "sand",
    "hair", "juice", "sugar", "salt", "butter", "cheese", "homework", "music",
}


# English pronouns force a gender decision on the figure, and these nouns carry one
# lexically. Never inferred from a proper name — see g038.
GENDERED_NOUNS = {
    "boy": "male", "man": "male", "men": "male", "father": "male", "dad": "male",
    "brother": "male", "son": "male", "king": "male", "grandfather": "male", "uncle": "male",
    "girl": "female", "woman": "female", "women": "female", "mother": "female",
    "mum": "female", "mom": "female", "sister": "female", "daughter": "female",
    "queen": "female", "grandmother": "female", "aunt": "female",
}

# Kinship terms used as names. Mum is the mother concept wearing a proper name, not a
# nameless person, so the lexicon can still find a symbol for it.
KINSHIP_PROPER = {
    "mum": "mother", "mom": "mother", "mummy": "mother", "mother": "mother",
    "dad": "father", "daddy": "father", "father": "father",
    "grandma": "grandmother", "grandpa": "grandfather",
    "nan": "grandmother", "granny": "grandmother",
}

# Verbs taking a recipient, whose direct object is transferred rather than acted on.
DITRANSITIVE_VERBS = {"give", "send", "show", "tell", "bring", "pass", "offer", "lend", "buy"}

# Past participles that read as states rather than actions. "her cat was lost" describes
# the cat, and rendering it as an event draws somebody losing something.
ADJECTIVAL_PARTICIPLES = {
    "lost", "broken", "tired", "done", "finished", "closed", "gone",
    "scared", "worried", "excited", "bored", "hurt",
}


# Adverbs that name a place. Without these, "we will stay inside" loses its location
# entirely, because the word is an adverb rather than a preposition with an object.
LOCATIVE_ADVERBS = {
    "inside": ("indoors", "in"),
    "indoors": ("indoors", "in"),
    "outside": ("outdoors", "out-of"),
    "outdoors": ("outdoors", "out-of"),
    "home": ("home", "at"),
    "upstairs": ("upstairs", "at"),
    "downstairs": ("downstairs", "at"),
}

# Non-spatial prepositions that introduce what a mental state is about.
ABOUT_PREPOSITIONS = {"about", "of", "for", "at"}


# --- classes the held-out run showed were missing -------------------------------------

# Pronouns standing in for a noun phrase. The concept is unknown; only the relation is.
POSSESSIVE_NOMINALS = {
    "mine": "1sg", "ours": "1pl", "yours": "2sg", "hers": "3sg", "theirs": "3pl",
}

FREQUENCY_ADVERBS = {
    "always": "always", "usually": "usually", "often": "often",
    "sometimes": "sometimes", "rarely": "rarely", "seldom": "rarely", "never": "never",
}

PHASE_ADVERBS = {"still": "still", "again": "again", "already": "already", "yet": "yet"}

# Directions with no landmark: the dog ran away, the ball rolled down.
DIRECTIONAL_ADVERBS = {
    "away": "away", "back": "back", "down": "down", "up": "up",
    "along": "along", "out": "out-of", "off": "off", "around": "around",
}

# Verbs where the thing moved is the object, not the subject. "He threw the ball into the
# box" puts the ball in the box, not the thrower.
MOTION_TRANSFER_VERBS = {
    "put", "place", "move", "throw", "push", "pull", "drop", "roll", "kick",
    "send", "carry", "bring", "take", "lay", "set", "hang", "pour", "post",
}

# Adverbs that are not manner, so that everything else ending in -ly can be.
NON_MANNER_ADVERBS = {
    "only", "really", "very", "too", "quite", "almost", "nearly", "hardly",
    "probably", "certainly", "surely", "simply", "merely", "early", "likely",
}

# Whole utterances that are interactional moves rather than descriptions. Matched on
# lemmas from the start of the sentence.
SPEECH_ACT_PHRASES = {
    ("thank", "you"): "thanks",
    ("thanks",): "thanks",
    ("please",): "please",
    ("yes",): "affirm",
    ("no",): "deny",
    ("good", "morning"): "greeting",
    ("good", "afternoon"): "greeting",
    ("good", "evening"): "greeting",
    ("good", "day"): "greeting",
    ("hello",): "greeting",
    ("hi",): "greeting",
    ("good", "night"): "farewell",
    ("goodbye",): "farewell",
    ("sorry",): "apology",
}
