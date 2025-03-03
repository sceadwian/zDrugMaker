import random
import os
import time

# ----------------------------
# Configuration and Constants
# ----------------------------

# Grid dimensions
WIDTH = 96
HEIGHT = 64

# Terrain types
GROUND = "GROUND"
WATER = "WATER"
ROCK = "ROCK"
VEGETATION = "VEGETATION"
BORDER = "BORDER"  # fixed border cells

# Symbols to display for each terrain type
TERRAIN_SYMBOLS = {
    GROUND: ".",
    WATER: "~",
    ROCK: "^",
    VEGETATION: "\"",
    BORDER: "#"
}

# Base probabilities for expansion (base chance to convert a neighboring cell)
# For ground and vegetation we use the community's growth trait,
# for water and rock we use the community's adaptability trait.
BASE_CONVERSION = {
    GROUND: 0.5,
    VEGETATION: 0.7,
    WATER: 0.2,
    ROCK: 0.1
}

# Community definitions: each community is represented by a unique symbol and ANSI color.
COMMUNITIES = {
    "A": {"color": "\033[31m"},  # Red
    "B": {"color": "\033[32m"},  # Green
    "C": {"color": "\033[33m"},  # Yellow
    "D": {"color": "\033[34m"},  # Blue
}
ANSI_RESET = "\033[0m"

# Community unique traits affecting expansion, combat, and decay.
# Traits:
#   growth:    affects expansion into friendly terrain (GROUND, VEGETATION)
#   aggression: influences how many enemy cells a soldier may remove
#   adaptability: helps overcome challenging terrains (WATER, ROCK)
#   resilience:   reduces chance of decay
#   mobility:     affects soldier movement speed or ability to traverse rough terrain
COMMUNITY_TRAITS = {
    "A": {"growth": 1.2, "aggression": 1.0, "adaptability": 0.8, "resilience": 0.9, "mobility": 1.0},
    "B": {"growth": 1.1, "aggression": 0.9, "adaptability": 1.0, "resilience": 1.0, "mobility": 1.1},
    "C": {"growth": 1.3, "aggression": 1.2, "adaptability": 0.7, "resilience": 0.8, "mobility": 0.9},
    "D": {"growth": 1.4, "aggression": 0.8, "adaptability": 1.1, "resilience": 1.2, "mobility": 1.0},
}

# Percent of total cells (including border) to be replaced with special terrain
SPECIAL_TERRAIN_PERCENT = 0.25

# Decay parameters: every DECAY_INTERVAL iterations, one cell per community may decay.
DECAY_INTERVAL = 100
BASE_DECAY_RATE = 0.05  # base chance to lose a community cell (divided by resilience)

# Soldier spawn chance (per community per iteration)
SOLDIER_SPAWN_CHANCE = 0.02

# Simulation refresh: print grid every PRINT_INTERVAL iterations.
PRINT_INTERVAL = 10

# Maximum simulation iterations ("years")
MAX_YEARS = 1000

# Global counter for total cells destroyed by decay or combat
total_destroyed = 0

# ----------------------------
# Grid and Initialization
# ----------------------------

def create_grid():
    """
    Create a grid as a 2D list of dictionaries.
    Each cell has:
      - 'terrain': one of the terrain types,
      - 'community': None or the symbol of the community that controls it.
    The border cells (outermost rows/cols) are fixed as BORDER.
    """
    grid = []
    for row in range(HEIGHT):
        row_cells = []
        for col in range(WIDTH):
            # Set border cells
            if row == 0 or row == HEIGHT - 1 or col == 0 or col == WIDTH - 1:
                cell = {"terrain": BORDER, "community": None}
            else:
                # Default interior cells start as GROUND
                cell = {"terrain": GROUND, "community": None}
            row_cells.append(cell)
        grid.append(row_cells)
    return grid

def add_special_terrain(grid):
    """
    Randomly assign WATER, ROCK, or VEGETATION to about 25% of the total grid cells.
    This function avoids border cells.
    """
    num_cells = (WIDTH - 2) * (HEIGHT - 2)
    num_special = int(num_cells * SPECIAL_TERRAIN_PERCENT)
    terrain_types = [WATER, ROCK, VEGETATION]
    count = 0
    while count < num_special:
        row = random.randint(1, HEIGHT - 2)
        col = random.randint(1, WIDTH - 2)
        # Only change cell if it is currently GROUND
        if grid[row][col]["terrain"] == GROUND:
            grid[row][col]["terrain"] = random.choice(terrain_types)
            count += 1

def place_initial_communities(grid):
    """
    For each community, choose a random interior cell that is GROUND and assign it.
    Returns a dictionary mapping community symbols to a list of their starting cell coordinates.
    """
    starting_positions = {}
    for community in COMMUNITIES.keys():
        placed = False
        while not placed:
            row = random.randint(1, HEIGHT - 2)
            col = random.randint(1, WIDTH - 2)
            # Ensure the cell is ground and unoccupied
            if grid[row][col]["terrain"] == GROUND and grid[row][col]["community"] is None:
                grid[row][col]["community"] = community
                starting_positions.setdefault(community, []).append((row, col))
                placed = True
    return starting_positions

# ----------------------------
# Community Expansion
# ----------------------------

def expand_community(grid, community):
    """
    Each cell belonging to 'community' attempts to expand into its neighboring cells.
    The chance to convert depends on the neighbor's terrain type and the community's traits.
    """
    moves = []  # list of potential expansion moves: (row, col, community)
    traits = COMMUNITY_TRAITS[community]

    # Loop over all grid cells to find cells controlled by the community.
    for row in range(1, HEIGHT - 1):
        for col in range(1, WIDTH - 1):
            if grid[row][col]["community"] == community:
                # Check all 8 neighbors (diagonals included)
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        # Skip the current cell
                        if dr == 0 and dc == 0:
                            continue
                        r, c = row + dr, col + dc
                        # Only consider interior cells (skip border)
                        if grid[r][c]["terrain"] == BORDER:
                            continue
                        # Only try to convert cells that are not already claimed
                        if grid[r][c]["community"] is None:
                            terrain = grid[r][c]["terrain"]
                            # Determine which trait to use:
                            if terrain in (GROUND, VEGETATION):
                                effective_prob = BASE_CONVERSION[terrain] * traits["growth"]
                            elif terrain in (WATER, ROCK):
                                effective_prob = BASE_CONVERSION[terrain] * traits["adaptability"]
                            else:
                                effective_prob = 0
                            # Attempt conversion based on probability
                            if random.random() < effective_prob:
                                moves.append((r, c, community))
    # Randomize move order so conflicts are handled randomly
    random.shuffle(moves)
    for r, c, comm in moves:
        if grid[r][c]["community"] is None:
            grid[r][c]["community"] = comm

# ----------------------------
# Decay Mechanic
# ----------------------------

def apply_decay(grid, iteration):
    """
    Every DECAY_INTERVAL iterations, each community may lose one cell.
    The chance to decay is BASE_DECAY_RATE divided by the community's resilience trait.
    """
    global total_destroyed
    if iteration % DECAY_INTERVAL != 0:
        return
    for community in COMMUNITIES.keys():
        # Collect coordinates of all cells owned by the community
        owned = [(r, c) for r in range(1, HEIGHT - 1)
                      for c in range(1, WIDTH - 1)
                      if grid[r][c]["community"] == community]
        if owned:
            r, c = random.choice(owned)
            resilience = COMMUNITY_TRAITS[community]["resilience"]
            if random.random() < (BASE_DECAY_RATE / resilience):
                grid[r][c]["community"] = None
                total_destroyed += 1

# ----------------------------
# Soldier Class and Mechanics
# ----------------------------

class Soldier:
    def __init__(self, community, x, y):
        self.community = community  # the soldier's allegiance
        self.x = x  # row position
        self.y = y  # col position
        # Retrieve traits for easy access
        self.mobility = COMMUNITY_TRAITS[community]["mobility"]
        self.aggression = COMMUNITY_TRAITS[community]["aggression"]

    def move(self, grid):
        """
        Move the soldier randomly to a neighboring cell.
        Soldiers avoid moving onto BORDER cells.
        If moving into water, the chance to move is reduced.
        """
        # Get list of neighbor moves (8 directions)
        directions = [(dr, dc) for dr in [-1, 0, 1] for dc in [-1, 0, 1]
                      if not (dr == 0 and dc == 0)]
        random.shuffle(directions)
        for dr, dc in directions:
            new_x = self.x + dr
            new_y = self.y + dc
            if grid[new_x][new_y]["terrain"] == BORDER:
                continue
            # If the cell is water, reduce chance to move there
            if grid[new_x][new_y]["terrain"] == WATER:
                if random.random() > 0.5 * self.mobility:
                    continue
            # Otherwise move there
            self.x, self.y = new_x, new_y
            break

    def attack(self, grid):
        """
        Soldier checks its current cell and neighbors for enemy community cells.
        Removes enemy cells based on the soldier's aggression trait.
        Returns the number of enemy cells removed.
        After attacking, the soldier is considered spent.
        """
        global total_destroyed
        cells_removed = 0
        # Consider current cell and 8 neighbors
        targets = []
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                r = self.x + dr
                c = self.y + dc
                if r < 1 or r >= HEIGHT - 1 or c < 1 or c >= WIDTH - 1:
                    continue
                cell_comm = grid[r][c]["community"]
                if cell_comm is not None and cell_comm != self.community:
                    targets.append((r, c))
        # Base attack chance: for each enemy cell, use aggression trait to decide removal
        for r, c in targets:
            if random.random() < 0.3 * self.aggression:
                grid[r][c]["community"] = None
                cells_removed += 1
                total_destroyed += 1
        return cells_removed

# ----------------------------
# Soldier Management
# ----------------------------

def spawn_soldiers(grid, soldiers):
    """
    For each community, with a small probability spawn a soldier at a random cell controlled by that community.
    """
    for community in COMMUNITIES.keys():
        # With probability SOLDIER_SPAWN_CHANCE, try to spawn a soldier
        if random.random() < SOLDIER_SPAWN_CHANCE:
            # Find all cells belonging to the community
            cells = [(r, c) for r in range(1, HEIGHT - 1)
                           for c in range(1, WIDTH - 1)
                           if grid[r][c]["community"] == community]
            if cells:
                r, c = random.choice(cells)
                soldiers.append(Soldier(community, r, c))

def update_soldiers(grid, soldiers):
    """
    Update each soldier: move, attempt attack if enemies are found.
    Remove soldiers that have attacked.
    """
    remaining = []
    for soldier in soldiers:
        soldier.move(grid)
        # Attack enemy cells in current neighborhood
        removed = soldier.attack(grid)
        if removed > 0:
            # Soldier is removed after a successful attack
            continue
        # Otherwise, keep soldier for next iteration
        remaining.append(soldier)
    return remaining

# ----------------------------
# Utility Functions
# ----------------------------

def count_community_cells(grid):
    """
    Count how many cells are controlled by each community.
    """
    counts = {comm: 0 for comm in COMMUNITIES.keys()}
    for row in range(1, HEIGHT - 1):
        for col in range(1, WIDTH - 1):
            comm = grid[row][col]["community"]
            if comm is not None:
                counts[comm] += 1
    return counts

def clear_console():
    """
    Clear the console for refreshed visualization.
    """
    os.system('cls' if os.name == 'nt' else 'clear')

def print_grid(grid, iteration):
    """
    Print the grid with ANSI color codes for communities.
    Terrain cells are printed using their designated symbols.
    Also print statistics about community sizes and total cells destroyed.
    """
    clear_console()
    print(f"Year: {iteration}")
    # Build each row as a string
    for row in grid:
        line = ""
        for cell in row:
            if cell["community"] is not None:
                # Print community symbol with its color
                color = COMMUNITIES[cell["community"]]["color"]
                line += color + cell["community"] + ANSI_RESET
            else:
                # Print terrain symbol
                line += TERRAIN_SYMBOLS[cell["terrain"]]
        print(line)
    counts = count_community_cells(grid)
    print("\nCommunity Sizes:")
    for comm, count in counts.items():
        print(f"  {comm}: {count} cells")
    print(f"Total cells destroyed (via decay or combat): {total_destroyed}")

# ----------------------------
# Main Simulation Loop
# ----------------------------

def main():
    grid = create_grid()
    add_special_terrain(grid)
    place_initial_communities(grid)
    soldiers = []  # list to hold active Soldier instances

    for year in range(1, MAX_YEARS + 1):
        # For each community, attempt to expand into neighboring cells
        for community in COMMUNITIES.keys():
            expand_community(grid, community)

        # Randomly spawn soldiers for each community
        spawn_soldiers(grid, soldiers)

        # Update soldier movement and combat; update the soldier list
        soldiers = update_soldiers(grid, soldiers)

        # Apply decay to simulate cell loss (every DECAY_INTERVAL iterations)
        apply_decay(grid, year)

        # Every PRINT_INTERVAL iterations, display the grid and statistics
        if year % PRINT_INTERVAL == 0:
            print_grid(grid, year)
            # Pause briefly so the simulation is viewable
            time.sleep(0.1)

if __name__ == '__main__':
    main()
