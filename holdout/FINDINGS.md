# Held-out results

**21% scene correct, against 100% on the tuning set.**

That gap is the whole point of the exercise. The 100% was always coverage of the 62
sentences the rules were written against; this is the first number that says anything
about the system.

| | tuning set (62) | held out (47) |
|---|---|---|
| scene correct | 100% | **21%** |
| entity precision / recall | 100% / 100% | 80% / 86% |
| roles given right entities | 100% | 76% |
| spatial relation | 100% | 58% |
| discourse (marked) | 100% | 25% |
| argument swaps | 0 | **0** |

## Method

Sentences came from McGuffey's First and Second Eclectic Readers via Project Gutenberg —
genuine Grade 1–2 material that nobody here wrote. 516 candidates passed a shape filter
(4–12 tokens, no digits, no dialogue), then 50 were taken at a fixed stride.

**Correction, made while drawing set two:** `tools/sample_holdout.py` no longer reproduces
these 50. The sentence splitter was changed after this set was drawn, and the current code
finds 485 candidates rather than 516 and redraws only 8 of the 50. The set itself is intact
— the sentences are in `sentences.json` and the annotations are hashed — but the claim that
it can be regenerated was true when written and is not true now. Set two is therefore made
disjoint by comparing sentence text rather than by index arithmetic.

Three were dropped before any annotation, on structural grounds recorded in
`excluded.json`: a byline, a sentence the splitter cut at "Mr.", and a greeting with no
predicate. None was dropped for looking difficult.

The remaining 47 were annotated by hand, validated against the schema, and hashed into
`LOCK.json` **before** the parser was run on any of them. Scored once.

**Where this is not clean:** the same person wrote the parser and the annotations, so this
is not an independent annotator. Sentence selection was independent, which is the main
protection, but annotation choices on ambiguous cases are not. McGuffey is also
nineteenth century, so vocabulary skews older than a modern classroom and unseen-word
failures are somewhat inflated. At 47 sentences the headline carries roughly ±6%.

## Two bottlenecks, not one

| | graphs | scene correct |
|---|---|---|
| Sentences the schema can fully hold | 28 | 29% |
| Sentences with something the schema cannot express | 19 | 11% |

**40% of real sentences contained something schema `0.2.0` cannot represent at all.** That
was not visible from the tuning set, because the tuning set was written by someone who
knew what the schema could hold.

And even on the 28 sentences the schema handles, the parser only gets 29% completely
right. Both layers are genuinely short. Fixing either alone will not move the headline
much.

## What the schema cannot hold

Counted across the 19 affected sentences, most frequent first:

| Missing | Seen in | Example |
|---|---|---|
| Vocatives | h010, h012, h015, h045 | *Did you call us, mamma?* |
| A second spatial phrase on one event | h007, h050 | *up on the bank, under the rock* |
| Direction with no ground | h021, h033, h037 | *fall down*, *went along*, *Away they marched* |
| Manner adverbs | h005, h033 | *sit still*, *went slowly* |
| Frequency and continuation | h029, h044, h049 | *always*, *never*, *still felt sad* |
| Comitative | h022, h029 | *take dinner with us* |
| Simultaneity between events | h033, h037 | *went along, reading a book* |
| Relative clauses | h031, h034 | *a house that is called a hive* |
| Containment between entities | h026, h046 | *a basket of fine apples* |
| Nominal predication | h041 | *was a great storyteller* — *great* has nowhere to go |
| Exclamative mood | h011 | *How fine he looks!* |
| Equative degree | h014 | *as blue as it can be* |
| `would` | h032 | not a value in the modality enum |

Several of these were already on the known-gaps list from the Dolch run — frequency,
degree, speech acts — which is corroboration rather than surprise. The new ones are
vocatives, second spatial phrases, groundless directions, relative clauses and
simultaneity, and they are frequent enough in real text to matter.

## What the parser gets wrong

122 individual failures across 37 graphs:

| Cause | Errors | Graphs |
|---|---|---|
| Role assignment | 37 | 25 |
| Entity boundary or head | 34 | 20 |
| Non-finite clause given finite features | 15 | 5 |
| Other features | 12 | 9 |
| Discourse not recovered | 6 | 6 |
| Spatial figure | 5 | 4 |
| Spatial relation or ground | 4 | 2 |
| Clause splitting | 4 | 4 |
| Mood | 3 | 3 |
| Predicate | 2 | 2 |

The clusters worth naming:

**Noun-phrase heads.** The parser takes the determiner or quantifier as the head in
*some of the crackers*, *what this meant*, *more than it needs*, *lend mine*. Each
produces a nonsense concept (`some`, `this`, `more`, `mine`) and loses the real one.

**Non-finite clauses.** The parser only recognises `xcomp`. Purpose infinitives
(*milk to drink*), perception complements (*see that boy fall*) and participials
(*reading a book*) get full tense, polarity and mood, which asserts things the text does
not.

**Spatial figure.** Assigned to the agent when it should be the thing moved —
*a pen in his hand*, *hitches Sport to this wagon*.

**Coordinated adjectives.** *green and fresh*, *very patient and kind* produce one event
where the annotation has two, so half the description is dropped.

**Mood from punctuation.** *Will you take dinner with us.* reads as a statement because
of a typo in the source, and the verse imperative ending in a question mark reads as a
question.

## The one thing that held

**Zero argument swaps, on both sets.** Where the parser identified the participants, it
never reversed who acted on whom. That is the failure this whole design exists to
prevent — the confident wrong picture that teaches a child the opposite of the sentence —
and it did not happen once in 109 role assignments on unseen text.

Roles given right entities at 76% says the same thing more quietly: when the parser knows
what the things are, it usually knows what they are doing. The entity layer is the weaker
one.

## What this changes

The plan said: above 55%, continue with rules; below 40%, bring the language-model escape
hatch forward. That gate was wrong, because it assumed the parser was the only variable.

An LLM would not have helped on 40% of these sentences, because the target representation
cannot hold the content whatever produces it. **Schema `0.3.0` comes before any more
parser work**, and it should be driven by the table above rather than by invention.

The parser work that follows is mostly unglamorous and mostly not about roles: noun-phrase
head selection, non-finite clause detection, coordination, and spatial figure. None of it
needs a model.

---

## Addendum: after the parser work

The 21% above is the record of what was measured, and it stands. What follows is a
diagnostic, not a second measurement.

The failure classes named above were fixed generally, verified by 26 tests on sentences
belonging to neither set (`tools/test_parser_coverage.py`), with the tuning set going from
67/77 to 77/77. Re-running this held-out set then moved scene correct from 21% to 23%.

**That comparison is not valid, for two independent reasons.**

First, the fixes were informed by this set's failure taxonomy. Even applied as classes
rather than sentence by sentence, the set is spent as a clean measurement.

Second, and more decisively: these annotations are locked at schema `0.2.0`, and the
parser now emits `0.3.0`. Where `0.2.0` could not express a vocative or a manner adverb,
the annotation deliberately omits it — so the parser correctly producing `address` or
`manner` now scores as an error. A third of the remaining failures (12 of 36 graphs) are
this mismatch rather than anything wrong with the parse.

The sub-metrics that are still comparable did move:

| | 21% run | now |
|---|---|---|
| Entity recall | 86% | 93% |
| Roles given right entities | 76% | 81% |
| Argument swaps | 0 | 0 |

**This set can no longer measure this parser.** The right next step is a fresh draw from
the same corpora at a different stride, annotated at `0.3.0` before the parser is run on
it. Nothing else will produce a number worth quoting.
