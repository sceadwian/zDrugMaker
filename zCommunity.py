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

# Define community colors
COLORS = {
    COMMUNITY_A: '\033[96m',  # Cyan
    COMMUNITY_B: '\033[92m',  # Green
    COMMUNITY_C: '\033[93m',  # Yellow
    COMMUNITY_D: '\033[91m',  # Red
    GROUND: '\033[0m',  # Reset to default
    POND: '\033[94m',  # Blue
    ROCK: '\033[90m',  # Dark Gray
    VEGETATION: '\033[32m',  # Green
    BORDER: '\033[97m',  # White
}

# Define the map
map_width = 96
map_height = 64
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

# Soldier class
class Soldier:
    def __init__(self, x, y, community):
        self.x = x
        self.y = y
        self.community = community

    def move(self):
        direction = random.choice(['up', 'down', 'left', 'right'])
        if direction == 'up':
            self.x -= 1
        elif direction == 'down':
            self.x += 1
        elif direction == 'left':
            self.y -= 1
        elif direction == 'right':
            self.y += 1
        self.x = max(1, min(self.x, map_height))
        self.y = max(1, min(self.y, map_width))

    def attack(self):
        if map[self.x][self.y] in communities and map[self.x][self.y] != self.community:
            map[self.x][self.y] = GROUND

# Initialize soldiers
soldiers = {community: [Soldier(random.randint(1, map_height), random.randint(1, map_width), community)] for community in communities}

# Function to get neighboring cells within a given radius
def get_neighbors(x, y, radius=1):
    neighbors = []
    for i in range(x-radius, x+radius+1):
        for j in range(y-radius, y+radius+1):
            if (i, j) != (x, y) and 1 <= i <= map_height and 1 <= j <= map_width:
                neighbors.append((i, j))
    return neighbors

# Function to expand a community
def expand_community(community):
    growth_rate = {
        GROUND: 15,
        POND: 20,
        ROCK: 10,
        VEGETATION: 25,
    }
    
    locations = [(i, j) for i in range(1, map_height+1) for j in range(1, map_width+1) if map[i][j] == community]
    
    for location in locations:
        x, y = location
        neighbors = get_neighbors(x, y, 1)
        for neighbor in neighbors:
            nx, ny = neighbor
            if map[nx][ny] in elements:
                map[nx][ny] = community if random.randint(1, 10) <= growth_rate[map[nx][ny]] else map[nx][ny]

    if year % 10 == 0 and random.random() < 0.2 * GROWTH_RATE[community]:
        while True:
            x, y = random.randint(1, map_height), random.randint(1, map_width)
            if map[x][y] not in communities and any(map[nx][ny] == community for nx, ny in get_neighbors(x, y)):
                map[x][y] = community
                break

def decay_community(community):
    community_cells = [(i, j) for i in range(1, map_height+1) for j in range(1, map_width+1) if map[i][j] == community]
    if len(community_cells) > 1:
        x, y = random.choice(community_cells)
        map[x][y] = GROUND

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def count_community(community):
    return sum(row.count(community) for row in map)

years = 500000
for year in range(years):
    try:
        for community in communities:
            expand_community(community)
            if year % 100 == 0:
                decay_community(community)
            for soldier in soldiers[community]:
                soldier.move()
                soldier.attack()

        if year % 50 == 0:
            for community in communities:
                if random.random() < count_community(community) / (map_width * map_height):
                    soldiers[community].append(Soldier(random.randint(1, map_height), random.randint(1, map_width), community))

        if year % 10 == 0:
            clear()
            print(f"Year: {year}")
            for i, row in enumerate(map):
                row_string = ''
                for j, cell in enumerate(row):
                    for community in communities:
                        if any(soldier.x == i and soldier.y == j for soldier in soldiers[community]):
                            row_string += COLORS[community] + 'S'
                            break
                    else:
                        row_string += COLORS[cell] + cell
                print(row_string)

            print("Community sizes:")
            print(f"{COMMUNITY_A}: {count_community(COMMUNITY_A)}")
            print(f"{COMMUNITY_B}: {count_community(COMMUNITY_B)}")
            print(f"{COMMUNITY_C}: {count_community(COMMUNITY_C)}")
            print(f"{COMMUNITY_D}: {count_community(COMMUNITY_D)}")

        time.sleep(0.000000002)
    except KeyboardInterrupt:
        print(f"\nSimulation stopped after {year+1} years.")
        break
