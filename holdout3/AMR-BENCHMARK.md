# AMR benchmark

**On unseen text the rule parser and a trained AMR parser are dead level: 17 of 27 events
each.** On the tuning set the rule parser wins 100% to 72%, which is what a set the rules
were written against is supposed to look like and is not evidence of anything.

## The question

Not "should AMR replace this". It cannot: AMR deliberately discards number, definiteness
and tense, and has no figure/ground, so it cannot be the target representation for a system
whose output is a picture. The question is narrower — **on who did what to whom, the one
dimension a trained parser is most likely to win, does it?**

## Setup

`amrlib` 0.8.1 with `parse_xfm_bart_base` (82.3 SMATCH, 516 MB, md5 verified), CPU
inference. The large model is 83.7 SMATCH; the 1.4-point difference does not decide
anything below.

Both systems are judged by the same crude yardstick, which is what makes the comparison fair
despite the yardstick being poor: for every gold event with a doer and a done-to, is the
same pair of concepts in the same two slots? AMR's `:ARG0` is read as the doer and `:ARG1`
as the done-to. Copular clauses are skipped, because gold writes them as `be.attribute` and
AMR does not write them as predicates at all.

**The first run of this benchmark was wrong and reported AMR at 55%.** The yardstick was
counting notation as disagreement: PropBank sense suffixes (`credit-01`), unlemmatised
plurals (`burs`), AMR's `and` node for a coordinated argument, and `amr-unknown` for the gap
in a wh-question. Fixing those moved AMR from 55% to 85% without touching either parser. It
is recorded here because a benchmark that flatters the home team by accident is worse than
no benchmark.

## Results

Held out set three, 47 sentences, 27 events with both roles:

| | predicate found | both roles right | reversed |
|---|---|---|---|
| rule parser | 18/27 (67%) | 17/18 (**94%**) | 0 |
| amrlib | 20/27 (**74%**) | 17/20 (85%) | 0 |

End to end both get **17 of 27**, or 63%.

Tuning set, 87 sentences, 29 events with both roles:

| | predicate found | both roles right | reversed |
|---|---|---|---|
| rule parser | 29/29 (100%) | 29/29 (100%) | 0 |
| amrlib | 27/29 (93%) | 21/27 (78%) | 0 |

The control matters: the rule parser's total dominance on the data it was built for vanishes
completely on data it has not seen. That gap is the entire reason held-out sets exist.

## The profiles differ, which is the interesting part

They arrive at the same 17 by opposite routes.

**AMR has better coverage.** It finds 74% of the predicates against 67% — it gets a handle on
sentences where the rule parser produces nothing, including some of the five where spaCy's
tagger reads the verb as a noun.

**The rules are more precise when they fire.** 94% against 85% on the predicates each one
finds. A rule that matches has been written deliberately; a model that generalises has
guessed.

**Neither reverses arguments.** Zero on both, on both sets. The failure this whole design
exists to prevent is not one an AMR parser introduces either.

## What AMR still gets wrong here

Three disagreements on set three, and only one is an error:

- `k042` *throw it* — AMR makes the thrown thing `credit-01`, carried over from the previous
  clause. A real mistake.
- `k031` *see the rain falling* — AMR says what is seen is the falling, gold says the rain.
  **AMR is arguably more correct than the annotation.**
- `k012` *found a piece of bread* — AMR says `piece`, gold says `bread`.

That last one deserves its own line. **The rule parser also says `piece`.** Two systems
sharing no lineage agree against the gold, which is the strongest available signal that the
annotation is the outlier and the partitive convention needs revisiting. It is exactly the
cross-check that was proposed as a way to catch annotator slips, and it caught one on its
first outing.

## What this changes

**Not the schema, and not a replacement.** 63% against 63% is not a reason to throw away a
deterministic, locally-runnable, zero-marginal-cost parser for a 516 MB model, on a project
whose non-profit footing requires cost per sentence to trend to zero.

**It does make the hybrid concrete rather than speculative.** The two systems fail in
different places: AMR covers more, rules are more precise, and the fields AMR throws away —
number, definiteness, tense — are exactly the ones spaCy already recovers for free. An
ensemble that takes AMR's predicate-argument structure where the rules find nothing, and
keeps the rules where they fire, would plausibly beat both. That is now a measurable claim
rather than an argument.

**And it sharpens the confidence question.** The rule parser's 94% precision on what it finds
is the more useful property for a teacher-first product than AMR's 74% coverage. A system
that draws only what it is sure about and flags the rest needs precision, not recall. The
rules already have it; nothing currently reads it.

## Reproducing

```bash
pip install amrlib penman unidecode
```

Then download `model_parse_xfm_bart_base` from the `amrlib-models` releases into
`amrlib/data/model_stog`, and:

```bash
python tools/benchmark_amr.py holdout3/gold
```

`unidecode` is a real dependency of amrlib that amrlib does not declare, so the import fails
without it. None of this is in `requirements.txt`: it is a benchmark dependency, not a
runtime one, and nothing in the rendering path should ever need a 516 MB model.

---

# The hybrid, built

`parser/amr_bridge.py` turns an AMR graph into scene graph nodes; `parse(text, tokens,
fallback=...)` consults it **only when the rules produce no events at all**. The design
follows from the benchmark above rather than from taste: the rules are the more precise of
the two, so AMR fills gaps and never overrides one.

Nothing in `parser/` imports amrlib at module level and nothing is added to
`requirements.txt`. `parse` takes a plain callable, so anything that turns a sentence into
penman will do — a hosted service, a cached table, a different parser entirely. The
rendering path must never need a 516 MB model.

## What it fixed

| Held-out set three | rules alone | hybrid |
|---|---|---|
| graphs with no events at all | **5** | **0** |
| schema or reference violations | 5 | 0 |
| entity recall | 80% | 82% |
| entity precision | 83% | 80% |
| scene correct | 6% | 6% |
| core correct | 11% | 11% |

**It eliminates every blank page and does not move accuracy at all.** That is the honest
headline and it should not be dressed up.

It touched **exactly the five empty graphs and nothing else**, which is the gaps-only design
holding: there is no regression risk in turning it on, because it cannot reach a sentence the
rules already handled.

## What the five became

| | gold | hybrid |
|---|---|---|
| k011 *What cunning, little eggs!* | `exist` exclamative | **identical** |
| k013 *Twinkle, twinkle, all the night.* | `twinkle` imperative | `twinkle` declarative |
| k015 *Scatter light divine!* | `scatter` imperative | `exist` exclamative |
| k032 *What ugly, gray streaks...* | one `exist` | two `be.attribute` |
| k045 *Have you no playthings?* | `have` interrogative | `exist` interrogative |

`k013` is the case the fallback was built for: spaCy tags *Twinkle* as a noun, so the rules
have no verbal root and produce nothing, and AMR recovers the verb. It still gets the mood
wrong, because with no verb tag there is no signal for an imperative and the sentence ends in
a full stop.

`k015` is AMR failing on its own terms — it hallucinates a concept called `atter` — and the
bridge cannot rescue a bad graph.

`k011` is worth its own line. The hybrid's graph is **byte-identical to the annotation** on
entities and events, and it still did not score as correct, because the invented `exist`
predicate had no alignment span and a node with no span can never be matched. Giving synthetic
events the fronted *What* or *How* as their span takes the hybrid to **9% scene correct and
13% core correct** — but that change was made after seeing these results, so those two
numbers are a diagnostic and the measurement stands at 6% and 11%.

## What it cost

Two bugs surfaced while wiring it up, both older than the hybrid:

**The parser was declaring `schema_version: "0.2.0"` while emitting `members`, `focus` and
`measure`** — two schema releases of drift. It was never caught because the only gate on
parser output was the referential checker, not the schema itself. The version is now read
from the schema file so it cannot drift again, and `run_parser.py` validates against the
schema as well.

## What it does not do

It does not raise accuracy, and nothing here suggests that a better AMR model would. The two
parsers agree on 17 of 27 events; where they disagree, they disagree for different reasons,
and averaging two systems that are each right about two thirds of the time does not produce
one that is right about all of it.

What it buys is that **a sentence the system cannot parse now produces a flagged
approximation instead of nothing**. For a teacher-first product that is the difference
between a blank page and a card that says *check this one* — which is a product decision, not
an accuracy one.
