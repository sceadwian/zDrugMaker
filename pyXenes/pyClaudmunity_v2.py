# version 20240704 using claude @first and then some edits with GPT with fixes
# 
import random
from dataclasses import dataclass
from typing import List
import time
import csv
import os

@dataclass
class Character:
    name: str
    age: int
    nationality: str
    metabolism: int
    work_ethic: int
    stamina: int
    intelligence: int
    mate_acquisition: int
    reproductive_fitness: int
    age_of_death: int
    in_relationship: bool = False
    partner: 'Character' = None

class Community:
    def __init__(self, name: str):
        self.name = name
        self.nutrition = 5000
        self.characters: List[Character] = []
        self.year = 0
        self.cycle = 0
        self.food_available = 100
        self.food_collected = 0
        self.food_consumed = 0
        self.next_character_id = 1
        self.nationalities = ["Morfigo", "Konforme", "Skibidi", "Poputah", "Elgibidi", "Noffinoffs"]
        self.csv_filename = f"{name}_population_stats.csv"
        
        if not os.path.exists(self.csv_filename):
            with open(self.csv_filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['year'] + [f'#{n}' for n in self.nationalities])

    def add_character(self, character: Character):
        self.characters.append(character)

    def remove_character(self, character: Character):
        if character.partner:
            character.partner.in_relationship = False
            character.partner.partner = None
        self.characters.remove(character)

    def update_food(self):
        self.food_available += random.randint(-10, 50)
        self.food_available = max(0, self.food_available)

    def collect_food(self):
        self.food_collected = 0
        efficiency_factor = 1.4  # Increase the base and extra collection by 40%

        for character in self.characters:
            base_collection = min(round(1 * efficiency_factor), self.food_available)
            extra_collection = 0
            if self.food_available > base_collection:
                extra_collection = min(random.randint(0, round(character.work_ethic * efficiency_factor)), self.food_available - base_collection)

            total_collected = base_collection + extra_collection
            self.nutrition += total_collected
            self.food_available -= total_collected
            self.food_collected += total_collected

    def consume_food(self):
        self.food_consumed = 0
        for character in self.characters:
            if self.nutrition >= character.metabolism:
                self.nutrition -= character.metabolism
                self.food_consumed += character.metabolism
            else:
                self.remove_character(character)
                print(f"Death Announcement: {character.name} ({character.nationality}) has died at age {character.age} due to starvation.")

    def age_characters(self):
        for character in self.characters:
            character.age += 1
            if character.age >= character.age_of_death:
                self.remove_character(character)
                print(f"Death Announcement: {character.name} ({character.nationality}) has died at age {character.age}.")

    def attempt_reproduction(self):
        for character in self.characters:
            if character.age >= 18 and not character.in_relationship:
                potential_partners = [c for c in self.characters if c.age >= 18 and not c.in_relationship and c.nationality == character.nationality and c != character]
                if potential_partners and random.random() < character.mate_acquisition / 10:
                    partner = random.choice(potential_partners)
                    character.in_relationship = True
                    character.partner = partner
                    partner.in_relationship = True
                    partner.partner = character
            
            if character.in_relationship and character.partner and random.random() < 0.25 * (character.reproductive_fitness / 10):
                new_character = self.create_new_character(character.nationality)
                self.add_character(new_character)
                print(f"New character born: {new_character.name} ({new_character.nationality})")

    def create_new_character(self, nationality):
        new_character = Character(
            name=f"toon{self.next_character_id:04d}",
            age=0,
            nationality=nationality,
            metabolism=random.randint(1, 10),
            work_ethic=random.randint(1, 10),
            stamina=random.randint(1, 10),
            intelligence=random.randint(1, 10),
            mate_acquisition=random.randint(1, 10),
            reproductive_fitness=random.randint(1, 10),
            age_of_death=random.randint(50, 100)
        )
        self.next_character_id += 1
        return new_character

    def run_cycle(self):
        self.cycle += 1
        if self.cycle > 12:
            self.cycle = 1
            self.year += 1
            self.age_characters()  # Age characters only once per year
            self.write_population_stats()

        self.update_food()
        self.collect_food()
        self.consume_food()
        self.attempt_reproduction()
        time.sleep(0.2)

    def write_population_stats(self):
        stats = [self.year] + [sum(1 for c in self.characters if c.nationality == n) for n in self.nationalities]
        with open(self.csv_filename, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(stats)

    def display_status(self):
        print(f"Current Year: {self.year}, Cycle: {self.cycle}")
        print(f"Food Available: {round(self.food_available)} units")
        print(f"Nutrition Available: {round(self.nutrition)} units")
        print(f"Food Collected this cycle: {round(self.food_collected)} units")
        print(f"Food Consumed this cycle: {round(self.food_consumed)} units")
        print("Characters Alive:")
        for character in self.characters:
            print(f"{character.name} - {character.nationality} - Age {character.age} - Mtblsm {character.metabolism} - WrkEt {character.work_ethic}")
        print()

def initialize_simulation(community_name: str):
    community = Community(community_name)
    for i in range(10):
        character = community.create_new_character(random.choice(community.nationalities))
        character.age = 18  # Set initial age to 18
        community.add_character(character)
    community.write_population_stats()  # Write initial stats
    return community

def run_simulation(community: Community, num_cycles: int):
    for _ in range(num_cycles):
        community.run_cycle()
        community.display_status()

# Usage
community_name = input("Enter the community name: ")
community = initialize_simulation(community_name)
num_cycles = int(input("Enter the number of cycles to run: "))
run_simulation(community, num_cycles)
