import sys
import argparse
from textstats import summary, top_words

def main():
    parser = argparse.ArgumentParser(description="Text statistics tool")
    parser.add_argument('FILE', nargs='?', help="Input file to analyze")
    parser.add_argument('--top', type=int, default=5, help="Number of top words to display (default: 5)")
    parser.add_argument('--stop', type=str, help="File containing stop words (one per line)")
    
    args = parser.parse_args()
    
    # Check if FILE is missing
    if args.FILE is None:
        sys.stderr.write("Error: Missing input file\n")
        sys.exit(1)
    
    # Read the input file
    try:
        with open(args.FILE, 'r', encoding='utf-8') as f:
            text = f.read()
    except FileNotFoundError:
        sys.stderr.write(f"Error: File '{args.FILE}' not found\n")
        sys.exit(1)
    
    # Load stop words if provided
    stop_words = None
    if args.stop:
        try:
            with open(args.stop, 'r', encoding='utf-8') as f:
                stop_words = set(line.strip().lower() for line in f if line.strip())
        except FileNotFoundError:
            sys.stderr.write(f"Error: Stop file '{args.stop}' not found\n")
            sys.exit(1)
    
    # Compute summary
    summary_result = summary(text)
    
    # Print summary in order: words, unique, sentences, avg_word_len
    print(f"words: {summary_result['words']}")
    print(f"unique: {summary_result['unique']}")
    print(f"sentences: {summary_result['sentences']}")
    print(f"avg_word_len: {summary_result['avg_word_len']}")
    print()
    
    # Print top N words
    top_words_result = top_words(text, args.top, stop=stop_words)
    for word, count in top_words_result:
        print(f"{word} {count}")

if __name__ == '__main__':
    main()