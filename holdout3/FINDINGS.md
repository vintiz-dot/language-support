# Held-out set three

**6% scene correct. 11% core correct.** Set two was 23% and 38%.

This is the cleanest measurement the project has taken and it is by far the worst result.
Those two facts are related.

## Why this one counts for more

Every previous number carried a discount. Set one is locked at schema `0.2.0` and set two at
`0.3.0`, so in both cases the parser eventually outgrew the schema its annotations were
frozen in, and correct output started scoring as error. Both were also drawn only from
McGuffey's First and Second Readers.

Set three is the first that is **annotated at the version the parser actually emits**, and
the first drawn across the band the app is actually for — Grade 1 to 3, after the target was
corrected from Grade 1–2. Nothing here is discounted for version drift.

**Where it is still not clean:** the same person wrote the parser and the annotations. The
plan was for the project owner to annotate all 50 independently, which would have removed
the caveat entirely. They started, found the task too specialised to do reliably, and handed
it back — which is itself a finding, and is recorded under *What this changes*.

## The numbers

| | tuning (87) | set one (47) | set two (48) | **set three (47)** |
|---|---|---|---|---|
| scene correct | 100% | 21% | 23% | **6%** |
| core correct | 100% | 36% | 38% | **11%** |
| entity precision / recall | 100% | 80% / 86% | 84% / 89% | **83% / 80%** |
| roles given right entities | 100% | 76% | 80% | **70%** |
| spatial relation | 100% | 58% | 73% | **71%** |
| discourse type | 100% | 25% | 29% | **37%** |
| argument swaps | 0 | 0 | 0 | **0** |

Sets one and two are not directly comparable to this one — different schema versions,
easier corpus — but the direction is unambiguous.

## What got harder

**The text.** Sets one and two came from the First and Second Readers. This one adds the
Third Reader, and the length filter was widened from 12 tokens to 16 because the old window
would have dropped exactly the sentences that make Grade 3 hard. Mean length 8.5 words
against 7.2, coordination in 26% of sentences against 12%.

**The schema, again.** 53% of these sentences contain something `0.4.0` cannot express,
against 40% for set two and 40% for set one. Every gap set two found is closed and none
recurred; the new ones are further out:

| Missing | Seen in |
|---|---|
| A cause role — *died of grief* | k039 |
| Means — *by thinking you will learn* | k038 |
| Temporal anchoring — *it was on a bright summer afternoon* | k020, k027 |
| Exclamative noun phrases with no verb at all | k011, k032 |
| Comparison of manner — *with more force than others* | k029 |
| Comparative on a modifier, with the comparand absent | k046 |
| A possessor slot for *whose* | k018 |
| Stacked intensifiers — *truly very glad* | k031 |
| Habitual past — *used to work* | k024 |
| Partitives — *a piece of bread*, *one of the boys* | k012, k047 |
| Equative with no comparand — *equally brilliant* | k035 |
| Hedged predication — *mostly white* | k021 |
| Interjections, and sentence-initial *But* and *And* | k030, k041, k043, k044 |

Two of these had to be filled by inventing a predicate that is not in the sentence: `exist`
for the exclamative noun phrases, and `belong` for *whose they are*. Those are annotator
decisions, not readings, and they are flagged in the graphs.

## Five graphs came back empty

`k011`, `k013`, `k015`, `k032` and `k045` produced **no events at all** — 11% of the set.
The validation gate added in phase 1d caught them immediately, which is the first time that
gate has paid for itself on real data.

The cause is not parser logic. spaCy's tagger reads the verb as a noun:

| Sentence | What spaCy makes the root |
|---|---|
| *Twinkle, twinkle, all the night.* | `twinkle` as a **noun** |
| *Scatter light divine!* | `divine` as a **noun** |
| *Have you no playthings?* | `playthings`, with *Have* demoted to an auxiliary |

Two of the five are genuinely verbless and needed an invented predicate in the gold as well.
The other three are ordinary imperatives and an ordinary question that the tagger got wrong.

**The parser has no fallback for a nominal root.** It emits nothing rather than degrading to
a partial graph, and nothing is not a safe default in a rendering system — it is a blank
page where a picture was expected, with no explanation attached.

## What the parser gets wrong

171 individual failures across 44 of 47 graphs:

| Class | Graphs |
|---|---|
| Entity head, boundary or concept | 24 |
| Role assignment | 23 |
| Predicate, mostly unresolved idioms | 9 |
| Discourse relation not recovered | 9 |
| Spatial figure | 7 |
| Spurious spatial relation | 6 |
| Imperative mood missed | 2 |
| Non-finite clause given finite features | 2 |

Entity recall fell to 80% from 89%, which is the sharpest single regression and drives most
of the rest: roles given the *right* entities held up much better, at 70%.

The `0.4.0` additions did what they were built for. **Coordination was right 5 times out of
5**, including the five-way subject in k004 that `0.3.0` would have exploded into ten
duplicate events. That is the one part of this run that worked as designed.

## The one that held

**Zero argument swaps, on all four sets.** Where the parser identified the participants it
never reversed who acted on whom, across 119 role assignments on the hardest text yet.

That claim is narrower than it sounds, and set two already showed why: the counter only
catches agent and patient inverted **inside one event**, not the wrong person carried across
a control verb. That count still does not exist and is still owed.

## What this changes

Three things, in order of how much they change.

**1. The earlier numbers were measuring an easier population than the app targets.** 21% and
23% came from Grade 1–2 readers. The honest figure for the actual band is 6%. Nothing was
wrong with those measurements; they were answers to a narrower question than the one being
asked.

**2. The annotation cost is itself a finding.** A representation that a competent person
cannot annotate after reading a full guide is a representation with a usability problem, not
merely a documentation problem. That has a direct consequence for the teacher-facing product:
the review-and-correct interface in phase 3 was going to expose this schema to teachers. On
this evidence it cannot, and the correction UI has to work in terms of pictures and roles in
plain words, never in terms of the graph.

**3. Refusing to draw is a feature, not a failure.** This project is teacher-first by
design: a teacher prepares and approves a set before any child sees it. That means the
system does not need to be right about every sentence — it needs to **know when it is not**.
At 6% fully correct and 11% core correct, a renderer that draws everything is unusable. A
renderer that draws the 11% it is confident about and flags the rest for a teacher is a
product. The `review` flag machinery already exists and nothing currently reads it.

The measurement to take next is therefore not "how much can we raise 6%" but **"how well
can the parser tell when it is wrong"** — precision at a confidence threshold, not accuracy
over everything.

On the parser itself, the cheap work is unchanged and still worth doing: a fallback for a
nominal root, an idiom list, and the control-subject counter. None of it will move 6% to
anything like acceptable on its own, which is the point of writing that down now rather than
after another round of rules.

The AMR option deserves the benchmark it was promised. Role assignment given the right
entities is 70% here, and that is the dimension a trained parser is most likely to beat.
Entity recall at 80% is the other half and is a different problem.
