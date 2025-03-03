import random
import os
import time

# Constants
GRID_WIDTH = 96
GRID_HEIGHT = 64
TERRAIN_TYPES = ["GROUND", "POND", "ROCK", "VEGETATION"]
COMMUNITY_SYMBOLS = ["A", "B", "C", "D"]
COMMUNITY_COLORS = ["\033[91m", "\033[92m", "\033[93m", "\033[94m"]  # ANSI colors: Red, Green, Yellow, Blue
RESET_COLOR = "\033[0m"

# Community traits
COMMUNITY_TRAITS = {
    "A": {"growth": 1.2, "aggression": 1.0, "adaptability": 0.8, "resilience": 0.9, "mobility": 1.0},
    "B": {"growth": 1.1, "aggression": 0.9, "adaptability": 1.0, "resilience": 1.0, "mobility": 1.1},
    "C": {"growth": 1.3, "aggression": 1.2, "adaptability": 0.7, "resilience": 0.8, "mobility": 0.9},
    "D": {"growth": 1.4, "aggression": 0.8, "adaptability": 1.1, "resilience": 1.2, "mobility": 1.0},
}

# Initialize grid
grid = [[random.choices(TERRAIN_TYPES, weights=[75, 8, 8, 9])[0] for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]

# Add communities to the grid
for y in range(GRID_HEIGHT):
    for x in range(GRID_WIDTH):
        if x == 0 or x == GRID_WIDTH - 1 or y == 0 or y == GRID_HEIGHT - 1:
            grid[y][x] = "ROCK"  # Border
        elif x % 24 == 0 and y % 16 == 0:  # Place communities at regular intervals
            community = random.choice(COMMUNITY_SYMBOLS)
            grid[y][x] = community

# Soldier class
class Soldier:
    def __init__(self, x, y, community):
        self.x = x
        self.y = y
        self.community = community

    def move(self):
        traits = COMMUNITY_TRAITS[self.community]
        mobility = traits["mobility"]
        dx = random.randint(-1, 1) * mobility
        dy = random.randint(-1, 1) * mobility
        new_x = self.x + dx
        new_y = self.y + dy
        if 0 <= new_x < GRID_WIDTH and 0 <= new_y < GRID_HEIGHT:
            self.x, self.y = new_x, new_y

    def attack(self):
        traits = COMMUNITY_TRAITS[self.community]
        aggression = traits["aggression"]
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                x = self.x + dx
                y = self.y + dy
                if 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT:
                    if grid[y][x] in COMMUNITY_SYMBOLS and grid[y][x] != self.community:
                        if random.random() < aggression:
                            grid[y][x] = "GROUND"  # Destroy enemy cell

# Expansion function
def expand_community(community):
    traits = COMMUNITY_TRAITS[community]
    growth = traits["growth"]
    adaptability = traits["adaptability"]
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if grid[y][x] == community:
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        if dx == 0 and dy == 0:
                            continue
                        new_x = x + dx
                        new_y = y + dy
                        if 0 <= new_x < GRID_WIDTH and 0 <= new_y < GRID_HEIGHT:
                            terrain = grid[new_y][new_x]
                            if terrain == "GROUND":
                                if random.random() < 0.1 * growth:
                                    grid[new_y][new_x] = community
                            elif terrain == "VEGETATION":
                                if random.random() < 0.2 * growth:
                                    grid[new_y][new_x] = community
                            elif terrain == "POND":
                                if random.random() < 0.05 * growth * adaptability:
                                    grid[new_y][new_x] = community
                            elif terrain == "ROCK":
                                if random.random() < 0.02 * growth * adaptability:
                                    grid[new_y][new_x] = community

# Decay function
def apply_decay():
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            cell = grid[y][x]
            if cell in COMMUNITY_SYMBOLS:
                traits = COMMUNITY_TRAITS[cell]
                resilience = traits["resilience"]
                if random.random() < 0.01 * (1 - resilience):
                    grid[y][x] = "GROUND"

# Print grid with ANSI colors
def print_grid():
    os.system("clear" if os.name == "posix" else "cls")
    for row in grid:
        for cell in row:
            if cell in COMMUNITY_SYMBOLS:
                print(f"{COMMUNITY_COLORS[COMMUNITY_SYMBOLS.index(cell)]}{cell}{RESET_COLOR}", end="")
            else:
                print(cell[0], end="")  # Print first letter of terrain type
        print()

# Simulation loop
soldiers = []
for _ in range(100):  # Initial soldiers
    x = random.randint(0, GRID_WIDTH - 1)
    y = random.randint(0, GRID_HEIGHT - 1)
    if grid[y][x] in COMMUNITY_SYMBOLS:
        soldiers.append(Soldier(x, y, grid[y][x]))

for year in range(1000):  # Run for 1000 years
    for community in COMMUNITY_SYMBOLS:
        expand_community(community)
    apply_decay()
    for soldier in soldiers:
        soldier.move()
        soldier.attack()
    if year % 10 == 0:
        print_grid()
        print(f"Year: {year}")
        time.sleep(1)