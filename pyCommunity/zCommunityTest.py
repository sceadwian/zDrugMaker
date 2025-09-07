#!/usr/bin/env python3
"""
Improved ASCII community simulation
- Clear separation of MODEL (world state), UPDATE (rules), and VIEW (rendering)
- Fixes runaway growth bug and adds terrain-aware, neighbor-modulated expansion
- Smarter soldier AI: gravitates toward enemies instead of random walk
- Deterministic runs via SEED; tunable speed and print cadence
- Cleaner borders, colors optional, and safer naming (no shadowing built-ins)
Standard library only.
"""

import os
import random
import sys
import time
from dataclasses import dataclass
from typing import List, Tuple, Dict, Iterable

# =========================
# Config
# =========================
SEED = 42                 # Set to None for non-deterministic
MAP_W = 96
MAP_H = 64
PRINT_EVERY = 10          # ticks between renders
TICKS = 20000             # simulation length
SLEEP_SEC = 0.0           # slow down rendering if desired (e.g., 0.02)
USE_COLOR = True          # disable if your terminal doesn't show ANSI colors
BORDER_CHAR = '#'

# Community glyphs (single-width ASCII recommended)
COMMUNITY_A = 'K'
COMMUNITY_B = '8'
COMMUNITY_C = 'O'
COMMUNITY_D = 'q'
COMMUNITIES = [COMMUNITY_A, COMMUNITY_B, COMMUNITY_C, COMMUNITY_D]

# Terrain
GROUND = ' '
POND = 'w'
ROCK = 'M'
VEGETATION = 't'
TERRAINS = [GROUND, POND, ROCK, VEGETATION]

# Colors (ANSI). Will be bypassed if USE_COLOR=False or NO_COLOR set.
COLORS = {
    COMMUNITY_A: '\033[96m',  # Cyan
    COMMUNITY_B: '\033[92m',  # Green
    COMMUNITY_C: '\033[93m',  # Yellow
    COMMUNITY_D: '\033[91m',  # Red
    GROUND:      '\033[0m',   # Reset/default
    POND:        '\033[94m',  # Blue
    ROCK:        '\033[90m',  # Dark Gray
    VEGETATION:  '\033[32m',  # Green
    BORDER_CHAR: '\033[97m',  # White
}
RESET = '\033[0m'

# Terrain expansion modifiers (probability multipliers)
TERRAIN_GROWTH_MOD = {
    GROUND: 1.00,
    VEGETATION: 0.80,
    ROCK: 0.20,
    POND: 0.05,
}

# Baseline per-neighbor expansion chance before modifiers
BASE_EXPANSION_P = 0.12
# Additional boost/penalty per same/enemy neighbor (8-neighborhood)
ALLY_NEIGHBOR_BONUS = 0.05    # up to +0.25
ENEMY_NEIGHBOR_PENALTY = 0.05 # up to -0.25
MAX_NEIGHBOR_BONUS = 0.25
MAX_NEIGHBOR_PENALTY = 0.25
# Limit how many expansion attempts per community per tick to prevent runaway growth
EXPANSION_ATTEMPTS_PER_TICK = 800

# Natural decay settings (cells revert to ground)
DECAY_EVERY = 100
DECAY_RATE_PER_1K = 1  # ~ this many cells per 1000 community cells decay when a decay event happens

# Soldier settings
SOLDIER_SPAWN_EVERY = 50
SOLDIER_MAX_PER_COMMUNITY = 50
SOLDIER_ATTACK_CAP = 3            # max tiles a soldier can destroy in one tick (includes current tile)
SOLDIER_SENSE_RADIUS = 8          # how far a soldier "looks" for enemies when choosing direction
SOLDIER_SPAWN_BASE = 0.02         # baseline spawn factor
SOLDIER_SPAWN_SCALE = 0.30        # additional factor scales with community area fraction

# =========================
# Utility
# =========================

def clamp(p: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if p < lo else hi if p > hi else p


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


# =========================
# World Model
# =========================
class World:
    def __init__(self, w: int, h: int):
        # include a 1-cell border – interior spans [1..h][1..w]
        self.W = w
        self.H = h
        self.grid: List[List[str]] = [[BORDER_CHAR] * (w + 2)]
        for _ in range(h):
            self.grid.append([BORDER_CHAR] + [GROUND] * w + [BORDER_CHAR])
        self.grid.append([BORDER_CHAR] * (w + 2))

        # soldier lists per community
        self.soldiers: Dict[str, List['Soldier']] = {c: [] for c in COMMUNITIES}
        self.destroyed_counts: Dict[str, int] = {c: 0 for c in COMMUNITIES}

        # place random terrain features sparsely
        self._seed_terrain()
        # place initial community seeds
        self._seed_communities()

    # ---------- terrain and seeding ----------
    def _rand_interior(self) -> Tuple[int, int]:
        return random.randint(1, self.H), random.randint(1, self.W)

    def _seed_terrain(self):
        # scatter some ponds/rocks/vegetation; tune density as desired
        elements = [POND, ROCK, VEGETATION]
        n_scatter = (self.W * self.H) // 6  # ~16% coverage with features
        for _ in range(n_scatter):
            x, y = self._rand_interior()
            if self.grid[x][y] == GROUND:
                self.grid[x][y] = random.choice(elements)

    def _seed_communities(self):
        for c in COMMUNITIES:
            while True:
                x, y = self._rand_interior()
                if self.grid[x][y] in TERRAINS:  # not already a community
                    self.grid[x][y] = c
                    break

    # ---------- queries ----------
    def neighbors8(self, x: int, y: int) -> Iterable[Tuple[int, int]]:
        for i in range(x - 1, x + 2):
            for j in range(y - 1, y + 2):
                if (i, j) == (x, y):
                    continue
                if 1 <= i <= self.H and 1 <= j <= self.W:
                    yield (i, j)

    def is_community(self, ch: str) -> bool:
        return ch in COMMUNITIES

    def count_community(self, c: str) -> int:
        return sum(row.count(c) for row in self.grid)

    def positions_of(self, c: str) -> List[Tuple[int, int]]:
        pos = []
        for i in range(1, self.H + 1):
            row = self.grid[i]
            for j in range(1, self.W + 1):
                if row[j] == c:
                    pos.append((i, j))
        return pos

    def frontier_candidates(self, c: str) -> List[Tuple[int, int]]:
        """Return empty/terrain cells adjacent to community c (potential expansion sites)."""
        frontier = set()
        for (i, j) in self.positions_of(c):
            for (ni, nj) in self.neighbors8(i, j):
                if self.grid[ni][nj] in TERRAINS:
                    frontier.add((ni, nj))
        return list(frontier)

    # ---------- updates ----------
    def expand(self, c: str):
        candidates = self.frontier_candidates(c)
        if not candidates:
            return
        random.shuffle(candidates)
        attempts = 0
        for (i, j) in candidates:
            if attempts >= EXPANSION_ATTEMPTS_PER_TICK:
                break
            terr = self.grid[i][j]
            base = BASE_EXPANSION_P * TERRAIN_GROWTH_MOD.get(terr, 0.0)
            # neighbor context
            ally_n = 0
            enemy_n = 0
            for (ni, nj) in self.neighbors8(i, j):
                val = self.grid[ni][nj]
                if val == c:
                    ally_n += 1
                elif self.is_community(val) and val != c:
                    enemy_n += 1
            p = base + min(ally_n * ALLY_NEIGHBOR_BONUS, MAX_NEIGHBOR_BONUS) \
                     - min(enemy_n * ENEMY_NEIGHBOR_PENALTY, MAX_NEIGHBOR_PENALTY)
            p = clamp(p, 0.0, 0.95)
            if random.random() < p:
                self.grid[i][j] = c
            attempts += 1

    def decay(self, c: str):
        if DECAY_EVERY <= 0:
            return
        if world_tick % DECAY_EVERY != 0:
            return
        total = self.count_community(c)
        if total <= 1:
            return
        # scale number of decays with size
        n_decay = max(1, (total // 1000) * DECAY_RATE_PER_1K)
        cells = self.positions_of(c)
        random.shuffle(cells)
        for (i, j) in cells[:n_decay]:
            self.grid[i][j] = GROUND

    def spawn_soldiers(self, c: str):
        if world_tick % SOLDIER_SPAWN_EVERY != 0:
            return
        if len(self.soldiers[c]) >= SOLDIER_MAX_PER_COMMUNITY:
            return
        area_frac = self.count_community(c) / (self.W * self.H)
        spawn_p = SOLDIER_SPAWN_BASE + SOLDIER_SPAWN_SCALE * area_frac
        if random.random() < spawn_p:
            # spawn near the community (pick a random community cell)
            cells = self.positions_of(c)
            if not cells:
                return
            i, j = random.choice(cells)
            self.soldiers[c].append(Soldier(i, j, c))

    def step_soldiers(self, c: str):
        for s in list(self.soldiers[c]):
            s.move(self)
            destroyed = s.attack(self)
            if destroyed > 0:
                # soldier "spent" when they successfully attack
                self.soldiers[c].remove(s)
                self.destroyed_counts[c] += destroyed


# =========================
# Soldier AI
# =========================
@dataclass
class Soldier:
    x: int
    y: int
    community: str

    def move(self, world: World):
        # try to move toward nearest enemy tile within sense radius; else random walk
        target = self._nearest_enemy_tile(world)
        if target:
            tx, ty = target
            dx = 0 if self.x == tx else (-1 if self.x > tx else 1)
            dy = 0 if self.y == ty else (-1 if self.y > ty else 1)
            nx = clamp_int(self.x + dx, 1, world.H)
            ny = clamp_int(self.y + dy, 1, world.W)
            # avoid walking into the border (already constrained), else move
            self.x, self.y = nx, ny
        else:
            # random step
            direction = random.choice(((1,0),(-1,0),(0,1),(0,-1)))
            nx = clamp_int(self.x + direction[0], 1, world.H)
            ny = clamp_int(self.y + direction[1], 1, world.W)
            self.x, self.y = nx, ny

    def _nearest_enemy_tile(self, world: World) -> Tuple[int, int] | None:
        best = None
        best_d2 = 10**9
        x0, y0 = self.x, self.y
        # scan local square
        r = SOLDIER_SENSE_RADIUS
        for i in range(max(1, x0 - r), min(world.H, x0 + r) + 1):
            row = world.grid[i]
            for j in range(max(1, y0 - r), min(world.W, y0 + r) + 1):
                ch = row[j]
                if world.is_community(ch) and ch != self.community:
                    d2 = (i - x0) * (i - x0) + (j - y0) * (j - y0)
                    if d2 < best_d2:
                        best_d2 = d2
                        best = (i, j)
        return best

    def attack(self, world: World) -> int:
        destroyed = 0
        # attack current tile
        if world.is_community(world.grid[self.x][self.y]) and world.grid[self.x][self.y] != self.community:
            world.grid[self.x][self.y] = GROUND
            destroyed += 1
        # attack up to N neighboring enemy tiles
        for (i, j) in world.neighbors8(self.x, self.y):
            if destroyed >= SOLDIER_ATTACK_CAP:
                break
            if world.is_community(world.grid[i][j]) and world.grid[i][j] != self.community:
                world.grid[i][j] = GROUND
                destroyed += 1
        return destroyed


def clamp_int(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else hi if v > hi else v


# =========================
# Rendering
# =========================
class Renderer:
    def __init__(self, world: World):
        self.world = world
        # respect NO_COLOR env var
        self.use_color = USE_COLOR and (os.environ.get('NO_COLOR') is None)

    def draw(self, tick: int):
        clear_screen()
        print(f"Tick: {tick}")
        g = self.world.grid
        for i in range(len(g)):
            row = g[i]
            line_chars: List[str] = []
            for j in range(len(row)):
                ch = row[j]
                # overlay soldiers
                soldier_drawn = False
                if 1 <= i <= self.world.H and 1 <= j <= self.world.W:
                    for c in COMMUNITIES:
                        for s in self.world.soldiers[c]:
                            if s.x == i and s.y == j:
                                line_chars.append(self._colorize(c, 'S'))
                                soldier_drawn = True
                                break
                        if soldier_drawn:
                            break
                if not soldier_drawn:
                    line_chars.append(self._colorize(ch, ch))
            print(''.join(line_chars))
        # legend & stats
        print("\nLegend: K=A, 8=B, O=C, q=D, S=Soldier")
        print("Community sizes:")
        for c in COMMUNITIES:
            print(f"  {c}: {self.world.count_community(c)}")
        print("Destruction counts (by attackers):")
        for c in COMMUNITIES:
            print(f"  {c}: {self.world.destroyed_counts[c]}")

    def _colorize(self, key: str, glyph: str) -> str:
        if not self.use_color:
            return glyph
        return COLORS.get(key, RESET) + glyph + RESET


# =========================
# Main loop
# =========================
if __name__ == '__main__':
    if SEED is not None:
        random.seed(SEED)

    world = World(MAP_W, MAP_H)
    renderer = Renderer(world)

    global world_tick
    world_tick = 0
    try:
        for world_tick in range(1, TICKS + 1):
            # 1) expansion & decay
            for c in COMMUNITIES:
                world.expand(c)
                world.decay(c)

            # 2) soldiers: spawn, move, fight
            for c in COMMUNITIES:
                world.spawn_soldiers(c)
            for c in COMMUNITIES:
                world.step_soldiers(c)

            # 3) render occasionally
            if world_tick % PRINT_EVERY == 0:
                renderer.draw(world_tick)
                if SLEEP_SEC > 0:
                    time.sleep(SLEEP_SEC)

    except KeyboardInterrupt:
        print(f"\nSimulation stopped at tick {world_tick}.")
