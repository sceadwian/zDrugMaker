#!/usr/bin/env python3
"""
zFileIndexer.py
Scan all files under the current directory for study codes and user-defined keywords,
then save an index to 'index.json'.
- Looks for study codes in file names and file contents.
- Loads keywords from 'zFileIndexer.txt' in the same directory (one per line).
- Extracts top 10 frequent terms per file (excluding common stop-words).
"""
import os
import re
import json
from collections import Counter

# Regex for study codes
STUDY_CODE_PATTERN = re.compile(r'\b(?:TSA-\d{5}-[A-Z]{3}|TPC1-\d{5}-[A-Z]{2})\b')

# Common stop-words to exclude
STOP_WORDS = {
    'the','is','and','of','to','a','in','for','on','with','as','by','it',
    'this','that','from','at','an','be','are','was','were','or','but',
    'not','they','their','have','has','had','him','his','her','here','there'
}

KEYWORDS_FILE = 'zFileIndexer.txt'
OUTPUT_FILE   = 'index.json'

def load_keywords():
    """Load keywords from KEYWORDS_FILE, one per line."""
    kws = set()
    if os.path.isfile(KEYWORDS_FILE):
        with open(KEYWORDS_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                w = line.strip().lower()
                if w:
                    kws.add(w)
    return kws

def read_text(path):
    """Read file content as text for indexing."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in ('.txt', '.csv'):
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        else:
            # Fallback: read binary and Latin-1 decode
            with open(path, 'rb') as f:
                data = f.read()
            return data.decode('latin-1', errors='ignore')
    except Exception:
        return ''

def tokenize(text):
    """Split text into word tokens."""
    return re.findall(r'\b\w+\b', text)

def index_file(path, keywords):
    """Index a single file for codes, keywords, and top terms."""
    name = os.path.basename(path)
    lname = name.lower()
    
    # 1) Study codes in name + content
    codes = STUDY_CODE_PATTERN.findall(name)
    content = read_text(path)
    codes += STUDY_CODE_PATTERN.findall(content)
    
    # 2) Exact keyword matches
    found_kw = [kw for kw in keywords
                if kw in lname or kw in content.lower()]
    
    # 3) Top frequent terms
    combined = lname + ' ' + content.lower()
    tokens = tokenize(combined)
    freq = Counter(w for w in tokens if w not in STOP_WORDS and len(w) > 3)
    top_terms = [t for t, c in freq.most_common(10)]
    
    if codes or found_kw or top_terms:
        return {
            'path': path,
            'codes': sorted(set(codes)),
            'keywords': sorted(set(found_kw)),
            'top_terms': top_terms
        }
    return None

def walk_and_index(root, keywords):
    """Walk through root directory and index each file."""
    index = []
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            path = os.path.join(dirpath, fname)
            rec = index_file(path, keywords)
            if rec:
                index.append(rec)
    return index

def main():
    try:
        print(f"Loading keywords from '{KEYWORDS_FILE}'...")
        keywords = load_keywords()
        print(f"  → {len(keywords)} keywords loaded.\n")
        
        print("Indexing files under current directory...")
        index = walk_and_index('.', keywords)
        print(f"  → {len(index)} files indexed.\n")
        
        print(f"Saving index to '{OUTPUT_FILE}'...")
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2)
        
        print("Done! Index saved successfully.")
        print(f"\nFound {len(index)} files with study codes, keywords, or significant terms.")
        
    except Exception as e:
        print(f"Error occurred: {e}")
    
    # Keep the window open
    input("\nPress Enter to close this window...")

if __name__ == '__main__':
    main()