# Language support — scene graph schema and gold set

Renders sentences as pictures for ESL Grade 1–2 readers. This repository holds the meaning
representation, the annotated examples it is tested against, a rule parser that produces
it, and a scoring harness. No renderer yet, and no images are fetched yet: the schema had
to survive contact with real sentences first, and now the parser has to.

The bet is that a picture should show **who does what to whom**, not a row of symbols
substituted word for word. Word substitution cannot distinguish `g001` from `g001b`
in [gold/01-patterns.json](gold/01-patterns.json), which are the same words in a
different order and mean opposite things.

## Layout

| Path | What it is |
|---|---|
| `schema/scene-graph.schema.json` | The scene graph, JSON Schema 2020-12. Version `0.3.0`. |
| `schema/scene-graph-0.2.0.json` | Frozen. The held-out set is locked against this version. |
| `gold/` | 77 hand-annotated scene graphs across 11 files. The tuning set. |
| `holdout/` | 47 annotated sentences from public-domain readers, locked and scored once. |
| `tools/check_gold.py` | Schema validation plus the referential checks the schema cannot express. |
| `tools/test_check_gold.py` | Negative tests proving the checker can actually fail. |
| `tools/check_coverage.py` | Measures what ARASAAC can draw, against the gold set or against Dolch. |
| `parser/rules.py` | The rule parser, over a spaCy dependency parse. |
| `parser/lexicon.py` | Pronouns, prepositions, phrasal verbs, idioms, verb classes. |
| `parser/patterns.py` | The role and phrasal-verb rules, as declarative dependency patterns. |
| `tools/score.py` | The scoring harness. Scores each dimension apart from the others. |
| `tools/test_score.py` | Tests that the harness catches each error class. |
| `tools/test_parser.py` | Parser behaviour, on sentences outside the gold set. |
| `tools/test_patterns.py` | Each rule tested on its own, apart from the parser. |
| `tools/test_parser_coverage.py` | The held-out failure classes, on sentences from neither set. |
| `tools/run_parser.py` | Parses every gold sentence into `predictions.json`. |
| `tools/fmt_gold.py` | Canonical formatting, so diffs stay about content. |
| `tools/migrate_0_2_0.py` | The 0.1.0 to 0.2.0 migration, kept as the record of what changed. |
| `tools/migrate_0_3_0.py` | The 0.2.0 to 0.3.0 migration. |
| `tools/sample_holdout.py` | Draws held-out sentences from public-domain readers. |
| `lexicon/wordlists/dolch.json` | Dolch list, each service word classed as content, function or gap. |
| `lexicon/concepts-required.json` | Generated. Every concept the gold set asks for. |
| `lexicon/arasaac-coverage-*.json` | Generated. Per-word lookup results. |

## Running it

```bash
python tools/check_gold.py validate
```

```bash
python tools/check_gold.py concepts
```

```bash
python tools/check_coverage.py dolch
```

```bash
python tools/fmt_gold.py
```

```bash
python tools/run_parser.py && python tools/score.py predictions.json --detail
```

```bash
python -m pytest
```

Install with `pip install -r requirements-dev.txt`, then
`python -m spacy download en_core_web_sm`. Runtime needs only `spacy` and `jsonschema`;
`pytest` is development-only, so nothing in the test stack reaches a classroom.

Current state: 77 tuning graphs and 47 held-out graphs, 0 failures, 0 warnings. 119 tests
passing. 99% ARASAAC coverage on Grade 1-2 content vocabulary.

**The number that matters: 21% scene correct on held out, against 100% on the tuning
set.** See [holdout/FINDINGS.md](holdout/FINDINGS.md). The tuning figure measures coverage
of the sentences the rules were written against and nothing more.

## Symbol coverage

Run against 268 Dolch words (pre-primer through second grade, plus the noun list).
Coverage means a returned pictogram carries the word as an **exact keyword** — ARASAAC's
search is fuzzy enough that asking for *hungry* returns food pictograms, so counting
non-empty results would badly overstate it.

**The art side is viable.** 156 of 158 words needing a symbol resolve exactly, 99%. The
two that do not:

- `pull` — ARASAAC holds only compounds (*pull out*, *pull down*, *pull hair*), no bare
  form. A hypernym fallback covers it.
- `robin` — genuinely absent, and a dated US-specific entry that should not be in a
  contemporary list anyway.

**Most sight words do not need a picture at all.** Of 179 service words, only 39% are
content. 51% are carried by a scene graph field, and `spatial.relation` alone carries
17 of them — more than any other field, which is the strongest evidence that modelling
prepositions explicitly was the right call rather than an indulgence.

This is the number that matters more than the 99%. A symbol-per-word system spends the
bulk of its vocabulary effort on words that are structure, not things.

A second run against the project's own gold vocabulary gives 98%, but that sample was
chosen here and skews concrete, so it is a floor check rather than a measurement.

> ARASAAC pictograms: author Sergio Palao, origin ARASAAC (https://arasaac.org), owned by
> the Government of Aragon, licensed CC BY-NC-SA. The Dolch list in this repository was
> transcribed by hand and should be verified against an authoritative source.

## What the gold set covers

Eight sentence patterns, and then the features that cut across all of them. Tense,
polarity and mood are deliberately not patterns — they are orthogonal, and treating them
as pattern variants is how you end up with a combinatorial pattern list.

| File | Cells | Covers |
|---|---|---|
| `01-patterns` | 9 | The eight base patterns, plus one minimal pair |
| `02-tense` | 6 | Present, past, future, progressive, irregular past |
| `03-negation` | 6 | Negated attribution, possession, modality, imperative, existential |
| `04-questions` | 6 | Wh-gaps in four positions, and yes-no |
| `05-number` | 5 | Explicit counts, bare plurals, quantifiers, mass nouns |
| `06-spatial` | 7 | A six-way preposition contrast set on identical objects |
| `07-reference` | 4 | Pronoun coreference across sentence boundaries |
| `08-discourse` | 5 | Sequence, cause, contrast, condition |
| `09-hard` | 4 | Idiom, polysemy, abstract predicate, phrasal verb |
| `10-deixis-degree` | 10 | Demonstratives, deictic locations, degree, comparison, irrealis |
| `11-address-manner` | 15 | Everything 0.3.0 added, each on a sentence the held-out set motivated |

The spatial block is the highest-value part. Six graphs hold the entities and predicate
constant and vary only the relation, so each one is a ready-made distractor for the other
five — and prepositions are where beginner comprehension actually breaks.

## Concept id conventions

Concept ids are lemma-based, lowercase, hyphenated for multi-word units, and
sense-discriminated with a dot only where a word is genuinely ambiguous:
`dog`, `look-after`, `bat.animal`, `be.located`.

They are deliberately **not** ARASAAC ids or WordNet synsets. The lexicon maps concepts
to art; the graph never names a symbol. That indirection is what lets the symbol set be
swapped later without touching a single annotation, and it keeps symbol licensing and
attribution entirely in the lexicon layer where it belongs.

Five ids carry special meaning:

- `speaker` — whoever is producing the utterance. `person: 1sg` for *I*, `1pl` for *we*.
- `addressee` — whoever is being spoken to. Renders as the reader, which is the hook for student avatars.
- `person` — a human whose identity the sentence does not establish, including unresolved pronouns.
- `thing` — a referent whose concept is unknown until coreference resolves it, as with *it*.
- `location` — a place the text does not name, carrying `deixis` for *here* and *there*.

None of the five resolves to a symbol. They are drawn by the character rig or by position
in the scene, which is why the coverage tool excludes them from its denominator.

## Modelling decisions worth knowing

**Attribute versus modifier.** In *the ball is red*, red is an event `attribute`; in
*two red balls*, it is an entity `modifier`. The first asserts redness and a blue ball is
a valid distractor; the second merely identifies which balls, and a blue ball is a
different sentence. See `g008` against `g029`.

**Possession is recorded twice.** `g004` carries both a `have` event and a `possessor`
property. The event is the assertion a distractor negates; the property is the state the
scene draws. Under negation only the event survives — see `g016`.

**Gender comes from pronouns, never from names.** In `g038`, *Sam* carries no gender; the
later *he* supplies it, and the renderer propagates it back through `coref`. Inferring
gender from a name draws the wrong child.

**Negation renders as a crossed claim, not as its opposite.** *The dog is not big* does
not entail that the dog is small, so `g015` must render a big dog crossed out. Drawing a
small dog teaches a false inference.

**Unknowns in questions are still real nodes.** `g022` gives the unknown eater an entity
with `question.target` pointing at it, so the role structure stays complete and the
renderer knows exactly where to draw the gap.

## What 0.2.0 changed

Four additions, each one evidenced by a gap the coverage run found rather than guessed at.

**`deixis` on entities**, `proximal` or `distal`. Crossed with the existing `number` this
covers all four demonstratives — *this* is proximal and singular, *those* is distal and
plural — so no separate four-way enum was needed. The same field also covers *here* and
*there*, as an entity with concept `location` used as a spatial ground (`g053`, `g054`).
One field, five of the highest-frequency gap words.

**`degree` on events**, and optionally on modifiers. `very`, `too`, `comparative` and
`superlative`. *very* and *too* are separate values because *too* is excessive rather than
merely intense: it says the property defeats some purpose, and rendering it as a stronger
*very* loses that. Comparatives take a `comparand` entity, because a comparison has to
draw both figures (`g057`).

**`irrealis` on events.** True when the event is not asserted to happen at all. This
turned out to cover more than conditionals: *she can swim* is an ability, not a swimming
scene, and that hazard was already flagged in `g005` before the flag existed. Future tense
is deliberately excluded — a future event is asserted to happen, just later, so marking it
irrealis would make the flag redundant with `tense`.

**Ids on discourse relations**, so they can carry alignment spans. Connectives moved off
the event spans and onto the relation: in `g043` the relation now owns both *First* and
*then* as one non-contiguous span, and the events own only their verbs.

Two smaller additions fell out of the same run: `at` in `spatial.relation`, which the
enum was missing despite being a primer word, and `disjunction` in `discourse.type` for
*or*.

The migration is in `tools/migrate_0_2_0.py`, kept rather than deleted because it is the
record of what moved and why. It is idempotent.

## What 0.3.0 changed

Every change answers a specific held-out sentence. The gap table in
[holdout/FINDINGS.md](holdout/FINDINGS.md) was the input; nothing here was invented, and
where the evidence was one sentence and the construction was not basic, the gap was left
open instead.

| Added | Answers | Seen in |
|---|---|---|
| `address` at utterance level | Vocatives. *mamma* is neither caller nor called, so it is not a role. | h010, h012, h015, h045 |
| `speech_act`, and `events` may be empty | *Yes*, *thank you*, *Good morning* assert nothing about a scene. | h005, Dolch |
| `spatial` becomes an array | One event, several figure-ground relations. | h007, h050 |
| `spatial.ground` optional | *fall down*, *Away they marched* — a path with no landmark. | h021, h033, h037 |
| `manner` | *sit still*, *went slowly*. | h005, h033 |
| `frequency` and `phase` | *always*, *never*; *still*, *again*. | h029, h044, h049 |
| `comitative` role | *take dinner with us*. | h022, h029 |
| `simultaneous` discourse type | *went along, reading a book* — one picture, not two panels. | h033, h037 |
| `modifies` on an event | Relative clauses. Modification is not a relation between two assertions. | h031, h034 |
| `located` on an entity | *the voice outside*, *a basket of apples*, *the music of thy voice*. | h026, h035, h046 |
| `category` on an event | *was a great storyteller* — an entity, so the modifier survives. | h041 |
| `exclamative` mood | *How fine he looks!* | h011 |
| `equative` degree | *as blue as it can be*. | h014 |
| `would` modality | | h032 |

Three of these are worth a second look, because they are distinctions the schema now
draws that it did not before.

**`located` versus `spatial`.** *The box on the shelf is red* does not assert that the box
is on the shelf; it says which box. The location sits on the entity, and only the redness
is asserted. A picture showing the box beside the shelf is a different sentence, not a
false one — which matters directly for distractor generation.

**`modifies` versus discourse.** *The dog that barked is big* has two events, but the
barking identifies the dog rather than being claimed. No discourse type fits, because
discourse relates two assertions and this relates an assertion to a thing.

**`frequency` versus `polarity`.** *never* is both: the event does not happen, and it never
does. Both are recorded, and the validator complains if they disagree.

### Versioning

`0.3.0` is a breaking change — `spatial` went from an object to an array. The held-out set
is locked at `0.2.0` and was deliberately **not** migrated, because rewriting it would
damage the record of what was scored. `schema/scene-graph-0.2.0.json` is a frozen copy,
and the validator picks a schema by the version each graph declares, so both sets coexist
and both validate.

## Parser work against the failure taxonomy

The classes in [holdout/FINDINGS.md](holdout/FINDINGS.md) were fixed as classes, not
sentence by sentence. The distinction matters: the taxonomy came from held-out data, so a
fix verified only on the sentence that revealed it proves nothing.

`tools/test_parser_coverage.py` holds 26 tests on sentences belonging to neither the
tuning set nor the held-out set. All 26 failed before the work and pass after it.

| Class | Was | Now |
|---|---|---|
| Noun-phrase heads | *some of the cakes* gave the concept `some` | follows the partitive to the noun, keeps the quantifier |
| Standalone pronouns | `this`, `mine` became concepts | `thing` plus deixis, or `thing` plus an owner |
| Relative pronouns | `that` became an entity | the role is filled by the noun the clause modifies |
| Non-finite clauses | only `xcomp` recognised | purpose infinitives, perception complements and participials too, none given a tense |
| Coordination | *red and sweet* gave one event | two events and an addition relation |
| Spatial figure | always the agent | the thing moved, for a list of transfer verbs |
| Mood | punctuation | subject-auxiliary inversion first, punctuation as fallback |
| `0.3.0` fields | not emitted | address, speech act, manner, frequency, phase, comitative, simultaneous, modifies, located, category, exclamative, equative, would, bare directions |

The tuning set went from 67/77 to **77/77**, with no regression on the 62 it was
originally built against, and zero argument swaps throughout.

**The held-out set can no longer measure this parser**, for two reasons set out in the
addendum to the findings: the fixes were informed by its failure classes, and it is locked
at `0.2.0` while the parser now emits `0.3.0`, so correctly producing a vocative scores as
an error. The next honest number needs a fresh draw.

## Known gaps

These are open, not forgotten.

1. **Unspecified plurals have no convention.** `g028` has plural cats and no count. The
   renderer needs a documented default, and whatever it picks must never be written back
   into the graph — otherwise counting questions become unanswerable.
2. **Inferred relations are not marked as inferred.** The causal link in `g039` is
   supplied by the reader, not by any word. A rule parser will miss it and a language
   model will assert it confidently, and right now the graph cannot tell the two apart.
3. **Speech acts have no home.** *please*, *thank you* and *yes* are not a missing field
   so much as a missing assumption: the schema models sentences that describe a scene, and
   these do not describe anything. They likely need a separate branch rather than another
   property, which is why `0.2.0` left them alone rather than bolting on an enum.
4. **Frequency and repetition.** *always* and *again* need a habitual or iterative value,
   probably on `aspect`. Small, but it interacts with the habitual reading of the present
   simple in `g009`, so it wants doing together with that.
5. **Four stragglers.** *with* (no comitative role), *as* (no comparison structure),
   *just* (focus particle), *let* (no hortative mood). Low frequency individually and each
   needs its own thinking; none blocks a parser.

`0.2.0` closed 11 of the 18 gap words the Dolch run found. The 7 left are the ones where
the right answer is a design decision rather than a field.

## Scoring

One accuracy number would be actively misleading. A parser that finds both animals in
*the dog chased the cat* and then assigns agent and patient backwards draws a confident,
wrong picture — worse for a learner than a parser that fails loudly, because nothing
signals the error. So the harness scores entities, roles, spatial relations, grammatical
features, discourse and alignment separately, and reports **roles given right entities**
alongside plain role accuracy. That conditioned number is the one that isolates role
assignment from entity recognition, and argument swaps are counted outright.

Entity ids are not comparable between two graphs, so correspondence runs through the
alignment: predicted and gold nodes are matched by token-span overlap, and every role
comparison goes through that mapping. Renaming every id changes nothing, which is a test.

Two distinctions the harness draws that a simpler one would collapse:

- **A wrong sense is not a miss.** Finding *bat* and calling it sporting equipment is a
  different failure from not finding it, and the two want different fixes.
- **Discourse type is not discourse direction.** *because* reverses the arrow against
  text order, so a parser can get every relation type right and every arrow backwards.
  Reversals are counted on their own.

`scene correct` is the headline: the fraction of sentences where everything that changes
the picture is right. A picture is right or wrong as a whole, so this is the number that
corresponds to something a child would see.

Running gold against itself must score 100% on every dimension. That identity check is a
permanent test, and it caught a real bug: implicit entities carry no token span, so span
matching could not reach them and they read as spurious on one side and missing on the
other.

## The parser

Rules over a spaCy dependency parse, not a model. Grade 1-2 syntax is short and regular
enough that rules cover it, and rules can say when they do not apply — a model cannot,
and a confidently wrong picture is the worst output this system can produce. It also
keeps cost per sentence at zero, which the non-profit footing requires.

Multi-word units resolve **before** roles are assigned. This ordering is the whole reason
`09-hard.json` exists: read left to right, *looked after his sister* gives a verb plus a
preposition and a plausible picture of someone standing behind a girl, and nothing in the
output signals the error.

The rules that decide who acts and who is acted on live in
[parser/patterns.py](parser/patterns.py) as declarative dependency patterns, not as
control flow. Each names the construction it matches, what it assigns and why, so the
rule set can be reviewed by someone who is not reading the parser — which matters for an
open project where the linguistic knowledge should be auditable. They are tested on their
own in `tools/test_patterns.py`, and they are load-bearing: disabling them drops scene
correct from 62/62 to 49/62.

One limitation is stated rather than hidden. `DependencyMatcher` has no operator for
"this child is absent", so the rule that separates *put on your coat* from *put the box on
the shelf* carries an explicit guard. The pattern says what to look for; the guard says
what rules it out. That is the honest shape of the knowledge.

**Results on the gold set: 62/62 scene correct.** Every dimension is at 100% except the
discourse relations that no word marks.

**That number is coverage of the tuning set, not a measure of the parser.** The rules were
written against these 62 sentences, so it says the rules cover them and nothing more. The
honest evidence is elsewhere:

- 19 behavioural tests in `tools/test_parser.py` run on sentences outside the gold set.
- A held-out probe of 12 unseen sentences scored 11 correct and found one real
  generalisation bug: `put on` fired as a phrasal verb in *put this box on the shelf*, so
  the shelf became the thing being put. A particle is always part of the verb, but a
  preposition only is when the verb has no object of its own. Fixed and locked in.

The remaining gap is deliberate. Four gold relations are inferred rather than marked —
the causal link in `g039` is supplied by the reader, not by any word — and the parser does
not emit them. Asserting a relation the text does not mark would put an inference into the
data. The schema now carries `inferred` on discourse relations so the harness can hold
those apart, which turned a parser "failure" into an honest zero on a category it was
never able to reach.

## Symbols and images

**Nothing fetches images yet.** The only network code is `tools/check_coverage.py`, and it
fetches metadata to answer one question: does a symbol for this word exist. It caches JSON
under `lexicon/.arasaac-cache/`. No image has been downloaded.

The chain is `concept id` → **lexicon (not built)** → `pictogram id` → image URL. The
middle link is the gap. `lexicon/arasaac-coverage-gold.json` happens to hold concept-to-id
pairs, but that is a by-product of measurement and nothing reads it.

Two endpoints, both verified:

```bash
curl -o dog.png "https://static.arasaac.org/pictograms/7202/7202_500.png"
```

```bash
curl -o dogs.png "https://api.arasaac.org/v1/pictograms/7202?plural=true&action=past"
```

The static CDN serves sizes 500 and 2500. The API takes rendering parameters, and several
map directly onto fields the scene graph already carries:

| Parameter | Scene graph field |
|---|---|
| `plural=true` | `number: pl` |
| `action=past` / `action=future` | `tense` |
| `color=false` | greyscale, for printing and colouring in |
| `skin`, `hair` | the personalisation hook |

Each returns genuinely different image bytes, so ARASAAC renders those markers server
side. That makes the strip renderer mostly URL construction from graph fields rather than
image manipulation — considerably cheaper than assumed. The `skin` and `hair` parameters
were only tried on an animal pictogram, where they have nothing to change, so test those
on a person before relying on them.

Two constraints when this gets built: every export needs ARASAAC attribution under
CC BY-NC-SA, and an ARASAAC symbol cannot be composited with a Mulberry one in a single
image.

## Next

**A second held-out set**, drawn at a different stride from the same corpora and annotated
at `0.3.0` before the parser touches it. `tools/sample_holdout.py` does the drawing. This
is the only thing that will produce a number worth quoting, and everything below it is
guesswork until it exists.

Expect it to land well below the tuning set again, and expect the gap to be smaller than
21-to-100. If it is not smaller, the class fixes did not generalise and the approach needs
rethinking rather than more rules.

After that, the lexicon layer and the strip renderer.

After that, the lexicon layer and the strip renderer. The lexicon is a concept-to-pictogram
map with provenance; the renderer is largely URL construction, given what the ARASAAC
parameters already do.

Art commissioning is still not urgent. ARASAAC covers the vocabulary well enough to build
and test the whole pipeline first, and the custom rigged set is only needed when scene
composition starts — which is after the graph has been proven against real classroom text.
