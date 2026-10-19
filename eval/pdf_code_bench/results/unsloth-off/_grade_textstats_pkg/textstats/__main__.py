"""CLI entry point: python -m textstats FILE [--top N] [--stop FILE]."""

import argparse
import sys

from .core import summary, top_words


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="textstats",
        description="Print a word summary of a text file.",
    )
    parser.add_argument("file", help="path to the text file")
    parser.add_argument(
        "--top", type=int, default=5, help="number of top words (default 5)"
    )
    parser.add_argument(
        "--stop",
        default=None,
        help="path to a file with stop words (one per line)",
    )
    args = parser.parse_args(argv)

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        print(f"error: cannot read {args.file}: {exc}", file=sys.stderr)
        return 1

    stop = None
    if args.stop:
        try:
            with open(args.stop, "r", encoding="utf-8") as f:
                stop = {line.strip().lower() for line in f if line.strip()}
        except OSError as exc:
            print(f"error: cannot read stop file {args.stop}: {exc}", file=sys.stderr)
            return 1

    stats = summary(text)
    print(f"words: {stats['words']}")
    print(f"unique: {stats['unique']}")
    print(f"sentences: {stats['sentences']}")
    print(f"avg_word_len: {stats['avg_word_len']}")
    print()
    for word, count in top_words(text, args.top, stop=stop):
        print(f"{word} {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
