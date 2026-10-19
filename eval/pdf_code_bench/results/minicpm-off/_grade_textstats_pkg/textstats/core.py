import re
from collections import Counter

def words(text):
    """
    Extract words from text. Words consist of letters, digits, and apostrophes
    inside words. Split on everything else. Unicode letters count as letters.
    Returns lowercase words.
    """
    # Pattern: sequences of letters, digits, and apostrophes that are part of words
    # We match word-like tokens: letters/digits, possibly with internal apostrophes
    pattern = r"[^\W_]+(?:'[^\W_]+)*"
    # \w in Unicode mode matches letters, digits, underscore; we exclude underscore
    # Actually, let's use a more explicit approach with Unicode letters
    # Match any sequence of characters that are letters, digits, or apostrophes
    # But we want to ensure apostrophes are internal (not at start/end)
    # Simpler: split on non-word chars, then clean
    
    # Use regex to find all word-like tokens
    # \p{L} for any Unicode letter, \p{N} for digits
    # Python re doesn't support \p{L} directly, so we use a different approach
    # Match sequences of characters that are not whitespace and not punctuation boundaries
    
    # Let's use: split on anything that's not a letter, digit, or apostrophe
    # Then filter out empty strings and clean leading/trailing apostrophes
    tokens = re.split(r"[^a-zA-Z0-9'\u00C0-\u02AF\u0370-\u03FF\u1E00-\u1EFF]+", text)
    
    result = []
    for token in tokens:
        if not token:
            continue
        # Remove leading/trailing apostrophes
        token = token.strip("'")
        if token:
            result.append(token.lower())
    return result

def top_words(text, n, stop=None):
    """
    Return list of (word, count) tuples, sorted by count desc then word asc.
    Skip words in the stop set.
    """
    if stop is None:
        stop = set()
    else:
        stop = set(stop)
    
    word_list = words(text)
    counter = Counter(word_list)
    
    # Filter out stop words
    filtered = {w: c for w, c in counter.items() if w not in stop}
    
    # Sort by count desc, then word asc
    sorted_items = sorted(filtered.items(), key=lambda x: (-x[1], x[0]))
    
    return sorted_items[:n]

def summary(text):
    """
    Return dict with keys: words (count), unique, sentences, avg_word_len.
    """
    word_list = words(text)
    words_count = len(word_list)
    unique_count = len(set(word_list))
    
    # Count sentences: runs ending in . ! or ?
    # Trailing text without punctuation counts as one more sentence if it has a word
    sentence_end_pattern = r'[.!?]'
    sentences = 0
    # Find all sentence-ending positions
    matches = list(re.finditer(sentence_end_pattern, text))
    sentences = len(matches)
    
    # Check for trailing text without punctuation
    # Find the last sentence-ending punctuation
    last_match = None
    for m in re.finditer(sentence_end_pattern, text):
        last_match = m
    
    if last_match:
        trailing = text[last_match.end():]
    else:
        trailing = text
    
    # If trailing text has a word, count as one more sentence
    trailing_words = words(trailing)
    if trailing_words:
        sentences += 1
    
    # Calculate average word length
    if word_list:
        avg_word_len = sum(len(w) for w in word_list) / len(word_list)
    else:
        avg_word_len = 0.0
    
    avg_word_len = round(avg_word_len, 2)
    
    return {
        'words': words_count,
        'unique': unique_count,
        'sentences': sentences,
        'avg_word_len': avg_word_len
    }