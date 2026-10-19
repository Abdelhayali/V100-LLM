"""Core text statistics helpers."""

import re
import unicodedata
from collections import Counter


def _word_chars(ch: str) -> bool:
    """A word character is a letter (any Unicode letter, e.g. é), a digit,
    or an apostrophe (') that appears *inside* a word."""
    if ch in "'’":
        return True
    if ch.isdigit():
        return True
    if ch.isalpha():
        return True
    return False


def words(text: str) -> list:
    """Split *text* into lowercase words.

    A word is a maximal run of letters (any Unicode letter, e.g. é), digits
    and apostrophes (apostrophes only count inside a word, so a leading or
    trailing apostrophe is not part of the word). Everything else is a
    separator.
    """
    if not text:
        return []
    result = []
    current = []
    for ch in text:
        if _word_chars(ch):
            current.append(ch)
        else:
            if current:
                # strip apostrophes that ended up at the edges (they only
                # count *inside* a word)
                word = "".join(current).lower()
                word = word.strip("'’")
                if word:
                    result.append(word)
                current = []
    if current:
        word = "".join(current).lower()
        word = word.strip("'’")
        if word:
            result.append(word)
    return result


def top_words(text: str, n: int, stop=None) -> list:
    """Return the *n* most frequent words as (word, count) pairs.

    Words in the *stop* set are skipped. Ties are broken by word ascending.
    """
    stop_set = set(stop) if stop else set()
    counts = Counter(w for w in words(text) if w not in stop_set)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[:n]


def summary(text: str) -> dict:
    """Return a summary dict with keys: words, unique, sentences,
    avg_word_len."""
    word_list = words(text)
    n_words = len(word_list)
    unique = len(set(word_list))

    # Sentences: runs ending in . ! or ? ; a trailing run without punctuation
    # counts as one more sentence if it contains a word.
    sentences = 0
    i = 0
    length = len(text)
    while i < length:
        m = re.compile(r"[.!?]").search(text, i)
        if m is None:
            # no more sentence terminators: count the tail if it has a word
            tail = text[i:]
            if any(ch.isalpha() or ch.isdigit() for ch in tail):
                sentences += 1
            break
        sentences += 1
        i = m.end()
    # A sentence terminator with no word before it still ends a run, but
    # only *runs* count; the loop above counts each terminator as one run.
    # That matches "count of runs ending in . ! or ?".

    avg = round(sum(len(w) for w in word_list) / n_words, 2) if n_words else 0.0

    return {
        "words": n_words,
        "unique": unique,
        "sentences": sentences,
        "avg_word_len": avg,
    }
