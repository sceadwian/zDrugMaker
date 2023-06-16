import random
import time
import os

# Define map constants
GROUND = ' '
POND = 'w'
ROCK = 'M'
VEGETATION = 't'
BORDER = '#'

# Define community constants
COMMUNITY_A = 'K'
COMMUNITY_B = '8'
COMMUNITY_C = 'O'
COMMUNITY_D = 'q'

# Define growth rates
GROWTH_RATE = {
    COMMUNITY_A: 1.2,
    COMMUNITY_B: 1.1,
    COMMUNITY_C: 1.3,
    COMMUNITY_D: 1.4,
}

# Define the map
map_width = 96  # Increased width
map_height = 64  # Reduced height
map = [[GROUND]*map_width for _ in range(map_height)]

# Add border to the map
map = [[BORDER]*(map_width+2)] + [[BORDER]+row+[BORDER] for row in map] + [[BORDER]*(map_width+2)]

# Randomly distribute other elements
elements = [POND, ROCK, VEGETATION]
for _ in range(map_width):
    x, y = random.randint(1, map_height), random.randint(1, map_width)
    map[x][y] = random.choice(elements)

# Initialize communities
communities = [COMMUNITY_A, COMMUNITY_B, COMMUNITY_C, COMMUNITY_D]
for community in communities:
    x, y = random.randint(1, map_height), random.randint(1, map_width)
    map[x][y] = community

# Function to get neighboring cells within a given radius
def get_neighbors(x, y, radius):
    neighbors = []
    for i in range(x-radius, x+radius+1):
        for j in range(y-radius, y+radius+1):
            if 1 <= i <= map_height and 1 <= j <= map_width:
                neighbors.append((i, j))
    return neighbors

# Function to expand a community
def expand_community(community):
    growth_rate = {
        GROUND: 20,  # greatly increased growth rates
        POND: 10,
        ROCK: 15,
        VEGETATION: 20,
    }
    
    # Find the current community locations
    locations = [(i, j) for i in range(1, map_height+1) for j in range(1, map_width+1) if map[i][j] == community]
    
    # Try to expand the community from each location
    for location in locations:
        x, y = location
        neighbors = get_neighbors(x, y, 3)  # get neighboring cells within radius of 3
        for neighbor in neighbors:
            nx, ny = neighbor
            if map[nx][ny] in elements:
                map[nx][ny] = community if random.randint(1, 10) <= growth_rate[map[nx][ny]] else map[nx][ny]

    # Spawn a new settlement probabilistically every 10 years, influenced by community growth rate
    if year % 10 == 0 and random.random() < 0.2 * GROWTH_RATE[community]:
        while True:
            x, y = random.randint(1, map_height), random.randint(1, map_width)
            if map[x][y] not in communities:
                map[x][y] = community
                break
# Function to clear console
def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

# Function to count community size
def count_community(community):
    return sum(row.count(community) for row in map)

# Run the simulation
years = 2000
for year in range(years):
    try:
        for community in communities:
            expand_community(community)

        # Only update the console every 10 time steps
        if year % 10 == 0:
            # Clear the console and print the current state of the map
            clear()
            print(f"Year: {year}")
            for row in map:
                print(''.join(row))

            # Print community sizes
            print("Community sizes:")
            print(f"{COMMUNITY_A}: {count_community(COMMUNITY_A)}")
            print(f"{COMMUNITY_B}: {count_community(COMMUNITY_B)}")
            print(f"{COMMUNITY_C}: {count_community(COMMUNITY_C)}")
            print(f"{COMMUNITY_D}: {count_community(COMMUNITY_D)}")

        # Pause between each turn
        time.sleep(0.01)
    except KeyboardInterrupt:
        print(f"\nSimulation stopped after {year+1} years.")
        break
