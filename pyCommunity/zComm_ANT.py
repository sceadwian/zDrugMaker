import random
import os
import time
import math
from typing import List, Dict, Tuple, Set

# Constants for terrain types
GROUND = " "
WATER = "~"
ROCK = "#"
VEGETATION = "*"

# Constants for communities
COMMUNITY_A = "A"
COMMUNITY_B = "B"
COMMUNITY_C = "C"
COMMUNITY_D = "D"

# ANSI color codes
COLORS = {
    GROUND: "\033[0;37m",      # White
    WATER: "\033[0;34m",       # Blue
    ROCK: "\033[0;90m",        # Dark gray
    VEGETATION: "\033[0;32m",  # Green
    COMMUNITY_A: "\033[0;31m", # Red
    COMMUNITY_B: "\033[0;35m", # Magenta
    COMMUNITY_C: "\033[0;33m", # Yellow
    COMMUNITY_D: "\033[0;36m", # Cyan
    "RESET": "\033[0m"         # Reset color
}

# Community traits
COMMUNITY_TRAITS = {
    COMMUNITY_A: {"growth": 1.2, "aggression": 1.0, "adaptability": 0.8, "resilience": 0.9, "mobility": 1.0},
    COMMUNITY_B: {"growth": 1.1, "aggression": 0.9, "adaptability": 1.0, "resilience": 1.0, "mobility": 1.1},
    COMMUNITY_C: {"growth": 1.3, "aggression": 1.2, "adaptability": 0.7, "resilience": 0.8, "mobility": 0.9},
    COMMUNITY_D: {"growth": 1.4, "aggression": 0.8, "adaptability": 1.1, "resilience": 1.2, "mobility": 1.0},
}

# Map dimensions
WIDTH = 96
HEIGHT = 64

class Soldier:
    def __init__(self, community: str, x: int, y: int):
        self.community = community
        self.x = x
        self.y = y
        self.lifespan = random.randint(50, 150)  # Random lifespan for soldiers
    
    def move(self, world) -> None:
        """Move the soldier randomly based on community mobility trait."""
        # Get the mobility factor for this soldier's community
        mobility = COMMUNITY_TRAITS[self.community]["mobility"]
        
        # Determine maximum movement distance based on mobility
        max_distance = max(1, round(mobility * 2))
        
        # Try to move up to max_distance times
        for _ in range(max_distance):
            possible_moves = []
            
            # Check all adjacent cells
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    
                    nx, ny = self.x + dx, self.y + dy
                    
                    # Skip if out of bounds
                    if nx < 0 or nx >= WIDTH or ny < 0 or ny >= HEIGHT:
                        continue
                    
                    # Skip if the cell is a rock (unless community has high adaptability)
                    if world.terrain[ny][nx] == ROCK and random.random() > COMMUNITY_TRAITS[self.community]["adaptability"] * 0.5:
                        continue
                    
                    # Water slows movement based on adaptability
                    if world.terrain[ny][nx] == WATER and random.random() > COMMUNITY_TRAITS[self.community]["adaptability"]:
                        continue
                    
                    possible_moves.append((nx, ny))
            
            if possible_moves:
                self.x, self.y = random.choice(possible_moves)
            else:
                break  # No valid moves available
    
    def attack(self, world) -> bool:
        """
        Attack enemy cells in vicinity. Return True if soldier should be removed after attack.
        """
        # Check current and adjacent cells for enemies
        targets = []
        
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                nx, ny = self.x + dx, self.y + dy
                
                # Skip if out of bounds
                if nx < 0 or nx >= WIDTH or ny < 0 or ny >= HEIGHT:
                    continue
                
                # If cell contains an enemy community, add it to targets
                if world.cells[ny][nx] in [COMMUNITY_A, COMMUNITY_B, COMMUNITY_C, COMMUNITY_D] and world.cells[ny][nx] != self.community:
                    targets.append((nx, ny))
        
        # Attack based on aggression trait
        aggression = COMMUNITY_TRAITS[self.community]["aggression"]
        attacks = max(1, round(aggression * 3))  # Number of attacks based on aggression
        
        attacked = False
        for _ in range(min(attacks, len(targets))):
            if targets:
                # Choose a random target and attack it
                tx, ty = random.choice(targets)
                targets.remove((tx, ty))
                
                # Higher aggression increases attack success probability
                if random.random() < aggression:
                    # Record the cell as destroyed for statistics
                    world.cells_destroyed[world.cells[ty][tx]] += 1
                    world.cells[ty][tx] = GROUND  # Convert back to ground
                    attacked = True
        
        # Decrement lifespan
        self.lifespan -= 1
        
        # Return True if soldier should be removed (attacked or died of old age)
        return attacked or self.lifespan <= 0

class World:
    def __init__(self):
        self.terrain = [[GROUND for _ in range(WIDTH)] for _ in range(HEIGHT)]
        self.cells = [[GROUND for _ in range(WIDTH)] for _ in range(HEIGHT)]
        self.soldiers = []
        self.stats = {COMMUNITY_A: 0, COMMUNITY_B: 0, COMMUNITY_C: 0, COMMUNITY_D: 0}
        self.cells_destroyed = {COMMUNITY_A: 0, COMMUNITY_B: 0, COMMUNITY_C: 0, COMMUNITY_D: 0}
        self.year = 0
    
    def initialize(self) -> None:
        """Initialize the world with terrain and starting communities."""
        # Generate terrain
        self._generate_terrain()
        
        # Place initial community settlements
        self._place_initial_communities()
    
    def _generate_terrain(self) -> None:
        """Generate terrain with water, rocks, and vegetation."""
        # Create border
        for y in range(HEIGHT):
            for x in range(WIDTH):
                if x == 0 or x == WIDTH - 1 or y == 0 or y == HEIGHT - 1:
                    self.terrain[y][x] = ROCK
        
        # Fill interior with random terrain (25% special terrain)
        for y in range(1, HEIGHT - 1):
            for x in range(1, WIDTH - 1):
                r = random.random()
                if r < 0.08:  # 8% water
                    self.terrain[y][x] = WATER
                elif r < 0.16:  # 8% rocks
                    self.terrain[y][x] = ROCK
                elif r < 0.25:  # 9% vegetation
                    self.terrain[y][x] = VEGETATION
                else:  # 75% ground
                    self.terrain[y][x] = GROUND
        
        # Create some water bodies (ponds)
        for _ in range(5):
            center_x = random.randint(10, WIDTH - 10)
            center_y = random.randint(10, HEIGHT - 10)
            size = random.randint(3, 8)
            
            for y in range(center_y - size, center_y + size):
                for x in range(center_x - size, center_x + size):
                    if 0 < x < WIDTH - 1 and 0 < y < HEIGHT - 1:
                        # Create circular-ish shapes for ponds
                        dist = math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
                        if dist < size * random.uniform(0.7, 1.0):
                            self.terrain[y][x] = WATER
        
        # Create some vegetation clusters
        for _ in range(8):
            center_x = random.randint(10, WIDTH - 10)
            center_y = random.randint(10, HEIGHT - 10)
            size = random.randint(4, 10)
            
            for y in range(center_y - size, center_y + size):
                for x in range(center_x - size, center_x + size):
                    if 0 < x < WIDTH - 1 and 0 < y < HEIGHT - 1:
                        # Create irregular shapes for vegetation
                        dist = math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
                        if dist < size * random.uniform(0.6, 0.9) and random.random() < 0.7:
                            self.terrain[y][x] = VEGETATION
    
    def _place_initial_communities(self) -> None:
        """Place the initial communities in different quadrants."""
        quadrants = [
            (WIDTH // 4, HEIGHT // 4),               # Top-left
            (WIDTH // 4 * 3, HEIGHT // 4),           # Top-right
            (WIDTH // 4, HEIGHT // 4 * 3),           # Bottom-left
            (WIDTH // 4 * 3, HEIGHT // 4 * 3)        # Bottom-right
        ]
        
        communities = [COMMUNITY_A, COMMUNITY_B, COMMUNITY_C, COMMUNITY_D]
        
        for i, community in enumerate(communities):
            center_x, center_y = quadrants[i]
            
            # Avoid placing on rocks or water
            attempts = 0
            while attempts < 100:
                offset_x, offset_y = random.randint(-10, 10), random.randint(-10, 10)
                x, y = center_x + offset_x, center_y + offset_y
                
                if 0 < x < WIDTH - 1 and 0 < y < HEIGHT - 1:
                    if self.terrain[y][x] != ROCK and self.terrain[y][x] != WATER:
                        # Place initial settlement
                        settlement_size = random.randint(3, 5)
                        for sy in range(y - settlement_size // 2, y + settlement_size // 2 + 1):
                            for sx in range(x - settlement_size // 2, x + settlement_size // 2 + 1):
                                if 0 < sx < WIDTH - 1 and 0 < sy < HEIGHT - 1:
                                    if random.random() < 0.7:  # Make settlements a bit irregular
                                        self.cells[sy][sx] = community
                        break
                
                attempts += 1
    
    def expand_community(self, community: str) -> None:
        """Expand a community to adjacent cells based on their traits."""
        growth_factor = COMMUNITY_TRAITS[community]["growth"]
        adaptability = COMMUNITY_TRAITS[community]["adaptability"]
        
        # Find all cells of this community
        community_cells = []
        for y in range(HEIGHT):
            for x in range(WIDTH):
                if self.cells[y][x] == community:
                    community_cells.append((x, y))
        
        # Try to expand from each cell
        for x, y in community_cells:
            # Check adjacent cells for expansion
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    
                    nx, ny = x + dx, y + dy
                    
                    # Skip if out of bounds
                    if nx < 0 or nx >= WIDTH or ny < 0 or ny >= HEIGHT:
                        continue
                    
                    # Skip if the cell is not empty
                    if self.cells[ny][nx] != GROUND:
                        continue
                    
                    # Determine expansion probability based on terrain and traits
                    base_probability = 0.02 * growth_factor  # Base expansion rate
                    
                    # Adjust for terrain
                    if self.terrain[ny][nx] == WATER:
                        # Water is difficult to convert
                        probability = base_probability * 0.3 * adaptability
                    elif self.terrain[ny][nx] == ROCK:
                        # Rocks are very difficult to convert
                        probability = base_probability * 0.1 * adaptability
                    elif self.terrain[ny][nx] == VEGETATION:
                        # Vegetation is easier to convert
                        probability = base_probability * 1.5
                    else:  # GROUND
                        probability = base_probability
                    
                    # Try to expand
                    if random.random() < probability:
                        self.cells[ny][nx] = community
    
    def apply_decay(self) -> None:
        """Randomly remove community cells to simulate decay."""
        # Find all community cells
        for y in range(HEIGHT):
            for x in range(WIDTH):
                if self.cells[y][x] in [COMMUNITY_A, COMMUNITY_B, COMMUNITY_C, COMMUNITY_D]:
                    community = self.cells[y][x]
                    resilience = COMMUNITY_TRAITS[community]["resilience"]
                    
                    # Decay probability inversely proportional to resilience
                    if random.random() < 0.005 / resilience:
                        self.cells[y][x] = GROUND
    
    def spawn_soldiers(self) -> None:
        """Spawn new soldiers for each community."""
        # Count current community sizes
        community_sizes = {COMMUNITY_A: 0, COMMUNITY_B: 0, COMMUNITY_C: 0, COMMUNITY_D: 0}
        community_cells = {COMMUNITY_A: [], COMMUNITY_B: [], COMMUNITY_C: [], COMMUNITY_D: []}
        
        for y in range(HEIGHT):
            for x in range(WIDTH):
                if self.cells[y][x] in community_sizes:
                    community_sizes[self.cells[y][x]] += 1
                    community_cells[self.cells[y][x]].append((x, y))
        
        # Spawn soldiers proportional to community size
        for community, size in community_sizes.items():
            # Base soldier spawn rate
            spawn_rate = 0.01
            
            # Adjust based on aggression
            aggression = COMMUNITY_TRAITS[community]["aggression"]
            adjusted_rate = spawn_rate * aggression
            
            # Determine how many soldiers to spawn
            num_to_spawn = max(1, int(size * adjusted_rate))
            
            # Spawn soldiers at random community cells
            for _ in range(num_to_spawn):
                if community_cells[community]:
                    x, y = random.choice(community_cells[community])
                    self.soldiers.append(Soldier(community, x, y))
    
    def update_soldiers(self) -> None:
        """Update all soldiers (move and attack)."""
        remaining_soldiers = []
        
        for soldier in self.soldiers:
            # Move the soldier
            soldier.move(self)
            
            # Attack and determine if soldier should be removed
            should_remove = soldier.attack(self)
            
            if not should_remove:
                remaining_soldiers.append(soldier)
        
        self.soldiers = remaining_soldiers
    
    def update_stats(self) -> None:
        """Update community statistics."""
        self.stats = {COMMUNITY_A: 0, COMMUNITY_B: 0, COMMUNITY_C: 0, COMMUNITY_D: 0}
        
        for y in range(HEIGHT):
            for x in range(WIDTH):
                if self.cells[y][x] in self.stats:
                    self.stats[self.cells[y][x]] += 1
    
    def display(self) -> None:
        """Display the current state of the world."""
        # Clear the screen
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Print header
        print(f"Year: {self.year}")
        
        # Print the grid
        for y in range(HEIGHT):
            for x in range(WIDTH):
                # Determine what to display
                if self.cells[y][x] in [COMMUNITY_A, COMMUNITY_B, COMMUNITY_C, COMMUNITY_D]:
                    symbol = self.cells[y][x]
                    color = COLORS[symbol]
                else:
                    symbol = self.terrain[y][x]
                    color = COLORS[symbol]
                
                # Check if there's a soldier here
                has_soldier = False
                for soldier in self.soldiers:
                    if soldier.x == x and soldier.y == y:
                        symbol = soldier.community.lower()  # Lowercase for soldiers
                        color = COLORS[soldier.community]
                        has_soldier = True
                        break
                
                print(f"{color}{symbol}{COLORS['RESET']}", end="")
            print()
        
        # Print statistics
        print("\nCommunity Statistics:")
        for community, count in self.stats.items():
            growth = COMMUNITY_TRAITS[community]["growth"]
            aggression = COMMUNITY_TRAITS[community]["aggression"]
            adaptability = COMMUNITY_TRAITS[community]["adaptability"]
            resilience = COMMUNITY_TRAITS[community]["resilience"]
            mobility = COMMUNITY_TRAITS[community]["mobility"]
            
            print(f"{COLORS[community]}Community {community}{COLORS['RESET']}: " + 
                  f"{count} cells, {self.cells_destroyed[community]} destroyed | " +
                  f"G:{growth:.1f} A:{aggression:.1f} AD:{adaptability:.1f} R:{resilience:.1f} M:{mobility:.1f}")
        
        print(f"\nSoldiers: {len(self.soldiers)}")
        soldier_counts = {COMMUNITY_A: 0, COMMUNITY_B: 0, COMMUNITY_C: 0, COMMUNITY_D: 0}
        for soldier in self.soldiers:
            soldier_counts[soldier.community] += 1
        
        for community, count in soldier_counts.items():
            print(f"{COLORS[community]}Community {community}{COLORS['RESET']} soldiers: {count}")

def simulate(years: int, display_interval: int = 10) -> None:
    """Run the simulation for a given number of years."""
    world = World()
    world.initialize()
    
    for year in range(years):
        world.year = year + 1
        
        # Community actions
        for community in [COMMUNITY_A, COMMUNITY_B, COMMUNITY_C, COMMUNITY_D]:
            world.expand_community(community)
        
        # Apply decay every 10 years
        if year % 10 == 0:
            world.apply_decay()
        
        # Spawn new soldiers every 5 years
        if year % 5 == 0:
            world.spawn_soldiers()
        
        # Update soldiers every year
        world.update_soldiers()
        
        # Update statistics
        world.update_stats()
        
        # Display the world at regular intervals
        if year % display_interval == 0 or year == years - 1:
            world.display()
            time.sleep(0.5)  # Pause to allow viewing

if __name__ == "__main__":
    # Run simulation for 500 years, displaying every 10 years
    simulate(500, 10)