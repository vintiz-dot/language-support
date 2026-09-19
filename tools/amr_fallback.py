"""An AMR fallback callable for `parse(..., fallback=...)`.

Separate from `parser/` on purpose: this is the only thing in the project that needs
amrlib and a 516 MB model, and nothing in the rendering path should ever import it. The
parser takes a plain callable, so anything that turns a sentence into penman notation will
do -- a hosted service, a cached table, a different parser.

    from tools.amr_fallback import amr_fallback
    graph = parse(text, tokens=tokens, fallback=amr_fallback())
"""

import functools
import sys
import warnings


@functools.lru_cache(maxsize=1)
def _model(device="cpu", batch_size=4, num_beams=1):
    warnings.filterwarnings("ignore")
    import amrlib

    return amrlib.load_stog_model(device=device, batch_size=batch_size, num_beams=num_beams)


def amr_fallback(device="cpu", cache=None):
    """Return a callable text -> penman string, or None when the model has nothing.

    cache, if given, is a dict of text -> penman used before the model is consulted. Batch
    callers should fill it in one `parse_sents` call: the model is far faster in batches
    than one sentence at a time, and the fallback fires on a minority of sentences anyway.
    """
    cache = {} if cache is None else cache

    def fallback(text):
        if text in cache:
            return cache[text]
        try:
            result = _model(device=device).parse_sents([text])
        except Exception as exc:  # noqa: BLE001 - reported, never fatal to a parse
            print(f"  amr fallback unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
            return None
        cache[text] = result[0] if result else None
        return cache[text]

    return fallback


def prefill(cache, sentences, device="cpu"):
    """Parse many sentences at once into a cache, which is much faster than one at a time."""
    missing = [s for s in sentences if s not in cache]
    if not missing:
        return cache
    for text, graph in zip(missing, _model(device=device).parse_sents(missing)):
        cache[text] = graph
    return cache
