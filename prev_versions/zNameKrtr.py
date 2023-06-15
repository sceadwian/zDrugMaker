import random
import re
from collections import defaultdict

def get_syllables(name):
    return re.findall(r'[bcdfghjklmnpqrstvwxyz]*[aeiou][bcdfghjklmnpqrstvwxyz]*', name, re.I)

class MarkovChain:
    def __init__(self):
        self.transitions = defaultdict(list)
        self.syllable_counts = []

    def train(self, data):
        for name in data:
            syllables = get_syllables(name)
            self.syllable_counts.append(len(syllables))
            self.transitions[None].append(syllables[0])
            for i in range(len(syllables) - 1):
                self.transitions[syllables[i]].append(syllables[i + 1])
            self.transitions[syllables[-1]].append(None)

    def generate(self):
        name = []
        syllable_count = random.choice(self.syllable_counts)
        current = random.choice(self.transitions[None])
        while current is not None and syllable_count > 0:
            name.append(current)
            current = random.choice(self.transitions[current])
            syllable_count -= 1
        return ''.join(name)

def add_name():
    first_name = input("Enter first name: ")
    last_name = input("Enter last name: ")
    with open('names.txt', 'a') as f:
        f.write(f"{first_name} {last_name}\n")

def analyze_names():
    first_names = []
    last_names = []
    with open('names.txt', 'r') as f:
        for line in f:
            parts = line.strip().split()
            first_names.append(parts[0].lower())
            last_names.append(parts[1].lower())
    return first_names, last_names

def generate_names(first_names, last_names, n):
    first_name_chain = MarkovChain()
    first_name_chain.train(first_names)
    last_name_chain = MarkovChain()
    last_name_chain.train(last_names)
    with open('zNameKrtrGenerated.txt', 'a') as f:
        for _ in range(n):
            first_name = first_name_chain.generate().capitalize()
            last_name = last_name_chain.generate().capitalize()
            f.write(f"{first_name} {last_name}\n")

def main():
    while True:
        print("\n1. Add name")
        print("2. Generate names")
        print("3. Exit")
        choice = input("Enter your choice: ")
        if choice == '1':
            add_name()
        elif choice == '2':
            first_names, last_names = analyze_names()
            n = int(input("Enter the number of names to generate: "))
            generate_names(first_names, last_names, n)
        elif choice == '3':
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
