"""
zpyCombatArena03 -- roster-driven top-down team combat sim (stdlib only).

zpy schema: fighters come from universal_characters_master.csv; their
0-100 attributes drive everything -- damage, dodge/block, attack tempo,
panic, and target choice. The tkinter window is just a viewer: the wider
game should call run_headless() or drive Sim directly.

v03 phased tick (removes update-order bias):
  0 snapshot   everyone's position/HP/state is frozen for this tick
  1 decide     each fighter acts against the snapshot; consequences of
               attacks (damage, stun, knockdown, effects) are queued,
               not applied, and every random roll comes from the acting
               fighter's own RNG stream -- so neither list position nor
               another fighter's rolls can change your fate
  2 commit     queued consequences land simultaneously; crowd separation
  3 projectiles fly and resolve (same queued-commit rule)
  4 effects    hazards, damage-over-time, visuals
  5 deaths     marked only here -- two lethal blows in one tick is a
               genuine mutual kill (an explicit draw), not a list quirk

v03 defense model (directional + tiered interruption):
  guard arc   melee fighters block inside a frontal 120-degree arc (full
              strength within 60), weaker deflection out to 110 degrees
              per side, nothing from behind; attacks from behind are also
              harder to dodge. Blocking works in MOVE and (weaker) RECOVER,
              never mid-attack. Heavy weapons partially smash through.
  blocked     a blocked hit does 35%/55% damage (front/side), cannot crit,
              gives reduced knockback, and never staggers or knocks down.
  interrupts  hit reaction (0.2s flinch) pauses an attack; a stagger LOSES
              the attack (back to MOVE, partial cooldown) and grants 2.5s
              of poise (stagger immunity) against stun-lock; a knockdown
              cancels the attack outright with full cooldown.

How attributes are used:
  Physique  strength/stamina/lifespan -> HP        speed -> move speed
            agility/balance/perception -> dodge    dexterity/focus -> crits
            composure/balance/strength -> block    balance resists knockdown
  Weapon    skill 0-100 per weapon TYPE = weighted blend of
  skill     technical_aptitude/focus/composure/patience/aggression
            (weights differ per type; see SKILL_WEIGHTS). Skill raises
            damage + accuracy and quickens windup/recovery.
  Behaviour intelligence+perception -> prefer wounded targets
            risk_assessment -> avoid high-threat enemies, safe bomb throws
            courage/willpower -> panic threshold; determination -> flee time
            aggression -> attack tempo and how tight they close in

Combat variety: dodge, block, crits, stagger stuns, knockdowns (falls),
bleed, poison, burn DoTs, bombs (AoE with falloff + friendly fire), and
firebombs that leave burning ground patches.

WEAPONS holds 25 weapons across 5 types -- each is one data row, so new
weapons are cheap. Same seed = identical fight, including team draws.
"""

import csv
import math
import os
import random
import tkinter as tk
from tkinter import ttk

# ---------------------------------------------------------------- constants

ARENA_W, ARENA_H = 640, 560
WALL_PAD = 24
DT = 1 / 30
TURN_RATE = math.radians(540)
MOVE, WINDUP, SWING, RECOVER = "MOVE", "WINDUP", "SWING", "RECOVER"

TEAM_NAMES = ("Red team", "Blue team")
TEAM_COLORS = ("#e05d5d", "#5d8fe0")
EFFECT_COLORS = {"bleed": "#ff7a6e", "poison": "#8fd48a", "burn": "#f0a03f"}


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def mix(c1, c2, f):
    """Blend two #rrggbb colors; f=0 gives c1, f=1 gives c2."""
    a = int(c1[1:], 16)
    b = int(c2[1:], 16)
    ch = [round((a >> s & 255) * (1 - f) + (b >> s & 255) * f)
          for s in (16, 8, 0)]
    return f"#{ch[0]:02x}{ch[1]:02x}{ch[2]:02x}"


def angdiff(a, b):
    """Signed smallest difference a-b, in [-pi, pi]."""
    return (a - b + math.pi) % (2 * math.pi) - math.pi


# ---------------------------------------------------------------- weapons

class Weapon:
    def __init__(self, name, wtype, reach, arc_deg, dmg, windup, strike,
                 recover, cooldown, color, width, proj_speed=0.0,
                 pref_range=0.0, min_range=0.0, bleed=None, poison=None,
                 stun_p=0.0, kd_p=0.0, aoe=None, fire=None,
                 cleave=(1, 0.0), kb_mult=1.0):
        self.name = name
        self.wtype = wtype            # blunt | blade | polearm | ranged | explosive
        self.melee = wtype in ("blunt", "blade", "polearm")
        self.reach = reach            # melee: length | ranged: max flight px
        self.arc = math.radians(arc_deg)
        self.dmg = dmg
        self.windup = windup
        self.strike = strike
        self.recover = recover
        self.cooldown = cooldown
        self.color = color
        self.width = width
        self.proj_speed = proj_speed
        self.pref_range = pref_range or reach * 0.8
        self.min_range = min_range
        self.bleed = bleed            # (chance, dps, seconds)
        self.poison = poison
        self.stun_p = stun_p          # stagger chance on hit
        self.kd_p = kd_p              # knockdown chance on hit
        self.aoe = aoe                # (radius, knockdown chance at center)
        self.fire = fire              # (dps, patch seconds) ground fire
        self.cleave = cleave          # (max targets, dmg falloff per extra)
        self.kb_mult = kb_mult        # knockback scale (shoves > pokes)


def _w(name, wtype, **kw):
    return name, Weapon(name, wtype, **kw)


WEAPONS = dict((
    # -- blunt: strength-driven, staggers and knockdowns
    _w("Stick", "blunt", reach=48, arc_deg=110, dmg=(4, 7), windup=.30,
       strike=.16, recover=.38, cooldown=.32, color="#c8a165", width=4,
       stun_p=.05),
    _w("Club", "blunt", reach=44, arc_deg=95, dmg=(7, 12), windup=.48,
       strike=.20, recover=.55, cooldown=.50, color="#8a6d4f", width=6,
       stun_p=.15, kd_p=.10),
    _w("Mace", "blunt", reach=44, arc_deg=90, dmg=(9, 14), windup=.52,
       strike=.20, recover=.58, cooldown=.55, color="#9aa1ab", width=6,
       stun_p=.20, kd_p=.12),
    _w("Warhammer", "blunt", reach=46, arc_deg=85, dmg=(12, 19), windup=.70,
       strike=.22, recover=.75, cooldown=.65, color="#7d848d", width=8,
       stun_p=.28, kd_p=.25, cleave=(2, .35)),
    _w("Quarterstaff", "blunt", reach=62, arc_deg=130, dmg=(5, 9), windup=.34,
       strike=.18, recover=.40, cooldown=.35, color="#b59a6a", width=4,
       stun_p=.10, kd_p=.15, cleave=(3, .30)),
    _w("Flail", "blunt", reach=50, arc_deg=120, dmg=(8, 14), windup=.55,
       strike=.24, recover=.60, cooldown=.50, color="#6f7680", width=5,
       stun_p=.18, kd_p=.18, cleave=(2, .25)),
    # -- blade: finesse, bleeds
    _w("Dagger", "blade", reach=30, arc_deg=70, dmg=(4, 7), windup=.22,
       strike=.12, recover=.28, cooldown=.22, color="#c7ccd4", width=3,
       bleed=(.30, 2.5, 2.5)),
    _w("Shortsword", "blade", reach=42, arc_deg=90, dmg=(6, 10), windup=.34,
       strike=.16, recover=.40, cooldown=.35, color="#c7ccd4", width=4,
       bleed=(.25, 3.0, 3.0)),
    _w("Longsword", "blade", reach=50, arc_deg=100, dmg=(8, 13), windup=.40,
       strike=.18, recover=.46, cooldown=.42, color="#d4d9e0", width=4,
       bleed=(.25, 3.0, 3.0)),
    _w("Greatsword", "blade", reach=58, arc_deg=110, dmg=(11, 17), windup=.60,
       strike=.22, recover=.66, cooldown=.55, color="#d4d9e0", width=6,
       bleed=(.20, 3.5, 3.0), kd_p=.08, cleave=(3, .35)),
    _w("Battleaxe", "blade", reach=46, arc_deg=95, dmg=(10, 16), windup=.55,
       strike=.20, recover=.62, cooldown=.50, color="#b8968a", width=6,
       bleed=(.35, 4.0, 3.0), cleave=(2, .30)),
    _w("Scimitar", "blade", reach=46, arc_deg=105, dmg=(7, 11), windup=.34,
       strike=.15, recover=.40, cooldown=.34, color="#d9cfa8", width=4,
       bleed=(.30, 3.0, 3.0), cleave=(2, .25)),
    # -- polearm: reach, narrow arcs
    _w("Spear", "polearm", reach=70, arc_deg=40, dmg=(7, 11), windup=.40,
       strike=.14, recover=.48, cooldown=.42, color="#b0b8c4", width=3),
    _w("Pike", "polearm", reach=84, arc_deg=28, dmg=(8, 12), windup=.48,
       strike=.14, recover=.55, cooldown=.50, color="#a7afba", width=3),
    _w("Halberd", "polearm", reach=74, arc_deg=55, dmg=(10, 15), windup=.55,
       strike=.18, recover=.62, cooldown=.52, color="#98a0ac", width=4,
       bleed=(.20, 3.0, 3.0), kd_p=.08, cleave=(2, .30)),
    _w("Glaive", "polearm", reach=72, arc_deg=70, dmg=(9, 13), windup=.48,
       strike=.17, recover=.55, cooldown=.46, color="#a2adc0", width=4,
       bleed=(.25, 3.0, 3.0), cleave=(3, .30)),
    # -- ranged: projectiles
    _w("Sling", "ranged", reach=300, arc_deg=0, dmg=(5, 9), windup=.65,
       strike=0, recover=.32, cooldown=.50, color="#9a8f80", width=2,
       proj_speed=340, pref_range=190, min_range=120),
    _w("Shortbow", "ranged", reach=330, arc_deg=0, dmg=(6, 10), windup=.55,
       strike=0, recover=.30, cooldown=.45, color="#a8845c", width=2,
       proj_speed=430, pref_range=200, min_range=130),
    _w("Longbow", "ranged", reach=420, arc_deg=0, dmg=(8, 13), windup=.80,
       strike=0, recover=.35, cooldown=.55, color="#8f6f4a", width=2,
       proj_speed=500, pref_range=250, min_range=160),
    _w("Crossbow", "ranged", reach=380, arc_deg=0, dmg=(10, 16), windup=1.05,
       strike=0, recover=.40, cooldown=1.00, color="#6e5b45", width=3,
       proj_speed=560, pref_range=230, min_range=150),
    _w("Javelin", "ranged", reach=240, arc_deg=0, dmg=(9, 15), windup=.70,
       strike=0, recover=.40, cooldown=.75, color="#b0a48e", width=3,
       proj_speed=320, pref_range=170, min_range=110, kd_p=.10),
    _w("Throwing Knives", "ranged", reach=220, arc_deg=0, dmg=(4, 7),
       windup=.30, strike=0, recover=.25, cooldown=.30, color="#c7ccd4",
       width=2, proj_speed=380, pref_range=160, min_range=100,
       bleed=(.25, 2.5, 2.5)),
    _w("Blowdart", "ranged", reach=260, arc_deg=0, dmg=(2, 4), windup=.50,
       strike=0, recover=.30, cooldown=.45, color="#7e9a6e", width=2,
       proj_speed=300, pref_range=190, min_range=130,
       poison=(.85, 2.0, 5.0)),
    # -- explosive: lobbed, AoE, friendly fire
    _w("Bomb", "explosive", reach=260, arc_deg=0, dmg=(14, 22), windup=.85,
       strike=0, recover=.60, cooldown=1.40, color="#3a3f45", width=4,
       proj_speed=230, pref_range=180, min_range=120, aoe=(56, .45)),
    _w("Firebomb", "explosive", reach=260, arc_deg=0, dmg=(7, 12), windup=.80,
       strike=0, recover=.55, cooldown=1.30, color="#c25b2e", width=4,
       proj_speed=230, pref_range=180, min_range=120, aoe=(48, .10),
       fire=(7.0, 3.5)),
))

WEAPONS_BY_TYPE = {}
for _wp in WEAPONS.values():
    WEAPONS_BY_TYPE.setdefault(_wp.wtype, []).append(_wp.name)

# what a cornered shooter swings when an enemy is on top of them: feeble
# damage, but a hefty shove (kb_mult) and a real stagger chance -- the
# point is to make room to shoot, not to win the brawl. Not in WEAPONS:
# nobody carries it, every ranged/explosive fighter falls back on it.
BASH_WEAPON = Weapon("Weapon Butt", "blunt", reach=34, arc_deg=100,
                     dmg=(2, 5), windup=.30, strike=.12, recover=.35,
                     cooldown=1.60, color="#9aa1ab", width=3,
                     stun_p=.15, kd_p=.08, kb_mult=1.6)

# per-type weights over the five weapon-ability attributes
SKILL_WEIGHTS = {
    "blunt":     {"aggression": .35, "composure": .25, "technical_aptitude": .15,
                  "focus": .15, "patience": .10},
    "blade":     {"technical_aptitude": .30, "focus": .25, "composure": .20,
                  "aggression": .15, "patience": .10},
    "polearm":   {"patience": .30, "technical_aptitude": .25, "focus": .20,
                  "composure": .15, "aggression": .10},
    "ranged":    {"focus": .35, "patience": .25, "technical_aptitude": .20,
                  "composure": .15, "aggression": .05},
    "explosive": {"technical_aptitude": .35, "composure": .25, "focus": .20,
                  "patience": .15, "aggression": .05},
}

# per-type physique mix that scales damage output
POWER_MIX = {
    "blunt":     {"strength": .70, "stamina": .30},
    "blade":     {"strength": .45, "dexterity": .40, "speed": .15},
    "polearm":   {"strength": .40, "dexterity": .30, "balance": .30},
    "ranged":    {"dexterity": .55, "strength": .25, "speed": .20},
    "explosive": {"dexterity": .60, "strength": .40},
}


def ga(char, key):
    """Attribute lookup with a neutral default for missing columns."""
    v = char.get(key, 50)
    return v if isinstance(v, int) else 50


def weapon_skill(char, wtype):
    return sum(ga(char, k) * w for k, w in SKILL_WEIGHTS[wtype].items())


def load_roster(path=None):
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "universal_characters_master.csv")
    roster = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            c = {}
            for k, v in row.items():
                v = (v or "").strip()
                c[k] = int(v) if v.lstrip("-").isdigit() else v
            roster.append(c)
    return roster


# ---------------------------------------------------------------- entities

class Effect:
    """A damage-over-time on a fighter (bleed / poison / burn)."""

    def __init__(self, kind, dps, ttl, src):
        self.kind = kind
        self.dps = dps
        self.ttl = ttl
        self.src = src               # fighter credited with the damage
        self.acc = 0.0               # accumulated damage not yet shown
        self.tick = 0.0


class Fighter:
    def __init__(self, char, team, x, y, facing, weapon_key, rng, slot=0):
        self.char = char
        self.slot = slot             # stable id: iteration order never varies
        self.name = char.get("display_name") or char.get("first_name", "?")
        self.team = team
        self.color = TEAM_COLORS[team]
        self.x, self.y = x, y
        self.facing = facing
        self.weapon = WEAPONS[weapon_key]
        self.radius = 13

        # -- derived from attributes (0-100 scale) --
        at = lambda k: ga(char, k)
        self.max_hp = int(45 + at("strength") * .30 + at("stamina") * .25
                          + at("lifespan") * .15)
        self.hp = float(self.max_hp)
        self.move_speed = 62 + at("speed") * .55
        self.dodge_stat = (at("agility") * .4 + at("balance") * .3
                           + at("perception") * .3)
        self.block_stat = (at("composure") * .4 + at("balance") * .3
                           + at("strength") * .3)
        self.skill = weapon_skill(char, self.weapon.wtype)
        mix = sum(at(k) * w for k, w in POWER_MIX[self.weapon.wtype].items())
        self.power_mult = 0.7 + mix / 100 * 0.6
        self.crit_p = 0.05 + at("dexterity") * .0008 + at("focus") * .0005
        self.atk_speed = clamp(1.20 - self.skill / 100 * .25
                               - at("speed") / 100 * .15, 0.75, 1.20)
        self.cd_mult = 1.25 - at("aggression") / 100 * 0.5
        self.smart = (at("intelligence") + at("perception")) / 2
        self.balance = at("balance")
        self.composure = at("composure")
        self.panic_threshold = clamp(0.32 - at("courage") * .0028
                                     - at("willpower") * .0008, 0.0, 0.35)
        self.flee_time = 2.0 + (100 - at("determination")) / 100 * 2.0
        self.risk = at("risk_assessment")

        # -- runtime state --
        self.rng = rng               # personal stream: my rolls are mine alone
        self.sx, self.sy = x, y      # tick-start snapshot (phase 0)
        self.svx = self.svy = 0.0
        self.shp = self.hp
        self.s_state = MOVE
        self.s_facing = facing
        self.s_down = False
        self.s_react = True
        self.poise_cd = 0.0          # stagger immunity after being staggered
        self.state = MOVE
        self.t_state = 0.0
        self.cooldown = 0.0
        self.stun = 0.0
        self.down = 0.0              # knocked off their feet
        self.flee = 0.0              # panicking
        self.panic_cd = 0.0
        self.kb_x = self.kb_y = 0.0
        self.vx = self.vy = 0.0      # measured velocity (for shot leading)
        self.sweep = self.sweep_prev = 0.0
        self.hits_landed = 0         # contacts made by the current swing
        self.swing_tried = set()     # foes already rolled against this swing
        self.effects = []
        self.target = None
        self.retarget_t = 0.0
        self.hold_t = 0.0            # time spent holding an obstructed shot
        self.bashing = False         # mid weapon-butt shove (ranged fighters)
        self.strafe_dir = rng.choice((-1.0, 1.0))
        self.strafe_t = rng.uniform(1.0, 2.5)
        self.dmg_dealt = 0.0
        self.alive = True

    # -- helpers -----------------------------------------------------------

    def active_weapon(self):
        return BASH_WEAPON if self.bashing else self.weapon

    def bearing_to(self, foe):
        """Angle to the foe's tick-start snapshot position."""
        return math.atan2(foe.sy - self.y, foe.sx - self.x)

    def dist_to(self, foe):
        return math.hypot(foe.sx - self.x, foe.sy - self.y)

    def turn_toward(self, target_angle, dt, rate=TURN_RATE):
        d = angdiff(target_angle, self.facing)
        self.facing = (self.facing
                       + max(-rate * dt, min(rate * dt, d))) % (2 * math.pi)

    def move(self, dx, dy, dt, mult=1.0):
        n = math.hypot(dx, dy)
        if n > 1e-6:
            self.x += dx / n * self.move_speed * mult * dt
            self.y += dy / n * self.move_speed * mult * dt

    def clamp_pos(self):
        self.x = max(WALL_PAD, min(ARENA_W - WALL_PAD, self.x))
        self.y = max(WALL_PAD, min(ARENA_H - WALL_PAD, self.y))

    def pick_target(self, sim):
        """Score enemies: distance, minus 'finish the wounded' for smart
        fighters, plus 'avoid the scary one' for high risk_assessment.
        Bombers also aim for enemy clusters and away from own allies."""
        wd = self.weapon
        best, best_s = None, float("inf")
        for g in sim.fighters:
            if g.team == self.team or not g.alive:
                continue
            threat = (g.weapon.dmg[0] + g.weapon.dmg[1]) / 2 * g.power_mult
            s = (self.dist_to(g)
                 - self.smart / 100 * 140 * (1 - g.shp / g.max_hp)
                 + self.risk / 100 * threat * 3)
            if wd.aoe is not None:
                r = wd.aoe[0]
                for h in sim.fighters:
                    if h is g or not h.alive:
                        continue
                    if math.hypot(h.sx - g.sx, h.sy - g.sy) < r:
                        if h.team == self.team:      # ally in the blast
                            s += 90 * self.risk / 100
                        else:                        # juicy cluster
                            s -= 45
                if self.dist_to(g) < wd.min_range:   # too close to bomb
                    s += 60
            if s < best_s:
                best, best_s = g, s
        return best

    # -- per-tick update ---------------------------------------------------

    def update(self, sim, dt):
        rng = self.rng
        wd = self.active_weapon()    # BASH_WEAPON while shoving
        px, py = self.x, self.y

        self.x += self.kb_x * dt
        self.y += self.kb_y * dt
        self.kb_x *= 0.85
        self.kb_y *= 0.85
        self.panic_cd = max(0.0, self.panic_cd - dt)
        self.poise_cd = max(0.0, self.poise_cd - dt)

        if self.down > 0:
            self.down -= dt
            self._end_move(px, py, dt)
            return
        if self.stun > 0:
            self.stun -= dt
            self._end_move(px, py, dt)
            return
        if self.cooldown > 0:
            self.cooldown -= dt

        # panic: low HP + low courage = run for it
        if (self.flee <= 0 and self.panic_cd <= 0 and self.state == MOVE
                and self.hp / self.max_hp < self.panic_threshold):
            self.flee = self.flee_time
            self.panic_cd = 6.0
            sim.log(f"{self.name} loses nerve and flees!")
        if self.flee > 0:
            self.flee -= dt
            near = sim.nearest_enemy(self)
            if near is not None:
                self.turn_toward(self.bearing_to(near) + math.pi, dt)
                self.move(self.x - near.sx, self.y - near.sy, dt, mult=1.1)
            self._end_move(px, py, dt)
            return

        # target selection (sticky, re-scored a few times a second)
        self.retarget_t -= dt
        if self.target is None or not self.target.alive:
            self.target = self.pick_target(sim)
            self.retarget_t = 0.4
        elif self.retarget_t <= 0 and self.state == MOVE:
            self.retarget_t = 0.4
            cand = self.pick_target(sim)
            if cand is not None and cand is not self.target:
                self.target = cand
        foe = self.target
        if foe is None:
            self._end_move(px, py, dt)
            return

        bearing = self.bearing_to(foe)
        dist = self.dist_to(foe)

        if self.state == MOVE:
            self.turn_toward(bearing, dt)
            self.strafe_t -= dt
            if self.strafe_t <= 0:
                self.strafe_dir = -self.strafe_dir
                self.strafe_t = rng.uniform(1.0, 2.5)

            pref = wd.pref_range * (0.85 if wd.melee else 1.0)
            if wd.melee:   # short weapons: bodies collide before pref range
                pref = max(pref, self.radius + foe.radius + 5)
            if not wd.melee and dist < wd.min_range:
                self.move(self.x - foe.sx, self.y - foe.sy, dt)
            elif dist > pref:
                self.move(foe.sx - self.x, foe.sy - self.y, dt)
            else:
                sx, sy = -(foe.sy - self.y), (foe.sx - self.x)
                self.move(sx * self.strafe_dir, sy * self.strafe_dir, dt,
                          mult=0.55)
            # shooters/bombers may loose even mid-retreat, as long as the
            # target sits in the safe band -- otherwise a chased bomber
            # backpedals forever and never throws
            in_window = (dist <= pref if wd.melee
                         else wd.min_range * 0.7 <= dist <= wd.reach * 0.95)
            # careful shooters hold fire while a teammate is in the line,
            # but only briefly -- crowded fights must not paralyze them
            obstructed = (wd.wtype == "ranged" and self.skill > 55
                          and not sim.shot_clear(self, foe))
            if obstructed and in_window and self.cooldown <= 0:
                self.hold_t += dt
            near = sim.nearest_enemy(self)
            if (not wd.melee and self.cooldown <= 0 and near is not None
                    and self.dist_to(near)
                    < self.radius + near.radius + 14):
                # enemy on top of a shooter: weapon-butt shove to make room
                self.bashing = True
                self.target = near
                self.state = WINDUP
                self.t_state = BASH_WEAPON.windup * self.atk_speed
            elif (self.cooldown <= 0 and in_window
                    and abs(angdiff(bearing, self.facing)) < 0.5
                    and sim.safe_to_attack(self, foe)
                    and (not obstructed or self.hold_t > 1.5)):
                self.state = WINDUP
                self.t_state = wd.windup * self.atk_speed
                self.hold_t = 0.0

        elif self.state == WINDUP:
            self.turn_toward(bearing, dt, rate=TURN_RATE * 0.4)
            self.t_state -= dt
            if self.t_state <= 0:
                if wd.melee:
                    self.state = SWING
                    self.t_state = wd.strike
                    self.hits_landed = 0
                    self.swing_tried.clear()
                    self.sweep = self.sweep_prev = self.facing - wd.arc / 2
                else:
                    sim.fire(self, foe)
                    self.state = RECOVER
                    self.t_state = wd.recover * self.atk_speed

        elif self.state == SWING:
            self.t_state -= dt
            p = 1.0 - max(self.t_state, 0.0) / wd.strike
            self.sweep_prev = self.sweep
            self.sweep = self.facing - wd.arc / 2 + wd.arc * p
            self.try_hit(sim)
            if self.t_state <= 0:
                self.state = RECOVER
                self.t_state = wd.recover * self.atk_speed

        elif self.state == RECOVER:
            self.t_state -= dt
            if self.t_state <= 0:
                self.state = MOVE
                self.cooldown = (wd.cooldown * self.cd_mult
                                 * rng.uniform(0.85, 1.3))
                self.bashing = False

        self._end_move(px, py, dt)

    def _end_move(self, px, py, dt):
        self.clamp_pos()
        self.vx = (self.x - px) / dt
        self.vy = (self.y - py) / dt

    def cancel_attack(self, partial):
        """A stagger (partial) or knockdown loses the attack in progress --
        it does not resume after the stun the way a flinch pause does."""
        if self.state in (WINDUP, SWING):
            self.state = MOVE
            self.t_state = 0.0
            self.cooldown = max(self.cooldown,
                                self.active_weapon().cooldown * self.cd_mult
                                * (0.6 if partial else 1.0))
        self.bashing = False

    def try_hit(self, sim):
        """Wide weapons cleave: the sweep keeps resolving contacts until
        cleave's max targets, each extra hit losing falloff damage."""
        wd = self.active_weapon()
        max_t, falloff = wd.cleave
        if self.hits_landed >= max_t:
            return
        for foe in sim.stable_order():
            if (foe.team == self.team or not foe.alive
                    or id(foe) in self.swing_tried):
                continue
            if self.dist_to(foe) > wd.reach + foe.radius:
                continue
            bearing = self.bearing_to(foe)
            a = angdiff(self.sweep_prev, bearing)
            b = angdiff(self.sweep, bearing)
            if a <= 0 <= b or abs(b) < 0.25:
                self.swing_tried.add(id(foe))
                if sim.resolve_attack(
                        self, foe, wd,
                        dmg_mult=(1 - falloff) ** self.hits_landed) != "dodge":
                    self.hits_landed += 1
                    if self.hits_landed >= max_t:
                        return


class Projectile:
    """kind 'bolt' flies straight and collides; 'lob' arcs to a point
    and explodes there (explosives)."""

    def __init__(self, kind, owner, weapon, x, y, tx, ty, rng):
        self.kind = kind
        self.owner = owner
        self.weapon = weapon
        self.x, self.y = x, y
        self.missed = set()          # fighters who already dodged this
        self.alive = True
        if kind == "bolt":
            ang = math.atan2(ty - y, tx - x)
            self.vx = math.cos(ang) * weapon.proj_speed
            self.vy = math.sin(ang) * weapon.proj_speed
            self.ttl = weapon.reach / weapon.proj_speed
        else:
            self.x0, self.y0 = x, y
            self.tx = clamp(tx, WALL_PAD, ARENA_W - WALL_PAD)
            self.ty = clamp(ty, WALL_PAD, ARENA_H - WALL_PAD)
            self.total = max(math.hypot(self.tx - x, self.ty - y)
                             / weapon.proj_speed, 0.2)
            self.t = 0.0

    def update(self, sim, dt):
        if self.kind == "lob":
            self.t += dt
            p = min(self.t / self.total, 1.0)
            self.x = self.x0 + (self.tx - self.x0) * p
            self.y = self.y0 + (self.ty - self.y0) * p
            self.arc_h = 38 * math.sin(math.pi * p)   # draw-only arc height
            if p >= 1.0:
                self.alive = False
                sim.explode(self.owner, self.weapon, self.tx, self.ty)
            return
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.ttl -= dt
        if self.ttl <= 0 or not (0 < self.x < ARENA_W and 0 < self.y < ARENA_H):
            self.alive = False
            return
        for f in sim.stable_order():
            if not f.alive or f is self.owner or id(f) in self.missed:
                continue
            ally = f.team == self.owner.team
            hit_r = f.radius * (0.8 if ally else 1.0) + 3
            if math.hypot(f.x - self.x, f.y - self.y) < hit_r:
                if ally:
                    # a teammate's body stops the shot cold -- no damage,
                    # but the arrow is wasted (lobbed bombs arc overhead)
                    self.alive = False
                    sim.fx.append(Fx("dmg", f.x, f.y - 20, 0.6,
                                     text="thunk", color="#8a949e", r0=8))
                    sim.log(f"{f.name} blocks {self.owner.name}'s shot")
                elif sim.resolve_attack(self.owner, f, self.weapon,
                                        ranged=True) == "dodge":
                    self.missed.add(id(f))   # sails past, may hit another
                else:
                    self.alive = False
                return


class FirePatch:
    def __init__(self, x, y, radius, dps, ttl, owner):
        self.x, self.y = x, y
        self.radius = radius
        self.dps = dps
        self.ttl = ttl
        self.owner = owner


class Fx:
    """kinds: dmg (floating text; r0 doubles as font size), ring, boom"""

    def __init__(self, kind, x, y, ttl, text="", color="white",
                 r0=10, r1=36):
        self.kind = kind
        self.x, self.y = x, y
        self.ttl = self.ttl0 = ttl
        self.text = text
        self.color = color
        self.r0, self.r1 = r0, r1

    def update(self, dt):
        self.ttl -= dt
        if self.kind == "dmg":
            self.y -= 28 * dt


class Particle:
    """A flying speck (blood, sparks, debris, smoke, flame). Purely
    cosmetic -- runs off Sim.vrng so it never disturbs combat rolls.
    Blood may leave a stain on the floor when it lands."""

    def __init__(self, x, y, ang, speed, ttl, r, color,
                 drag=0.88, rise=0.0, stain=None):
        self.x, self.y = x, y
        self.vx = math.cos(ang) * speed
        self.vy = math.sin(ang) * speed
        self.ttl = ttl
        self.r = r
        self.color = color
        self.drag = drag
        self.rise = rise             # px/s upward drift (smoke, flames)
        self.stain = stain           # (radius, color) left behind on expiry

    def update(self, sim, dt):
        self.x += self.vx * dt
        self.y += (self.vy - self.rise) * dt
        self.vx *= self.drag
        self.vy *= self.drag
        self.ttl -= dt
        if self.ttl <= 0 and self.stain:
            sim.add_stain(self.x, self.y, *self.stain)


# ---------------------------------------------------------------- sim world

class Sim:
    def __init__(self, seed, team_a, team_b):
        """team_a / team_b: lists of (char_dict, weapon_key), 1-5 each."""
        self.seed = seed
        self.rng = random.Random(seed)
        self.vrng = random.Random(seed ^ 0x5EED)   # visuals-only stream
        self.t = 0.0
        self.winner = None            # None, a TEAM_NAMES entry, or "draw"
        self.projectiles = []
        self.hazards = []
        self.fx = []
        self.particles = []
        self.stains = []              # persistent floor marks (x, y, r, color)
        self.shake = 0.0              # camera shake magnitude, px
        self.events = []
        self.pending = []             # queued combat consequences (phase 2)
        self.spawn_queue = []         # projectiles born this tick
        self.fighters = []
        for team, (specs, x0, face) in enumerate((
                (team_a, 120, 0.0),
                (team_b, ARENA_W - 120, math.pi))):
            n = len(specs)
            for i, (char, wkey) in enumerate(specs):
                y = ARENA_H / 2 + (i - (n - 1) / 2) * 72
                # personal RNG keyed by team+slot, not list position, so
                # update order can never shift anyone's rolls
                self.fighters.append(
                    Fighter(char, team, x0, y, face, wkey,
                            random.Random(f"{seed}:{team}:{i}"),
                            slot=(team, i)))
        self.log(f"Red {len(team_a)} v {len(team_b)} Blue -- seed {seed}")
        for f in self.fighters:
            self.log(f"  {'R' if f.team == 0 else 'B'} {f.name}: "
                     f"{f.weapon.name} (skill {f.skill:.0f}, hp {f.max_hp})")

    # -- queries -----------------------------------------------------------

    def stable_order(self):
        """Fighters in fixed (team, slot) order -- loops that consume rng
        per fighter must use this so list position can never shift rolls."""
        return sorted(self.fighters, key=lambda g: g.slot)

    def nearest_enemy(self, f):
        best, best_d = None, float("inf")
        for g in self.fighters:
            if g.team == f.team or not g.alive:
                continue
            d = f.dist_to(g)
            if d < best_d:
                best, best_d = g, d
        return best

    def shot_clear(self, shooter, foe):
        """True if no ally stands on the straight line to the target
        (snapshot positions; padded a couple px)."""
        x1, y1 = shooter.x, shooter.y
        dx, dy = foe.sx - x1, foe.sy - y1
        seg2 = dx * dx + dy * dy
        if seg2 < 1e-9:
            return True
        for g in self.fighters:
            if not g.alive or g is shooter or g.team != shooter.team:
                continue
            t = clamp(((g.sx - x1) * dx + (g.sy - y1) * dy) / seg2, 0, 1)
            if math.hypot(g.sx - (x1 + dx * t),
                          g.sy - (y1 + dy * t)) < g.radius + 2:
                return False
        return True

    def safe_to_attack(self, f, foe):
        """Only very careful bombers hold the throw over an ally in the
        blast; everyone else trusts target selection to steer them away."""
        wd = f.weapon
        if wd.aoe is None or f.risk < 65:
            return True
        r = wd.aoe[0] - 4
        return not any(g.alive and g.team == f.team and g is not f
                       and math.hypot(g.sx - foe.sx, g.sy - foe.sy) < r
                       for g in self.fighters)

    def log(self, text):
        self.events.append((self.t, text))

    # -- visual helpers ----------------------------------------------------

    def add_stain(self, x, y, r, color):
        self.stains.append((x, y, r, color))
        if len(self.stains) > 220:
            del self.stains[:len(self.stains) - 220]

    def spawn_blood(self, x, y, ang, n, speed=110):
        v = self.vrng
        for _ in range(n):
            self.particles.append(Particle(
                x, y, ang + v.gauss(0, 0.7), v.uniform(30, speed),
                v.uniform(0.2, 0.5), v.uniform(1.5, 3),
                v.choice(("#a8322a", "#c0392b", "#8f1f1f")),
                stain=(v.uniform(1.5, 4), v.choice(("#4a1712", "#3f1410")))))

    def spawn_sparks(self, x, y, ang, n=5):
        v = self.vrng
        for _ in range(n):
            self.particles.append(Particle(
                x, y, ang + v.gauss(0, 1.4), v.uniform(70, 170),
                v.uniform(0.1, 0.25), v.uniform(1, 2),
                v.choice(("#ffdf8a", "#ffd24d", "#f2f6fa"))))

    # -- stepping ----------------------------------------------------------

    def flush_pending(self):
        for fn in self.pending:
            fn()
        self.pending = []

    def step(self):
        if self.winner is not None:
            return
        self.t += DT
        alive = [f for f in self.fighters if f.alive]

        # phase 0: freeze this tick's world for everyone to act against
        for f in alive:
            f.sx, f.sy = f.x, f.y
            f.svx, f.svy = f.vx, f.vy
            f.shp = f.hp
            f.s_state = f.state
            f.s_facing = f.facing
            f.s_down = f.down > 0
            f.s_react = f.down <= 0 and f.stun <= 0 and f.flee <= 0

        # phase 1: everyone decides and moves against the snapshot;
        # attack consequences are queued, not applied
        for f in alive:
            f.update(self, DT)

        # phase 2: consequences land simultaneously
        self.flush_pending()

        # crowd separation over every overlapping pair (allies too),
        # on real (post-move) positions
        for i, f in enumerate(alive):
            for g in alive[i + 1:]:
                d = math.hypot(g.x - f.x, g.y - f.y)
                if 1e-6 < d < f.radius + g.radius:
                    push = (f.radius + g.radius - d) / 2
                    nx, ny = (g.x - f.x) / d, (g.y - f.y) / d
                    f.x -= nx * push
                    f.y -= ny * push
                    g.x += nx * push
                    g.y += ny * push
            f.clamp_pos()

        # phase 3: projectiles (new spawns join the flight this tick)
        self.projectiles += self.spawn_queue
        self.spawn_queue = []
        for p in self.projectiles:
            p.update(self, DT)
        self.projectiles = [p for p in self.projectiles if p.alive]
        self.flush_pending()

        for hz in self.hazards:
            hz.ttl -= DT
            for f in alive:
                if math.hypot(f.x - hz.x, f.y - hz.y) < hz.radius + f.radius:
                    self.add_effect(f, "burn", hz.dps, 0.6, hz.owner)
            if self.vrng.random() < 0.55:      # licking flames
                a = self.vrng.uniform(0, 2 * math.pi)
                d = self.vrng.uniform(0, hz.radius * 0.8)
                self.particles.append(Particle(
                    hz.x + math.cos(a) * d, hz.y + math.sin(a) * d,
                    -math.pi / 2, self.vrng.uniform(5, 15),
                    self.vrng.uniform(0.3, 0.6), self.vrng.uniform(2, 3.5),
                    self.vrng.choice(("#f0a03f", "#ffd24d", "#c25b2e")),
                    drag=1.0, rise=28))
        self.hazards = [h for h in self.hazards if h.ttl > 0]

        for pt in self.particles:
            pt.update(self, DT)
        self.particles = [p for p in self.particles if p.ttl > 0]
        self.shake *= 0.82

        # damage-over-time ticks; numbers surface about once a second
        for f in alive:
            for e in f.effects:
                e.ttl -= DT
                delta = e.dps * DT
                f.hp -= delta
                e.acc += delta
                if e.src is not None and e.src.team != f.team:
                    e.src.dmg_dealt += delta
                e.tick += DT
                if (e.tick >= 1.0 or e.ttl <= 0) and e.acc >= 1:
                    self.fx.append(Fx("dmg", f.x, f.y - 20, 0.8,
                                      text=str(int(e.acc)),
                                      color=EFFECT_COLORS[e.kind], r0=9))
                    if e.kind == "bleed":       # dripping a trail
                        self.add_stain(f.x + self.vrng.gauss(0, 4),
                                       f.y + self.vrng.gauss(0, 4),
                                       self.vrng.uniform(1.5, 3), "#4a1712")
                    e.acc -= int(e.acc)
                    e.tick = 0.0
            f.effects = [e for e in f.effects if e.ttl > 0]

        for fx in self.fx:
            fx.update(DT)
        self.fx = [f for f in self.fx if f.ttl > 0]

        dead = [f for f in self.fighters if f.hp <= 0 and f.alive]
        for f in dead:
            f.alive = False
            f.hp = 0
            f.drop_ang = self.vrng.uniform(0, 2 * math.pi)
            for _ in range(3):        # pool under the fallen
                self.add_stain(f.x + self.vrng.gauss(0, 5),
                               f.y + self.vrng.gauss(0, 5),
                               self.vrng.uniform(6, 12),
                               self.vrng.choice(("#4a1712", "#3f1410")))
            self.spawn_blood(f.x, f.y, self.vrng.uniform(0, 2 * math.pi),
                             10, speed=150)
            self.shake = max(self.shake, 3.0)
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

    # -- combat resolution -------------------------------------------------

    def resolve_attack(self, atk, dfd, wd, ranged=False, dmg_mult=1.0):
        """One attack against one defender: dodge, block, then damage plus
        weapon effects. All rolls come from the ATTACKER's personal rng;
        all state changes are queued on sim.pending so every attack this
        tick resolves against the same snapshot (no update-order bias).
        Returns 'dodge' | 'block' | 'hit'."""
        rng = atk.rng
        can_react = dfd.s_react
        # where is the attack coming from, relative to the defender's facing?
        rel = abs(angdiff(math.atan2(atk.sy - dfd.sy, atk.sx - dfd.sx),
                          dfd.s_facing))

        p_dodge = clamp(0.04 + dfd.dodge_stat * .0032 - atk.skill * .0012,
                        0.02, 0.30)
        if ranged:
            p_dodge *= 0.8
        if rel > math.radians(120):   # hit from behind: hard to see coming
            p_dodge *= 0.5
        if can_react and rng.random() < p_dodge:
            ang = atk.bearing_to(dfd) + rng.choice((1, -1)) * math.pi / 2

            def commit_dodge():
                dfd.kb_x += math.cos(ang) * 110
                dfd.kb_y += math.sin(ang) * 110
            self.pending.append(commit_dodge)
            for k in range(3):        # motion streaks behind the sidestep
                self.particles.append(Particle(
                    dfd.x - math.cos(ang) * 6 * k, dfd.y - math.sin(ang) * 6 * k,
                    ang + math.pi, 40, 0.22, 2.5 - k * 0.6, "#8a949e"))
            self.fx.append(Fx("dmg", dfd.x, dfd.y - 20, 0.6,
                              text="miss", color="#8a949e", r0=9))
            self.log(f"{dfd.name} dodges {atk.name}")
            return "dodge"

        # directional guard: full block up front, deflection to the sides,
        # nothing from behind; blocking works in MOVE and (weaker) RECOVER
        blocked = False
        block_mult = 0.35
        if (can_react and dfd.weapon.melee
                and dfd.s_state in (MOVE, RECOVER)):
            if rel <= math.radians(60):
                arc_mult = 1.0
            elif rel <= math.radians(110):
                arc_mult, block_mult = 0.5, 0.55
            else:
                arc_mult = 0.0        # can't guard your back
            mass = (wd.dmg[0] + wd.dmg[1]) / 2   # heavy weapons crash through
            p_block = (min(dfd.block_stat * .0028, 0.28) * arc_mult
                       * clamp(1.25 - mass / 24, 0.55, 1.10)
                       * (0.6 if ranged else 1.0)
                       * (0.6 if dfd.s_state == RECOVER else 1.0))
            blocked = rng.random() < p_block

        dmg = (rng.randint(*wd.dmg) * atk.power_mult
               * (0.75 + atk.skill * .005) * dmg_mult)
        crit = not blocked and rng.random() < atk.crit_p
        if crit:
            dmg *= 2
        if dfd.s_down:
            dmg *= 1.3               # can't defend from the floor
        if blocked:
            dmg *= block_mult
        dmg = max(1, int(round(dmg)))

        # a caught-on-the-guard hit never staggers, fells, or poisons
        note = ""
        stagger = 0.0
        if (not blocked and wd.stun_p and dfd.poise_cd <= 0
                and rng.random() < wd.stun_p * (1.3 - dfd.composure / 100)):
            stagger = 0.75 * (1.2 - dfd.composure / 200)
            note = ", staggered"
        kd = 0.0
        if (not blocked and wd.kd_p and not dfd.s_down
                and rng.random() < wd.kd_p * (1.35 - dfd.balance / 100)):
            kd = 1.0 + rng.random() * 0.5
            note = ", knocked down!"
        bleed = bool(not blocked and wd.bleed
                     and rng.random() < wd.bleed[0])
        poison = bool(not blocked and wd.poison
                      and rng.random() < wd.poison[0])

        ang = atk.bearing_to(dfd)
        kb = (60 if ranged else 150) * wd.kb_mult * (0.3 if blocked else 1.0)

        def commit_hit():
            dfd.hp -= dmg
            if atk.team != dfd.team:
                atk.dmg_dealt += dmg
            dfd.kb_x += math.cos(ang) * kb
            dfd.kb_y += math.sin(ang) * kb
            if not blocked:           # flinch: pauses, never cancels
                dfd.stun = max(dfd.stun, 0.28 if crit else 0.18)
            if stagger:               # attack lost + poise vs stun-lock
                dfd.stun = max(dfd.stun, stagger)
                dfd.poise_cd = 2.5
                dfd.cancel_attack(partial=True)
            if kd and dfd.down <= 0:  # knockdown: attack cancelled outright
                dfd.down = kd
                dfd.cancel_attack(partial=False)
            if bleed:
                self.add_effect(dfd, "bleed", wd.bleed[1], wd.bleed[2], atk)
            if poison:
                self.add_effect(dfd, "poison", wd.poison[1], wd.poison[2], atk)
        self.pending.append(commit_hit)

        ang_out = ang
        if blocked:
            self.spawn_sparks(dfd.x - math.cos(ang_out) * dfd.radius,
                              dfd.y - math.sin(ang_out) * dfd.radius, ang_out)
        else:
            self.spawn_blood(dfd.x, dfd.y, ang_out, 8 if crit else 5)
        if crit:
            self.shake = max(self.shake, 2.0)
        if note:                      # staggered or knocked down
            self.shake = max(self.shake, 2.5)
        self.fx.append(Fx("ring", dfd.x, dfd.y, 0.25))
        self.fx.append(Fx("dmg", dfd.x, dfd.y - 22, 0.9,
                          text=f"{dmg}{'!' if crit else ''}",
                          color="#ffd24d" if crit else
                          ("#9fb2c4" if blocked else "white"),
                          r0=14 if crit else 10))
        verb = "blocks" if blocked else "hits"
        who = f"{dfd.name} {verb} -- {atk.name} deals" if blocked else \
              f"{atk.name} {verb} {dfd.name} for"
        self.log(f"{who} {dmg} ({wd.name}"
                 f"{', CRIT' if crit else ''}{note})")
        return "block" if blocked else "hit"

    def add_effect(self, f, kind, dps, ttl, src):
        for e in f.effects:
            if e.kind == kind:
                e.ttl = max(e.ttl, ttl)
                return
        f.effects.append(Effect(kind, dps, ttl, src))
        if kind != "burn" or ttl > 0.7:
            flavor = {"bleed": "is bleeding", "poison": "is poisoned",
                      "burn": "catches fire"}[kind]
            self.log(f"{f.name} {flavor}!")
        elif not any(e.kind == "burn" for e in f.effects[:-1]):
            self.log(f"{f.name} catches fire!")

    def fire(self, shooter, foe):
        """Loose a projectile (bolt) or lob an explosive at the target."""
        wd = shooter.weapon
        rng = shooter.rng
        spread = math.radians(10) * (1.25 - shooter.skill / 100)
        tx, ty = foe.sx, foe.sy
        if shooter.smart > 55 and wd.proj_speed > 0:   # lead a moving target
            t_fly = shooter.dist_to(foe) / wd.proj_speed
            tx += foe.svx * t_fly * 0.8
            ty += foe.svy * t_fly * 0.8
        if wd.wtype == "explosive":
            err = rng.gauss(0, 14 * (1.25 - shooter.skill / 100))
            ang = rng.uniform(0, 2 * math.pi)
            self.spawn_queue.append(
                Projectile("lob", shooter, wd, shooter.x, shooter.y,
                           tx + math.cos(ang) * abs(err),
                           ty + math.sin(ang) * abs(err), rng))
            self.log(f"{shooter.name} lobs a {wd.name}!")
        else:
            ang = (math.atan2(ty - shooter.y, tx - shooter.x)
                   + rng.gauss(0, spread))
            d = math.hypot(tx - shooter.x, ty - shooter.y)
            self.spawn_queue.append(
                Projectile("bolt", shooter, wd, shooter.x, shooter.y,
                           shooter.x + math.cos(ang) * d,
                           shooter.y + math.sin(ang) * d, rng))
            self.log(f"{shooter.name} lets fly ({wd.name})")

    def explode(self, owner, wd, x, y):
        radius, kd_center = wd.aoe
        v = self.vrng
        self.shake = max(self.shake, 7.0)
        self.add_stain(x, y, radius * 0.5, "#1c2126")     # scorch mark
        self.add_stain(x + v.gauss(0, 6), y + v.gauss(0, 6),
                       radius * 0.3, "#20262c")
        for _ in range(12):                               # hot debris
            self.particles.append(Particle(
                x, y, v.uniform(0, 2 * math.pi), v.uniform(80, 260),
                v.uniform(0.2, 0.5), v.uniform(1.5, 3),
                v.choice(("#f0a03f", "#ffd24d", "#c25b2e", "#3a3f45"))))
        for _ in range(6):                                # drifting smoke
            self.particles.append(Particle(
                x + v.gauss(0, 8), y + v.gauss(0, 8),
                v.uniform(0, 2 * math.pi), v.uniform(8, 20),
                v.uniform(0.7, 1.3), v.uniform(4, 7), "#4a5158",
                drag=0.97, rise=20))
        self.fx.append(Fx("boom", x, y, 0.4, r0=8, r1=radius + 14))
        self.fx.append(Fx("ring", x, y, 0.25, r0=4, r1=radius))
        self.log(f"BOOM -- {owner.name}'s {wd.name} goes off!")
        for f in self.stable_order():               # friendly fire included
            if not f.alive:
                continue
            d = math.hypot(f.x - x, f.y - y)
            if d > radius + f.radius:
                continue
            fall = 1 - 0.7 * clamp(d / radius, 0, 1)
            dmg = (owner.rng.randint(*wd.dmg) * owner.power_mult
                   * (0.75 + owner.skill * .005)
                   * fall * (1 - ga(f.char, "agility") / 100 * 0.15))
            dmg = max(1, int(round(dmg)))
            f.hp -= dmg
            if owner.team != f.team:
                owner.dmg_dealt += dmg
            ang = math.atan2(f.y - y, f.x - x) if d > 1 else \
                owner.rng.uniform(0, 2 * math.pi)
            f.kb_x += math.cos(ang) * 220 * fall
            f.kb_y += math.sin(ang) * 220 * fall
            if owner.rng.random() < kd_center * fall * (1.35 - f.balance / 100):
                f.down = 1.1 + owner.rng.random() * 0.5
                f.cancel_attack(partial=False)
                self.log(f"{f.name} is blown off their feet!")
            self.fx.append(Fx("dmg", f.x, f.y - 22, 0.9, text=str(dmg),
                              color="#f0a03f"))
            tag = " (friendly fire!)" if f.team == owner.team else ""
            self.log(f"  blast hits {f.name} for {dmg}{tag}")
        if wd.fire:
            self.hazards.append(FirePatch(x, y, radius * 0.7,
                                          wd.fire[0], wd.fire[1], owner))


def run_headless(seed, team_a, team_b, max_time=240.0):
    """Resolve a fight with no window -- the wider game's entry point.
    team_a/team_b: lists of (char_dict, weapon_key)."""
    sim = Sim(seed, team_a, team_b)
    while sim.winner is None and sim.t < max_time:
        sim.step()
    return {
        "winner": sim.winner or "timeout",
        "time": round(sim.t, 2),
        "survivors": [(f.name, int(f.hp)) for f in sim.fighters if f.alive],
        "stats": [(f.name, f.weapon.name, round(f.dmg_dealt, 1))
                  for f in sim.fighters],
        "events": sim.events,
    }


# ---------------------------------------------------------------- tk shell

class App:
    def __init__(self, root):
        self.root = root
        root.title("zpyCombatArena 03 -- universal character schema")
        root.configure(bg="#1d2126")
        root.resizable(False, False)
        self.roster = load_roster()

        self.canvas = tk.Canvas(root, width=ARENA_W, height=ARENA_H,
                                bg="#232a31", highlightthickness=0)
        self.canvas.grid(row=0, column=0, rowspan=3, padx=(10, 6), pady=10)

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Treeview", background="#14171b",
                        fieldbackground="#14171b", foreground="#c9d2dc",
                        rowheight=19, borderwidth=0, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#262c33",
                        foreground="#8a949e", borderwidth=0,
                        font=("Segoe UI", 9))

        panel = tk.Frame(root, bg="#1d2126")
        panel.grid(row=0, column=1, sticky="new", padx=(0, 10), pady=(12, 0))
        self.build_panel(panel)

        cols = ("name", "weapon", "skill", "hp", "dps", "dmg")
        widths = (108, 96, 40, 58, 44, 44)
        self.tree = ttk.Treeview(root, columns=cols, show="headings",
                                 height=11)
        for c, w in zip(cols, widths):
            self.tree.heading(c, text=c.upper() if c in ("hp", "dps")
                              else c.capitalize())
            self.tree.column(c, width=w, anchor="w" if c in ("name", "weapon")
                             else "center")
        self.tree.tag_configure("t0", foreground=TEAM_COLORS[0])
        self.tree.tag_configure("t1", foreground=TEAM_COLORS[1])
        self.tree.tag_configure("dead", foreground="#565d64")
        self.tree.grid(row=1, column=1, sticky="new", padx=(0, 10))

        self.log_text = tk.Text(root, width=48, height=9, bg="#14171b",
                                fg="#c9d2dc", relief="flat", state="disabled",
                                font=("Consolas", 8), wrap="word")
        self.log_text.grid(row=2, column=1, sticky="nsew",
                           padx=(0, 10), pady=(6, 10))

        self.running = False
        self.accum = 0.0
        self.logged = 0
        self.rows = {}
        self.sim = None
        self.new_fight(seed=random.randrange(1_000_000))
        self.tick()

    # -- controls ----------------------------------------------------------

    def build_panel(self, panel):
        tk.Label(panel, text="zpyCombatArena", bg="#1d2126", fg="#e8edf2",
                 font=("Segoe UI", 13, "bold")).grid(row=0, column=0,
                                                     columnspan=3, sticky="w")
        self.btn_start = tk.Button(panel, text="Start", width=8,
                                   command=self.toggle)
        self.btn_start.grid(row=1, column=0, sticky="w", pady=6)
        tk.Button(panel, text="New Fight", width=9,
                  command=lambda: self.new_fight(
                      random.randrange(1_000_000))).grid(row=1, column=1,
                                                         sticky="w", padx=4)
        tk.Button(panel, text="Rematch", width=8,
                  command=lambda: self.new_fight(self.sim.seed)
                  ).grid(row=1, column=2, sticky="w")

        row2 = tk.Frame(panel, bg="#1d2126")
        row2.grid(row=2, column=0, columnspan=3, sticky="w", pady=(2, 0))

        def small(text):
            tk.Label(row2, text=text, bg="#1d2126", fg="#8a949e",
                     font=("Segoe UI", 9)).pack(side="left", padx=(0, 3))
        self.size_a = tk.IntVar(value=3)
        self.size_b = tk.IntVar(value=3)
        small("Red")
        tk.Spinbox(row2, from_=1, to=5, width=3, textvariable=self.size_a,
                   state="readonly").pack(side="left")
        small(" Blue")
        tk.Spinbox(row2, from_=1, to=5, width=3, textvariable=self.size_b,
                   state="readonly").pack(side="left")
        small("  Weapons")
        self.weap_mode = tk.StringVar(value="Best fit")
        ttk.Combobox(row2, textvariable=self.weap_mode,
                     values=["Best fit", "Random"], state="readonly",
                     width=8).pack(side="left")

        row3 = tk.Frame(panel, bg="#1d2126")
        row3.grid(row=3, column=0, columnspan=3, sticky="w")
        tk.Label(row3, text="Speed", bg="#1d2126", fg="#8a949e",
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.speed = tk.DoubleVar(value=1.0)
        tk.Scale(row3, variable=self.speed, from_=0.5, to=6.0, resolution=0.5,
                 orient="horizontal", length=200, bg="#1d2126", fg="#c9d2dc",
                 highlightthickness=0).pack(side="left")

    def toggle(self):
        self.running = not self.running
        self.btn_start.config(text="Pause" if self.running else "Start")

    def new_fight(self, seed):
        roll = random.Random(seed ^ 0xC0FFEE)   # team draw rides the seed too
        na, nb = self.size_a.get(), self.size_b.get()
        chars = roll.sample(self.roster, na + nb)
        mode = self.weap_mode.get()

        def arm(char):
            if mode == "Random":
                return roll.choice(list(WEAPONS))
            best = max(WEAPONS_BY_TYPE, key=lambda t: weapon_skill(char, t))
            return roll.choice(WEAPONS_BY_TYPE[best])

        self.sim = Sim(seed, [(c, arm(c)) for c in chars[:na]],
                       [(c, arm(c)) for c in chars[na:]])
        self.logged = 0
        self.running = False
        self.btn_start.config(text="Start")
        self.flush_log(clear=True)
        self.rebuild_table()
        self.render()

    # -- main loop ---------------------------------------------------------

    def tick(self):
        if self.running:
            self.accum += self.speed.get()
            while self.accum >= 1.0:
                self.sim.step()
                self.accum -= 1.0
            self.flush_log()
            self.update_table()
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

    # -- stats table -------------------------------------------------------

    def rebuild_table(self):
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for f in self.sim.fighters:
            iid = self.tree.insert("", "end", tags=(f"t{f.team}",))
            self.rows[id(f)] = iid
        self.update_table()

    def update_table(self):
        t = max(self.sim.t, 1.0)
        for f in self.sim.fighters:
            iid = self.rows[id(f)]
            self.tree.item(iid, values=(
                f.name, f.weapon.name, f"{f.skill:.0f}",
                f"{max(int(f.hp), 0)}/{f.max_hp}",
                f"{f.dmg_dealt / t:.1f}", f"{f.dmg_dealt:.0f}"),
                tags=("dead",) if not f.alive else (f"t{f.team}",))

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

        for sx, sy, sr, scol in self.sim.stains:
            c.create_oval(sx - sr, sy - sr, sx + sr, sy + sr,
                          fill=scol, outline="")

        for hz in self.sim.hazards:
            flick = 3 * (int(self.sim.t * 12) % 2)
            c.create_oval(hz.x - hz.radius, hz.y - hz.radius,
                          hz.x + hz.radius, hz.y + hz.radius,
                          outline="#c25b2e", width=2)
            r2 = hz.radius * 0.55 + flick
            c.create_oval(hz.x - r2, hz.y - r2, hz.x + r2, hz.y + r2,
                          outline="#f0a03f", width=2)

        for p in self.sim.projectiles:
            if p.kind == "lob":
                y = p.y - getattr(p, "arc_h", 0)
                c.create_oval(p.x - 5, y - 5, p.x + 5, y + 5,
                              fill="#3a3f45", outline="#f0a03f", width=2)
            else:
                c.create_line(p.x - p.vx * 0.03, p.y - p.vy * 0.03, p.x, p.y,
                              fill=p.weapon.color, width=2)

        for f in self.sim.fighters:
            self.draw_fighter(f)

        for pt in self.sim.particles:
            c.create_oval(pt.x - pt.r, pt.y - pt.r, pt.x + pt.r, pt.y + pt.r,
                          fill=pt.color, outline="")

        for fx in self.sim.fx:
            frac = 1 - fx.ttl / fx.ttl0
            if fx.kind == "ring":
                r = fx.r0 + (fx.r1 - fx.r0) * frac
                c.create_oval(fx.x - r, fx.y - r, fx.x + r, fx.y + r,
                              outline="#ffdf8a", width=2)
            elif fx.kind == "boom":
                r = fx.r0 + (fx.r1 - fx.r0) * frac
                c.create_oval(fx.x - r, fx.y - r, fx.x + r, fx.y + r,
                              outline="#f0a03f", width=4)
            else:
                c.create_text(fx.x, fx.y, text=fx.text, fill=fx.color,
                              font=("Segoe UI", int(fx.r0), "bold"))

        c.create_text(8, 10, anchor="w", fill="#5c656e", font=("Consolas", 9),
                      text=f"t={self.sim.t:5.1f}s  seed={self.sim.seed}")
        if self.sim.winner is not None:
            msg = ("It's a draw!" if self.sim.winner == "draw"
                   else f"{self.sim.winner} wins!")
            c.create_text(ARENA_W / 2, ARENA_H / 2 - 10, text=msg,
                          fill="#f2f6fa", font=("Segoe UI", 24, "bold"))
            c.create_text(ARENA_W / 2, ARENA_H / 2 + 22,
                          text="New Fight = new teams / Rematch = replay",
                          fill="#8a949e", font=("Segoe UI", 10))

        if self.sim.shake > 0.4:      # camera shake: nudge the whole frame
            c.move("all", random.uniform(-1, 1) * self.sim.shake,
                   random.uniform(-1, 1) * self.sim.shake)

    def draw_fighter(self, f):
        c = self.canvas
        r = f.radius
        if not f.alive:
            da = getattr(f, "drop_ang", 0.8)   # weapon lies where it fell
            wd = f.weapon
            if wd.wtype == "explosive":
                c.create_oval(f.x + 14, f.y + 8, f.x + 22, f.y + 16,
                              fill="#3a3f45", outline=wd.color)
            else:
                c.create_line(f.x + math.cos(da) * 8, f.y + math.sin(da) * 8,
                              f.x + math.cos(da) * (8 + wd.reach * 0.5),
                              f.y + math.sin(da) * (8 + wd.reach * 0.5),
                              fill=mix(wd.color, "#232a31", 0.35),
                              width=max(2, wd.width - 1), capstyle="round")
            c.create_oval(f.x - r, f.y - r * 0.6, f.x + r, f.y + r * 0.6,
                          fill="#3a3f45", outline="#565d64", width=2)
            c.create_line(f.x - 5, f.y - 4, f.x + 5, f.y + 4,
                          fill="#8a949e", width=2)
            c.create_line(f.x - 5, f.y + 4, f.x + 5, f.y - 4,
                          fill="#8a949e", width=2)
            return

        c.create_oval(f.x - r * 0.9 + 3, f.y - r * 0.5 + 6,
                      f.x + r * 0.9 + 3, f.y + r * 0.5 + 6,
                      fill="#1b2025", outline="")      # ground shadow

        if f.down > 0:                      # knocked down: squashed, no weapon
            c.create_oval(f.x - r - 3, f.y - r * 0.55, f.x + r + 3,
                          f.y + r * 0.55, fill=f.color, outline="#10141a",
                          width=2)
            self.draw_bars(f)
            return

        wd = f.active_weapon()              # shows the butt-strike shove too
        if f.state == SWING:
            wang, wlen = f.sweep, wd.reach
            start = f.facing - wd.arc / 2    # fading trail behind the swing
            for k in (0.75, 0.5, 0.25):
                ta = start + (f.sweep - start) * k
                c.create_line(f.x + math.cos(ta) * r,
                              f.y + math.sin(ta) * r,
                              f.x + math.cos(ta) * wd.reach * 0.95,
                              f.y + math.sin(ta) * wd.reach * 0.95,
                              fill=mix(wd.color, "#232a31", 1 - k * 0.8),
                              width=max(1, wd.width - 2))
        elif f.state == WINDUP:
            frac = 1 - f.t_state / (wd.windup * f.atk_speed)
            wang = f.facing - wd.arc / 2 - 0.4 * frac
            wlen = wd.reach * (0.55 if wd.melee else 0.0)
            if not wd.melee:
                wang, wlen = f.facing, 16 + 6 * frac
        else:
            wang = f.facing + 0.5
            wlen = wd.reach * 0.55 if wd.melee else 16
        if wd.wtype == "explosive":
            hx = f.x + math.cos(f.facing) * (r + 5)
            hy = f.y + math.sin(f.facing) * (r + 5)
            c.create_oval(hx - 4, hy - 4, hx + 4, hy + 4, fill="#3a3f45",
                          outline=wd.color, width=2)
        else:
            c.create_line(f.x, f.y, f.x + math.cos(wang) * wlen,
                          f.y + math.sin(wang) * wlen,
                          fill=wd.color, width=wd.width, capstyle="round")

        outline = "#ffd24d" if f.stun > 0 else "#10141a"
        c.create_oval(f.x - r, f.y - r, f.x + r, f.y + r,
                      fill=f.color, outline=outline, width=2)
        c.create_line(f.x, f.y, f.x + math.cos(f.facing) * r,
                      f.y + math.sin(f.facing) * r, fill="#10141a", width=2)
        if f.stun > 0:                       # dazed stars circling the head
            for i in (0, 1):
                sa = self.sim.t * 9 + i * math.pi
                c.create_text(f.x + math.cos(sa) * (r + 5),
                              f.y - r - 4 + math.sin(sa) * 3,
                              text="*", fill="#ffd24d",
                              font=("Segoe UI", 10, "bold"))
        if f.flee > 0:
            c.create_text(f.x + r + 6, f.y - r - 6, text="!",
                          fill="#ffd24d", font=("Segoe UI", 11, "bold"))
        self.draw_bars(f)

    def draw_bars(self, f):
        c = self.canvas
        r = f.radius
        bw = 34
        frac = clamp(f.hp / f.max_hp, 0, 1)
        col = "#57c96b" if frac > 0.5 else ("#e0b53f" if frac > 0.25
                                            else "#e05d5d")
        c.create_rectangle(f.x - bw / 2, f.y - r - 11, f.x + bw / 2,
                           f.y - r - 6, fill="#14171b", outline="")
        c.create_rectangle(f.x - bw / 2, f.y - r - 11,
                           f.x - bw / 2 + bw * frac, f.y - r - 6,
                           fill=col, outline="")
        for i, e in enumerate(f.effects):
            ex = f.x - bw / 2 + 4 + i * 8
            c.create_oval(ex - 3, f.y - r - 18, ex + 3, f.y - r - 12,
                          fill=EFFECT_COLORS[e.kind], outline="")
        c.create_text(f.x, f.y + r + 10, text=f.name, fill="#c9d2dc",
                      font=("Segoe UI", 8, "bold"))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
