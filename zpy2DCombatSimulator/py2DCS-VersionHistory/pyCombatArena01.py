"""
pyCombatArena01 -- top-down 2D combat sim prototype (stdlib only, tkinter).

Football-Manager-style visualization: fighters are circles, weapons are
lines, hits show as sparks + floating damage numbers, everything narrated
in an event log.

Engine layout:
  Sim        -- deterministic fixed-timestep world (no tkinter inside).
                Supports two teams of 1-5 fighters each.
  Fighter    -- state machine: MOVE -> WINDUP -> SWING/FIRE -> RECOVER,
                with nearest-enemy target picking (sticky, to avoid flicker).
  Weapon     -- pure data; add a new dict entry in WEAPONS to add a weapon.
  Projectile -- anything that flies (sling stone today; arrows later).
  Fx         -- short-lived visuals (damage numbers, hit rings).
  App        -- tkinter shell: renders the Sim each frame, owns controls.

The wider game should call run_headless() (or drive Sim directly) -- combat
is a self-contained module that takes team rosters in and hands a result
back; the tkinter App is just one consumer of it.

Roadmap hooks (not built yet, but the pipeline supports them):
  * DoT: give Fighter a list of (dps, ttl) effects ticked in Sim.step.
  * AoE/explosives: on projectile impact, damage all fighters within R.
  * Per-fighter stats (speed/strength/hp) fed in via the roster specs.

Same seed = same fight (Rematch button replays it exactly).
"""

import math
import random
import tkinter as tk
from tkinter import ttk

# ---------------------------------------------------------------- constants

ARENA_W, ARENA_H = 640, 560
WALL_PAD = 24                      # fighters are clamped inside this margin
DT = 1 / 30                        # fixed sim timestep (seconds)
TURN_RATE = math.radians(540)      # how fast a fighter can rotate, rad/s
MOVE_SPEED = 95.0                  # px/s
CRIT_CHANCE = 0.10

MOVE, WINDUP, SWING, RECOVER = "MOVE", "WINDUP", "SWING", "RECOVER"

TEAM_NAMES = ("Red team", "Blue team")
TEAM_COLORS = ("#e05d5d", "#5d8fe0")
RED_NAMES = ("Ash", "Rex", "Ivy", "Moa", "Zed")
BLUE_NAMES = ("Bolt", "Nix", "Fay", "Gus", "Lux")


class Weapon:
    """Pure data. kind is 'melee' or 'ranged'."""

    def __init__(self, name, kind, reach, arc_deg, dmg, windup, strike,
                 recover, cooldown, color, width, proj_speed=0.0,
                 pref_range=0.0, min_range=0.0):
        self.name = name
        self.kind = kind
        self.reach = reach            # melee: stick length | ranged: max flight
        self.arc = math.radians(arc_deg)
        self.dmg = dmg                # (lo, hi)
        self.windup = windup
        self.strike = strike          # melee: swing duration
        self.recover = recover
        self.cooldown = cooldown
        self.color = color
        self.width = width
        self.proj_speed = proj_speed
        self.pref_range = pref_range or reach * 0.8
        self.min_range = min_range    # ranged: back off if foe gets closer


WEAPONS = {
    "Stick":  Weapon("Stick", "melee", reach=48, arc_deg=110, dmg=(5, 9),
                     windup=0.32, strike=0.16, recover=0.40, cooldown=0.35,
                     color="#c8a165", width=4),
    "Club":   Weapon("Club", "melee", reach=42, arc_deg=95, dmg=(9, 15),
                     windup=0.55, strike=0.20, recover=0.60, cooldown=0.55,
                     color="#8a6d4f", width=7),
    "Spear":  Weapon("Spear", "melee", reach=70, arc_deg=40, dmg=(7, 11),
                     windup=0.42, strike=0.14, recover=0.50, cooldown=0.45,
                     color="#b0b8c4", width=3),
    "Sling":  Weapon("Sling", "ranged", reach=300, arc_deg=0, dmg=(6, 10),
                     windup=0.70, strike=0.0, recover=0.35, cooldown=0.55,
                     color="#9a8f80", width=2, proj_speed=340.0,
                     pref_range=190.0, min_range=120.0),
}


def angdiff(a, b):
    """Signed smallest difference a-b, in [-pi, pi]."""
    return (a - b + math.pi) % (2 * math.pi) - math.pi


# ---------------------------------------------------------------- entities

class Fighter:
    def __init__(self, name, team, x, y, facing, weapon_key, rng):
        self.name = name
        self.team = team
        self.color = TEAM_COLORS[team]
        self.target = None
        self.x, self.y = x, y
        self.facing = facing
        self.weapon = WEAPONS[weapon_key]
        self.max_hp = 60
        self.hp = self.max_hp
        self.radius = 14
        self.state = MOVE
        self.t_state = 0.0            # time left in current state
        self.cooldown = 0.0
        self.stun = 0.0
        self.kb_x = self.kb_y = 0.0   # knockback impulse, decays fast
        self.sweep = 0.0              # current swing angle (world)
        self.sweep_prev = 0.0
        self.hit_done = False         # one hit per swing
        self.strafe_dir = rng.choice((-1.0, 1.0))
        self.strafe_t = rng.uniform(1.0, 2.5)
        self.alive = True

    # -- helpers -----------------------------------------------------------

    def bearing_to(self, foe):
        return math.atan2(foe.y - self.y, foe.x - self.x)

    def dist_to(self, foe):
        return math.hypot(foe.x - self.x, foe.y - self.y)

    def turn_toward(self, target_angle, dt, rate=TURN_RATE):
        d = angdiff(target_angle, self.facing)
        step = max(-rate * dt, min(rate * dt, d))
        self.facing = (self.facing + step) % (2 * math.pi)

    def move(self, dx, dy, dt, speed=MOVE_SPEED):
        n = math.hypot(dx, dy)
        if n > 1e-6:
            self.x += dx / n * speed * dt
            self.y += dy / n * speed * dt

    # -- per-tick update ---------------------------------------------------

    def update(self, sim, dt):
        rng = sim.rng
        wd = self.weapon

        # knockback always applies, even while stunned
        self.x += self.kb_x * dt
        self.y += self.kb_y * dt
        self.kb_x *= 0.85
        self.kb_y *= 0.85

        if self.stun > 0:
            self.stun -= dt
            self.clamp()
            return
        if self.cooldown > 0:
            self.cooldown -= dt

        # target picking: keep the current target unless it's dead or
        # someone else is clearly (20%+) closer -- avoids flip-flopping
        if self.target is None or not self.target.alive:
            self.target = sim.nearest_enemy(self)
        elif self.state == MOVE:
            near = sim.nearest_enemy(self)
            if near is not self.target and \
                    self.dist_to(near) < self.dist_to(self.target) * 0.8:
                self.target = near
        foe = self.target
        if foe is None:
            self.clamp()
            return

        bearing = self.bearing_to(foe)
        dist = self.dist_to(foe)

        if self.state == MOVE:
            self.turn_toward(bearing, dt)
            self.strafe_t -= dt
            if self.strafe_t <= 0:            # change circling direction now and then
                self.strafe_dir = -self.strafe_dir
                self.strafe_t = rng.uniform(1.0, 2.5)

            if wd.kind == "ranged" and dist < wd.min_range:
                self.move(self.x - foe.x, self.y - foe.y, dt)   # kite away
            elif dist > wd.pref_range:
                self.move(foe.x - self.x, foe.y - self.y, dt)
            else:
                # in range: circle the foe while waiting on cooldown
                px, py = -(foe.y - self.y), (foe.x - self.x)
                self.move(px * self.strafe_dir, py * self.strafe_dir, dt,
                          speed=MOVE_SPEED * 0.55)
                if self.cooldown <= 0 and abs(angdiff(bearing, self.facing)) < 0.5:
                    self.state = WINDUP
                    self.t_state = wd.windup

        elif self.state == WINDUP:
            self.turn_toward(bearing, dt, rate=TURN_RATE * 0.4)  # can track a bit
            self.t_state -= dt
            if self.t_state <= 0:
                if wd.kind == "melee":
                    self.state = SWING
                    self.t_state = wd.strike
                    self.hit_done = False
                    self.sweep = self.sweep_prev = self.facing - wd.arc / 2
                else:
                    sim.fire_projectile(self, foe)
                    self.state = RECOVER
                    self.t_state = wd.recover

        elif self.state == SWING:
            self.t_state -= dt
            p = 1.0 - max(self.t_state, 0.0) / wd.strike
            self.sweep_prev = self.sweep
            self.sweep = self.facing - wd.arc / 2 + wd.arc * p
            self.try_hit(sim)
            if self.t_state <= 0:
                self.state = RECOVER
                self.t_state = wd.recover

        elif self.state == RECOVER:
            self.t_state -= dt
            if self.t_state <= 0:
                self.state = MOVE
                self.cooldown = wd.cooldown * rng.uniform(0.85, 1.3)

        self.clamp()   # (crowd separation happens in Sim.step, over all pairs)

    def try_hit(self, sim):
        """Hit lands the tick the sweeping stick crosses an enemy's bearing.
        Any enemy in the arc can be clipped, not just the current target."""
        if self.hit_done:
            return
        wd = self.weapon
        for foe in sim.fighters:
            if foe.team == self.team or not foe.alive:
                continue
            if self.dist_to(foe) > wd.reach + foe.radius:
                continue
            bearing = self.bearing_to(foe)
            a = angdiff(self.sweep_prev, bearing)
            b = angdiff(self.sweep, bearing)
            if a <= 0 <= b or abs(b) < 0.25:
                self.hit_done = True
                sim.apply_hit(self, foe, knockback=150.0)
                return

    def clamp(self):
        self.x = max(WALL_PAD, min(ARENA_W - WALL_PAD, self.x))
        self.y = max(WALL_PAD, min(ARENA_H - WALL_PAD, self.y))


class Projectile:
    def __init__(self, owner, x, y, angle, weapon):
        self.owner = owner
        self.weapon = weapon
        self.x, self.y = x, y
        self.vx = math.cos(angle) * weapon.proj_speed
        self.vy = math.sin(angle) * weapon.proj_speed
        self.ttl = weapon.reach / weapon.proj_speed
        self.radius = 3
        self.alive = True

    def update(self, sim, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.ttl -= dt
        if self.ttl <= 0 or not (0 < self.x < ARENA_W and 0 < self.y < ARENA_H):
            self.alive = False
            return
        for f in sim.fighters:
            if f.team == self.owner.team or not f.alive:
                continue
            if math.hypot(f.x - self.x, f.y - self.y) < f.radius + self.radius:
                sim.apply_hit(self.owner, f, knockback=60.0, weapon=self.weapon)
                self.alive = False
                return


class Fx:
    """Short-lived visual: kind is 'dmg' (floating text) or 'ring'."""

    def __init__(self, kind, x, y, ttl, text="", color="white"):
        self.kind = kind
        self.x, self.y = x, y
        self.ttl = self.ttl0 = ttl
        self.text = text
        self.color = color

    def update(self, dt):
        self.ttl -= dt
        if self.kind == "dmg":
            self.y -= 28 * dt


# ---------------------------------------------------------------- sim world

class Sim:
    def __init__(self, seed, team_a, team_b):
        """team_a / team_b: lists of (name, weapon_key), 1-5 fighters each.
        This roster interface is what the wider game will feed later."""
        self.seed = seed
        self.rng = random.Random(seed)
        self.t = 0.0
        self.winner = None            # None, a TEAM_NAMES entry, or "draw"
        self.projectiles = []
        self.fx = []
        self.events = []              # (time, text) appended for the log
        self.fighters = []
        for team, (specs, x0, face) in enumerate((
                (team_a, 120, 0.0),
                (team_b, ARENA_W - 120, math.pi))):
            n = len(specs)
            for i, (name, wkey) in enumerate(specs):
                y = ARENA_H / 2 + (i - (n - 1) / 2) * 72
                self.fighters.append(
                    Fighter(name, team, x0, y, face, wkey, self.rng))
        self.log(f"Red {len(team_a)} v {len(team_b)} Blue -- seed {seed}")

    def nearest_enemy(self, f):
        best, best_d = None, float("inf")
        for g in self.fighters:
            if g.team == f.team or not g.alive:
                continue
            d = f.dist_to(g)
            if d < best_d:
                best, best_d = g, d
        return best

    def log(self, text):
        self.events.append((self.t, text))

    def step(self):
        if self.winner is not None:
            return
        self.t += DT
        alive = [f for f in self.fighters if f.alive]
        for f in alive:
            f.update(self, DT)

        # crowd separation: shove any overlapping pair apart (allies too)
        for i, f in enumerate(alive):
            for g in alive[i + 1:]:
                d = f.dist_to(g)
                if 1e-6 < d < f.radius + g.radius:
                    push = (f.radius + g.radius - d) / 2
                    nx, ny = (g.x - f.x) / d, (g.y - f.y) / d
                    f.x -= nx * push
                    f.y -= ny * push
                    g.x += nx * push
                    g.y += ny * push
            f.clamp()

        for p in self.projectiles:
            p.update(self, DT)
        self.projectiles = [p for p in self.projectiles if p.alive]
        for fx in self.fx:
            fx.update(DT)
        self.fx = [f for f in self.fx if f.ttl > 0]

        dead = [f for f in self.fighters if f.hp <= 0 and f.alive]
        for f in dead:
            f.alive = False
            self.log(f"{f.name} is down!")
        if dead:
            up = [sum(1 for f in self.fighters if f.team == t and f.alive)
                  for t in (0, 1)]
            if up[0] == 0 and up[1] == 0:
                self.winner = "draw"
                self.log("Mutual wipeout -- it's a draw!")
            elif up[0] == 0 or up[1] == 0:
                t = 1 if up[0] == 0 else 0
                self.winner = TEAM_NAMES[t]
                self.log(f"{self.winner} wins in {self.t:.1f}s"
                         f" ({up[t]} standing)")

    def apply_hit(self, attacker, target, knockback, weapon=None):
        wd = weapon or attacker.weapon
        dmg = self.rng.randint(*wd.dmg)
        crit = self.rng.random() < CRIT_CHANCE
        if crit:
            dmg *= 2
        target.hp -= dmg
        ang = math.atan2(target.y - attacker.y, target.x - attacker.x)
        target.kb_x += math.cos(ang) * knockback
        target.kb_y += math.sin(ang) * knockback
        target.stun = 0.30 if crit else 0.20
        self.fx.append(Fx("ring", target.x, target.y, 0.25))
        self.fx.append(Fx("dmg", target.x, target.y - 22, 0.9,
                          text=f"{dmg}{'!' if crit else ''}",
                          color="#ffd24d" if crit else "white"))
        self.log(f"{attacker.name} hits {target.name} for {dmg}"
                 f" ({wd.name}{', CRIT' if crit else ''})")

    def fire_projectile(self, shooter, foe):
        ang = shooter.bearing_to(foe) + self.rng.gauss(0, math.radians(4))
        self.projectiles.append(
            Projectile(shooter, shooter.x, shooter.y, ang, shooter.weapon))
        self.log(f"{shooter.name} lets fly ({shooter.weapon.name})")


def run_headless(seed, team_a, team_b, max_time=180.0):
    """Resolve a fight with no window -- the wider game's entry point.

    >>> run_headless(7, [("Ash", "Stick")], [("Bolt", "Sling")])["winner"]
    """
    sim = Sim(seed, team_a, team_b)
    while sim.winner is None and sim.t < max_time:
        sim.step()
    return {
        "winner": sim.winner or "timeout",
        "time": round(sim.t, 2),
        "survivors": [(f.name, f.hp) for f in sim.fighters if f.alive],
        "events": sim.events,
    }


# ---------------------------------------------------------------- tk shell

class App:
    def __init__(self, root):
        self.root = root
        root.title("pyCombatArena 01")
        root.configure(bg="#1d2126")
        root.resizable(False, False)

        self.canvas = tk.Canvas(root, width=ARENA_W, height=ARENA_H,
                                bg="#232a31", highlightthickness=0)
        self.canvas.grid(row=0, column=0, rowspan=2, padx=(10, 6), pady=10)

        panel = tk.Frame(root, bg="#1d2126")
        panel.grid(row=0, column=1, sticky="new", padx=(0, 10), pady=(12, 0))
        self.build_panel(panel)

        self.log_text = tk.Text(root, width=38, height=14, bg="#14171b",
                                fg="#c9d2dc", relief="flat", state="disabled",
                                font=("Consolas", 9), wrap="word")
        self.log_text.grid(row=1, column=1, sticky="nsew",
                           padx=(0, 10), pady=(6, 10))

        self.running = False
        self.accum = 0.0
        self.logged = 0               # how many sim events already printed
        self.sim = None
        self.new_fight(seed=random.randrange(1_000_000))
        self.tick()

    # -- controls ----------------------------------------------------------

    def build_panel(self, panel):
        def lbl(text, r):
            tk.Label(panel, text=text, bg="#1d2126", fg="#8a949e",
                     font=("Segoe UI", 9)).grid(row=r, column=0,
                                                sticky="w", pady=(6, 0))
        tk.Label(panel, text="pyCombatArena", bg="#1d2126", fg="#e8edf2",
                 font=("Segoe UI", 13, "bold")).grid(row=0, column=0,
                                                     columnspan=2, sticky="w")

        self.btn_start = tk.Button(panel, text="Start", width=10,
                                   command=self.toggle)
        self.btn_start.grid(row=1, column=0, sticky="w", pady=6)
        tk.Button(panel, text="New Fight", width=10,
                  command=lambda: self.new_fight(
                      random.randrange(1_000_000))).grid(row=1, column=1,
                                                         sticky="w", padx=4)
        tk.Button(panel, text="Rematch (same seed)", width=22,
                  command=lambda: self.new_fight(self.sim.seed)
                  ).grid(row=2, column=0, columnspan=2, sticky="w")

        lbl("Speed", 3)
        self.speed = tk.DoubleVar(value=1.0)
        tk.Scale(panel, variable=self.speed, from_=0.5, to=4.0,
                 resolution=0.5, orient="horizontal", length=180,
                 bg="#1d2126", fg="#c9d2dc", highlightthickness=0
                 ).grid(row=4, column=0, columnspan=2, sticky="w")

        names = list(WEAPONS) + ["Mixed"]
        self.size_a = tk.IntVar(value=3)
        self.size_b = tk.IntVar(value=3)
        self.weap_a = tk.StringVar(value="Stick")
        self.weap_b = tk.StringVar(value="Stick")
        for r, (label, size_var, weap_var) in enumerate((
                ("Red team", self.size_a, self.weap_a),
                ("Blue team", self.size_b, self.weap_b))):
            row = 5 + r * 2
            lbl(f"{label}: fighters / weapon", row)
            frame = tk.Frame(panel, bg="#1d2126")
            frame.grid(row=row + 1, column=0, columnspan=2, sticky="w")
            tk.Spinbox(frame, from_=1, to=5, width=4, textvariable=size_var,
                       state="readonly").pack(side="left")
            ttk.Combobox(frame, textvariable=weap_var, values=names,
                         state="readonly", width=10).pack(side="left", padx=6)
        tk.Label(panel, text="(team setup applies on New Fight)",
                 bg="#1d2126", fg="#5c656e", font=("Segoe UI", 8)
                 ).grid(row=9, column=0, columnspan=2, sticky="w")

    def toggle(self):
        self.running = not self.running
        self.btn_start.config(text="Pause" if self.running else "Start")

    def new_fight(self, seed):
        # "Mixed" weapon rolls come off the seed too, so Rematch replays them
        roll = random.Random(seed ^ 0xC0FFEE)

        def roster(names, size_var, weap_var):
            choice = weap_var.get()
            return [(names[i],
                     roll.choice(list(WEAPONS)) if choice == "Mixed"
                     else choice)
                    for i in range(size_var.get())]

        self.sim = Sim(seed,
                       roster(RED_NAMES, self.size_a, self.weap_a),
                       roster(BLUE_NAMES, self.size_b, self.weap_b))
        self.logged = 0
        self.running = False
        self.btn_start.config(text="Start")
        self.flush_log(clear=True)
        self.render()

    # -- main loop ---------------------------------------------------------

    def tick(self):
        if self.running:
            self.accum += self.speed.get()
            while self.accum >= 1.0:
                self.sim.step()
                self.accum -= 1.0
            self.flush_log()
            self.render()
            if self.sim.winner is not None:
                self.running = False
                self.btn_start.config(text="Start")
        self.root.after(33, self.tick)

    def flush_log(self, clear=False):
        self.log_text.config(state="normal")
        if clear:
            self.log_text.delete("1.0", "end")
        for t, text in self.sim.events[self.logged:]:
            self.log_text.insert("end", f"[{t:5.1f}] {text}\n")
        self.logged = len(self.sim.events)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    # -- drawing -----------------------------------------------------------

    def render(self):
        c = self.canvas
        c.delete("all")
        for gx in range(0, ARENA_W, 40):
            c.create_line(gx, 0, gx, ARENA_H, fill="#28313a")
        for gy in range(0, ARENA_H, 40):
            c.create_line(0, gy, ARENA_W, gy, fill="#28313a")
        c.create_rectangle(WALL_PAD - 14, WALL_PAD - 14,
                           ARENA_W - WALL_PAD + 14, ARENA_H - WALL_PAD + 14,
                           outline="#3d4854", width=3)

        for p in self.sim.projectiles:
            c.create_line(p.x - p.vx * 0.04, p.y - p.vy * 0.04, p.x, p.y,
                          fill="#7d7468", width=2)
            c.create_oval(p.x - 3, p.y - 3, p.x + 3, p.y + 3,
                          fill="#cfc4b2", outline="")

        for f in self.sim.fighters:
            self.draw_fighter(f)

        for fx in self.sim.fx:
            if fx.kind == "ring":
                r = 10 + 26 * (1 - fx.ttl / fx.ttl0)
                c.create_oval(fx.x - r, fx.y - r, fx.x + r, fx.y + r,
                              outline="#ffdf8a", width=2)
            else:
                c.create_text(fx.x, fx.y, text=fx.text, fill=fx.color,
                              font=("Segoe UI", 11, "bold"))

        c.create_text(8, 10, anchor="w", fill="#5c656e",
                      font=("Consolas", 9),
                      text=f"t={self.sim.t:5.1f}s  seed={self.sim.seed}")
        if self.sim.winner is not None:
            msg = ("It's a draw!" if self.sim.winner == "draw"
                   else f"{self.sim.winner} wins!")
            c.create_text(ARENA_W / 2, ARENA_H / 2 - 10, text=msg,
                          fill="#f2f6fa", font=("Segoe UI", 24, "bold"))
            c.create_text(ARENA_W / 2, ARENA_H / 2 + 22,
                          text="New Fight for a fresh seed / Rematch to replay",
                          fill="#8a949e", font=("Segoe UI", 10))

    def draw_fighter(self, f):
        c = self.canvas
        r = f.radius
        if not f.alive:
            c.create_oval(f.x - r, f.y - r, f.x + r, f.y + r,
                          fill="#3a3f45", outline="#565d64", width=2)
            c.create_line(f.x - 6, f.y - 6, f.x + 6, f.y + 6,
                          fill="#8a949e", width=2)
            c.create_line(f.x - 6, f.y + 6, f.x + 6, f.y - 6,
                          fill="#8a949e", width=2)
            return

        wd = f.weapon
        # weapon line: angle depends on state so you can read the attack
        if f.state == SWING:
            wang, wlen = f.sweep, wd.reach
        elif f.state == WINDUP:
            frac = 1 - f.t_state / wd.windup          # pull back as it charges
            wang = f.facing - wd.arc / 2 - 0.4 * frac
            wlen = wd.reach * (0.55 if wd.kind == "melee" else 0.35)
        else:
            wang = f.facing + 0.5
            wlen = (wd.reach * 0.55 if wd.kind == "melee" else 16)
        c.create_line(f.x, f.y,
                      f.x + math.cos(wang) * wlen,
                      f.y + math.sin(wang) * wlen,
                      fill=wd.color, width=wd.width, capstyle="round")

        outline = "#ffd24d" if f.stun > 0 else "#10141a"
        c.create_oval(f.x - r, f.y - r, f.x + r, f.y + r,
                      fill=f.color, outline=outline, width=2)
        c.create_line(f.x, f.y,
                      f.x + math.cos(f.facing) * r,
                      f.y + math.sin(f.facing) * r,
                      fill="#10141a", width=2)

        bw = 36
        frac = max(f.hp, 0) / f.max_hp
        bar_col = "#57c96b" if frac > 0.5 else ("#e0b53f" if frac > 0.25
                                                else "#e05d5d")
        c.create_rectangle(f.x - bw / 2, f.y - r - 12, f.x + bw / 2,
                           f.y - r - 7, fill="#14171b", outline="")
        c.create_rectangle(f.x - bw / 2, f.y - r - 12,
                           f.x - bw / 2 + bw * frac, f.y - r - 7,
                           fill=bar_col, outline="")
        c.create_text(f.x, f.y + r + 11, text=f.name, fill="#c9d2dc",
                      font=("Segoe UI", 9, "bold"))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
