# Can the parser tell when it is wrong?

**No. Not usefully.** This was the highest-value unbuilt thing in the project by my own
argument, and measuring it killed it. The finding is worth more than the feature would have
been, so it is written down rather than quietly dropped.

## The argument that led here

The project is teacher-first, so it does not need to be right about every sentence — it
needs to know when it is not. At 11% core correct a renderer that draws everything is
unusable; one that draws what it is confident about and flags the rest is a product. That
reframing turned the open question from *how do we raise 11%* into *what can be read off a
parse, without the answer, that says this one is safe to draw*.

The `review` flag machinery has existed since `0.2.0` and nothing read it. The editor now
does. So the remaining step was to find the threshold.

## What was measured

`tools/confidence.py` computes nine properties of a predicted graph, all of them readable
without the gold annotation — because at render time there is no gold annotation. It then
asks, for each one, what withholding on it would buy: how much of the set still gets drawn,
and how often the drawn part is right.

Pooled over held-out sets two and three, 95 graphs, 23 core correct (24%):

| signal | raised on | correct when raised | withhold → draws | right |
|---|---|---|---|---|
| no events at all | 5 | **0/5** | 95% | 26% |
| a review flag | 10 | **0/10** | 89% | 27% |
| an event with no roles | 5 | **0/5** | 95% | 26% |
| coordination | 5 | **0/5** | 95% | 26% |
| a content word with no picture | 28 | 3/28 | 71% | 30% |
| a discourse relation | 15 | 2/15 | 84% | 26% |
| more than one event | 37 | 4/37 | 61% | **33%** |
| over 8 words | 50 | 10/50 | 47% | 29% |
| a concept the lexicon lacks | 68 | 18/68 | 28% | 19% |

## The result

**Four signals are perfectly precise and almost never fire.** No events, a review flag, an
event with no roles, and coordination each mark failure without a single exception across 95
graphs — but between them they cover a handful of sentences. Precision without mass buys
nothing.

**The one signal with mass is weak.** Withholding on multi-event sentences draws 61% of the
set and is right 33% of the time, against a 24% base rate. Nine points. A teacher handed a
set where two in three cards are still wrong has not been helped.

**Two signals point the wrong way.** Longer sentences and sentences using concepts the
lexicon lacks are *more* likely to be right, not less. That is an artifact rather than a
discovery: the short sentences in these sets are the odd ones — exclamatives, fragments,
*Twinkle, twinkle* — and those are exactly what defeats the parser. It is a warning about
reading any of these rates too closely.

**The ceiling is about 33% precision at 61% coverage.** That is not a product. Withholding
on every signal at once leaves 3 to 6 sentences out of 95, which is not a product either.

## Why this is not simply bad news

Two things worth keeping.

**The flags are honest.** Ten graphs carried a review flag and not one of them was correct.
The flag machinery is not noise — it says something true every time it speaks. It is just
close to silent, firing on 10% of sentences. That means the fix is not to distrust the
flags; it is that the parser has no way to flag the ordinary sentence it merely got wrong.

**Coordination being 0/5 is not a contradiction.** Set three's findings record that
coordination was handled correctly 5 times out of 5. Both are true: the coordination was
right and the graph was still wrong somewhere else. That is what a conjunction over every
node does to a long sentence, and it is the clearest illustration available of why
`core correct` had to be separated from `scene correct` and why neither can be raised by
fixing one construction.

## What it changes

**The teacher is the confidence threshold.** That is not a consolation prize, it is the
design the project already committed to. The editor shows the parse laid over the words, so
a wrong picture sits over the wrong word and is visible in one glance; the teacher fixes it
in one click. An automatic threshold would have let the system draw a set unsupervised, and
the measurement says it cannot, so the teacher-first framing is not a constraint being
worked around — it is the thing carrying the product.

So the next work is **not** a threshold. It is the rest of the teacher loop: approve a
sentence, save a set, and let a student read an approved set. Those are the steps that turn
a parse a teacher has corrected into something a child can use, and none of them depend on
the parser getting better.

The parser should still get better. But it should get better because sentences are wrong,
not because a threshold is waiting on it.

## Reproducing

```bash
python tools/confidence.py holdout3/predictions.json holdout3/gold
```

```bash
python tools/confidence.py holdout2/predictions.json holdout2/gold
```

**These are diagnostics, not measurements.** All three held-out sets are spent, so any
threshold chosen on these numbers is fitted to the set it was chosen on. The tool reports
each set separately so a signal that works on only one is visible as such — *more than one
event* lifts set two from 38% to 47% and does nothing at all on set three, which is exactly
the pattern a fitted signal shows. Confirming any of this needs a fresh draw, and a fresh
draw is not worth spending until something has changed that it would measure.
