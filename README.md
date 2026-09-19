# Language support — scene graph schema and gold set

Renders sentences as pictures for ESL Grade 1–3 readers. This repository holds the meaning
representation, the annotated examples it is tested against, a rule parser that produces
it, and a scoring harness. No renderer yet, and no images are fetched yet: the schema had
to survive contact with real sentences first, and now the parser has to.

The bet is that a picture should show **who does what to whom**, not a row of symbols
substituted word for word. Word substitution cannot distinguish `g001` from `g001b`
in [gold/01-patterns.json](gold/01-patterns.json), which are the same words in a
different order and mean opposite things.

## Where this is

| Phase | | State |
|---|---|---|
| 1 | **Meaning layer** — schema, gold set, scoring harness, rule parser, held-out measurement | Done. The measurement is spent; see below. |
| 1b | **Second held-out set**, annotated at `0.3.0` before the parser sees it | Done. 23% scene correct, 38% core correct. |
| 1c | **Third held-out set spanning Grade 3**, after the target widened from 1-2 to 1-3 | Done. **6% scene correct, 11% core correct.** |
| 1d | **Parser fixes** the second set called for | Done. |
| 1e | **Schema `0.4.0`** — coordination, focus, measure | Done, before set three is annotated rather than after. |
| 2 | **Symbol layer** — concept-to-pictogram lexicon, strip renderer | Done. First pictures. |
| 3 | **Teacher loop** — type a sentence, see the strip, edit, approve, save a set | Done. |
| 4 | **Student view** — approved sets, read only | Done. The pipeline runs end to end. |
| 5 | **Scale** — model assist where the rules fail, second symbol set, custom art | Not started |

**The pipeline runs end to end.** `python tools/serve.py` opens an editor where a teacher
types a sentence, watches the pictures appear over the words they came from, clicks any one
to change it, approves it and saves a set; `/read` opens that set for a child, one sentence
at a time, read only.

What that does **not** mean is that the parser is good. It is right about 11% of held-out
sentences, and [CONFIDENCE.md](CONFIDENCE.md) shows it cannot tell which 11%. The pipeline
is complete because the teacher is in it, not because the machine is finished.

Phase 1b was the gate, and it has been passed through rather than passed: the number is
real but low, and the headline metric turned out to be the wrong one to steer by. See
[holdout2/FINDINGS.md](holdout2/FINDINGS.md). Both held-out sets are now spent for tuning.

## Layout

| Path | What it is |
|---|---|
| `schema/scene-graph.schema.json` | The scene graph, JSON Schema 2020-12. Version `0.4.0`. |
| `schema/scene-graph-0.2.0.json` | Frozen. Held-out set one is locked against it. |
| `schema/scene-graph-0.3.0.json` | Frozen. Held-out set two is locked against it. |
| `gold/` | 87 hand-annotated scene graphs across 12 files. The tuning set. |
| `holdout/` | Set one: 47 annotated sentences, locked at `0.2.0`, scored once. |
| `holdout2/` | Set two: 48 annotated sentences, locked at `0.3.0`, scored once. |
| `holdout3/` | Set three: 47 annotated sentences across Grade 1-3, locked at `0.4.0`, scored once. |
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
| `tools/test_parser_fixes.py` | Phase 1d, on sentences belonging to no gold set. |
| `tools/test_parser_0_4_0.py` | Coordination, focus and measure, likewise. |
| `tools/annotate.py` | Scaffold, progress, validation and locking for a set being annotated by hand. |
| `tools/benchmark_amr.py` | Rule parser against an off-the-shelf AMR parser on role assignment. |
| `parser/amr_bridge.py` | Turns an AMR graph into scene graph nodes, for gaps the rules cannot fill. |
| `tools/amr_fallback.py` | The optional AMR callable `parse` accepts. Never imported by `parser/`. |
| `tools/migrate_0_4_0.py` | The 0.3.0 to 0.4.0 migration. |
| `tools/sample_holdout.py` | Draws held-out sentences. `--set 2` draws the disjoint second set. |
| `LICENSE` / `LICENSE-DATA` / `NOTICE` | Apache-2.0 for the code, CC BY 4.0 for the annotations, attributions. |
| `tools/build_lexicon.py` | Builds the concept-to-pictogram map from the cached ARASAAC searches. |
| `lexicon/concepts.json` | Generated. The lexicon: concept to pictogram, with alternatives. |
| `lexicon/overrides.json` | The teacher's own choices. Keyed by concept, so a fix applies everywhere. |
| `renderer/strip.py` | Scene graph to a strip of pictures laid over the words they came from. |
| `renderer/sets.py` | Approved sets. Approval freezes the pictures, not the sentence. |
| `sets/` | The teacher's saved sets, one readable JSON file each. |
| `tools/test_sets.py` | Approval, freezing, and that a set name cannot escape `sets/`. |
| `tools/serve.py` | The editor's local server. Standard library only, loopback only. |
| `editor/index.html` | The teacher's editor: type, watch, change a picture, approve, save. |
| `editor/read.html` | The student view. Reads a saved set; no parser, no lexicon. |
| `tools/test_serve.py` | The HTTP surface, over a real socket. |
| `tools/test_strip.py` | The rendering decisions, against gold graphs rather than the parser. |
| `tools/confidence.py` | What predicts a correct parse, from the prediction alone. See `CONFIDENCE.md`. |
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
python tools/serve.py
```

```bash
python tools/build_lexicon.py
```

```bash
python -m pytest
```

Install with `pip install -r requirements-dev.txt`, then
`python -m spacy download en_core_web_sm`. Runtime needs only `spacy` and `jsonschema`;
`pytest` is development-only, so nothing in the test stack reaches a classroom.

Current state: 87 tuning graphs and 142 held-out graphs across three sets, 0 failures, 0
warnings. 254 tests passing. 99% ARASAAC coverage on Grade 1-3 content vocabulary.

**The numbers that matter, from the third held-out set: 6% scene correct and 11% core
correct.** Core correct counts only what changes the picture — entity concepts, predicates,
roles and polarity — and reads 100% on the tuning set, so it is the same bar on fewer
fields. Scene correct is an all-or-nothing conjunction that a definite article can sink,
and it is no longer the number to steer by. Set three is the first annotated at the version the parser emits and the first drawn across
the whole Grade 1-3 band, so it is the cleanest measurement taken and by far the worst.
See [holdout3/FINDINGS.md](holdout3/FINDINGS.md).

The 100% tuning figure measures coverage of the sentences the rules were written against
and nothing more.

## Symbol coverage

Run against 309 Dolch words (pre-primer through third grade, plus the noun list).
Coverage means a returned pictogram carries the word as an **exact keyword** — ARASAAC's
search is fuzzy enough that asking for *hungry* returns food pictograms, so counting
non-empty results would badly overstate it.

**The art side is viable.** 179 of 181 words needing a symbol resolve exactly, 99%.
Widening from Grade 1-2 to Grade 1-3 added 41 service words and did not move that figure.
The two that do not resolve:

- `pull` — ARASAAC holds only compounds (*pull out*, *pull down*, *pull hair*), no bare
  form. A hypernym fallback covers it.
- `robin` — genuinely absent, and a dated US-specific entry that should not be in a
  contemporary list anyway.

**Most sight words do not need a picture at all.** Of 220 service words, only 42% are
content. 48% are carried by a scene graph field, and `spatial.relation` alone carries
18 of them — more than any other field, which is the strongest evidence that modelling
prepositions explicitly was the right call rather than an indulgence.

**Seven are still gaps at `0.3.0`, and sixteen have been closed since first measured.**
The open ones are `just`, `let`, `far`, `only`, `shall`, `start` and `together`. Two of
those — `far` and `only` — are the same gaps the second held-out set found independently,
which is the strongest signal available that they are worth a `0.4.0`.

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

`scene correct` is the fraction of sentences where every field agrees. A picture is right
or wrong as a whole, so it corresponds to something a child would see — but it is a
conjunction over everything, so a definite article or an aspect can sink a graph whose
picture would be fine, and it falls as the schema grows richer whether or not the parser
got worse. That makes it a poor thing to steer by.

`core correct` is the one to steer by: entity concepts, predicates, roles and polarity
only — who, what, doing what to whom, and whether it happened. It reads 100% on the tuning
set, so it is the same bar on fewer fields rather than an easier one.

Two failures are counted apart from the dimension they live in, because both were
invisible in the totals:

- **A wrong doer is not always an argument swap.** A swap is agent and patient inverted
  inside one event. *Mum told Sam to wash the cup* with Mum washing is not inverted — it is
  a real entity in the doer slot, borrowed from another event, and it read as a single role
  miss indistinguishable from a missing one. `wrong doer` counts it and `borrowed` counts
  the control-verb signature.
- **A relation nothing in the text marks is an invented claim.** These were scored as
  neither right nor wrong, which is part of why every *And*-initial clause carrying a
  relation from its only event **to itself** survived a full scoring run: `check_gold` had
  forbidden the shape since it was written, and the scorer had no opinion about it. Set
  two's locked predictions carry five; set three, parsed after the fix, carries none.

Running gold against itself must score 100% on every dimension. That identity check is a
permanent test, and it caught a real bug: implicit entities carry no token span, so span
matching could not reach them and they read as spurious on one side and missing on the
other.

## The parser

Rules over a spaCy dependency parse, not a model. Grade 1-3 syntax is short and regular
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

**Still nothing downloads an image.** The editor's pictures are fetched by the browser
straight from ARASAAC's CDN, so no image file is written to disk or committed here. The
only network code on this side is `tools/check_coverage.py`, which fetches metadata to
answer one question — does a symbol for this word exist — and caches the JSON under
`lexicon/.arasaac-cache/`.

The chain is `concept id` → **lexicon** → `pictogram id` → image URL, and the middle link
now exists as `lexicon/concepts.json`: 207 concepts, 197 with an exact keyword match, 5
structural, 5 where ARASAAC has nothing exact. It is generated from the cache, so a rebuild
is offline, and it is committed so a clean clone works without hitting the API.

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

## Licence

**Apache-2.0 for the code, CC BY 4.0 for the annotations, and ARASAAC's own CC BY-NC-SA
for the one file derived from it.** Three licences rather than one because this repository
is not one kind of thing, and a single code licence would misdescribe most of it.

| | | Why |
|---|---|---|
| Code — parser, scorer, renderer, tools | Apache-2.0 | Permissive, and its `NOTICE` mechanism propagates the ARASAAC attribution that has to travel with any rendered output anyway. The patent grant costs nothing and matters if this ever takes institutional or commissioned contributions. |
| Data — schema, and all 229 annotated graphs | CC BY 4.0 | A held-out set is only worth annotating if other people can measure against it. Attribution is the only condition, because attribution is the part that matters: a number reported against these sets should be traceable to the version and lock it was scored under. |
| `lexicon/concepts.json` | CC BY-NC-SA | Derived from ARASAAC's database. Not ours to relicense. |

That last row is the one worth knowing about, and it is easy to miss. It holds pictogram
ids and keywords rather than images, but it is still ARASAAC's data, so **it carries a
non-commercial restriction the rest of the repository does not.** Anything built on the
lexicon inherits it; anything built on the parser, the schema or the scoring harness does
not. Rebuilding that file against a differently-licensed symbol set is a supported move —
the concept ids in the graph never name a symbol, which is exactly what that indirection
was for.

Apache-2.0 was chosen over MIT for one concrete reason rather than a general preference:
there is third-party attribution here that must survive redistribution, and `NOTICE` is the
mechanism for that. `renderer/strip.py` also emits the attribution as a field on every
strip, so it travels with the data rather than depending on a particular page.

The copyright line reads *the language-support contributors*. Replace it with a legal name
or an organisation if you would rather it named one.

## The editor

```bash
python tools/serve.py
```

Type a sentence; the pictures appear over the words they came from; click any picture to
change it. Standard library only, bound to the loopback interface, and nothing is added to
`requirements.txt` — a classroom machine should not need a model download or an account.

**A picture belongs to a span, not to a word.** That is the whole distinction this project
exists for, and it is what the `alignment` field was always for. *look after his sister* is
one picture over two words rather than a verb symbol followed by a preposition symbol;
*the dog* is one picture over two words rather than a determiner nobody can draw. Function
words get no picture at all, because the graph carries them as fields — which is the 48% of
the Dolch list that a symbol-per-word system spends its vocabulary effort on for nothing.

Three consequences fall out of that decision rather than being designed in.

**The strip is an inspection tool.** When the parser is wrong, the picture sits over the
wrong words, so the teacher sees the mistake in the place it happened instead of being
handed a score. Given that held-out accuracy is 11%, a teacher-first product needs exactly
this more than it needs a better parser.

**The scene graph fields become URL parameters.** ARASAAC renders plural and tense server
side, so `number: pl` becomes `?plural=true` and `tense: past` becomes `?action=past`, and
the renderer is mostly URL construction. Negation is the exception: there is no parameter
for *this is denied*, so the strip draws the crossed claim itself — *The dog is not big*
shows **big** crossed out, never a small dog.

**Something finally reads the review flags.** The machinery has existed since `0.2.0` and
nothing consumed it. A cell is flagged amber when no symbol carries the word exactly, and
marked with a `?` when the parser said `parse_uncertain`. The footer counts them: *6
pictures over 13 words · 1 to check*.

Two smaller things the first run of it turned up, both fixed:

- **A span need not be contiguous.** In *Put the box on the shelf* the event owns *Put* and
  *on* with the object between them. Rendering that as one cell printed "Put on" and took
  *on* out of its place, so the strip stopped reading as the sentence. The picture now goes
  on the first stretch and the rest stay where they belong, tied back to it — which also
  gives coreference a free ride: the second *he* in *First he ate, then he slept* shows as a
  continuation of the same person rather than as a second person.
- **A teacher types words the lexicon has never seen.** The gold set is 87 sentences, not a
  vocabulary, so a missing symbol would have been unfixable the first time the editor met an
  ordinary noun. Clicking a cell with no picture runs a live ARASAAC search, cached, so it
  is asked once ever. *shelf* returns only *bookshelf*, which is flagged amber rather than
  presented as a match.

Choices are stored in `lexicon/overrides.json`, keyed by concept rather than by sentence: a
teacher who fixes *person* fixes it everywhere, which is what makes the lexicon layer worth
having. Every strip carries the ARASAAC attribution as data rather than as page furniture,
because CC BY-NC-SA requires it on every export.

### Approving and saving

**Approval freezes the pictures, not the sentence.** A saved set stores the resolved strip —
which pictogram sits over which words — rather than only the text. If it stored the text and
re-parsed on opening, a parser change or a lexicon rebuild would silently redraw a set a
teacher had already signed off, and nobody would be told. That is the same reasoning as the
hashes on the held-out sets: the record of what was agreed has to survive the thing that
produced it. `test_a_saved_set_does_not_change_when_the_lexicon_does` is the test that keeps
it true, and it is the one worth reading if any of this changes.

The scene graph is kept beside the frozen cells as provenance, so a later renderer can
compose a scene rather than a strip. It is explicitly **not** the authority for what gets
drawn; the cells are. Re-deriving pictures from the graph on load would undo the freeze.

A set is one readable JSON file under `sets/` — not a database, because a teacher should be
able to read, copy, mail or delete their own work without this project's help. The listing
carries a `to check` count, so a set that still holds a fuzzy symbol or an uncertain parse
says so before it reaches a class.

Set names become filenames, so they are reduced to a strict `[a-z0-9-]` allow-list rather
than escaped: the name arrives over HTTP, and a set called `../../etc/passwd` must not be
able to address anything outside `sets/`. The title the teacher typed is stored separately
and kept verbatim, so *Niños primero* saves as `ni-os-primero.json` and still reads back
under its own name.

### The student view

```bash
python tools/serve.py   # then /read
```

Open an approved set, one sentence at a time, large. Back and Next, or the arrow keys.
Nothing else: no editing, no typing, no settings.

It **reads a saved set and nothing else** — it never parses, never looks a concept up, and
never loads the lexicon. That is not a simplification, it is the payoff from freezing the
pictures on approval: what a child sees is exactly what the teacher approved, and there is
no path by which a parser change could alter it. A test asserts the page does not so much
as mention `/api/strip`.

**It also shows no review flags.** Whether the parser was unsure about *look after* is the
teacher's business and belongs in the editor, where it appears; putting it in front of a
child would teach them to distrust the page. The teacher-facing and student-facing views
deliberately hold different amounts of the truth.

Negation survives to full size: *Sam did not look after the dogs* draws the crossed picture
and the plural marker, which is the whole `g015` argument — a crossed claim, never its
opposite — reaching an actual reader for the first time.

## The target is Grade 1-3

It was Grade 1-2 until this was corrected, and the change is not only wording.

**Vocabulary.** The Dolch list here excluded third-grade service words as out of scope.
They are now in: 41 words, taking the list to 220 service words plus 89 nouns. ARASAAC
coverage did not move — still 99% — so the art side absorbs the wider band for free.

**The schema.** The third-grade band brought four new gaps, and two of them are the ones
the second held-out set found independently: `far` (*not far from home* — a distance
attribute that takes a ground) and `only` (a focus particle that changes what is claimed).
Two sources that share no method now point at the same two holes, which is the best
evidence available that `0.4.0` should close them.

**The held-out sets.** Sets one and two were drawn from McGuffey's First and Second
Readers, which do not reach Grade 3, so neither set spans the target any more. They stay
exactly as they are — locked, and reproducible from exactly the two books they were drawn
from — and set three adds the Third Reader, with the length filter widened from 12 tokens
to 16 because the old window would have dropped the longer sentences that make Grade 3
harder.

Set three is drawn and disjoint from both earlier sets. It is measurably harder: mean 8.5
words against 7.2, and coordination doubles from 12% of sentences to 26%. **Coordinated
noun phrases are already the workaround this schema handles worst**, so that alone predicts
a lower score than set two.

## Phase 1d: the parser fixes

Written the same way as the previous round: 25 tests on sentences belonging to no gold set,
written first and confirmed failing, so a fix that only works on the sentence that revealed
the problem does not pass. Set three is drawn but unannotated and nothing here is taken
from it.

**Two of the five were the same one-line bug.** `doc[1] is doc[1]` is `False` in spaCy —
`Token` is a proxy built fresh on each access — and two places compared tokens with `is`:

- `child is not swallowed` was meant to stop a verb's own preposition being read as a
  spatial relation as well. It never once worked. *look at the man* produced the predicate
  `look-at` **and** a spatial `at`.
- `head.head is not head` was meant to detect the root. It is true even at the root, so
  every clause opening with *And*, *But* or *Then* was given a discourse relation **from
  its only event to itself**. In Grade 1-3 text that is not a rare shape.

| Fix | What it was doing |
|---|---|
| Token identity | the two above |
| Idioms | *take care of*, *make fun of*, *put in order* read literally, leaving `care`, `fun` and `order` as things |
| Phrasal verbs | *listen to*, *drive off* and five more not recognised |
| Exclamative | only found when *how* or *what* was fronted, so *He broke the window!* read as a statement |
| Control subjects | *Mum told Sam to wash the cup* had **Mum** washing |

Idioms turned out to be two mechanisms rather than one. `IDIOMS` consumes the whole clause
and leaves no participants, which is right for *raining cats and dogs* and wrong for *take
care of your coat*, where someone is still doing it to something. `PREDICATE_IDIOMS`
replaces only the verb and lets role assignment run; `VERB_PP_IDIOMS` handles the shape
where the idiom's material is a fixed prepositional phrase and the object is an ordinary
one.

### The gate that was missing

`tools/run_parser.py` now runs every graph it produces through the same validator the gold
annotations have always been run through, and fails if any violate it.

The self-referential discourse relation was **already forbidden** — `check_gold.py` has
rejected that shape since it was written. Nothing was asking it about parser output. Adding
the check immediately surfaced a second bug of the same kind: a yes-no question marker was
being attached to the embedded clause as well as the matrix one, so *Did you see that boy
fall down?* asked about the falling too.

### What it moved

Both held-out sets are spent, so these are labelled diagnostics and not measurements.

| | before 1d | after 1d |
|---|---|---|
| set two, scene correct | 23% | **29%** |
| set two, core correct | 38% | **42%** |
| tuning set | 100% | 100% |
| tests | 121 | 146 |

Set one moves 23% to 21%, downward, which is expected: it is locked at `0.2.0`, whose mood
enum has no `exclamative`, so a parser that now gets exclamatives right scores worse
against it. That is the version mismatch already recorded in its findings, not a
regression.

## What 0.4.0 changed

Done **before** set three is annotated, not after, which is the whole point. Set one is
stranded at `0.2.0` and set two is now stranded at `0.3.0` — in both cases the parser
outgrew the schema the annotations were frozen in, so correct output scores as error. A day
of hand annotation is too expensive to strand the same way.

| Added | Answers | Evidence |
|---|---|---|
| `members` + `coordination` on an entity | Coordinated noun phrases. The role points at the group. | held out j019, j046; 26% of set three |
| `focus` on an event | `only`, `just`, `even`, `too`, `also` | held out j005, j010, j029; Dolch `just`, `only` |
| `measure` on an event | *seven years old*, *two metres high* | held out j039 |

Each meets the bar `0.3.0` set for itself: answer a specific held-out sentence, and leave
the gap open where the evidence was one sentence and the construction was not basic. What
stayed open is listed in `holdout3/ANNOTATING.md` so the annotator does not try to force it.

**Coordination is the one that changes meaning rather than detail.** *Tom and Ben are
friends* is not Tom being a friend and Ben being a friend, and the `0.3.0` workaround of
duplicating the event asserted the wrong thing rather than merely a clumsy thing. `focus` is
the same argument on a smaller scale: *only the dog barked* and *the dog barked* are
different claims, and a picture that cannot tell them apart is showing a different sentence.

`measure` exists because dropping it inverts rather than loses. *Ralph Wick was seven years
old* reduced to *Ralph was old*.

The migration is additive, so `tools/migrate_0_4_0.py` is a version bump. The held-out sets
were deliberately not migrated. `gold/12-coordination.json` holds ten worked examples, and
the parser scores 87/87 on the tuning set with coordination, focus and measure all at 100%.

## Annotating a held-out set

`tools/annotate.py` scaffolds a drawn set into stubs carrying id, text and tokens, shows one
sentence at a time with its token indices, reports progress, validates what is finished, and
refuses to lock while anything is unfinished or failing.

```bash
python tools/annotate.py scaffold
```

```bash
python tools/annotate.py show k004
```

```bash
python tools/annotate.py status
```

```bash
python tools/annotate.py lock
```

`holdout3/ANNOTATING.md` is the conventions: concept naming, the `located` versus `spatial`
distinction, which preposition belongs to whose alignment span, what a non-finite clause may
not carry, and the list of gaps not to fight. It exists because set two turned up two
annotations that contradicted the project's own conventions, and conventions that live only
in existing files get diverged from.

## What set three changed

The earlier numbers were answering a narrower question than the one being asked. 21% and 23%
came from Grade 1-2 readers; the honest figure for the band the app actually targets is
**6%**. Three consequences, none of them about writing more rules.

**Five graphs came back empty.** spaCy's tagger reads the verb as a noun in *Twinkle,
twinkle*, *Scatter light divine* and *Have you no playthings?*, so there is no verbal root and
the parser emits nothing at all. The validation gate from phase 1d caught it the moment the
set was scored, which is the first time that gate has paid for itself. A renderer needs a
fallback for a nominal root; a blank page with no explanation is not a safe default.

**The annotation cost is a finding in its own right.** This set was meant to be annotated
independently by the project owner, which would have removed the same-annotator caveat
entirely. They found the task too specialised to do reliably after reading the full guide.
A representation a competent person cannot annotate is a usability problem, and it lands
directly on phase 3: the teacher correction interface cannot expose this schema. It has to
work in pictures and plain words.

**Refusing to draw is a feature.** The project is teacher-first by design, so the system does
not need to be right about every sentence — it needs to know when it is not. At 6% fully
correct a renderer that draws everything is unusable; one that draws what it is confident
about and flags the rest is a product. The `review` flag machinery exists and nothing reads
it. The next measurement is not how much 6% can be raised, but **precision at a confidence
threshold**.

Coordination was the one thing that worked as designed: right 5 times out of 5, including the
five-way subject in `k004` that `0.3.0` would have exploded into ten duplicate events.

## The AMR benchmark

**On unseen text the rule parser and a trained AMR parser are dead level: 17 of 27 events
each.** On the tuning set the rules win 100% to 72%, which is what a set the rules were
written against is supposed to look like and proves nothing.

They reach the same 17 by opposite routes. AMR finds more predicates, 74% against 67%,
including some of the sentences where spaCy's tagger defeats the rules entirely. The rules
are more precise on what they do find, 94% against 85%. Neither reverses arguments, on
either set.

That does not make AMR a replacement — it discards number, definiteness and tense, so it
cannot be the target representation, and 63% against 63% is no reason to take on a 516 MB
model in a project that needs cost per sentence to trend to zero. It does make the **hybrid**
concrete: the two fail in different places, and the fields AMR throws away are the ones spaCy
already recovers for free.

Two things worth recording. The first version of this benchmark reported AMR at 55%, because
the yardstick was counting PropBank sense suffixes and AMR's coordination nodes as wrong
answers; fixing the yardstick moved AMR 30 points without touching either parser. And on
`k012` both parsers disagree with the gold in the same way, which is the strongest available
signal that the annotation is the outlier. See
[holdout3/AMR-BENCHMARK.md](holdout3/AMR-BENCHMARK.md).

## The hybrid

`parse(text, tokens, fallback=...)` consults an AMR parser **only when the rules produce no
events at all**, because the benchmark says the rules are the more precise of the two. AMR
fills gaps and never overrides one.

```bash
python tools/run_parser.py holdout3/gold out.json --amr
```

On set three it takes graphs with no events at all from **5 to 0**, and schema violations
from 5 to 0, while **leaving accuracy exactly where it was** at 6% scene correct. It touched
precisely those five graphs and nothing else, so turning it on carries no regression risk.

That is the whole result: it does not make the parser more accurate, it stops it producing
blank pages. For a teacher-first product that is the difference between nothing and a card
saying *check this one*, which is a product decision rather than an accuracy one.

Nothing in `parser/` imports amrlib at module level and none of it is in `requirements.txt`.
`parse` takes a plain callable, so the rendering path never needs a 516 MB model.

Wiring it up surfaced an older bug worth naming: **the parser had been declaring
`schema_version: "0.2.0"` while emitting `members`, `focus` and `measure`**, two schema
releases of drift, because the only gate on its output was the referential checker and not
the schema. The version is now read from the schema file, and `run_parser.py` validates
against it.

## Can the parser tell when it is wrong?

**No, and that was worth finding out.** Withholding on every signal the parser produces
leaves a handful of sentences out of 95; the one signal with real mass lifts core correct
from 24% to 33%, which is not a product. The full table is in [CONFIDENCE.md](CONFIDENCE.md).

This was the next step by my own argument — a system that draws only what it is sure about
and flags the rest needs a threshold, and nothing read the flags. The editor gave the flags
a consumer, and then the measurement said there is no threshold to find.

Two things survive it. **The flags are honest**: ten graphs across two held-out sets carried
a review flag and not one was correct. They are not noise, they are nearly silent — the
parser has no way to flag the ordinary sentence it merely got wrong. And **coordination
scoring 0/5 is not a contradiction** of set three's finding that coordination worked 5 times
out of 5: the coordination was right and the graph was wrong elsewhere, which is the
clearest illustration available of what a conjunction over every node does to a long
sentence.

What it changes is the plan. **The teacher is the confidence threshold**, which is the
design this project already committed to rather than a fallback. A wrong picture sits over
the wrong word and is visible at a glance; a click fixes it. So the next work is the rest of
the teacher loop, not a threshold — and none of it depends on the parser improving.

## Next

Phases 1 to 4 are done and the pipeline runs end to end. That is a smaller claim than it
sounds, and the honest list of what is not done is longer than the list of what is.

**The parser is right about 11% of held-out sentences.** This is the real number and
everything else is downstream of it. It is now unblocked in a way it was not before: there
is no threshold waiting on it, no measurement owed, and a teacher-facing tool that shows
exactly where it goes wrong. It should improve because sentences are wrong, not because
something is gated on it. All three held-out sets are spent, so the next honest measurement
needs a fourth draw — and now there is finally something whose improvement it would measure.

**The lexicon holds 207 concepts, which is a gold set and not a vocabulary.** Every sentence
outside it depends on the live lookup. Building it out against the Dolch noun list and
common Grade 1-3 vocabulary is cheap and offline after the first run.

**Nothing has been used by a teacher or a child.** Every design decision here is argued from
evidence about parsing and none from evidence about classrooms. The editor was built to a
constraint set three produced — that the schema is too specialised to expose — but whether
clicking a picture is actually how a teacher wants to correct one is untested.

**Every held-out set was annotated by the same party that wrote the parser.** An independent
annotation was attempted and abandoned because the schema proved too specialised to hand
over. That caveat sits under every number in this file; see
[holdout3/FINDINGS.md](holdout3/FINDINGS.md).

**Phase 5 is untouched**: a second symbol set, custom rigged art, and model assist where the
rules fail. The AMR hybrid is the one piece of this that exists, and it raises coverage
without raising accuracy. Art commissioning is still not urgent — ARASAAC carried the whole
pipeline, which is now demonstrated rather than assumed.
