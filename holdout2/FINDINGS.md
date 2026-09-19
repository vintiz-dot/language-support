# Held-out set two

**23% scene correct.** Set one was 21%.

Last session I wrote down what would count as success, so that it could fail:

> Expect it to land well below the tuning set again, and expect the gap to be smaller than
> 21-to-100. If it is not smaller, the class fixes did not generalise and the approach needs
> rethinking rather than more rules.

**The gap is not smaller.** 23-to-100 against 21-to-100 is the same gap. The prediction
failed on its own terms, and the rest of this document is written on that basis rather
than around it.

## Method

Same corpus as set one, McGuffey's First and Second Eclectic Readers. Set one's sentences
were removed from the candidate pool first, then the same stride applied to the remainder,
so the two sets are disjoint by construction rather than by arithmetic. `tools/sample_holdout.py --set 2`
reproduces the draw.

Two of the 50 were dropped on structural grounds recorded in `excluded.json`: a byline, and
a verse line whose subject is on the previous line. Neither was dropped for being hard.

The remaining 48 were annotated by hand at schema `0.3.0`, validated, and hashed into
`LOCK.json` **before the parser was run on any of them**. The parser was then run once and
scored once. The tokeniser was used during annotation to fix token indices, which is not
parsing.

**Where this is not clean:** the same person wrote the parser and the annotations, so the
annotator is not independent. Sentence selection is independent, which is the main
protection. At 48 sentences the headline carries roughly ±6%, so 23% and 21% are not
distinguishable from each other in any case.

## The two numbers

| | tuning (77) | set one (47) | set two (48) |
|---|---|---|---|
| scene correct | 100% | 21% | **23%** |
| core correct | 100% | 36%* | **38%** |
| entity precision / recall | 100% / 100% | 80% / 86% | 84% / 89% |
| roles given right entities | 100% | 76% | 80% |
| spatial relation | 100% | 58% | 73% |
| discourse (marked) | 100% | 25% | 29% |
| argument swaps | 0 | 0 | **0** |

\* set one re-scored with the current parser, which was fixed against its failure classes,
so that cell flatters the parser. Set two's 38% is the clean one.

**Core correct** counts only what changes the picture: entity concepts, predicates, role
assignment and polarity. Who, what, doing what to whom, and whether it happened. It ignores
definiteness, aspect, alignment spans and discourse. It reads 100% on the tuning set, so it
is not a weaker metric smuggled in to look better — it is the same bar on fewer fields.

That 38% against 23% is the most useful thing here. **Scene correct is a conjunction over
roughly ten fields per graph, so it is dominated by graph length**, and a graph can lose it
on a definite article. More than a third of these sentences produce a picture that is right
about who did what.

## Why the headline did not move

The components all improved, and the conjunction did not:

Entity recall went 86% → 89%, roles given right entities 76% → 80%, spatial relation
58% → 73%. Every one of those is a real gain from last session's class fixes, and none of
them is large enough to survive being multiplied together eight times. At 89% entity
recall, a graph with four entities is fully right on entities alone about 63% of the time.

So the class fixes **did** generalise — just not enough to clear an all-or-nothing bar.
That is a different conclusion from "the approach is wrong", and it is the one the evidence
supports. What it rules out is expecting the headline to move by fixing another handful of
classes.

## The schema, again

**40% of these sentences contain something `0.3.0` cannot express.** Set one's figure for
`0.2.0` was also 40%.

That looks like no progress and is not. Every gap set one found is closed, and none of them
recurred: vocatives, manner, frequency, groundless direction, comitative, relative clauses,
second spatial phrases, exclamative, equative and `would` all annotate cleanly now. The new
40% is a different and more peripheral set:

| Missing | Seen in | Example |
|---|---|---|
| Focus and additive particles | j005, j010, j029, j035 | *too*, *only one queen*, *instead* |
| Measure phrases on an attribute | j039, j025 | *seven years old*, *a long time* |
| Verse fragment with no matrix clause | j023, j033, j042, j046 | *Till the sun is in the sky.* |
| Coordinated noun phrases | j019, j046 | *the rabbits and their little master* |
| Modifiers on `setting.time` | j043, j006 | *One cold, windy night* |
| Interval frequency | j032 | *every day*, which `always` overstates |
| Apposition | j024 | *We ... you and I* |
| Reaction adjunct | j034 | *to the delight of all* |
| Distance predicate taking a ground | j017 | *not far from home* |
| A role for the target of a feeling | j045 | *offended with me* |

Two of these are worth acting on and the rest are not. **Coordinated noun phrases** are
ordinary Grade 1–2 English and currently become duplicate events sharing a verb token,
which is a workaround. **Focus particles** change what the sentence claims — *only one
queen can live in each hive* becomes *a queen can live in each hive*, which is a different
and wrong fact. The verse fragments are an artefact of drawing from nineteenth-century
readers and would not appear in modern classroom text.

`j039` deserves its own line. *Ralph Wick was seven years old* loses *seven years* and what
survives asserts that a seven-year-old was **old**. That is not lossy, it is inverted, and
it is the exact failure mode this project exists to prevent — it just arrives through a
missing field rather than a reversed role.

## What the parser gets wrong

139 individual failures across 37 graphs:

| Class | Graphs |
|---|---|
| Entity head, boundary or concept | 20 |
| Role assignment | 17 |
| Spatial figure | 8 |
| Predicate, mostly unresolved idioms | 8 |
| Preposition consumed twice | 7 |
| Discourse relation not recovered | 5 |
| Non-finite clause given finite features | 3 |
| Exclamative mood missed | 3 |
| Imperative mood missed | 1 |

**Preposition consumed twice** is new, cheap to fix, and costs more than its rank suggests.
When a verb absorbs its preposition, the preposition is still also read as a spatial
relation: *look at the man* yields the predicate `look-at` **and** a spatial `at`; *drive
off other birds* yields `drive` plus a spurious `off`; *listen to*, *put in order* and
*left to* all do the same. Seven graphs, and for two of them it is the only remaining
error. One rule — a preposition already spent on the predicate cannot also be a relation —
should clear it.

**Idioms are not resolved at all.** *take care of*, *put in order* and *make fun of* come
out as `take`, `put` and `make`, with `care`, `order` and `fun` as spurious entities. The
lexicon knows `look-after`; it does not know these. This is a vocabulary list, not an
algorithm.

**Exclamatives are only found when fronted.** *How fine he looks!* works. *He levies a
tax!*, *Her kisses will wake you instead!* and *And the voices shrill!* all read as
declarative. Mood currently keys on a fronted *how*/*what* and the parser never falls back
to the exclamation mark.

## The one that the metric missed

**Argument swaps: 0, on all three sets.** That still holds, and it is still the thing that
matters most.

But `j047` — *Ellet told George to go and look in his cap* — makes **Ellet** the one who
looks. The agent of the embedded clause should be George. The swap counter did not catch it
because it counts agent and patient inverted **within one event**, and this is the wrong
participant carried across a control verb into another event.

So the headline claim needs narrowing: the parser does not reverse who acted on whom inside
a clause, and it can still attach the wrong person to an embedded one. The metric was
measuring something narrower than I have been describing. Control-verb subject assignment
should be counted separately, and will be before any number from this is quoted again.

## Two annotation errors, mine

Recorded because a locked set that is quietly wrong is worse than one that is openly wrong,
and neither was corrected after scoring.

`j010` and `j018` annotate *look at* as the predicate `look` with a `theme`. The project's
own lexicon maps `("look", "at")` to `look-at`, and `g050` uses `look-after` with a
`patient`. My annotation contradicted the established convention and the parser was right.
Re-scoring against a corrected scratch copy leaves the headline at 23%, because both graphs
still fail on the spurious spatial described above.

`j029` omits `gender` on *queen*, which is lexically female and which the parser supplied
correctly.

## What this changes

Not the schema. `0.3.0` holds ordinary classroom English, and the remaining gaps are either
peripheral or artefacts of nineteenth-century verse. Coordinated noun phrases and focus
particles are the only two worth a `0.4.0`, and neither is urgent.

Not the approach either. Zero in-clause argument swaps across 105 role assignments here
and 109 on set one is the result this design was built for, and it held on a set drawn after the
parser was finished.

What changes is the headline metric. **Scene correct should stop being the number quoted.**
It is an all-or-nothing conjunction that a definite article can sink, it barely moves when
every component improves, and it will keep reading in the twenties while the system is
getting steadily better at the thing it is for. Core correct, at 38%, measures whether the
picture would be right. That is the number to carry forward, alongside the swap count and
a new control-subject count.

The cheap parser work, in order of cost to benefit: the doubled preposition, the idiom
list, exclamative fallback, and control-verb subjects. None of it needs a model, and none
of it should be tuned against this set, which is now spent.
