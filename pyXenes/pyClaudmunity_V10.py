#now with names
import random
from dataclasses import dataclass
from typing import List
import time
import csv
from datetime import datetime
import os
import tkinter as tk
from tkinter import ttk, scrolledtext

@dataclass
class Character:
    name: str
    toon_id: str
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
    health: str = "Healthy"

class Community:
    def __init__(self, name: str):
        self.name = name
        self.nutrition = 2000
        self.characters: List[Character] = []
        self.year = 0
        self.cycle = 0
        self.food_available = 100
        self.food_collected = 0
        self.food_consumed = 0
        self.next_character_id = 1
        self.nationalities = ["Morfigo", "Konforme", "Skibidi", "Poputah", "Elgibidi", "Noffinoffs"]
        self.csv_filename = f"{name}_population_stats.csv"
        self.food_nutrition_filename = f"{name}_food_nutrition_stats.csv"
        self.event_log_filename = f"{name}_event_log.csv"
        self.research_points = 0
        self.food_min = -100
        self.food_max = 500
        
        if not os.path.exists(self.csv_filename):
            with open(self.csv_filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['year'] + [f'#{n}' for n in self.nationalities])
        
        if not os.path.exists(self.food_nutrition_filename):
            with open(self.food_nutrition_filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['year', 'cycle', 'food_available', 'nutrition_available'])

        with open(self.event_log_filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'Year', 'Cycle', 'Event'])

        self.load_names()

    def load_names(self):
        self.name_lists = {}
        for nationality in self.nationalities:
            filename = f"pyCl_{nationality.lower()}.csv"
            if os.path.exists(filename):
                with open(filename, 'r', newline='') as f:
                    reader = csv.reader(f)
                    self.name_lists[nationality] = [row[0] for row in reader]
            else:
                print(f"Warning: Name file {filename} not found. Using default names for {nationality}.")
                self.name_lists[nationality] = [f"{nationality}Person"]

    def add_character(self, character: Character):
        self.characters.append(character)

    def remove_character(self, character: Character, cause: str):
        if character.partner:
            character.partner.in_relationship = False
            character.partner.partner = None
        self.characters.remove(character)
        event = f"Death Announcement: {character.name} ({character.toon_id}) ({character.nationality}) has died at age {character.age} due to {cause}."
        self.log_event(event)

    def update_food(self):
        self.food_available += random.randint(self.food_min, self.food_max)
        self.food_available = max(0, self.food_available)

    def collect_food(self):
        self.food_collected = 0
        efficiency_factor = 6.0  # Increase the base and extra collection by 500%

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
            required_food = character.metabolism / 2  # Cut food consumption by half
            if self.nutrition >= required_food:
                self.nutrition -= required_food
                self.food_consumed += required_food
            else:
                # 25% chance of death due to starvation
                if random.random() < 0.25:
                    self.remove_character(character, "Starvation")
                else:
                    # Character survives starvation this time but loses stamina
                    character.stamina -= 1
                    if character.stamina <= 0:
                        self.remove_character(character, "Stress")
                    else:
                        event = f"{character.name} ({character.toon_id}) ({character.nationality}) is starving but survived this cycle. Stamina reduced to {character.stamina}."
                        self.log_event(event)

    def age_characters(self):
        for character in self.characters:
            character.age += 1
            if character.age >= character.age_of_death:
                self.remove_character(character, "Old Age")
            else:
                self.check_for_diseases(character)

    def check_for_diseases(self, character):
        if character.age > 30 and random.random() < 0.01:
            self.remove_character(character, "Cancer")
        elif character.age > 55 and random.random() < 0.01:
            self.remove_character(character, "Heart Attack")
        elif character.age < 15 and random.random() < 0.03:
            self.remove_character(character, "Flu")
        elif character.age < 6 and random.random() < 0.05:
            self.remove_character(character, "Pneumonia")
        elif character.age % 2 == 0 and random.random() < 0.01:
            self.remove_character(character, "Dehydration")
        elif 15 <= character.age <= 45 and random.random() < 0.01:
            self.remove_character(character, "Suicide")
        elif random.random() < 0.01:
            self.remove_character(character, "Food Poisoning")

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
                event = f"New character born: {new_character.name} ({new_character.toon_id}) ({new_character.nationality}) - Parents: {character.name} ({character.toon_id}) and {character.partner.name} ({character.partner.toon_id})"
                self.log_event(event)

    def create_new_character(self, nationality):
        stat_ranges = {
            "Morfigo": {
                "stamina": (1, 8),
                "work_ethic": (5, 10),
                "metabolism": (2, 8),
                "intelligence": (3, 10),
                "mate_acquisition": (2, 8),
                "reproductive_fitness": (1, 10),
                "age_of_death": (40, 80)
            },
            "Konforme": {
                "stamina": (2, 9),
                "work_ethic": (2, 6),
                "metabolism": (1, 10),
                "intelligence": (1, 7),
                "mate_acquisition": (5, 10),
                "reproductive_fitness": (5, 10),
                "age_of_death": (30, 100)
            },
            "Skibidi": {
                "stamina": (1, 5),
                "work_ethic": (6, 9),
                "metabolism": (1, 10),
                "intelligence": (1, 10),
                "mate_acquisition": (1, 10),
                "reproductive_fitness": (6, 10),
                "age_of_death": (20, 40)
            },
            "Poputah": {
                "stamina": (3, 10),
                "work_ethic": (6, 10),
                "metabolism": (5, 10),
                "intelligence": (8, 10),
                "mate_acquisition": (1, 5),
                "reproductive_fitness": (3, 7),
                "age_of_death": (20, 100)
            },
            "Elgibidi": {
                "stamina": (1, 10),
                "work_ethic": (1, 5),
                "metabolism": (4, 9),
                "intelligence": (1, 4),
                "mate_acquisition": (5, 10),
                "reproductive_fitness": (1, 2),
                "age_of_death": (50, 100)
            },
            "Noffinoffs": {
                "stamina": (1, 5),
                "work_ethic": (6, 9),
                "metabolism": (1, 7),
                "intelligence": (3, 6),
                "mate_acquisition": (6, 10),
                "reproductive_fitness": (5, 9),
                "age_of_death": (55, 90)
            }
        }

        ranges = stat_ranges[nationality]
        
        # Choose a random name from the appropriate list
        name = random.choice(self.name_lists[nationality])

        new_character = Character(
            name=name,
            toon_id=f"toon{self.next_character_id:04d}",
            age=0,
            nationality=nationality,
            metabolism=random.randint(*ranges["metabolism"]),
            work_ethic=random.randint(*ranges["work_ethic"]),
            stamina=random.randint(*ranges["stamina"]),
            intelligence=random.randint(*ranges["intelligence"]),
            mate_acquisition=random.randint(*ranges["mate_acquisition"]),
            reproductive_fitness=random.randint(*ranges["reproductive_fitness"]),
            age_of_death=random.randint(*ranges["age_of_death"])
        )
        self.next_character_id += 1
        return new_character

    def accumulate_research(self):
        total_intelligence = sum(character.intelligence for character in self.characters)
        self.research_points += total_intelligence
        self.check_research_upgrades()

    def check_research_upgrades(self):
        if self.research_points >= 2000000:
            self.food_min = 400
            self.food_max = 8000
        elif self.research_points >= 500000:
            self.food_min = 300
            self.food_max = 600
        elif self.research_points >= 50000:
            self.food_min = 0
        elif self.research_points >= 5000:
            self.food_min = -100
            self.food_max = 600
        elif self.research_points >= 500:
            self.food_min = -100
            self.food_max = 550

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
        self.accumulate_research()
        self.write_food_nutrition_stats()
        time.sleep(0.01)

    def write_population_stats(self):
        stats = [self.year] + [sum(1 for c in self.characters if c.nationality == n) for n in self.nationalities]
        with open(self.csv_filename, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(stats)
    
    def write_food_nutrition_stats(self):
        stats = [self.year, self.cycle, round(self.food_available), round(self.nutrition)]
        with open(self.food_nutrition_filename, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(stats)

    def log_event(self, event: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.event_log_filename, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, self.year, self.cycle, event])
        print(f"[Year {self.year}-Cycle {self.cycle}] {event}")

    def display_status(self):
        status = f"Current Year: {self.year}, Cycle: {self.cycle}\n"
        status += f"Population: {len(self.characters)}\n"
        status += f"Research Points: {self.research_points}\n"
        status += f"Food Available: {round(self.food_available)} units\n"
        status += f"Nutrition Available: {round(self.nutrition)} units\n"
        status += f"Food Collected this cycle: {round(self.food_collected)} units\n"
        status += f"Food Consumed this cycle: {round(self.food_consumed)} units\n"
        status += "Characters Alive:\n"
        for character in self.characters:
            status += f"{character.name} ({character.toon_id}) - {character.nationality} - Age {character.age} - Mtblsm {character.metabolism} - WrkEt {character.work_ethic} - Int {character.intelligence} {'*' * character.stamina}\n"
        return status

class SimulationGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Community Simulation")
        self.master.geometry("800x600")
        self.master.configure(bg="#f0f0f0")

        self.community = None
        self.running = False

        self.create_widgets()

    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.master, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)

        # Community name input
        ttk.Label(main_frame, text="Community Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.community_name_entry = ttk.Entry(main_frame, width=30)
        self.community_name_entry.grid(row=0, column=1, sticky=tk.W, pady=5)

        # Number of cycles input
        ttk.Label(main_frame, text="Number of Cycles:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.num_cycles_entry = ttk.Entry(main_frame, width=10)
        self.num_cycles_entry.grid(row=1, column=1, sticky=tk.W, pady=5)

        # Start button
        self.start_button = ttk.Button(main_frame, text="Start Simulation", command=self.start_simulation)
        self.start_button.grid(row=2, column=0, columnspan=2, pady=10)

        # Status display
        self.status_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, width=80, height=20)
        self.status_text.grid(row=3, column=0, columnspan=2, pady=10)

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, length=300, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=4, column=0, columnspan=2, pady=10)

        # Apply some styling
        style = ttk.Style()
        style.configure("TButton", padding=6, relief="flat", background="#ccc")
        style.configure("TEntry", padding=5)
        style.configure("TLabel", background="#f0f0f0", padding=5)

    def start_simulation(self):
        if self.running:
            return

        community_name = self.community_name_entry.get()
        num_cycles = int(self.num_cycles_entry.get())

        self.community = initialize_simulation(community_name)
        self.running = True
        self.start_button.config(state=tk.DISABLED)

        self.run_simulation(num_cycles)

    def run_simulation(self, num_cycles):
        if not self.running:
            self.start_button.config(state=tk.NORMAL)
            return

        self.community.run_cycle()
        status = self.community.display_status()
        self.status_text.delete(1.0, tk.END)
        self.status_text.insert(tk.END, status)

        progress = (self.community.cycle + (self.community.year * 12)) / num_cycles * 100
        self.progress_var.set(progress)

        if self.community.cycle + (self.community.year * 12) < num_cycles:
            self.master.after(100, lambda: self.run_simulation(num_cycles))
        else:
            self.running = False
            self.start_button.config(state=tk.NORMAL)

def initialize_simulation(community_name: str):
    community = Community(community_name)
    for i in range(25):
        character = community.create_new_character(random.choice(community.nationalities))
        character.age = 18  # Set initial age to 18
        community.add_character(character)
    community.write_population_stats()  # Write initial stats
    return community

if __name__ == "__main__":
    root = tk.Tk()
    app = SimulationGUI(root)
    root.mainloop()