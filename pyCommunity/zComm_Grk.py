import random
import os
import time

# ANSI color codes for visualization
COLORS = {
    'GROUND': '\033[90m',     # Grey
    'POND': '\033[94m',       # Blue
    'ROCK': '\033[37m',       # White
    'VEGETATION': '\033[92m', # Green
    'A': '\033[91m',         # Red
    'B': '\033[93m',         # Yellow
    'C': '\033[95m',         # Purple
    'D': '\033[96m',         # Cyan
    'RESET': '\033[0m'
}

# Terrain and community symbols
TERRAIN = {'GROUND': '.', 'POND': '~', 'ROCK': '#', 'VEGETATION': '*'}
COMMUNITIES = {'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D'}

# Community traits affecting their behavior
COMMUNITY_TRAITS = {
    'A': {"growth": 1.2, "aggression": 1.0, "adaptability": 0.8, "resilience": 0.9, "mobility": 1.0},
    'B': {"growth": 1.1, "aggression": 0.9, "adaptability": 1.0, "resilience": 1.0, "mobility": 1.1},
    'C': {"growth": 1.3, "aggression": 1.2, "adaptability": 0.7, "resilience": 0.8, "mobility": 0.9},
    'D': {"growth": 1.4, "aggression": 0.8, "adaptability": 1.1, "resilience": 1.2, "mobility": 1.0},
}

# Grid dimensions with border
WIDTH, HEIGHT = 96, 64
GRID = [[None for _ in range(WIDTH + 2)] for _ in range(HEIGHT + 2)]

# Soldier class for combat simulation
class Soldier:
    def __init__(self, community, x, y):
        self.community = community
        self.x = x
        self.y = y
        self.traits = COMMUNITY_TRAITS[community]

    def move(self):
        # Movement influenced by mobility trait
        moves = int(1 + self.traits["mobility"])
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        for _ in range(moves):
            dx, dy = random.choice(directions)
            new_x, new_y = self.x + dx, self.y + dy
            # Check if move is valid and not rock (unless adaptable)
            if (1 <= new_x <= WIDTH and 1 <= new_y <= HEIGHT and
                (GRID[new_y][new_x] != 'ROCK' or self.traits["adaptability"] > 1.0)):
                self.x, self.y = new_x, new_y

    def attack(self):
        # Check surrounding cells for enemy communities
        destroyed = 0
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                x, y = self.x + dx, self.y + dy
                if (1 <= x <= WIDTH and 1 <= y <= HEIGHT and
                    GRID[y][x] in COMMUNITIES and GRID[y][x] != self.community):
                    # Attack strength based on aggression trait
                    if random.random() < self.traits["aggression"] * 0.3:
                        GRID[y][x] = 'GROUND'
                        destroyed += 1
        return destroyed

# Initialize the grid with terrain
def initialize_grid():
    total_cells = WIDTH * HEIGHT
    terrain_cells = int(total_cells * 0.25)  # 25% terrain features
    
    # Fill with ground
    for y in range(1, HEIGHT + 1):
        for x in range(1, WIDTH + 1):
            GRID[y][x] = 'GROUND'
    
    # Add terrain features
    for _ in range(terrain_cells // 3):
        for terrain in ['POND', 'ROCK', 'VEGETATION']:
            x, y = random.randint(1, WIDTH), random.randint(1, HEIGHT)
            GRID[y][x] = terrain
    
    # Add initial community cells
    for comm in COMMUNITIES:
        while True:
            x, y = random.randint(1, WIDTH), random.randint(1, HEIGHT)
            if GRID[y][x] == 'GROUND':
                GRID[y][x] = comm
                break

# Expand community based on traits and terrain
def expand_community(community):
    traits = COMMUNITY_TRAITS[community]
    for y in range(1, HEIGHT + 1):
        for x in range(1, WIDTH + 1):
            if GRID[y][x] == community:
                for dy, dx in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                    new_y, new_x = y + dy, x + dx
                    terrain = GRID[new_y][new_x]
                    if terrain in TERRAIN:
                        # Base expansion chances modified by terrain and traits
                        chance = traits["growth"] * 0.1
                        if terrain == 'POND':
                            chance *= 0.3 * traits["adaptability"]
                        elif terrain == 'ROCK':
                            chance *= 0.1 * traits["adaptability"]
                        elif terrain == 'VEGETATION':
                            chance *= 1.5
                        if random.random() < chance:
                            GRID[new_y][new_x] = community

# Apply decay to communities
def apply_decay(iteration):
    if iteration % 100 == 0:
        for y in range(1, HEIGHT + 1):
            for x in range(1, WIDTH + 1):
                if GRID[y][x] in COMMUNITIES:
                    traits = COMMUNITY_TRAITS[GRID[y][x]]
                    if random.random() > traits["resilience"] * 0.95:
                        GRID[y][x] = 'GROUND'

# Display the grid with statistics
def display_grid(iteration, stats):
    os.system('cls' if os.name == 'nt' else 'clear')
    for y in range(1, HEIGHT + 1):
        for x in range(1, WIDTH + 1):
            cell = GRID[y][x]
            color = COLORS.get(cell, COLORS['GROUND'])
            symbol = TERRAIN.get(cell, cell)
            print(f"{color}{symbol}{COLORS['RESET']}", end='')
        print()
    print(f"\nIteration: {iteration}")
    for comm in COMMUNITIES:
        print(f"{COLORS[comm]}{comm}{COLORS['RESET']}: {stats[comm]} cells")
    print(f"Total cells destroyed: {stats['destroyed']}")

# Main simulation loop
def simulate():
    initialize_grid()
    soldiers = []
    stats = {comm: 0 for comm in COMMUNITIES}
    stats['destroyed'] = 0
    
    for iteration in range(1000):  # Run for 1000 years
        # Community expansion
        for comm in COMMUNITIES:
            expand_community(comm)
        
        # Decay
        apply_decay(iteration)
        
        # Soldier management
        if iteration % 20 == 0:  # Spawn soldiers every 20 iterations
            for comm in COMMUNITIES:
                if random.random() < COMMUNITY_TRAITS[comm]["aggression"] * 0.2:
                    x, y = random.randint(1, WIDTH), random.randint(1, HEIGHT)
                    if GRID[y][x] == comm:
                        soldiers.append(Soldier(comm, x, y))
        
        # Soldier movement and combat
        for soldier in soldiers[:]:
            soldier.move()
            destroyed = soldier.attack()
            if destroyed > 0:
                stats['destroyed'] += destroyed
                soldiers.remove(soldier)
        
        # Update stats and display
        if iteration % 10 == 0:
            stats.update({comm: sum(row.count(comm) for row in GRID) for comm in COMMUNITIES})
            display_grid(iteration, stats)
            time.sleep(0.5)

if __name__ == "__main__":
    simulate()