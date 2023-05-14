import itertools
import random
import time
import csv

def allocation(filename, number_of_groups):
    if not 1 < number_of_groups <= 10:
        print("Invalid number of groups")
        return

    print(f"Filename: {filename}")
    index = {}

    # Creates an index, dictionary with {ID:Weights}
    with open(filename, 'r') as text_file:
        for l in text_file:
            result = l.strip('\n').strip().split(',')
            index[result[0]] = int(result[1])

    animal_IDs = list(index.keys())

    best_group_diff = float('inf')
    best_groups = [None] * number_of_groups

    for _ in range(500):
        random.shuffle(animal_IDs)
        groups = [[] for _ in range(number_of_groups)]

        for i, animal_id in enumerate(animal_IDs):
            groups[i % number_of_groups].append(animal_id)

        avg_bws = [sum(index[animal_id] for animal_id in group) / len(group) for group in groups]
        group_diff = sum(abs(avg_bws[i] - avg_bws[j]) for i in range(number_of_groups) for j in range(i + 1, number_of_groups)) / (number_of_groups * (number_of_groups - 1) // 2)

        if group_diff < best_group_diff:
            best_group_diff = group_diff
            best_groups = [list(group) for group in groups]

    print(f"\n\n\n{'=' * 40}")
    for i, best_group in enumerate(best_groups):
        print(f"Group {i + 1}: {best_group}")
    print(f"{'=' * 40}\n")

    with open('OUTPUT_zAllocator.txt', 'w') as results:
        results.write('\nOriginal input\n')
        for key, value in sorted(index.items()):
            results.write(f"{key},{value}\n")

        for i, best_group in enumerate(best_groups):
            results.write(f"\nGroup {i + 1}\n")
            for key in best_group:
                results.write(f"{key},{index[key]}\n")

print("\n" + "=" * 80)
print("LBS Animal Allocator Applet v1.0")
print("=" * 80 + "\n\n")
filename_input = input('Filename: ')
number_of_groups = int(input('Number of groups (2 to 10): '))
allocation(filename_input, number_of_groups)
time.sleep(5)
