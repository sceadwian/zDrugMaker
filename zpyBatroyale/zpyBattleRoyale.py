"""zpyBattleRoyale.py — roster-based battle royale simulation prototype.

zpy naming schema: zpyNameOfScript (roster-based scripts living in pyToonRepository).

Reads competitors from universal_characters_master.csv (roster is read-only) and
the arena from zmapArenaWideTall01.zmap. The user selects 20 competitors; the sim
runs tick-based until one survivor remains. Text CLI, stdlib only.

Core loop per tick:
  zone collapse -> AI state decisions -> movement -> tile effects (stash/trap/
  medical/POI) -> detection (perception vs stealth) -> combat -> upkeep.

Behaviour states carry six priority weights (speed, stamina use, stamina
recovery, perception, stealth, readiness) that scale the derived stats.

Interactive mode animates in place (ANSI redraw, map auto-fit to the terminal)
with drama-weighted pacing: quiet ticks run briskly, combat slows down so each
exchange can be read, eliminations hold the frame and raise a banner, and the
endgame plays out deliberately. Live controls: [space] pause, [+]/[-] pace,
[q] skip to results.

Run interactively:   python zpyBattleRoyale.py [--pace 1.5] [--scale 1-6]
Run non-interactive: python zpyBattleRoyale.py --auto [--seed 123] [--quiet]
"""

import argparse
import csv
import math
import os
import random
import shutil
import sys
import time

try:
    import msvcrt  # Windows-only: live keyboard controls during the match
except ImportError:
    msvcrt = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROSTER_CSV = os.path.join(BASE_DIR, "universal_characters_master.csv")
MAP_FILE = os.path.join(BASE_DIR, "zmapArenaWideTall01.zmap")

# ---------------------------------------------------------------- constants

PICK_COUNT = 20          # competitors entering the arena
MAX_TICKS = 700
FRAME_EVERY = 2          # ticks between redraws when nothing is happening
EVENT_FEED = 8           # recent event lines shown under the map
MAP_SCALE = None         # None = auto-fit to terminal; set an int (1-6) to force

# drama-weighted pacing: seconds per frame, chosen by the most dramatic
# event of the current tick (0 quiet, 1 minor, 2 combat, 3 elimination)
PACE_DELAYS = {0: 0.25, 1: 0.5, 2: 0.9, 3: 2.2}
ENDGAME_SLOWDOWN = 1.4   # extra delay multiplier once <=4 remain
BANNER_SECONDS = 5.0     # how long an elimination banner stays up

CLR_DRAMA = {3: "\x1b[1;31m", 2: "\x1b[97m", 1: "\x1b[33m", 0: "\x1b[2m"}
CLR_RESET = "\x1b[0m"
DECIDE_EVERY = 4         # ticks between AI state reassessments
MAX_CELLS_PER_TICK = 4

ZONE_START_TICK = 140    # arena collapse begins
ZONE_SHRINK_EVERY = 5    # ticks per 1-cell margin growth
ZONE_DAMAGE = 3.0        # hp per tick outside the safe zone

PATH_MEM_VISIT = 1.5     # movement-memory penalty added to a just-left cell
PATH_MEM_BLOCKED = 3.0   # heavier penalty where a route failed to progress
PATH_MEM_DECAY = 0.85    # per-tick decay of movement-memory penalties
PATH_MEM_CAP = 6.0       # max penalty a single cell can accumulate
PATH_MEM_MAX = 48        # cells remembered per toon before pruning

STASH_STOCK = 2          # weapons per stash before it runs dry
TRAP_DAMAGE = (15, 35)
MEDICAL_HEAL = 4.0       # hp per tick standing on a medical tile
THREAT_MEMORY = 12       # ticks a last-seen enemy position is remembered

# 2-char display tiles, doubled-width rendering (map metadata: 120x100 -> 240 wide)
TILE_DISPLAY = {
    "open_ground": "  ",
    "wall": "██",         # ██
    "forest": "♣♣",       # ♣♣
    "water": "≈≈",        # ≈≈
    "weapon_stash": "⚔ ",      # ⚔
    "point_of_interest": "◎ ", # ◎
    "vantage_point": "▲▲",# ▲▲ (high ground)
    "medical": "✚ ",           # ✚
    "trap": "!!",
    "collapsed": "░░",    # ░░ outside the safe zone
}

# which tile wins when a downsampled block holds several kinds
TILE_PRIORITY = {
    "weapon_stash": 9,
    "medical": 8,
    "trap": 7,
    "point_of_interest": 6,
    "vantage_point": 5,
    "wall": 4,
    "water": 3,
    "forest": 2,
    "open_ground": 1,
}

# terrain -> (move_cost, stamina_mult, passable)
TERRAIN = {
    "open_ground":       (1.0, 1.0, True),
    "wall":              (0.0, 0.0, False),
    "forest":            (1.5, 1.2, True),
    "water":             (2.5, 2.0, True),
    "weapon_stash":      (1.0, 1.0, True),
    "point_of_interest": (1.0, 1.0, True),
    "vantage_point":     (1.3, 1.3, True),
    "medical":           (1.0, 1.0, True),
    "trap":              (1.0, 1.0, True),
}

# state -> (speed, stam_use, stam_recov, perception, stealth, readiness)
BEHAVIOUR_STATES = {
    "rushing":      (4, 3, 0, 2, 0, 1),
    "cautious":     (1, 1, 2, 3, 2, 1),
    "aggressive":   (3, 2, 0, 2, 0, 3),
    "resting":      (0, 0, 5, 2, 3, 0),
    "camping":      (0, 0, 1, 5, 3, 2),
    "sneaking":     (1, 0, 1, 3, 3, 2),
    "scouting":     (2, 2, 1, 3, 1, 1),
    "defensive":    (1, 2, 1, 2, 1, 3),
    "strategizing": (1, 1, 3, 2, 1, 2),
    "vigilant":     (1, 2, 3, 3, 0, 1),
    "hunting":      (2, 1, 0, 4, 2, 1),
    "fleeing":      (4, 3, 0, 3, 0, 0),
    "hiding":       (0, 0, 2, 3, 3, 2),
    "panicking":    (2, 4, 2, 0, 1, 1),
}

W_SPEED, W_STAMUSE, W_RECOV, W_PERC, W_STEALTH, W_READY = range(6)

# one-glyph stance icons for the survivor panel
STATE_GLYPHS = {
    "rushing": "»",
    "cautious": "?",
    "aggressive": "⚔",
    "resting": "☾",
    "camping": "⌂",
    "sneaking": "…",
    "scouting": "◎",
    "defensive": "▣",
    "strategizing": "✎",
    "vigilant": "!",
    "hunting": "⌖",
    "fleeing": "↯",
    "hiding": "▓",
    "panicking": "X",
}

# stance color families: red = attack, magenta = guard, yellow = flight/speed,
# cyan = stealth, green = recovery, plain = neutral exploring
STATE_CLR = {
    "aggressive": "\x1b[91m",
    "hunting": "\x1b[91m",
    "defensive": "\x1b[95m",
    "vigilant": "\x1b[95m",
    "rushing": "\x1b[93m",
    "fleeing": "\x1b[93m",
    "panicking": "\x1b[93m",
    "sneaking": "\x1b[96m",
    "hiding": "\x1b[96m",
    "camping": "\x1b[96m",
    "resting": "\x1b[92m",
    "strategizing": "\x1b[92m",
    "cautious": "\x1b[37m",
    "scouting": "\x1b[37m",
}

TILE_CLR = {
    "open_ground": "",
    "wall": "\x1b[90m",
    "forest": "\x1b[32m",
    "water": "\x1b[94m",
    "weapon_stash": "\x1b[93m",
    "point_of_interest": "\x1b[95m",
    "vantage_point": "\x1b[96m",
    "medical": "\x1b[92m",
    "trap": "\x1b[91m",
    "collapsed": "\x1b[2;90m",
}
MARKER_CLR = "\x1b[1;30;103m"  # toon markers: bold black on yellow


def hp_clr(v):
    return "\x1b[92m" if v > 66 else ("\x1b[93m" if v > 33 else "\x1b[91m")

# weapon: (name, damage_bonus, range, rarity_weight)
WEAPON_TABLE = [
    ("improvised club", 4, 1, 25),
    ("knife",           7, 1, 25),
    ("spear",          10, 2, 18),
    ("bow",             9, 4, 12),
    ("axe",            12, 1, 12),
    ("sword",          13, 1, 8),
]
UNARMED = ("bare hands", 0, 1, 0)

DIRS8 = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]


# --------------------------------------------------------------- map loader

class Arena:
    def __init__(self, path):
        self.legend = {}
        self.name = os.path.basename(path)
        rows = []
        section = None
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.rstrip("\n")
                strip = line.strip()
                if strip.startswith("[") and strip.endswith("]"):
                    section = strip[1:-1]
                    continue
                if section == "metadata":
                    if "=" in strip:
                        k, v = [s.strip() for s in strip.split("=", 1)]
                        if k == "width":
                            self.width = int(v)
                        elif k == "height":
                            self.height = int(v)
                elif section == "legend":
                    if "=" in strip:
                        k, v = [s.strip() for s in strip.split("=", 1)]
                        self.legend[k] = v
                elif section == "map":
                    if strip:
                        rows.append(line)
        self.width = getattr(self, "width", max(len(r) for r in rows))
        self.height = getattr(self, "height", len(rows))
        self.grid = []
        for y in range(self.height):
            line = rows[y] if y < len(rows) else ""
            line = line.ljust(self.width, ".")
            self.grid.append([self.legend.get(ch, "open_ground") for ch in line[: self.width]])
        self.stash_stock = {}
        for y in range(self.height):
            for x in range(self.width):
                if self.grid[y][x] == "weapon_stash":
                    self.stash_stock[(x, y)] = STASH_STOCK

    def tile(self, x, y):
        return self.grid[y][x]

    def in_bounds(self, x, y):
        return 0 <= x < self.width and 0 <= y < self.height

    def passable(self, x, y):
        return self.in_bounds(x, y) and TERRAIN[self.tile(x, y)][2]

    def tiles_of(self, name):
        return [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if self.grid[y][x] == name
        ]

    def consume(self, x, y):
        """Deplete a one-shot tile (trap fired, stash emptied, POI looted)."""
        self.grid[y][x] = "open_ground"


# -------------------------------------------------------------------- toons

class Toon:
    def __init__(self, num, row):
        self.num = num
        self.row = row
        self.name = row.get("display_name") or row.get("first_name") or "?"
        self.short = row.get("short_name", "???")
        self.x = 0
        self.y = 0
        self.hp = 100.0
        self.stam = 100.0
        self.weapon = None
        self.state = "rushing"
        self.alive = True
        self.kills = 0
        self.dmg_dealt = 0.0
        self.death_tick = None
        self.cause = ""
        self.target = None            # (x, y) movement goal
        self.threat = None            # (toon, tick, x, y) last detected enemy
        self.looted_pois = set()
        self.stuck = 0
        self.last_pos = (0, 0)
        self.move_debt = 0.0
        self.path_mem = {}            # (x, y) -> decaying avoidance penalty

    def s(self, attr):
        try:
            return int(self.row.get(attr) or 40)
        except ValueError:
            return 40

    def w(self, idx):
        return BEHAVIOUR_STATES[self.state][idx]

    def power(self):
        """Rough combat power estimate used for fight-or-flee decisions."""
        wpn = self.weapon or UNARMED
        return (
            self.s("strength") * 0.4
            + (self.s("coordination") + self.s("dexterity")) * 0.15
            + self.s("agility") * 0.3
            + wpn[1] * 2.5
            + self.hp * 0.5
        )

    def label(self):
        return "%s (%02d)" % (self.name, self.num)


# --------------------------------------------------------------- simulation

class Game:
    def __init__(self, arena, toons, seed, interactive=True, quiet=False,
                 scale=MAP_SCALE, pace=1.0):
        self.arena = arena
        self.toons = toons
        self.seed = seed
        self.fixed_scale = scale
        self.pace = pace             # delay multiplier: <1 faster, >1 slower
        self.rng = random.Random(seed)
        self.tick = 0
        self.margin = 0
        self.log = []                # (line, drama) pairs
        self.tick_drama = 0          # most dramatic event level this tick
        self.banner = ""
        self.banner_until = 0.0
        self.first_blood = None
        self.interactive = interactive
        self.animate = interactive   # in-place animated frames vs streamed text
        self.paused = False
        self.quiet = quiet
        self.placements = []  # dead toons in death order

    # ---- logging

    def event(self, msg, drama=1):
        line = "[t%03d] %s" % (self.tick, msg)
        self.log.append((line, drama))
        self.tick_drama = max(self.tick_drama, drama)
        if not self.animate and not self.quiet:
            print(line)

    def frame_delay(self):
        d = PACE_DELAYS[self.tick_drama]
        if len(self.alive_toons()) <= 4:
            d *= ENDGAME_SLOWDOWN
        return d * self.pace

    # ---- zone

    def in_zone(self, x, y):
        m = self.margin
        return m <= x < self.arena.width - m and m <= y < self.arena.height - m

    def zone_center(self):
        return self.arena.width // 2, self.arena.height // 2

    # ---- spawning

    def spawn_all(self):
        cx, cy = self.arena.width / 2.0, self.arena.height / 2.0
        rx, ry = self.arena.width * 0.44, self.arena.height * 0.44
        taken = set()
        for i, toon in enumerate(self.toons):
            ang = 2 * math.pi * i / len(self.toons)
            px = int(cx + rx * math.cos(ang))
            py = int(cy + ry * math.sin(ang))
            toon.x, toon.y = self.snap_spawn(px, py, taken)
            taken.add((toon.x, toon.y))
            toon.last_pos = (toon.x, toon.y)

    def snap_spawn(self, px, py, taken):
        for radius in range(0, 30):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    x, y = px + dx, py + dy
                    if (
                        self.arena.passable(x, y)
                        and self.arena.tile(x, y) not in ("water", "trap")
                        and (x, y) not in taken
                    ):
                        return x, y
        return px, py

    # ---- helpers

    def alive_toons(self):
        return [t for t in self.toons if t.alive]

    def occupied(self):
        return {(t.x, t.y): t for t in self.alive_toons()}

    def nearest_tile(self, toon, name, in_zone_only=True, with_stock=False):
        best, best_d = None, 1e9
        for (x, y) in self.arena.tiles_of(name):
            if in_zone_only and not self.in_zone(x, y):
                continue
            if with_stock and self.arena.stash_stock.get((x, y), 0) <= 0:
                continue
            d = math.hypot(x - toon.x, y - toon.y)
            if d < best_d:
                best, best_d = (x, y), d
        return best

    def eff_perception(self, toon):
        p = toon.s("perception") * (0.5 + 0.15 * toon.w(W_PERC))
        if self.arena.tile(toon.x, toon.y) == "vantage_point":
            p += 18
        if self.arena.tile(toon.x, toon.y) == "forest":
            p -= 8
        return p

    def eff_stealth(self, toon):
        s = (30 + toon.s("patience") * 0.3 + toon.s("agility") * 0.2) * (
            0.4 + 0.2 * toon.w(W_STEALTH)
        )
        tile = self.arena.tile(toon.x, toon.y)
        if tile == "forest":
            s += 14
        elif tile == "water":
            s -= 12
        return s

    # ---- AI state decisions

    def decide_state(self, toon):
        old = toon.state
        threat = self.current_threat(toon)
        late_game = len(self.alive_toons()) <= 4 or self.margin > min(
            self.arena.width, self.arena.height
        ) * 0.3

        if not self.in_zone(toon.x, toon.y):
            # collapse overrides everything: sprint for safety
            toon.state = "fleeing" if toon.stam > 10 else "panicking"
            cx, cy = self.zone_center()
            toon.target = (cx + self.rng.randint(-10, 10), cy + self.rng.randint(-8, 8))
        elif threat is not None:
            self.fight_or_flee(toon, threat)
        elif toon.stam <= 15:
            toon.state = "resting"
            toon.target = None
        elif toon.hp < 40:
            med = self.nearest_tile(toon, "medical")
            if med and self.arena.tile(toon.x, toon.y) != "medical":
                toon.state = "sneaking"
                toon.target = med
            else:
                toon.state = "hiding" if toon.s("patience") > 50 else "resting"
                toon.target = None
        elif toon.weapon is None:
            stash = self.nearest_tile(toon, "weapon_stash", with_stock=True)
            if stash:
                toon.state = "rushing" if toon.s("courage") > 30 else "cautious"
                toon.target = stash
            else:
                toon.state = "scouting"
                toon.target = self.wander_target(toon)
        elif late_game:
            toon.state = "hunting" if toon.s("aggression") > 45 else "vigilant"
            if toon.state == "hunting":
                # so few remain that hunters can track their prey across the zone
                prey = self.nearest_enemy(toon)
                if prey is not None:
                    toon.target = (
                        prey.x + self.rng.randint(-3, 3),
                        prey.y + self.rng.randint(-3, 3),
                    )
                else:
                    toon.target = self.wander_target(toon)
            else:
                toon.target = None
        else:
            self.personality_state(toon)

        if toon.state != old:
            self.event("%s: %s -> %s" % (toon.label(), old, toon.state), drama=0)

    def personality_state(self, toon):
        agg = toon.s("aggression") + self.rng.randint(-12, 12)
        pat = toon.s("patience") + self.rng.randint(-12, 12)
        crg = toon.s("courage")
        if agg > 68:
            toon.state = "hunting"
            toon.target = self.wander_target(toon)
        elif pat > 70:
            toon.state = "camping"
            toon.target = None
        elif crg < 35:
            toon.state = "sneaking"
            toon.target = self.wander_target(toon)
        elif toon.s("intelligence") > 75 and self.rng.random() < 0.3:
            toon.state = "strategizing"
            toon.target = None
        else:
            toon.state = "scouting" if crg > 55 else "cautious"
            toon.target = self.wander_target(toon)

    def wander_target(self, toon):
        pois = self.arena.tiles_of("point_of_interest") + self.arena.tiles_of(
            "vantage_point"
        )
        pois = [p for p in pois if self.in_zone(*p) and p not in toon.looted_pois]
        if pois and self.rng.random() < 0.6:
            return self.rng.choice(pois)
        cx, cy = self.zone_center()
        span_x = max(4, (self.arena.width - 2 * self.margin) // 2 - 2)
        span_y = max(4, (self.arena.height - 2 * self.margin) // 2 - 2)
        return (
            cx + self.rng.randint(-span_x, span_x),
            cy + self.rng.randint(-span_y, span_y),
        )

    def nearest_enemy(self, toon):
        best, best_d = None, 1e9
        for other in self.alive_toons():
            if other is toon:
                continue
            d = math.hypot(other.x - toon.x, other.y - toon.y)
            if d < best_d:
                best, best_d = other, d
        return best

    def current_threat(self, toon):
        if toon.threat is None:
            return None
        enemy, seen_tick, _, _ = toon.threat
        if not enemy.alive or self.tick - seen_tick > THREAT_MEMORY:
            toon.threat = None
            return None
        return toon.threat

    def fight_or_flee(self, toon, threat):
        enemy, _, ex, ey = threat
        balance = toon.power() - enemy.power()
        score = (
            toon.s("aggression") * 0.4
            + toon.s("courage") * 0.3
            + balance * 0.6
            + (20 if toon.weapon else -25)
            + (toon.hp - 50) * 0.4
            - toon.s("risk_assessment") * 0.15
        )
        if score > 30:
            toon.state = "aggressive"
            toon.target = (ex, ey)
        elif score > 5:
            toon.state = "defensive"
            toon.target = None
        elif toon.s("patience") > 65 and self.arena.tile(toon.x, toon.y) == "forest":
            toon.state = "hiding"
            toon.target = None
        else:
            toon.state = "fleeing"
            dx, dy = toon.x - ex, toon.y - ey
            n = math.hypot(dx, dy) or 1.0
            fx = int(toon.x + dx / n * 12)
            fy = int(toon.y + dy / n * 12)
            m = self.margin + 2
            fx = max(m, min(self.arena.width - 1 - m, fx))
            fy = max(m, min(self.arena.height - 1 - m, fy))
            toon.target = (fx, fy)

    # ---- movement

    def move_toon(self, toon):
        self.decay_path_mem(toon)
        if toon.target is None:
            return
        tx, ty = toon.target
        if (toon.x, toon.y) == (tx, ty):
            toon.target = None
            return
        speed_w = toon.w(W_SPEED)
        if speed_w == 0:
            return
        pts = (0.4 + toon.s("speed") / 150.0) * speed_w + toon.move_debt
        occupied = self.occupied()
        cells = 0
        while cells < MAX_CELLS_PER_TICK:
            step = self.pick_step(toon, tx, ty, occupied)
            if step is None:
                self.remember_cell(toon, (toon.x, toon.y), PATH_MEM_BLOCKED)
                break
            nx, ny = step
            cost = TERRAIN[self.arena.tile(nx, ny)][0]
            if pts < cost:
                break
            pts -= cost
            self.remember_cell(toon, (toon.x, toon.y), PATH_MEM_VISIT)
            occupied.pop((toon.x, toon.y), None)
            toon.x, toon.y = nx, ny
            occupied[(nx, ny)] = toon
            cells += 1
            self.drain_stamina(toon)
            self.tile_effects(toon)
            if not toon.alive or toon.state == "panicking":
                break
            if (toon.x, toon.y) == (tx, ty):
                toon.target = None
                break
        toon.move_debt = min(pts, 2.0)
        if (toon.x, toon.y) == toon.last_pos and toon.target is not None:
            toon.stuck += 1
            self.remember_cell(toon, (toon.x, toon.y), PATH_MEM_BLOCKED)
            if toon.stuck > 6:
                # no progress for several attempts: abandon this destination
                toon.target = self.wander_target(toon)
                toon.stuck = 0
        else:
            toon.stuck = 0
        toon.last_pos = (toon.x, toon.y)

    def pick_step(self, toon, tx, ty, occupied):
        """Two-step look-ahead: each candidate first step is scored by the
        best position it could reach on a follow-up step (progress toward the
        goal, terrain cost, crowding), plus the first step's own cost, the
        toon's movement memory, and a little randomness."""
        best, best_score = None, None
        for dx, dy in DIRS8:
            nx, ny = toon.x + dx, toon.y + dy
            if not self.arena.passable(nx, ny) or (nx, ny) in occupied:
                continue
            if (nx, ny) == (tx, ty):
                return (nx, ny)
            # best follow-up: standing still is the fallback second step
            best2 = math.hypot(tx - nx, ty - ny)
            for dx2, dy2 in DIRS8:
                mx, my = nx + dx2, ny + dy2
                if (mx, my) == (toon.x, toon.y):
                    continue  # doubling straight back is never progress
                if not self.arena.passable(mx, my):
                    continue
                s2 = (
                    math.hypot(tx - mx, ty - my)
                    + TERRAIN[self.arena.tile(mx, my)][0] * 0.4
                    + toon.path_mem.get((mx, my), 0.0)
                    + (1.5 if (mx, my) in occupied else 0.0)
                )
                if s2 < best2:
                    best2 = s2
            score = (
                best2
                + TERRAIN[self.arena.tile(nx, ny)][0] * 0.4
                + toon.path_mem.get((nx, ny), 0.0)
                + self.rng.random() * 0.3
            )
            if best_score is None or score < best_score:
                best, best_score = (nx, ny), score
        return best

    def remember_cell(self, toon, cell, penalty):
        toon.path_mem[cell] = min(PATH_MEM_CAP, toon.path_mem.get(cell, 0.0) + penalty)
        if len(toon.path_mem) > PATH_MEM_MAX:
            for old in sorted(toon.path_mem, key=toon.path_mem.get)[
                : len(toon.path_mem) - PATH_MEM_MAX
            ]:
                del toon.path_mem[old]

    def decay_path_mem(self, toon):
        toon.path_mem = {
            c: p * PATH_MEM_DECAY
            for c, p in toon.path_mem.items()
            if p * PATH_MEM_DECAY > 0.05
        }

    def drain_stamina(self, toon):
        tile = self.arena.tile(toon.x, toon.y)
        stam_mult = TERRAIN[tile][1]
        drain = (
            stam_mult
            * (0.3 + 0.25 * toon.w(W_STAMUSE))
            * (1.6 - toon.s("stamina") / 99.0)
        )
        toon.stam = max(0.0, toon.stam - drain)
        if toon.stam <= 0 and toon.state in ("rushing", "fleeing", "aggressive"):
            toon.state = "resting"
            toon.target = None
            self.event("%s collapses from exhaustion and rests" % toon.label())

    # ---- tile effects

    def tile_effects(self, toon):
        x, y = toon.x, toon.y
        tile = self.arena.tile(x, y)
        if tile == "weapon_stash" and self.arena.stash_stock.get((x, y), 0) > 0:
            self.grab_weapon(toon, x, y)
        elif tile == "trap":
            self.trigger_trap(toon, x, y)
        elif tile == "point_of_interest" and (x, y) not in toon.looted_pois:
            toon.looted_pois.add((x, y))
            toon.hp = min(100.0, toon.hp + 10)
            toon.stam = min(100.0, toon.stam + 25)
            self.event(
                "%s scavenges supplies at (%d,%d) [+10hp +25stam]"
                % (toon.label(), x, y)
            )

    def grab_weapon(self, toon, x, y):
        pool = [w for w in WEAPON_TABLE]
        weights = [w[3] for w in pool]
        new = self.rng.choices(pool, weights=weights, k=1)[0]
        cur = toon.weapon
        if cur is None or new[1] > cur[1]:
            toon.weapon = new
            self.arena.stash_stock[(x, y)] -= 1
            self.event("%s takes a %s from the stash at (%d,%d)" % (toon.label(), new[0], x, y))
            if self.arena.stash_stock[(x, y)] <= 0:
                self.arena.consume(x, y)
                self.event("stash at (%d,%d) is empty" % (x, y), drama=0)
            self.decide_state(toon)

    def trigger_trap(self, toon, x, y):
        awareness = (
            (toon.s("perception") + toon.s("risk_assessment")) / 2.0
            + toon.w(W_READY) * 6
            + self.rng.randint(0, 40)
        )
        if awareness > 72:
            self.event("%s spots and disarms a trap at (%d,%d)" % (toon.label(), x, y))
        else:
            dmg = self.rng.randint(*TRAP_DAMAGE)
            toon.hp -= dmg
            self.event(
                "%s stumbles into a trap at (%d,%d) [-%d hp]" % (toon.label(), x, y, dmg),
                drama=2,
            )
            if toon.hp <= 0:
                self.kill(toon, None, "trap")
            elif (toon.s("courage") + toon.s("determination")) / 2 + self.rng.randint(
                0, 30
            ) < 55:
                toon.state = "panicking"
                toon.target = self.wander_target(toon)
        self.arena.consume(x, y)

    # ---- detection & combat

    def detection_phase(self):
        alive = self.alive_toons()
        for looker in alive:
            radius = 14 + (4 if self.arena.tile(looker.x, looker.y) == "vantage_point" else 0)
            for other in alive:
                if other is looker:
                    continue
                d = math.hypot(other.x - looker.x, other.y - looker.y)
                if d > radius:
                    continue
                roll = (
                    self.eff_perception(looker)
                    - d * 6
                    + self.rng.randint(-15, 15)
                )
                # nobody stays hidden at point-blank range
                if d <= 2.5 or roll > self.eff_stealth(other):
                    first_sight = looker.threat is None or looker.threat[0] is not other
                    looker.threat = (other, self.tick, other.x, other.y)
                    if first_sight and d < 10:
                        self.event(
                            "%s spots %s %.0f cells away"
                            % (looker.label(), other.label(), d),
                            drama=2,
                        )
                        self.decide_state(looker)

    def combat_phase(self):
        done = set()
        for toon in list(self.alive_toons()):
            if not toon.alive:
                continue
            threat = self.current_threat(toon)
            if threat is None:
                continue
            enemy = threat[0]
            if not enemy.alive:
                continue
            pair = frozenset((toon.num, enemy.num))
            if pair in done:
                continue
            d = math.hypot(enemy.x - toon.x, enemy.y - toon.y)
            wpn = toon.weapon or UNARMED
            wants_fight = toon.state in ("aggressive", "hunting", "defensive", "camping")
            if d <= wpn[2] and wants_fight:
                done.add(pair)
                self.combat_round(toon, enemy)

    def combat_round(self, a, b):
        for attacker, defender in ((a, b), (b, a)):
            if not (attacker.alive and defender.alive):
                return
            wpn = attacker.weapon or UNARMED
            d = math.hypot(defender.x - attacker.x, defender.y - attacker.y)
            if d > wpn[2]:
                continue
            atk = (
                attacker.s("strength") * 0.30
                + attacker.s("coordination") * 0.20
                + attacker.s("dexterity") * 0.20
                + attacker.s("agility") * 0.15
                + attacker.s("courage") * 0.15
                + attacker.w(W_READY) * 4
                + self.rng.randint(0, 30)
            )
            dfn = (
                defender.s("agility") * 0.25
                + defender.s("balance") * 0.25
                + defender.s("perception") * 0.20
                + defender.s("speed") * 0.15
                + defender.s("risk_assessment") * 0.15
                + defender.w(W_READY) * 4
                + self.rng.randint(0, 30)
            )
            if atk > dfn:
                dmg = 6 + wpn[1] + attacker.s("strength") / 12.0 + self.rng.randint(0, 6)
                defender.hp -= dmg
                attacker.dmg_dealt += dmg
                self.event(
                    "%s hits %s with %s [-%.0f hp, %.0f left]"
                    % (attacker.label(), defender.label(), wpn[0], dmg, max(0, defender.hp)),
                    drama=2,
                )
                if defender.hp <= 0:
                    self.kill(defender, attacker, "slain by %s" % attacker.label())
                    return
                self.flee_check(defender, attacker)
            else:
                self.event(
                    "%s swings at %s but misses" % (attacker.label(), defender.label()),
                    drama=2,
                )

    def flee_check(self, toon, enemy):
        if toon.hp < 35 and toon.s("courage") + self.rng.randint(0, 30) < 70:
            toon.threat = (enemy, self.tick, enemy.x, enemy.y)
            self.fight_or_flee(toon, toon.threat)
            if toon.state == "fleeing":
                self.event("%s breaks off and flees" % toon.label(), drama=2)

    def kill(self, victim, killer, cause):
        victim.alive = False
        victim.hp = 0
        victim.death_tick = self.tick
        victim.cause = cause
        self.placements.append(victim)
        if self.first_blood is None:
            by = killer.label() if killer else cause
            self.first_blood = "%s felled by %s at t%d" % (victim.label(), by, self.tick)
        if killer is not None:
            killer.kills += 1
            killer.threat = None
            self.event(
                "*** %s is eliminated by %s (kill #%d) — %d remain"
                % (victim.label(), killer.label(), killer.kills, len(self.alive_toons())),
                drama=3,
            )
            self.banner = "⚔  %s ELIMINATED %s — %d remain" % (
                killer.label(),
                victim.label(),
                len(self.alive_toons()),
            )
            self.decide_state(killer)
        else:
            self.event(
                "*** %s is eliminated (%s) — %d remain"
                % (victim.label(), cause, len(self.alive_toons())),
                drama=3,
            )
            self.banner = "☠  %s ELIMINATED (%s) — %d remain" % (
                victim.label(),
                cause,
                len(self.alive_toons()),
            )
        self.banner_until = time.time() + BANNER_SECONDS

    # ---- upkeep

    def upkeep(self, toon):
        regen = (0.5 + toon.s("recovery") / 99.0) * 1.2 * toon.w(W_RECOV)
        toon.stam = min(100.0, toon.stam + regen)
        if self.arena.tile(toon.x, toon.y) == "medical" and toon.hp < 100:
            heal = MEDICAL_HEAL * (0.6 + toon.s("resilience") / 150.0)
            toon.hp = min(100.0, toon.hp + heal)
        if not self.in_zone(toon.x, toon.y):
            toon.hp -= ZONE_DAMAGE
            if toon.hp <= 0:
                self.kill(toon, None, "caught in the arena collapse")
        if toon.state == "panicking" and self.rng.random() < 0.25:
            toon.state = "cautious"

    # ---- zone control

    def update_zone(self):
        if self.tick == ZONE_START_TICK:
            self.event("!!! THE ARENA BEGINS TO COLLAPSE FROM THE EDGES !!!", drama=2)
        if self.tick >= ZONE_START_TICK and (self.tick - ZONE_START_TICK) % ZONE_SHRINK_EVERY == 0:
            limit = min(self.arena.width, self.arena.height) // 2 - 4
            if self.margin < limit:
                self.margin += 1

    # ---- main loop

    def run(self):
        self.spawn_all()
        self.event(
            "Match start: %d competitors enter %s (seed %s)"
            % (len(self.toons), self.arena.name, self.seed),
            drama=2,
        )
        if self.animate:
            sys.stdout.write("\x1b[2J")  # clear once; frames redraw in place
            self.draw_frame()
            time.sleep(1.0)
        while self.tick < MAX_TICKS and len(self.alive_toons()) > 1:
            self.tick += 1
            self.tick_drama = 0
            self.update_zone()
            for toon in self.alive_toons():
                if self.tick % DECIDE_EVERY == 0 or toon.target is None:
                    self.decide_state(toon)
            for toon in self.alive_toons():
                self.move_toon(toon)
            self.detection_phase()
            self.combat_phase()
            for toon in self.alive_toons():
                self.upkeep(toon)
            # drama gets a frame immediately; quiet ticks redraw less often
            if self.animate and (self.tick_drama > 0 or self.tick % FRAME_EVERY == 0):
                self.draw_frame()
                self.poll_keys()
                if self.animate:
                    time.sleep(self.frame_delay())
        self.finish()

    # ---- live controls (Windows: space/+/-/q while the match runs)

    def poll_keys(self):
        if msvcrt is None:
            return
        while msvcrt.kbhit():
            self.handle_key(msvcrt.getwch().lower())
        while self.paused and self.animate:
            self.draw_frame()
            self.handle_key(msvcrt.getwch().lower())  # blocks until a key

    def handle_key(self, ch):
        if ch == " ":
            self.paused = not self.paused
        elif ch in "+=":
            self.pace = max(0.1, self.pace / 1.4)
        elif ch == "-":
            self.pace = min(8.0, self.pace * 1.4)
        elif ch == "q":
            self.animate = False
            self.quiet = True
            self.paused = False
            print("\nskipping to results...")

    def finish(self):
        alive = self.alive_toons()
        if len(alive) == 1:
            winner = alive[0]
        else:
            alive.sort(key=lambda t: (t.hp + t.kills * 25), reverse=True)
            winner = alive[0] if alive else self.placements[-1]
            for t in alive[1:]:
                t.alive = False
                t.death_tick = self.tick
                t.cause = "time limit"
                self.placements.append(t)
        if self.animate:
            self.draw_frame()      # leave the last live frame on screen
            self.animate = False
            print()                # results scroll below it from here on
        self.quiet = False
        self.event(
            "=== WINNER: %s with %d kill(s) after %d ticks ==="
            % (winner.label(), winner.kills, self.tick),
            drama=3,
        )
        self.render()
        self.print_results(winner)
        self.print_match_report(winner)
        self.write_report(winner)

    def print_results(self, winner):
        print()
        print("\x1b[1mFINAL PLACEMENTS\x1b[0m")
        print("%4s %-24s %5s %6s  %s" % ("#", "name", "kills", "died", "cause"))
        order = [winner] + list(reversed(self.placements))
        for place, t in enumerate(order, start=1):
            died = "-" if t is winner else "t%d" % (t.death_tick or 0)
            cause = "SURVIVED" if t is winner else (t.cause or "?")
            clr = "\x1b[1;92m" if place == 1 else ("\x1b[93m" if place <= 3 else "")
            end = CLR_RESET if clr else ""
            print(clr + "%4d %-24s %5d %6s  %s" % (place, t.label(), t.kills, died, cause) + end)

    def print_match_report(self, winner):
        Y, G, R, D, Z = "\x1b[1;93m", "\x1b[1;92m", "\x1b[1;91m", "\x1b[2m", CLR_RESET
        deadliest = max(self.toons, key=lambda t: (t.kills, t.dmg_dealt))
        bruiser = max(self.toons, key=lambda t: t.dmg_dealt)
        causes = [t.cause for t in self.placements]
        n_combat = sum(1 for c in causes if c.startswith("slain"))
        n_trap = sum(1 for c in causes if c == "trap")
        n_zone = sum(1 for c in causes if "collapse" in c)
        print()
        print(Y + "═" * 56 + Z)
        print(Y + "  MATCH REPORT — seed %s, %d ticks" % (self.seed, self.tick) + Z)
        print(Y + "═" * 56 + Z)
        print(G + "  ★ champion    %s — %d kill(s), %.0f damage dealt"
              % (winner.label(), winner.kills, winner.dmg_dealt) + Z)
        print(R + "  ⚔ deadliest   %s — %d elimination(s)"
              % (deadliest.label(), deadliest.kills) + Z)
        print(R + "  » hardest hit %s — %.0f total damage"
              % (bruiser.label(), bruiser.dmg_dealt) + Z)
        if self.first_blood:
            print("  ☠ first blood %s" % self.first_blood)
        print(D + "  eliminations: %d in combat, %d by trap, %d to the collapse"
              % (n_combat, n_trap, n_zone) + Z)
        print(Y + "═" * 56 + Z)

    def write_report(self, winner):
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(BASE_DIR, "zpyBattleRoyale_report_%s_seed%s.txt" % (ts, self.seed))
        with open(path, "w", encoding="utf-8") as f:
            f.write("zpyBattleRoyale report — seed %s — map %s\n" % (self.seed, self.arena.name))
            f.write("winner: %s (%d kills)\n\n" % (winner.label(), winner.kills))
            f.write("FINAL PLACEMENTS\n")
            order = [winner] + list(reversed(self.placements))
            for place, t in enumerate(order, start=1):
                cause = "SURVIVED" if t is winner else (t.cause or "?")
                f.write("%3d. %-24s kills=%d  %s\n" % (place, t.label(), t.kills, cause))
            f.write("\nEVENT LOG\n")
            f.write("\n".join(line for line, _ in self.log))
            f.write("\n")
        print("\nreport saved -> %s" % os.path.basename(path))

    # ---- rendering

    def pick_scale(self):
        """Auto-fit the map to the terminal unless --scale forces a value."""
        if self.fixed_scale:
            return max(1, self.fixed_scale)
        cols, rows = shutil.get_terminal_size((120, 40))
        alive = len(self.alive_toons())
        two_col = cols >= self.STATUS_ENTRY_WIDTH * 2 + 3
        alive_rows = (alive + 1) // 2 if two_col else alive
        reserved = 3 + alive_rows + EVENT_FEED + 2
        avail_h = max(8, rows - reserved)
        avail_w = max(20, cols - 1)
        need_h = math.ceil(self.arena.height / avail_h)
        need_w = math.ceil(self.arena.width * 2 / avail_w)
        return min(6, max(1, need_h, need_w))

    def build_map_lines(self, sc):
        markers = {(t.x, t.y): "%02d" % t.num for t in self.alive_toons()}
        out = []
        for by in range(0, self.arena.height, sc):
            row = []
            for bx in range(0, self.arena.width, sc):
                row.append(self.render_block(bx, by, sc, markers))
            out.append("".join(row))
        return out

    STATUS_ENTRY_WIDTH = 51  # visible chars per survivor entry (before colors)

    def compact_status_lines(self, cols):
        entries = []
        for t in self.toons:
            if not t.alive:
                continue
            wpn = (t.weapon[0] if t.weapon else "-")[:9]
            glyph = STATE_GLYPHS.get(t.state, "?")
            sclr = STATE_CLR.get(t.state, "")
            kills = (
                "\x1b[1;91mk%d\x1b[0m" % t.kills if t.kills else "\x1b[2mk0\x1b[0m"
            )
            entries.append(
                "%02d %-12s " % (t.num, t.name[:12])
                + hp_clr(t.hp)
                + "%3.0f" % t.hp
                + CLR_RESET
                + "/\x1b[2m%3.0f\x1b[0m " % t.stam
                + sclr
                + glyph
                + " %-12s" % t.state
                + CLR_RESET
                + " %-9s " % wpn
                + kills
            )
        two_col = cols >= self.STATUS_ENTRY_WIDTH * 2 + 3
        lines = []
        step = 2 if two_col else 1
        for i in range(0, len(entries), step):
            lines.append("   ".join(entries[i : i + step]))
        return lines

    def draw_frame(self):
        cols = shutil.get_terminal_size((120, 40)).columns
        sc = self.pick_scale()
        head = (
            "\x1b[1;96mtick %4d | alive %2d | zone %2d | pace x%.1f\x1b[0m"
            % (self.tick, len(self.alive_toons()), self.margin, self.pace)
        )
        if self.paused:
            head += " \x1b[1;93m*PAUSED*\x1b[0m"
        if msvcrt is not None:
            head += " \x1b[2m[space]pause [+]faster [-]slower [q]results\x1b[0m"
        rows = [head]
        if time.time() < self.banner_until:
            rows.append(CLR_DRAMA[3] + self.banner[: cols - 1] + CLR_RESET)
        else:
            rows.append("")
        # map and status lines carry ANSI colors and are already sized to fit
        rows.extend(self.build_map_lines(sc))
        rows.append("")
        rows.extend(self.compact_status_lines(cols))
        rows.append("\x1b[2m" + "-" * min(60, cols - 1) + CLR_RESET)
        for line, drama in self.log[-EVENT_FEED:]:
            rows.append(CLR_DRAMA[drama] + line[: cols - 1] + CLR_RESET)
        # redraw in place: home cursor, clear each line's leftovers, clear below
        buf = "\x1b[H" + "".join(r + "\x1b[K\n" for r in rows) + "\x1b[0J"
        sys.stdout.write(buf)
        sys.stdout.flush()

    def render(self):
        """Plain (scrolling) map print, used for the final screen."""
        if self.quiet:
            return
        print()
        print("=" * 60)
        print("TICK %d — %d alive — zone margin %d" % (self.tick, len(self.alive_toons()), self.margin))
        print("\n".join(self.build_map_lines(self.pick_scale())))
        print()
        self.print_status_table()

    def render_block(self, bx, by, sc, markers):
        """One display glyph for the sc x sc block of cells at (bx, by)."""
        best_tile, best_pri = "open_ground", 0
        any_in_zone = False
        for y in range(by, min(by + sc, self.arena.height)):
            for x in range(bx, min(bx + sc, self.arena.width)):
                if (x, y) in markers:
                    return MARKER_CLR + markers[(x, y)] + CLR_RESET
                if self.in_zone(x, y):
                    any_in_zone = True
                    tile = self.arena.tile(x, y)
                    pri = TILE_PRIORITY[tile]
                    if pri > best_pri:
                        best_tile, best_pri = tile, pri
        if not any_in_zone:
            return TILE_CLR["collapsed"] + TILE_DISPLAY["collapsed"] + CLR_RESET
        clr = TILE_CLR[best_tile]
        if not clr:
            return TILE_DISPLAY[best_tile]
        return clr + TILE_DISPLAY[best_tile] + CLR_RESET

    def print_status_table(self):
        print("%3s %-20s %4s %5s %-12s %-15s %5s" % ("id", "name", "hp", "stam", "state", "weapon", "kills"))
        for t in self.toons:
            if t.alive:
                wpn = t.weapon[0] if t.weapon else "-"
                print(
                    "%3s %-20s %4.0f %5.0f %-12s %-15s %5d"
                    % ("%02d" % t.num, t.name, t.hp, t.stam, t.state, wpn, t.kills)
                )
            else:
                print("%3s %-20s %s" % ("%02d" % t.num, t.name, "DEAD (t%d)" % (t.death_tick or 0)))


# ------------------------------------------------------------ roster + CLI

def load_roster():
    with open(ROSTER_CSV, encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r.get("character_id")]
    return rows


def parse_selection(text, n_avail):
    picked = []
    for token in text.replace(" ", "").split(","):
        if not token:
            continue
        if "-" in token:
            a, b = token.split("-", 1)
            try:
                lo, hi = int(a), int(b)
            except ValueError:
                continue
            picked.extend(range(lo, hi + 1))
        else:
            try:
                picked.append(int(token))
            except ValueError:
                continue
    seen = set()
    result = []
    for p in picked:
        if 1 <= p <= n_avail and p not in seen:
            seen.add(p)
            result.append(p)
    return result


def select_competitors(rows, rng, auto=False):
    count = min(PICK_COUNT, len(rows))
    if auto:
        return rng.sample(rows, count)
    print("AVAILABLE COMPETITORS (%d) — pick %d" % (len(rows), count))
    print("%4s %-24s %3s %3s %3s %3s %3s %3s" % ("#", "name", "STR", "SPD", "AGI", "PER", "CRG", "AGG"))
    for i, r in enumerate(rows, start=1):
        print(
            "%4d %-24s %3s %3s %3s %3s %3s %3s"
            % (
                i,
                (r.get("display_name") or "?")[:24],
                r.get("strength", ""),
                r.get("speed", ""),
                r.get("agility", ""),
                r.get("perception", ""),
                r.get("courage", ""),
                r.get("aggression", ""),
            )
        )
    print()
    print("Enter numbers/ranges (e.g. 1,3,5-12), 'a' = first %d, 'r' = random %d." % (count, count))
    print("If you pick fewer than %d, the rest are filled randomly." % count)
    while True:
        try:
            raw = input("selection > ").strip().lower()
        except EOFError:
            raw = "r"
        if raw == "a":
            return rows[:count]
        if raw == "r" or raw == "":
            return rng.sample(rows, count)
        idx = parse_selection(raw, len(rows))
        if not idx:
            print("could not parse anything — try again")
            continue
        idx = idx[:count]
        chosen = [rows[i - 1] for i in idx]
        if len(chosen) < count:
            rest = [r for r in rows if r not in chosen]
            chosen += rng.sample(rest, count - len(chosen))
            print("filled remaining %d slots randomly" % (count - len(idx)))
        return chosen


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    os.system("")  # enables ANSI escape codes in the classic Windows console
    ap = argparse.ArgumentParser(description="zpyBattleRoyale — roster battle royale sim")
    ap.add_argument("--auto", action="store_true", help="random 20 picks, no pauses")
    ap.add_argument("--seed", type=int, default=None, help="RNG seed for reproducible matches")
    ap.add_argument("--quiet", action="store_true", help="suppress tick events, show results only")
    ap.add_argument(
        "--scale",
        type=int,
        default=MAP_SCALE,
        help="force map downsampling 1-6 (default: auto-fit to terminal size)",
    )
    ap.add_argument(
        "--pace",
        type=float,
        default=1.0,
        help="pacing multiplier: <1 faster, >1 slower (default 1.0)",
    )
    args = ap.parse_args()

    seed = args.seed if args.seed is not None else random.randrange(1, 10 ** 6)
    rng = random.Random(seed)

    if not os.path.exists(ROSTER_CSV):
        print("roster not found: %s" % ROSTER_CSV)
        return
    if not os.path.exists(MAP_FILE):
        print("map not found: %s" % MAP_FILE)
        return

    print("zpyBattleRoyale — seed %d" % seed)
    rows = load_roster()
    chosen = select_competitors(rows, rng, auto=args.auto)
    arena = Arena(MAP_FILE)
    toons = [Toon(i + 1, row) for i, row in enumerate(chosen)]
    game = Game(
        arena,
        toons,
        seed,
        interactive=not args.auto,
        quiet=args.quiet,
        scale=args.scale,
        pace=args.pace,
    )
    game.run()
    if not args.auto:
        # keep the results on screen until the player dismisses them
        try:
            input("\npress [Enter] to close...")
        except EOFError:
            pass


if __name__ == "__main__":
    main()
