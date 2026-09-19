# Annotating held-out set three

50 sentences, schema `0.4.0`, McGuffey's First, Second and Third Readers.

**The one rule everything else serves: annotate the sentence, not the story.** If the source
says the speaker is a duck and the sentence does not, the sentence does not. If *his* has no
antecedent in this sentence, the owner is an implicit person and nothing more. A held-out set
measures what is recoverable from the words in front of you.

**Do not run the parser on these sentences.** Not `run_parser.py`, not `parse()` in a REPL.
The whole value of this set is that the annotations were written first. `annotate.py` uses the
tokeniser only, which is not parsing.

---

## Workflow

```bash
python tools/annotate.py status
```

```bash
python tools/annotate.py show k004
```

```bash
python tools/annotate.py check
```

```bash
python tools/annotate.py lock
```

Each stub carries `"notes": "TODO"`. Anything still `TODO` is skipped by `check` and blocks
`lock`, so replace it when a graph is finished — with a real note, or `""` if there is
nothing to say. Run `check` often; it catches dangling references, bad alignment indices and
a dozen other things long before `lock` does.

---

## Excluding a sentence

Structural grounds only, **never because it looks hard**. Two tests:

- **No predicate at all.** A byline, a heading, a bare noun phrase.
- **Unrecoverable fragment.** The sentence splitter cut it mid-clause, or a verse line whose
  subject is on the previous line, so no scene graph can be built.

Archaic vocabulary, metaphor, idiom and typographical errors in the source all stay in. Set
two kept *Don not fall* with its typo, and kept *He levies a tax!* despite the vocabulary.

To exclude one, add it to `holdout3/excluded.json` with a reason, then re-run `scaffold`:

```json
[{"id": "k048", "text": "...", "source": "mcguffey-3", "reason": "a byline, not a sentence: no predicate"}]
```

---

## Entities

`concept` is a lemma, lower case, hyphenated if multiword: `dog`, `look-after`, `bat.animal`
when a sense needs discriminating. Never a symbol id — the lexicon resolves art, the graph
never names it.

| Situation | Convention |
|---|---|
| *I*, *me*, *we* | `concept: "speaker"` with `person: "1sg"` / `"1pl"` |
| *you* | `concept: "addressee"` |
| *he*, *she*, *it*, *they* | `concept: "person"` (or `"thing"` if not animate), plus `person`, `gender` |
| Any bare proper name | `concept: "person"`, `proper_name: "Fido"` — **even for animals**, unless the sentence itself says otherwise |
| First name and surname | one entity, `proper_name: "Ralph Wick"` |
| Standalone *this* / *that* | `concept: "thing"` plus `deixis` |
| *mine*, *yours* | `concept: "thing"` plus `possessor` |
| *here*, *there* | `concept: "location"`, `animacy: "place"`, plus `deixis` |
| Unrecoverable *it* / *them* | `concept: "thing"`, and say so in the notes |

`animacy` is one of `person`, `animal`, `object`, `place`, `abstract`.
`number` is `sg`, `pl` or `mass`. `definite` is *the* versus *a*.
`quantity` is an explicit count (*three girls* → `3`); `quantifier` is `some|many|few|all|no|any|every`.

`modifiers` is a list of bare concepts, or `{"concept": "big", "degree": "very"}` when the
modifier itself carries a degree. A compound noun (*kitchen clock*, *sitting room*) becomes a
modifier, because the schema has no compound.

`possessor` covers ownership **and** kinship: *the mother of the children* has `possessor`
pointing at the children.

`implicit: true` marks an entity with no words of its own — the addressee of an imperative,
the unstated owner of *his*. Implicit entities get no alignment span, and `check` will warn
about any entity that has neither.

`coref` points at an earlier mention of the same referent. Two mentions of one person get two
entities, both aligned, with the later carrying `coref`.

### Groups — new in `0.4.0`

A coordinated noun phrase is **one** entity with `members` and `coordination`, and it has no
`concept` of its own:

```json
"e3": {"members": ["e1", "e2"], "coordination": "and", "number": "pl", "animacy": "person"}
```

The **role points at the group, not at a member**. `coordination` is `"and"` or `"or"`, and
the distinction is real: *milk and water* is a different picture from *milk or water*. An
`"or"` group takes no `number`, because only one of them is involved.

This replaces the `0.3.0` workaround of duplicating the event. See `gold/12-coordination.json`
for six worked examples, including the case that forces it: *Tom and Ben are friends* is not
Tom being a friend and Ben being a friend.

### `located` versus `spatial`

*The box on the shelf is red* does not assert that the box is on the shelf — it says **which**
box. That goes on the entity:

```json
"e1": {"concept": "box", "definite": true, "located": {"relation": "on", "ground": "e2"}}
```

Only the redness is asserted. Ask: is this phrase telling me which thing, or telling me
something that happened? Which thing → `located`. Something that happened → `spatial` on the
event.

---

## Events

`predicate` is a lemma, with four reserved copulas:

| Predicate | For |
|---|---|
| `be.attribute` | *is red*, *feels safe* — with `attribute` |
| `be.located` | *is on the table*, *Where is the cat?* — with `spatial` |
| `be.category` | *is a farmer* — with `category` pointing at an entity |
| `exist` | *there is a cat* |

Phrasal verbs and idioms resolve to one hyphenated concept: `look-after`, `look-at`,
`pick-up`, `drive-off`, `listen-to`. *take care of* is `look-after`, *make fun of* is `mock`,
*put in order* is `tidy`. A literal reading here is the exact failure this project exists to
prevent — *put the room in order* read literally puts a room inside a thing called order.

### Roles

`agent`, `patient`, `theme`, `recipient`, `experiencer`, `beneficiary`, `instrument`,
`comitative`.

- `theme` rather than `patient` when the object is not changed: things given, seen, liked,
  wanted, had.
- `experiencer` for the subject of `like`, `see`, `hear`, `think`, `know`, `feel`, `want`.
- `comitative` is *along with*, not *against*. *offended with me* has no role that fits — that
  is a recorded gap, not a use for `comitative`.
- Intransitive change-of-state verbs (*fall*, *drown*) take `agent`, for consistency with the
  rest of the set, even though nobody chose to do them.

**Who performs an embedded clause.** *Mum told Sam to wash the cup* is **Sam** washing. The
matrix object controls, unless the verb is *promise* and its kin. This is the error the
argument-swap counter does not catch, so it is worth checking twice.

### Non-finite clauses

A clause that asserts nothing carries nothing. Purpose infinitives (*bread to eat*),
perception complements (*saw him fall*), participials (*sat, waiting*):

**no `tense`, no `mood`.** Keep `aspect` — `progressive` for a participle, `simple`
otherwise. A non-finite clause also takes no `question`, which is why an embedded *how to*
or *where to* goes unrecorded.

Polarity is the exception: drop it unless the text explicitly negates the clause. *Not
seeing it, he grew uneasy* carries `polarity: "negative"` on the participle, because the
*Not* is right there and dropping it inverts the sentence.

### Features

`tense` past/present/future, `aspect` simple/progressive/perfect, `polarity`
positive/negative, `mood` declarative/interrogative/imperative/exclamative.

Read mood off the grammar, not the punctuation. Subject-auxiliary inversion makes a question
even with a full stop; a bare verb with no subject is an imperative even with an exclamation
mark. `exclamative` is for *How fine he looks!* and for a plain clause the mark is doing real
work on — not for an emphatic imperative.

`modality` is `can|must|may|should|would|want|going-to`, with `irrealis: true` when the event
is not asserted to have happened.

`degree` is `very|too|equative|comparative|superlative`, with `comparand` pointing at what is
compared. The attribute stays in **base form**: *wiser than Laura* is `attribute: "wise"`,
`degree: "comparative"`. *best* is `attribute: "good"`, `degree: "superlative"`.

`manner` is a bare concept (`slowly`, `well`). `frequency` is
`always|usually|often|sometimes|rarely|never` — and `never` means `polarity: "negative"` too.
`phase` is `again|still|already|yet`.

### `focus` and `measure` — new in `0.4.0`

```json
"focus": {"particle": "only", "target": "e1"}
"measure": {"quantity": 7, "unit": "year"}
```

`focus` particles are `only|just|even|too|also`. *Only the dog barked* is not *the dog
barked* — the claim is that nothing else did. Attach it to the event, targeting whatever it
narrows. Note that *too* is a focus particle in *He too can swim* and a **degree** in *too
big*; they are different fields.

`measure` needs `attribute` to measure. Without it *seven years old* reduces to *old*, which
for a seven-year-old is not lossy but inverted.

### Relating events

`complement` points at an embedded clause the verb takes (*likes to swim*, *saw him fall*).
`modifies` points at an **entity** the clause identifies (*the dog that barked*) — that is
modification, not discourse, and no discourse type fits it.

`discourse` relates two **assertions**: `sequence|cause|contrast|addition|condition|purpose|disjunction|simultaneous`.

- Clause-level *and* is **`sequence`** when it joins two happenings (see `g042`), and
  **`addition`** when it joins two states: *he is brave, and he is also very active* is not
  a sequence of anything.
- Coordinated **adjectives** on one subject are two events joined by **`addition`**.
- Coordinated **nouns** are a group, not a discourse relation.
- Give the relation a `marker` when a word realises it, or `inferred: true` when the reader
  supplies it. One or the other, never both.

---

## Alignment

Every node gets the token indices it is realised by. Punctuation is not aligned.

**The preposition goes with whatever carries the relation.** For a `spatial` on an event, the
preposition joins the **event's** span — *He has a pen in his hand* aligns `ev1` to `has` and
`in`. For a `located` on an entity, it joins the **entity's** span.

An attribute joins the event's span: *The moral tone is plain* aligns `ev1` to `is` and
`plain`.

A group spans the whole coordinated phrase, connectors included; its members span their own
parts inside it. Overlapping spans are fine.

A discourse relation aligns to its marker.

`setting` carries no alignment at all, so *Now* and *Then* go unaligned when recorded there —
note it as a gap rather than forcing them somewhere.

---

## Utterance level

`address` points at a vocative — the person spoken to. In an imperative the addressee is also
the agent, so `address` and `roles.agent` are the **same node**.

`speech_act` is `greeting|farewell|thanks|please|affirm|deny|apology`. A bare *Thank you.* has
a `speech_act` and an empty `events` list; *No, John, she likes the pond* has a `speech_act`
**and** a scene.

`setting` takes `time`, `location` and `weather` as bare concepts.

---

## Notes, gaps and flags

Write a `notes` line whenever a choice was not obvious. Start it with **`GAP:`** when the
schema could not hold something in the sentence — those notes are the findings, and set two's
gap rate of 40% came straight out of them.

Known gaps at `0.4.0`, so do not try to force these:

apposition (*we, you and I*) · measure without a number (*a long time*) · reaction adjuncts
(*to the delight of all*) · distance predicates taking a ground (*far from home*) · interval
frequency (*every day*) · modifiers on `setting.time` (*one cold, windy night*) · a role for
the target of a feeling (*offended with me*) · emphatic *do* · *instead* · subordinators with
no matrix clause, which verse produces a lot of

`review` flags a node for a human: `sense_ambiguous`, `role_uncertain`, `no_symbol`,
`idiom_suspected`, `out_of_vocabulary`, `parse_uncertain`, `not_depictable`. Use them rather
than resolving a genuine ambiguity silently.

---

## A worked example

*The boy gave the book to his sister.*

```json
{
  "schema_version": "0.4.0",
  "id": "kNNN",
  "text": "The boy gave the book to his sister.",
  "tokens": ["The", "boy", "gave", "the", "book", "to", "his", "sister", "."],
  "entities": {
    "e1": {"concept": "boy", "number": "sg", "definite": true, "animacy": "person", "gender": "male"},
    "e2": {"concept": "book", "number": "sg", "definite": true, "animacy": "object"},
    "e3": {"concept": "sister", "number": "sg", "definite": true, "animacy": "person", "gender": "female", "possessor": "e1"}
  },
  "events": [
    {
      "id": "ev1",
      "predicate": "give",
      "roles": {"agent": "e1", "theme": "e2", "recipient": "e3"},
      "tense": "past",
      "aspect": "simple",
      "polarity": "positive",
      "mood": "declarative"
    }
  ],
  "alignment": [
    {"node": "e1", "tokens": [0, 1]},
    {"node": "ev1", "tokens": [2, 5]},
    {"node": "e2", "tokens": [3, 4]},
    {"node": "e3", "tokens": [6, 7]}
  ],
  "notes": ""
}
```

Note `theme` rather than `patient` for the book, `to` sitting in the event's span, and *his*
resolving to the boy rather than becoming an entity of its own.

---

## When you are done

```bash
python tools/annotate.py lock
```

That refuses to run while anything is `TODO` or failing validation. Once it writes
`LOCK.json`, the set is frozen and the parser may be run on it — **once**.
