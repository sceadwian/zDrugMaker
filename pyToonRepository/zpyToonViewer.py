"""zpyToonViewer -- GUI browser for the universal character roster.

Naming schema
-------------
This script follows the *zpy* schema: new scripts are named zpyNameOfScript.
(Legacy scripts follow the older pyNameOfScript convention.)

Data source
-----------
Reads universal_characters_master.csv (schema 1.0, see
universal_character_schema.md) from the same folder as this script, falling
back to a pyToonRepository/ subfolder. The CSV is treated as read-only; this
tool only visualizes it.

Views
-----
* Characters  -- per-character attribute bars, color-coded by rating band,
                 with population median / quartile notches on every bar,
                 politics and morality spectrum strips, and an optional
                 second-character comparison overlay.
* Population  -- roster-wide analytics: demographics, political and moral
                 spectra, core group averages (PHY/COG/PSY/SOC), per-
                 attribute box plots, correlations, and a rating band census.
* 2dCS Rating -- how the 2D Combat Simulator reads each character: an
                 aptitude score for all five weapon classes, the specific
                 weapons that suit them best, the combat numbers the engine
                 derives from their sheet, and a plain-English reading of
                 how they will actually behave in a fight.

This viewer does NOT need to sit next to the simulator (v06g). The ratings
tab reads its weights from whichever of these is best: the live engine if
it happens to be importable, else a small cs_weights.json snapshot copied
in beside this script, else the values built into this file as of 2dCS
v06f. All three compute IDENTICAL ratings -- verified by parity check --
so the only thing that changes is how fresh they can be after a rebalance.
The tab always states which of the three is in use. See the 2dCS BRIDGE
block below, and zpyArenaExport.py in the simulator folder for how the
snapshot is produced.

History
-------
v06g  Decoupled the ratings tab from needing the simulator nearby. It used
      to hard-import zpyCombatArena06 and go blank without it -- which
      surfaced when the user relocated this file away from the simulator
      folder to keep it with the rest of their roster tools. Tracing the
      actual dependency found it was five numbers (SKILL_WEIGHTS,
      POWER_MIX, the frame_health formula, VITALITY, CLASS_BIAS); every
      other figure on the tab was already plain arithmetic over a
      character's own attributes. Added the engine/snapshot/built-in
      fallback chain above so the file can travel on its own.

Python 3, standard library only (tkinter + csv + statistics).
"""

import csv
import statistics as st
import tkinter as tk
from collections import Counter
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk

SCRIPT_NAME = "zpyToonViewer"
SCHEMA_NOTE = ("naming schema: zpy  |  new tools are named zpyNameOfScript  "
               "(legacy tools: pyNameOfScript)")

CSV_NAME = "universal_characters_master.csv"
_HERE = Path(__file__).resolve().parent
# Look next to the script first, then in a pyToonRepository subfolder.
CSV_PATH = next((p for p in (_HERE / CSV_NAME,
                             _HERE / "pyToonRepository" / CSV_NAME)
                 if p.exists()), _HERE / CSV_NAME)

# Attribute groups, in schema order.
GROUPS = [
    ("Physical", ["strength", "stamina", "speed", "agility", "coordination",
                  "dexterity", "balance", "recovery", "resilience",
                  "metabolism", "lifespan"]),
    ("Cognitive", ["intelligence", "perception", "focus", "memory",
                   "creativity", "learning", "technical_aptitude",
                   "tactical_awareness"]),
    ("Psychological", ["willpower", "faith", "courage", "composure",
                       "discipline", "determination", "adaptability",
                       "patience", "risk_assessment"]),
    ("Social", ["charisma", "empathy", "conversation", "deception",
                "loyalty", "aggression"]),
]
ALL_ATTRS = [a for _, attrs in GROUPS for a in attrs]

# Core sub-groups used for per-character averages: capability traits only.
# Physical drops the lifestyle traits (metabolism, lifespan); Social drops
# the morally-flavoured tendencies (aggression, loyalty, deception).
CORE_EXCLUDE = {
    "Physical": {"metabolism", "lifespan"},
    "Social": {"aggression", "loyalty", "deception"},
}
CORE_GROUPS = [(g, [a for a in attrs if a not in CORE_EXCLUDE.get(g, ())])
               for g, attrs in GROUPS]
CORE_ABBR = {"Physical": "PHY", "Cognitive": "COG",
             "Psychological": "PSY", "Social": "SOC"}

# 1-99 axis columns rendered as gradient strips, not rating bars:
# (column, caption, left-end RGB, right-end RGB, bucket names).
AXES = [
    ("left2right", "left2right (politics)",
     (0x33, 0x55, 0xb7), (0xb7, 0x55, 0x33), ("left", "centre", "right")),
    ("evil2good", "evil2good (morality)",
     (0x7a, 0x1a, 0x1a), (0x2e, 0x7d, 0x32), ("evil", "neutral", "good")),
]

# Rating bands from universal_character_schema.md:
# (upper bound, color, schema label, compact word shown next to each bar).
BANDS = [
    (9,  "#b71c1c", "Extremely low", "dire"),
    (24, "#d84315", "Very low",      "weak"),
    (39, "#ef6c00", "Below average", "poor"),
    (59, "#f2b41f", "Average",       "average"),
    (74, "#9e9d24", "Above average", "solid"),
    (89, "#558b2f", "Excellent",     "great"),
    (98, "#2e7d32", "Exceptional",   "elite"),
    (99, "#b8860b", "Maximum",       "max"),
]
BAND_RANGES = ["1-9", "10-24", "25-39", "40-59", "60-74", "75-89",
               "90-98", "99"]


def _wrap(text, width):
    """Word-wrap for canvas text, which does not wrap on its own."""
    words, lines, line = text.split(), [], ""
    for w in words:
        if line and len(line) + 1 + len(w) > width:
            lines.append(line)
            line = w
        else:
            line = (line + " " + w) if line else w
    if line:
        lines.append(line)
    return lines


def band_for(value):
    for upper, color, label, short in BANDS:
        if value <= upper:
            return color, label, short
    return BANDS[-1][1], BANDS[-1][2], BANDS[-1][3]


def load_roster(path):
    """Load the master CSV (UTF-8 with BOM) into a list of dicts."""
    roster = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if not row.get("character_id"):
                continue
            for attr in ALL_ATTRS + ["left2right", "evil2good",
                                     "birth_year", "height_cm", "weight_kg"]:
                try:
                    row[attr] = int(row[attr])
                except (ValueError, TypeError, KeyError):
                    row[attr] = None
            roster.append(row)
    return roster


def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return 0.0
    return sxy / (sxx * syy) ** 0.5


def compute_attr_stats(roster):
    """Per-attribute population stats: mean, spread, quartiles, extremes."""
    out = {}
    for attr in ALL_ATTRS:
        vals = [c[attr] for c in roster]
        q1, med, q3 = st.quantiles(vals, n=4, method="inclusive")
        mn, mx = min(vals), max(vals)
        min_who = [c["short_name"] for c in roster if c[attr] == mn]
        max_who = [c["short_name"] for c in roster if c[attr] == mx]
        out[attr] = {
            "vals": vals,
            "mean": st.fmean(vals),
            "stdev": st.pstdev(vals),
            "q1": q1, "median": med, "q3": q3,
            "min": mn, "max": mx,
            "min_who": "/".join(min_who[:2]),
            "max_who": "/".join(max_who[:2]),
        }
    return out


# ===================================================================
# 2dCS BRIDGE
# ===================================================================
# The ratings tab reports how the COMBAT SIMULATOR reads these characters,
# so every weight below is imported from the engine rather than copied
# into this file. A copy would be a second source of truth that silently
# goes stale the next time a weapon is rebalanced -- and this tool exists
# to tell the truth about the sim, so it must ask the sim.
#
# If the engine is not beside this script (the pyToonRepository copy of
# the viewer, for instance) the tab says so instead of guessing.
# v06g: everything this bridge needs from the simulator turns out to be
# five numbers -- SKILL_WEIGHTS, POWER_MIX, the frame_health formula,
# VITALITY, and CLASS_BIAS. Every other figure on the ratings tab
# (dodge, guard, crit, stamina, temperament, ...) was ALREADY plain
# arithmetic over a character's own attributes, duplicated here rather
# than read off a live Fighter -- it never touched the engine at all.
#
# So this used to import the whole engine just to reach five numbers, and
# the tab went blank the moment the viewer was not sitting in the same
# folder as the simulator. Three ways to get those five numbers now, tried
# in order of freshness:
#
#   1. ENGINE  -- zpyCombatArena06 is importable (viewer sits beside the
#                 simulator, or on sys.path). Always exactly current.
#   2. SNAPSHOT -- cs_weights.json sits beside this script. Produced by
#                 `py -3 zpyArenaExport.py` in the simulator folder and
#                 then copied wherever the viewer lives. Current as of
#                 whenever it was last regenerated.
#   3. BUILT-IN -- neither is present. The viewer still rates characters,
#                 using the weights baked in below as of 2dCS v06f. These
#                 will drift if the simulator is rebalanced and nobody
#                 refreshes the snapshot -- which is why the tab always
#                 states which of the three it is using and how current
#                 that is.
#
# Refresh the snapshot after any weapon or class-bias change:
#     py -3 zpyArenaExport.py          (in the simulator folder)
#     copy the resulting cs_weights.json next to this viewer

_BUILTIN_CS = {
    "cs_version": "v06g",
    "skill_weights": {
        "blunt": {"aggression": .35, "composure": .25,
                  "technical_aptitude": .15, "focus": .15, "patience": .10},
        "blade": {"technical_aptitude": .30, "focus": .25, "composure": .20,
                  "aggression": .15, "patience": .10},
        "polearm": {"patience": .30, "technical_aptitude": .25,
                    "focus": .20, "composure": .15, "aggression": .10},
        "ranged": {"focus": .35, "patience": .25, "technical_aptitude": .20,
                   "composure": .15, "aggression": .05},
        "explosive": {"technical_aptitude": .35, "composure": .25,
                      "focus": .20, "patience": .15, "aggression": .05},
    },
    "power_mix": {
        "blunt": {"strength": .7, "stamina": .3},
        "blade": {"strength": .45, "dexterity": .4, "speed": .15},
        "polearm": {"strength": .4, "dexterity": .3, "balance": .3},
        "ranged": {"dexterity": .55, "strength": .25, "speed": .2},
        "explosive": {"dexterity": .6, "strength": .4},
    },
    "frame_health": {"base": 45, "resilience": .30, "stamina": .25,
                     "lifespan": .15},
    "vitality": 2.0,
    "class_bias": {"blade": 2.0, "polearm": 1.5},
}


def _load_cs_weights():
    """(data, source) -- source is "engine", "snapshot" or "builtin"."""
    try:
        import zpyCombatArena06 as _arena
        try:
            import zpyArenaTournament as _game
            version, bias = "v" + _game.VERSION, _game.CLASS_BIAS
        except Exception:
            version, bias = "v" + getattr(_arena, "ENGINE_VERSION", "06f"), {}
        return {
            "cs_version": version,
            "skill_weights": _arena.SKILL_WEIGHTS,
            "power_mix": _arena.POWER_MIX,
            "frame_health": {"base": 45, "resilience": .30, "stamina": .25,
                             "lifespan": .15},
            "vitality": _arena.VITALITY,
            "class_bias": bias,
        }, "engine", ""
    except Exception:
        pass
    snap = _HERE / "cs_weights.json"
    if snap.exists():
        try:
            import json
            return (json.loads(snap.read_text(encoding="utf-8")),
                    "snapshot", "")
        except Exception as exc:
            return _BUILTIN_CS, "builtin", "cs_weights.json unreadable: %s" % exc
    return _BUILTIN_CS, "builtin", ""


_CS, CS_SOURCE, CS_ERROR = _load_cs_weights()
CS_VERSION = _CS["cs_version"]
SKILL_WEIGHTS = _CS["skill_weights"]
POWER_MIX = _CS["power_mix"]
FRAME_HEALTH = _CS["frame_health"]
VITALITY = _CS["vitality"]
CLASS_BIAS = _CS["class_bias"]
CS_SOURCE_BLURB = {
    "engine": "read live from zpyCombatArena06.py sitting beside this "
              "viewer -- always exactly current",
    "snapshot": "read from cs_weights.json -- current as of whatever the "
                "snapshot was last regenerated (%s)" % CS_VERSION,
    "builtin": "the simulator is not nearby and no cs_weights.json was "
              "found, so this is using the weights built into the viewer "
              "as of 2dCS %s. Run `py -3 zpyArenaExport.py` in the "
              "simulator folder and copy cs_weights.json here to refresh."
              % CS_VERSION,
}


def cs_ga(char, key):
    """Attribute lookup with a neutral default -- same rule the engine's
    own ga() uses, so a missing column reads as average rather than zero."""
    v = char.get(key, 50)
    return v if isinstance(v, int) else 50


def cs_clamp(v, lo, hi):
    return max(lo, min(hi, v))


def cs_frame_health(char):
    fh = FRAME_HEALTH
    return int(fh["base"] + cs_ga(char, "resilience") * fh["resilience"]
               + cs_ga(char, "stamina") * fh["stamina"]
               + cs_ga(char, "lifespan") * fh["lifespan"])


WCLASSES = ("blunt", "blade", "polearm", "ranged", "explosive")

# How much of a character's fitness for a weapon class is know-how, and how
# much is the body behind the blow. Both matter: skill spans 0.75x-1.25x on
# damage AND buys up to 37% faster swings plus deliberate aim, while the
# power mix spans 0.70x-1.30x on damage alone. Skill therefore carries a
# little more, and the split is shown on screen so it can be argued with.
#
# VALIDATED, not asserted. 26 characters x 5 classes, 12 fights each against
# a fixed opponent, correlating this rating with the measured win rate:
#
#     class      r(skill)  r(power)  r(aptitude)  r(+staying power)
#     blunt          0.67      0.72         0.80              0.81
#     blade          0.79      0.59         0.84              0.84
#     polearm        0.79      0.50         0.82              0.86
#     ranged         0.76      0.44         0.78              0.76
#     explosive      0.79      0.24         0.68              0.71
#
# So it predicts well WITHIN a class. Pooled across classes it falls to
# 0.61, because the classes are not equally strong -- a 60-rated polearm
# fighter beats a 60-rated archer on the weapon, not the character. That is
# why the tab says so on screen, and why RECOMMENDED ARMAMENT multiplies
# fitness by each weapon's own measured win rate to answer the cross-class
# question honestly.
#
# Note also that power barely predicts anything for explosives (0.24) -- a
# thrown bomb is mostly skill and placement -- which is worth remembering
# before anyone tunes these weights.
APT_SKILL, APT_POWER = 0.55, 0.45
# Aptitude is class-specific. Staying power is not -- it applies whatever
# you hand them -- so it is reported separately and folded in only for the
# roster ranking, where "who is best with a blade" really does depend on
# whether they survive long enough to use it.
RANK_APT, RANK_GENERAL = 0.60, 0.40

# The measured strength AND class of each individual weapon, both parsed
# out of the lab bench table that produced the manual. Both, not just the
# win rate: RECOMMENDED ARMAMENT needs to know which class a weapon
# belongs to, and that used to come from importing the live engine and
# reading WEAPONS[name].wtype. The class is already sitting in this same
# file's own columns (zpyArenaLab's own output format lists it first), so
# reading it from here instead removes the last hard dependency on the
# simulator being nearby. Optional either way: without manual_data.json
# the tab still rates characters, it just cannot recommend a weapon.
def _load_weapon_table():
    path = _HERE / "manual_data.json"
    if not path.exists():
        return {}
    try:
        import json
        rows = json.loads(path.read_text(encoding="utf-8"))["lab_table"]
    except Exception:
        return {}
    out = {}
    for line in rows:
        parts = line.split()
        if len(parts) >= 10 and parts[-1].isdigit() and "-" in line:
            try:
                out[" ".join(parts[:-10])] = (int(parts[-5]), parts[-10])
            except ValueError:
                pass
    return out


WEAPON_TABLE = _load_weapon_table()          # name -> (win%, class)
WEAPON_STRENGTH = {n: w for n, (w, _t) in WEAPON_TABLE.items()}


def cs_skill(char, wclass):
    """How WELL this character uses the class -- the engine's own blend."""
    return sum(cs_ga(char, k) * w
               for k, w in SKILL_WEIGHTS[wclass].items())


def cs_power(char, wclass):
    """How HARD they hit with it, on the same 0-100 scale."""
    return sum(cs_ga(char, k) * w for k, w in POWER_MIX[wclass].items())


def cs_aptitude(char, wclass):
    return APT_SKILL * cs_skill(char, wclass) + APT_POWER * cs_power(char,
                                                                    wclass)


def cs_general(char):
    """Class-independent staying power: frame, evasion, guard, wind."""
    frame = cs_frame_health(char)
    ga = cs_ga
    dodge = (ga(char, "agility") * .4 + ga(char, "balance") * .3
             + ga(char, "perception") * .3)
    guard = (ga(char, "composure") * .4 + ga(char, "balance") * .3
             + ga(char, "strength") * .3)
    stam = (45 + ga(char, "stamina") * .35 + ga(char, "recovery") * .20
            + ga(char, "resilience") * .10)
    return ((frame - 45) / 0.70 * .40 + dodge * .22 + guard * .18
            + (stam - 45) / 0.65 * .20)


def cs_profile(char):
    """Everything the ratings tab needs about one character, straight out
    of the engine's own formulas."""
    ga = cs_ga
    at = lambda k: ga(char, k)
    frame = cs_frame_health(char)
    prof = {
        "apt": {w: cs_aptitude(char, w) for w in WCLASSES},
        "skill": {w: cs_skill(char, w) for w in WCLASSES},
        "power": {w: cs_power(char, w) for w in WCLASSES},
        "general": cs_general(char),
        "frame": frame,
        "hp": int(frame * VITALITY),
        "speed": 62 + at("speed") * .55,
        "dodge": at("agility") * .4 + at("balance") * .3 + at("perception") * .3,
        "guard": at("composure") * .4 + at("balance") * .3 + at("strength") * .3,
        "crit": 0.05 + at("dexterity") * .0008 + at("focus") * .0005,
        "stam": int(45 + at("stamina") * .35 + at("recovery") * .20
                    + at("resilience") * .10),
        "reserve": cs_clamp(0.30 - at("aggression") * .0022
                               + at("discipline") * .0018
                               + at("patience") * .0012, 0.04, 0.45),
        "tempo": 1.25 - at("aggression") / 100 * 0.5,
        "recover": 0.75 + at("recovery") / 100 * 0.9,
        "nerve": cs_clamp(0.32 - at("courage") * .0028
                             - at("willpower") * .0008, 0.0, 0.35),
        "flee": 2.0 + (100 - at("determination")) / 100 * 2.0,
    }
    # atk_speed needs the class, so report it for their best one
    best = max(WCLASSES, key=lambda w: prof["apt"][w])
    prof["best"] = best
    prof["atk_speed"] = cs_clamp(
        1.20 - prof["skill"][best] / 100 * .25 - at("speed") / 100 * .15,
        0.75, 1.20)
    # the seven personality composites the intent layer actually argues over
    prof["mind"] = {
        "Pressure": (at("aggression") * .45 + at("courage") * .30
                     + at("determination") * .25),
        "Restraint": (at("discipline") * .40 + at("patience") * .35
                      + at("composure") * .25),
        "Calculation": (at("intelligence") * .40 + at("perception") * .30
                        + at("technical_aptitude") * .30),
        "Self-preservation": (at("risk_assessment") * .45
                              + at("composure") * .30 + at("willpower") * .25),
        "Persistence": at("determination") * .55 + at("courage") * .45,
        "Duty": (at("discipline") * .40 + at("courage") * .30
                 + at("intelligence") * .30),
        "Defiance": (at("courage") * .40 + at("determination") * .35
                     + at("aggression") * .25),
    }
    return prof


def cs_behaviour(prof):
    """Plain-English reading of the composites -- what the intent layer
    will actually do with this character. Each line names the pressure it
    came from so a surprising one can be traced back."""
    m_ = prof["mind"]
    out = []
    p, r = m_["Pressure"], m_["Restraint"]
    if p - r > 12:
        out.append(("Comes forward.", "Pressure %.0f over Restraint %.0f -- "
                    "expect PRESS most of the fight, closing rather than "
                    "circling." % (p, r)))
    elif r - p > 12:
        out.append(("Makes you come to them.", "Restraint %.0f over Pressure "
                    "%.0f -- expect PROBE and GUARD, waiting for an opening "
                    "instead of forcing one." % (r, p)))
    else:
        out.append(("Takes the fight as it comes.", "Pressure %.0f and "
                    "Restraint %.0f are close, so they switch plans more "
                    "often than most." % (p, r)))

    sp = m_["Self-preservation"]
    if sp >= 70:
        out.append(("Reads the danger.", "Self-preservation %.0f -- breaks "
                    "off early, avoids hazards, and will not walk into a "
                    "crowd." % sp))
    elif sp <= 40:
        out.append(("Does not read the danger.", "Self-preservation %.0f -- "
                    "will stand in fire and take on more than one." % sp))

    c = m_["Calculation"]
    if c >= 70:
        out.append(("Fights with their head.", "Calculation %.0f -- FLANKs "
                    "once the front door is shut, and picks targets rather "
                    "than swinging at whoever is nearest." % c))
    elif c <= 40:
        out.append(("Fights in front of them.", "Calculation %.0f -- takes "
                    "the direct line and rarely works around a guard." % c))

    d = m_["Duty"]
    if d >= 70:
        out.append(("Turns back for team-mates.", "Duty %.0f -- expect "
                    "PROTECT when an ally is pressed. A liability in a "
                    "losing team, an anchor in a winning one." % d))

    df, per = m_["Defiance"], m_["Persistence"]
    if df >= 70:
        out.append(("Goes down swinging.", "Defiance %.0f -- turns DESPERATE "
                    "rather than fleeing when it goes badly." % df))
    if per <= 40:
        out.append(("Gives up the chase.", "Persistence %.0f -- drops a "
                    "pursuit quickly and loses interest in a runner." % per))

    n = prof["nerve"]
    if n <= 0.06:
        out.append(("Does not break.", "Panics below %.0f%% health -- "
                    "effectively never." % (n * 100)))
    elif n >= 0.22:
        out.append(("Breaks early.", "Panics below %.0f%% health and runs "
                    "for %.1f seconds." % (n * 100, prof["flee"])))

    res = prof["reserve"]
    if res <= 0.12:
        out.append(("Spends everything.", "Keeps only %.0f%% of their wind "
                    "in reserve -- fast starter, badly exposed late."
                    % (res * 100)))
    elif res >= 0.30:
        out.append(("Paces themselves.", "Holds %.0f%% of their wind back, "
                    "so they are still swinging at full speed when others "
                    "are not." % (res * 100)))
    return out


class ToonViewer(tk.Tk):
    ROW_H = 22          # pixels per attribute bar row (character view)
    HEAD_H = 30         # pixels per group header
    LABEL_W = 150       # attribute label column width
    VALUE_W = 92        # value text column width

    def __init__(self, roster):
        super().__init__()
        self.roster = roster
        self.by_name = {c["display_name"]: c for c in roster}
        self.by_id = {c["character_id"]: c for c in roster}
        self.current = None
        self.compare = None
        self._compute_population()

        self.title("%s  --  universal character visualizer  [zpy schema]"
                   % SCRIPT_NAME)
        self.geometry("1120x760")
        self.minsize(900, 580)

        self._build_ui()
        self._refresh_list()
        if roster:
            self.listbox.selection_set(0)
            self._on_select()

    # -------------------------------------------------- population stats
    def _compute_population(self):
        roster = self.roster
        self.stats = compute_attr_stats(roster)
        # per-character core group averages and their composite
        self.core = {
            c["character_id"]: {g: st.fmean(c[a] for a in attrs)
                                for g, attrs in CORE_GROUPS}
            for c in roster}
        self.composite = {cid: st.fmean(gs.values())
                          for cid, gs in self.core.items()}
        self.ranking = sorted(
            roster, key=lambda c: self.composite[c["character_id"]],
            reverse=True)
        # spread of each character's own 34 ratings (well-rounded vs spiky)
        self.spread = {c["character_id"]:
                       st.pstdev([c[a] for a in ALL_ATTRS]) for c in roster}
        # all attribute-pair correlations across the roster
        pairs = []
        for i, a in enumerate(ALL_ATTRS):
            xs = self.stats[a]["vals"]
            for b in ALL_ATTRS[i + 1:]:
                pairs.append((pearson(xs, self.stats[b]["vals"]), a, b))
        pairs.sort()
        self.corr_neg = pairs[:5]
        self.corr_pos = pairs[::-1][:7]

    # ------------------------------------------------------------- UI build
    def _build_ui(self):
        # Header banner making the zpy naming schema obvious.
        banner = tk.Frame(self, bg="#1f2733")
        banner.pack(fill="x")
        tk.Label(banner, text=SCRIPT_NAME, bg="#1f2733", fg="#7fd4a8",
                 font=("Consolas", 15, "bold")).pack(side="left",
                                                     padx=(12, 8), pady=6)
        tk.Label(banner, text=SCHEMA_NOTE, bg="#1f2733", fg="#c9d4e0",
                 font=("Consolas", 9)).pack(side="left", pady=6)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        char_tab = ttk.Frame(self.notebook, padding=8)
        pop_tab = ttk.Frame(self.notebook, padding=8)
        rate_tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(char_tab, text="  Characters  ")
        self.notebook.add(pop_tab, text="  Population  ")
        self.notebook.add(rate_tab, text="  2dCS Rating  ")

        self._build_character_tab(char_tab)
        self._build_population_tab(pop_tab)
        self._build_rating_tab(rate_tab)
        self.bind_all("<MouseWheel>", self._on_wheel)

    def _build_character_tab(self, body):
        # ---- left pane: search / sort / roster list
        left = ttk.Frame(body)
        left.pack(side="left", fill="y", padx=(0, 8))

        ttk.Label(left, text="Filter").pack(anchor="w")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self._refresh_list())
        ttk.Entry(left, textvariable=self.filter_var, width=26).pack(
            fill="x", pady=(0, 6))

        ttk.Label(left, text="Sort by").pack(anchor="w")
        self.sort_var = tk.StringVar(value="display_name")
        sort_box = ttk.Combobox(left, textvariable=self.sort_var, width=24,
                                state="readonly",
                                values=(["display_name", "left2right",
                                         "evil2good"] + ALL_ATTRS))
        sort_box.pack(fill="x", pady=(0, 6))
        sort_box.bind("<<ComboboxSelected>>", lambda e: self._refresh_list())

        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(list_frame, width=28, exportselection=False,
                                  font=("Consolas", 10))
        sb = ttk.Scrollbar(list_frame, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._on_select())

        ttk.Label(left, text="Compare with (overlay)").pack(anchor="w",
                                                            pady=(6, 0))
        self.compare_var = tk.StringVar(value="(none)")
        cmp_box = ttk.Combobox(left, textvariable=self.compare_var, width=24,
                               state="readonly",
                               values=["(none)"] + sorted(self.by_name))
        cmp_box.pack(fill="x")
        cmp_box.bind("<<ComboboxSelected>>", lambda e: self._on_compare())

        # ---- right pane: identity card + scrollable attribute canvas
        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self.identity = tk.Label(right, justify="left", anchor="w",
                                 font=("Consolas", 10), bd=1, relief="solid",
                                 padx=10, pady=8, bg="#f4f6f8")
        self.identity.pack(fill="x", pady=(0, 6))

        canvas_frame = ttk.Frame(right)
        canvas_frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(canvas_frame, bg="white",
                                highlightthickness=0)
        csb = ttk.Scrollbar(canvas_frame, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=csb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        csb.pack(side="right", fill="y")
        self.canvas.bind("<Configure>", lambda e: self._draw())

        legend_bands = "  ".join("%s %s" % (short, rng) for
                                 (_hi, _c, _label, short), rng in
                                 zip(BANDS, BAND_RANGES))
        self.legend = tk.Label(
            right, font=("Consolas", 8), anchor="w", justify="left",
            text=(legend_bands +
                  "\nbar marks:  ▾ population median   "
                  "▴▴ population Q1/Q3   "
                  "| black line = compare character"))
        self.legend.pack(fill="x")

    def _build_population_tab(self, body):
        frame = ttk.Frame(body)
        frame.pack(fill="both", expand=True)
        self.pcanvas = tk.Canvas(frame, bg="white", highlightthickness=0)
        psb = ttk.Scrollbar(frame, command=self.pcanvas.yview)
        self.pcanvas.configure(yscrollcommand=psb.set)
        self.pcanvas.pack(side="left", fill="both", expand=True)
        psb.pack(side="right", fill="y")
        self.pcanvas.bind("<Configure>", lambda e: self._draw_population())

    # -------------------------------------------------------- 2dCS ratings
    def _build_rating_tab(self, body):
        # v06g: this used to refuse to build at all unless the simulator
        # was importable. It always has usable weights now -- engine,
        # snapshot, or built-in -- so the tab always builds; only the
        # source note at the bottom of each report changes.
        if CS_SOURCE == "builtin" and CS_ERROR:
            warn = ttk.Label(
                body, text="cs_weights.json exists but could not be read "
                           "(%s) -- using the weights built into this "
                           "viewer instead." % CS_ERROR,
                foreground="#b71c1c", wraplength=760, justify="left")
            warn.pack(fill="x", padx=4, pady=(0, 6))

        self._profiles = {c["character_id"]: cs_profile(c)
                          for c in self.roster}
        # roster ranking per class: aptitude for the class, weighted with
        # the staying power that decides whether they live to use it
        self._class_rank = {}
        for w in WCLASSES:
            order = sorted(
                self.roster,
                key=lambda c: -(RANK_APT * self._profiles[c["character_id"]]
                                ["apt"][w]
                                + RANK_GENERAL
                                * self._profiles[c["character_id"]]["general"]))
            self._class_rank[w] = [c["character_id"] for c in order]

        left = ttk.Frame(body)
        left.pack(side="left", fill="y", padx=(0, 8))
        ttk.Label(left, text="Filter").pack(anchor="w")
        self.rfilter_var = tk.StringVar()
        self.rfilter_var.trace_add("write",
                                   lambda *_: self._refresh_rating_list())
        ttk.Entry(left, textvariable=self.rfilter_var, width=30).pack(
            fill="x", pady=(0, 6))

        ttk.Label(left, text="Rank by").pack(anchor="w")
        self.rsort_var = tk.StringVar(value="best class")
        rbox = ttk.Combobox(left, textvariable=self.rsort_var, width=28,
                            state="readonly",
                            values=["best class", "name"] + list(WCLASSES)
                            + ["staying power"])
        rbox.pack(fill="x", pady=(0, 6))
        rbox.bind("<<ComboboxSelected>>",
                  lambda e: self._refresh_rating_list())

        lf = ttk.Frame(left)
        lf.pack(fill="both", expand=True)
        self.rlist = tk.Listbox(lf, width=32, exportselection=False,
                                font=("Consolas", 9))
        rsb = ttk.Scrollbar(lf, command=self.rlist.yview)
        self.rlist.configure(yscrollcommand=rsb.set)
        self.rlist.pack(side="left", fill="both", expand=True)
        rsb.pack(side="right", fill="y")
        self.rlist.bind("<<ListboxSelect>>",
                        lambda e: self._on_rating_select())

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)
        cf = ttk.Frame(right)
        cf.pack(fill="both", expand=True)
        self.rcanvas = tk.Canvas(cf, bg="white", highlightthickness=0)
        csb2 = ttk.Scrollbar(cf, command=self.rcanvas.yview)
        self.rcanvas.configure(yscrollcommand=csb2.set)
        self.rcanvas.pack(side="left", fill="both", expand=True)
        csb2.pack(side="right", fill="y")
        self.rcanvas.bind("<Configure>", lambda e: self._draw_rating())

        self.rcurrent = None
        self._refresh_rating_list()
        if self.roster:
            self.rlist.selection_set(0)
            self._on_rating_select()

    def _char_w(self, size):
        """Measured width of one Consolas character at `size`. Cached --
        tkinter font measurement is not free and this runs per line."""
        cache = getattr(self, "_cw_cache", None)
        if cache is None:
            cache = self._cw_cache = {}
        if size not in cache:
            import tkinter.font as tkfont
            cache[size] = max(
                1.0, tkfont.Font(font=("Consolas", size)).measure("0"))
        return cache[size]

    def _refresh_rating_list(self):
        key = self.rsort_var.get()
        needle = self.rfilter_var.get().strip().lower()
        self.rlist.delete(0, "end")
        self._rvisible = []
        if key == "name":
            order = sorted(self.roster, key=lambda c: c["display_name"])
        elif key == "staying power":
            order = sorted(self.roster,
                           key=lambda c: -self._profiles[c["character_id"]]
                           ["general"])
        elif key in WCLASSES:
            order = [self.by_id[i] for i in self._class_rank[key]]
        else:                                   # best class
            order = sorted(self.roster,
                           key=lambda c: -max(self._profiles[c["character_id"]]
                                              ["apt"].values()))
        for c in order:
            if needle and needle not in c["display_name"].lower():
                continue
            p = self._profiles[c["character_id"]]
            if key in WCLASSES:
                label = "%2.0f %-3s %s" % (p["apt"][key], key[:3].upper(),
                                           c["display_name"])
            elif key == "staying power":
                label = "%2.0f     %s" % (p["general"], c["display_name"])
            else:
                label = "%2.0f %-3s %s" % (max(p["apt"].values()),
                                           p["best"][:3].upper(),
                                           c["display_name"])
            self.rlist.insert("end", label)
            self._rvisible.append(c)
        if self.rcurrent in self._rvisible:
            self.rlist.selection_set(self._rvisible.index(self.rcurrent))

    def _on_rating_select(self):
        sel = self.rlist.curselection()
        if sel and self._rvisible:
            self.rcurrent = self._rvisible[sel[0]]
            self._draw_rating()

    def _draw_rating(self):
        cv = getattr(self, "rcanvas", None)
        if cv is None or not self.rcurrent:
            return
        cv.delete("all")
        c = self.rcurrent
        p = self._profiles[c["character_id"]]
        width = max(cv.winfo_width(), 620)
        n = len(self.roster)

        def text(x, y, s, size=9, bold=False, color="#1f2733", anchor="nw"):
            font = ("Consolas", size, "bold") if bold else ("Consolas", size)
            cv.create_text(x, y, anchor=anchor, text=s, font=font, fill=color)

        def section(y, title):
            text(12, y, title, size=11, bold=True)
            cv.create_line(12, y + 20, width - 16, y + 20, fill="#8a959e")
            return y + 28

        def bar(x, y, w, h, value, color, track="#e8ecf0"):
            cv.create_rectangle(x, y, x + w, y + h, fill=track, outline=track)
            fill = max(0, min(value, 100)) / 100 * w
            if fill > 0:
                cv.create_rectangle(x, y, x + fill, y + h, fill=color,
                                    outline=color)

        def note(y, body, x=12, size=8, color="#5a6675"):
            """Small print, wrapped to whatever width the window is now.

            Canvas text does not wrap on its own, so a long note just runs
            off the right-hand edge. The wrap width is MEASURED from the
            actual font rather than estimated from the point size -- an
            estimate was close enough to look right and still overflowed
            by a few pixels."""
            per_char = self._char_w(size)
            chars = max(40, int((width - x - 20) / per_char))
            for line in _wrap(body, chars):
                text(x, y, line, size=size, color=color)
                y += size + 5
            return y

        y = 10
        text(12, y, "2dCS COMBAT RATING -- %s" % c["display_name"],
             size=12, bold=True)
        y += 20
        text(12, y, "how the 2D Combat Simulator %s reads this character   "
                    "|   %s / %s" % (CS_VERSION, c["character_id"],
                                     c["short_name"]),
             size=9, color="#5a6675")
        y += 26

        # ------------------------------------------------ weapon aptitude
        y = section(y, "WEAPON APTITUDE  --  what they are worth with each "
                       "class")
        # Explicit column positions rather than one padded string: the bar
        # sits between two text columns, so a format width that grows past
        # x=BAR would print straight through it.
        CX, SX, PX, BX, BW, VX = 12, 132, 178, 190, 140, 344
        text(CX, y, "CLASS", size=8, bold=True, color="#5a6675")
        text(SX, y, "SKILL", size=8, bold=True, color="#5a6675", anchor="ne")
        text(PX, y, "POWER", size=8, bold=True, color="#5a6675", anchor="ne")
        text(BX, y, "APTITUDE", size=8, bold=True, color="#5a6675")
        text(VX, y, "GRADE / ROSTER RANK", size=8, bold=True,
             color="#5a6675")
        y += 16
        best_apt = max(p["apt"].values())
        for w in sorted(WCLASSES, key=lambda k: -p["apt"][k]):
            color, _label, short = band_for(int(p["apt"][w]))
            rank = self._class_rank[w].index(c["character_id"]) + 1
            lead = p["apt"][w] == best_apt
            text(CX, y, w, size=9, bold=lead)
            text(SX, y, "%.0f" % p["skill"][w], size=9, anchor="ne")
            text(PX, y, "%.0f" % p["power"][w], size=9, anchor="ne")
            bar(BX, y + 3, BW, 10, p["apt"][w], color)
            text(VX, y, "%5.1f  %-8s  #%d of %d"
                 % (p["apt"][w], short, rank, n), size=9,
                 color="#1f2733" if lead else "#5a6675")
            y += 18
        y += 4
        y = note(y, "APTITUDE = %.2f x skill + %.2f x power. Skill is the "
                    "engine's own per-class attribute blend; power is what "
                    "scales the damage." % (APT_SKILL, APT_POWER))
        y = note(y, "Roster rank also weighs staying power (%.0f/100 here), "
                    "because surviving to use the weapon is half of being "
                    "good with it." % p["general"])
        y += 14

        # -------------------------------------------- recommended armament
        y = section(y, "RECOMMENDED ARMAMENT  --  their fit x the weapon's "
                       "own measured strength")
        if WEAPON_TABLE:
            picks = []
            for wname, (strength, wtype) in WEAPON_TABLE.items():
                fit = p["apt"][wtype]
                picks.append((fit / 100 * strength, wname, wtype, fit,
                              strength))
            picks.sort(reverse=True)
            WX, CLX, FX, SX2, BX2, BW2, TX = 12, 140, 260, 330, 344, 130, 486
            text(WX, y, "WEAPON", size=8, bold=True, color="#5a6675")
            text(CLX, y, "CLASS", size=8, bold=True, color="#5a6675")
            text(FX, y, "THEIR FIT", size=8, bold=True, color="#5a6675",
                 anchor="ne")
            text(SX2, y, "WEAPON", size=8, bold=True, color="#5a6675",
                 anchor="ne")
            text(BX2, y, "COMBINED", size=8, bold=True, color="#5a6675")
            y += 16
            for score, wname, wt, fit, strength in picks[:6]:
                text(WX, y, wname, size=9)
                text(CLX, y, wt, size=9, color="#5a6675")
                text(FX, y, "%.0f" % fit, size=9, anchor="ne")
                text(SX2, y, "%d%%" % strength, size=9, anchor="ne")
                bar(BX2, y + 3, BW2, 10, score, "#2e7d32")
                text(TX, y, "%.0f" % score, size=9)
                y += 17
            y += 4
            y = note(y, "Weapon win rates are measured 3v3 mirror duels from "
                        "the 2dCS bench, not estimates -- a weapon nobody "
                        "wins with is a poor pick however well it suits "
                        "them.")
        else:
            y = note(y, "manual_data.json not found -- specific weapon "
                        "recommendations need the measured bench results.",
                     size=9, color="#b71c1c")
        if CLASS_BIAS:
            best_biased = max(
                WCLASSES, key=lambda w: cs_skill(c, w)
                + CLASS_BIAS.get(w, 0.0))
            y = note(y, "The game itself would arm them from %s -- its own "
                        "pick applies a small bias toward blades and "
                        "polearms." % best_biased.upper())
            y += 6
        y += 8

        # ------------------------------------------------------ in a fight
        y = section(y, "IN A FIGHT  --  the numbers the engine derives")
        stats = [
            ("Health", "%d" % p["hp"], "frame %d x vitality" % p["frame"]),
            ("Move speed", "%.0f px/s" % p["speed"], "from speed"),
            ("Dodge", "%.0f" % p["dodge"], "agility, balance, perception"),
            ("Guard", "%.0f" % p["guard"], "composure, balance, strength"),
            ("Critical", "%.1f%%" % (p["crit"] * 100),
             "dexterity and focus"),
            ("Swing speed", "x%.2f" % p["atk_speed"],
             "lower is faster; from %s skill" % p["best"]),
            ("Tempo", "x%.2f" % p["tempo"],
             "pause between attacks; from aggression"),
            ("Stamina", "%d" % p["stam"], "recovers x%.2f" % p["recover"]),
            ("Reserve", "%.0f%%" % (p["reserve"] * 100),
             "wind they refuse to spend"),
            ("Nerve", "panics under %.0f%%" % (p["nerve"] * 100),
             "runs for %.1fs" % p["flee"]),
        ]
        for label, val, why in stats:
            text(12, y, "%-13s %-16s %s" % (label, val, why), size=9,
                 color="#1f2733")
            y += 16
        y += 12

        # ----------------------------------------------------- temperament
        y = section(y, "TEMPERAMENT  --  the pressures the intent layer "
                       "argues over")
        for name, val in sorted(p["mind"].items(), key=lambda kv: -kv[1]):
            color, _lab, short = band_for(int(val))
            text(12, y, name, size=9)
            bar(190, y + 3, 140, 10, val, color)
            text(344, y, "%5.1f  %s" % (val, short), size=9)
            y += 18
        y += 10

        # ------------------------------------------------------- behaviour
        y = section(y, "HOW THEY FIGHT")
        for headline, why in cs_behaviour(p):
            text(12, y, headline, size=10, bold=True)
            y += 16
            for line in _wrap(why, max(40, (width - 60) // 7)):
                text(24, y, line, size=9, color="#3f4a57")
                y += 14
            y += 6
        y += 6

        # ------------------------------------------------------ provenance
        cv.create_line(12, y, width - 16, y, fill="#8a959e")
        y += 8
        y = note(y, "All figures on this tab describe 2dCS %s. %s"
                 % (CS_VERSION, CS_SOURCE_BLURB[CS_SOURCE]))
        y = note(y, "Aptitude is DERIVED from the engine's formulas rather "
                    "than measured. Checked against real fights it tracks "
                    "the win rate closely WITHIN a class (r = 0.68 to 0.86 "
                    "over 26 characters x 5 classes x 12 fights).")
        y = note(y, "Do NOT read it across classes: a 60 with a polearm "
                    "beats a 60 with a bow, because the classes themselves "
                    "are not equally strong. RECOMMENDED ARMAMENT is the "
                    "cross-class answer -- it folds in each weapon's own "
                    "measured result.")
        y = note(y, "Rebalancing weapons changes all of this. Re-run "
                    "zpyArenaLab and refresh manual_data.json after any "
                    "change.")
        y += 20
        cv.configure(scrollregion=(0, 0, width, y))

    def _on_wheel(self, event):
        try:
            idx = self.notebook.index(self.notebook.select())
        except tk.TclError:
            return
        cv = (self.canvas, self.pcanvas,
              getattr(self, "rcanvas", None))[idx] if idx < 3 else self.canvas
        if cv is not None:
            cv.yview_scroll(-1 * (event.delta // 120), "units")

    # ------------------------------------------------------------ list ops
    def _sorted_roster(self):
        key = self.sort_var.get()
        if key == "display_name":
            return sorted(self.roster, key=lambda c: c["display_name"])
        return sorted(self.roster, key=lambda c: c[key] or 0, reverse=True)

    def _refresh_list(self):
        needle = self.filter_var.get().strip().lower()
        key = self.sort_var.get()
        self.listbox.delete(0, "end")
        self._visible = []
        for c in self._sorted_roster():
            if needle and needle not in c["display_name"].lower():
                continue
            label = c["display_name"]
            if key != "display_name":
                label = "%2d  %s" % (c[key] or 0, label)
            self.listbox.insert("end", label)
            self._visible.append(c)
        # keep current selection highlighted if still visible
        if self.current in self._visible:
            self.listbox.selection_set(self._visible.index(self.current))

    def _on_select(self):
        if not hasattr(self, "_visible"):
            self._refresh_list()
        sel = self.listbox.curselection()
        if sel and self._visible:
            self.current = self._visible[sel[0]]
            self._update_identity()
            self._draw()

    def _on_compare(self):
        self.compare = self.by_name.get(self.compare_var.get())
        self._draw()

    # ----------------------------------------------------- character view
    def _update_identity(self):
        c = self.current
        age = date.today().year - c["birth_year"]
        cid = c["character_id"]
        rank = self.ranking.index(c) + 1
        core_txt = "  ".join("%s %.1f" % (CORE_ABBR[g], self.core[cid][g])
                             for g, _attrs in CORE_GROUPS)
        self.identity.configure(text=(
            "%s  (%s / %s)\n"
            "%s %s, born %d (age %d today) | %s | %s | schema v%s\n"
            "%d cm, %d kg | politics (1L..99R): %d | "
            "morality (1 evil..99 good): %d\n"
            "core averages: %s  ->  composite %.1f (rank %d of %d)\n"
            "%s"
        ) % (c["display_name"], c["character_id"], c["short_name"],
             c["species"], c["sex"], c["birth_year"], age,
             c["nationality"], c["religion"], c["schema_version"],
             c["height_cm"], c["weight_kg"], c["left2right"],
             c["evil2good"],
             core_txt, self.composite[cid], rank, len(self.roster),
             c["description"]))

    def _draw_spectrum(self, cv, x, y, w, h, c0, c1):
        """Gradient strip between two RGB endpoint colors."""
        for i in range(w):
            frac = i / max(w - 1, 1)
            rgb = tuple(int(a + frac * (b - a)) for a, b in zip(c0, c1))
            cv.create_line(x + i, y, x + i, y + h,
                           fill="#%02x%02x%02x" % rgb)

    def _draw(self):
        cv = self.canvas
        cv.delete("all")
        if not self.current:
            return
        width = max(cv.winfo_width(), 400)
        bar_x = self.LABEL_W
        bar_w = width - bar_x - self.VALUE_W - 16
        y = 10

        # axis spectrum strips (politics, morality)
        for col, _caption, c0, c1, _buckets in AXES:
            cv.create_text(8, y + 8, anchor="w", text=col,
                           font=("Consolas", 9, "bold"))
            self._draw_spectrum(cv, bar_x, y + 2, bar_w, 12, c0, c1)
            px = bar_x + (self.current[col] - 1) / 98 * bar_w
            cv.create_polygon(px - 5, y - 2, px + 5, y - 2, px, y + 6,
                              fill="black")
            if self.compare and self.compare is not self.current:
                cx = bar_x + (self.compare[col] - 1) / 98 * bar_w
                cv.create_line(cx, y + 1, cx, y + 15, fill="#1f2733",
                               width=2)
            cv.create_text(bar_x + bar_w + 8, y + 8, anchor="w",
                           text=str(self.current[col]),
                           font=("Consolas", 9))
            y += 26
        y += 4

        for group, attrs in GROUPS:
            avg = sum(self.current[a] for a in attrs) / len(attrs)
            pop_avg = st.fmean(self.stats[a]["mean"] for a in attrs)
            cv.create_text(8, y + self.HEAD_H / 2, anchor="w",
                           text="%s  (avg %.0f, population avg %.0f)"
                                % (group.upper(), avg, pop_avg),
                           font=("Consolas", 10, "bold"), fill="#1f2733")
            cv.create_line(8, y + self.HEAD_H - 4, width - 12,
                           y + self.HEAD_H - 4, fill="#c0c8d0")
            y += self.HEAD_H
            for attr in attrs:
                val = self.current[attr]
                s = self.stats[attr]
                color, _label, short = band_for(val)
                cy = y + self.ROW_H / 2
                cv.create_text(12, cy, anchor="w", text=attr,
                               font=("Consolas", 9))
                cv.create_rectangle(bar_x, y + 4, bar_x + bar_w,
                                    y + self.ROW_H - 4,
                                    fill="#eceff2", outline="#d5dade")
                cv.create_rectangle(bar_x, y + 4,
                                    bar_x + val / 99 * bar_w,
                                    y + self.ROW_H - 4,
                                    fill=color, outline=color)
                # population notches: median (down-triangle, top edge),
                # Q1 / Q3 (up-triangles, bottom edge)
                mx = bar_x + s["median"] / 99 * bar_w
                cv.create_polygon(mx - 4, y + 1, mx + 4, y + 1, mx, y + 8,
                                  fill="#22303c", outline="")
                for q in (s["q1"], s["q3"]):
                    qx = bar_x + q / 99 * bar_w
                    cv.create_polygon(qx - 3, y + self.ROW_H - 1,
                                      qx + 3, y + self.ROW_H - 1,
                                      qx, y + self.ROW_H - 7,
                                      fill="#8a959e", outline="")
                if self.compare and self.compare is not self.current:
                    cx = bar_x + self.compare[attr] / 99 * bar_w
                    cv.create_line(cx, y + 1, cx, y + self.ROW_H - 1,
                                   fill="#1f2733", width=2)
                cv.create_text(bar_x + bar_w + 8, cy, anchor="w",
                               text="%2d %s" % (val, short),
                               font=("Consolas", 8))
                y += self.ROW_H
            y += 8

        if self.compare and self.compare is not self.current:
            cv.create_text(12, y + 8, anchor="w",
                           text="black tick = %s"
                                % self.compare["display_name"],
                           font=("Consolas", 8, "italic"), fill="#1f2733")
            y += 20

        cv.configure(scrollregion=(0, 0, width, y + 10))

    # ---------------------------------------------------- population view
    def _draw_population(self):
        cv = self.pcanvas
        cv.delete("all")
        roster = self.roster
        if not roster:
            return
        width = max(cv.winfo_width(), 640)
        n = len(roster)
        year = date.today().year

        def text(x, y, s, size=9, bold=False, color="#1f2733",
                 anchor="nw"):
            font = ("Consolas", size, "bold") if bold else ("Consolas", size)
            cv.create_text(x, y, anchor=anchor, text=s, font=font,
                           fill=color)

        def section(y, title):
            text(12, y, title, size=11, bold=True)
            cv.create_line(12, y + 20, width - 16, y + 20, fill="#8a959e")
            return y + 28

        y = 10
        text(12, y, "POPULATION REPORT -- %d characters -- %s" %
             (n, CSV_PATH.name), size=12, bold=True)
        y += 30

        # ---------------------------------------------------- demographics
        y = section(y, "DEMOGRAPHICS")
        sexes = Counter(c["sex"] for c in roster)
        by_sex_overall = {
            s: st.fmean(self.composite[c["character_id"]]
                        for c in roster if c["sex"] == s)
            for s in sexes}
        species = Counter(c["species"] for c in roster)
        ages = sorted(((year - c["birth_year"], c) for c in roster),
                      key=lambda t: t[0])
        heights = sorted(roster, key=lambda c: c["height_cm"])
        weights = sorted(roster, key=lambda c: c["weight_kg"])
        bmis = [c["weight_kg"] / (c["height_cm"] / 100) ** 2 for c in roster]
        religions = Counter(c["religion"] for c in roster)
        rel_faith = {r: st.fmean(c["faith"] for c in roster
                                 if c["religion"] == r) for r in religions}
        nats = Counter(c["nationality"] for c in roster)
        lines = [
            "Roster: %d characters | sex: %s | species: %s" % (
                n,
                "  ".join("%s %d (core composite avg %.1f)"
                          % (s, sexes[s], by_sex_overall[s])
                          for s in sorted(sexes)),
                ", ".join("%s %d" % (sp, ct)
                          for sp, ct in species.most_common())),
            "Age (in %d): mean %.1f | youngest %d (%s) | oldest %d (%s)" % (
                year, st.fmean(a for a, _ in ages),
                ages[0][0], ages[0][1]["display_name"],
                ages[-1][0], ages[-1][1]["display_name"]),
            "Height: mean %.1f cm (%d %s - %d %s)" % (
                st.fmean(c["height_cm"] for c in roster),
                heights[0]["height_cm"], heights[0]["short_name"],
                heights[-1]["height_cm"], heights[-1]["short_name"]),
            "Weight: mean %.1f kg (%d %s - %d %s) | mean BMI %.1f" % (
                st.fmean(c["weight_kg"] for c in roster),
                weights[0]["weight_kg"], weights[0]["short_name"],
                weights[-1]["weight_kg"], weights[-1]["short_name"],
                st.fmean(bmis)),
            "Religion (mean faith rating): " + "  ".join(
                "%s %d (%.0f)" % (r, religions[r], rel_faith[r])
                for r, _cnt in religions.most_common()),
            "Nationalities: %d distinct%s" % (
                len(nats),
                " (every character unique)" if len(nats) == n else
                " | most common: " + ", ".join(
                    "%s x%d" % (nm, ct) for nm, ct in nats.most_common(3))),
        ]
        for line in lines:
            text(20, y, line)
            y += 17
        y += 10

        # -------------------------------------- political and moral spectra
        y = section(y, "POLITICAL AND MORAL SPECTRA (each tick = one "
                       "character, marker = mean)")
        strip_x, strip_w = 20, width - 40
        for col, caption, c0, c1, buckets in AXES:
            vals = [c[col] for c in roster]
            text(20, y, caption, size=9, bold=True)
            y += 16
            self._draw_spectrum(cv, strip_x, y + 4, strip_w, 14, c0, c1)
            for c in roster:
                px = strip_x + (c[col] - 1) / 98 * strip_w
                cv.create_line(px, y + 2, px, y + 20, fill="#111", width=2)
            mean_px = strip_x + (st.fmean(vals) - 1) / 98 * strip_w
            cv.create_polygon(mean_px - 6, y - 4, mean_px + 6, y - 4,
                              mean_px, y + 3, fill="#1f2733")
            y += 26
            counts = (sum(1 for v in vals if v < 40),
                      sum(1 for v in vals if 40 <= v <= 60),
                      sum(1 for v in vals if v > 60))
            text(20, y, "mean %.1f | median %.1f | %s(<40) %d / %s(40-60) "
                        "%d / %s(>60) %d"
                 % (st.fmean(vals), st.median(vals),
                    buckets[0], counts[0], buckets[1], counts[1],
                    buckets[2], counts[2]))
            y += 16
            # which rated attributes track this axis most strongly?
            corr = sorted((pearson(vals, self.stats[a]["vals"]), a)
                          for a in ALL_ATTRS)
            text(20, y, "tracks: %s | opposes: %s"
                 % ("  ".join("%s %+.2f" % (a, r)
                              for r, a in corr[::-1][:3]),
                    "  ".join("%s %+.2f" % (a, r) for r, a in corr[:3])),
                 size=8, color="#5f6a73")
            y += 22

        # ------------------------------------------------ core group table
        y = section(y, "CORE GROUP AVERAGES (sorted by composite)")
        text(20, y, "PHY excludes metabolism/lifespan | SOC is charisma/"
                    "empathy/conversation only (no aggression/loyalty/"
                    "deception)", size=8, color="#5f6a73")
        y += 16
        comps = list(self.composite.values())
        text(20, y, "composite: mean %.1f | median %.1f | stdev %.1f | "
                    "range %.1f - %.1f"
             % (st.fmean(comps), st.median(comps), st.pstdev(comps),
                min(comps), max(comps)))
        y += 20
        name_w = 215
        slot_w = (width - name_w - 90) / 4
        for j, (g, attrs) in enumerate(CORE_GROUPS):
            text(name_w + j * slot_w, y, "%s (%d)" % (CORE_ABBR[g],
                                                      len(attrs)),
                 size=8, bold=True)
        text(name_w + 4 * slot_w + 6, y, "COMP", size=8, bold=True)
        y += 15
        for i, c in enumerate(self.ranking):
            cid = c["character_id"]
            ry = y + i * 18
            text(20, ry + 2, "%2d. %-20s" % (i + 1, c["display_name"]),
                 size=8)
            for j, (g, _attrs) in enumerate(CORE_GROUPS):
                v = self.core[cid][g]
                color = band_for(round(v))[0]
                bx = name_w + j * slot_w
                bw = slot_w - 48
                cv.create_rectangle(bx, ry + 3, bx + bw, ry + 15,
                                    fill="#eceff2", outline="#d5dade")
                cv.create_rectangle(bx, ry + 3, bx + v / 99 * bw, ry + 15,
                                    fill=color, outline=color)
                text(bx + bw + 4, ry + 2, "%.1f" % v, size=8)
            text(name_w + 4 * slot_w + 6, ry + 2,
                 "%.1f" % self.composite[cid], size=8, bold=True)
        y += len(self.ranking) * 18 + 10

        # ------------------------------------------- leaders and archetypes
        y = section(y, "GROUP LEADERS AND ARCHETYPES")
        for group, attrs in GROUPS:
            top3 = sorted(roster,
                          key=lambda c: st.fmean(c[a] for a in attrs),
                          reverse=True)[:3]
            text(20, y, "%-14s %s" % (group + ":", "  ".join(
                "%s %.1f" % (c["short_name"],
                             st.fmean(c[a] for a in attrs))
                for c in top3)))
            y += 17
        rounded = sorted(roster, key=lambda c: self.spread[c["character_id"]])
        text(20, y, "Most well-rounded (lowest own-rating spread): %s | "
                    "Most specialized: %s"
             % ("  ".join("%s sd %.1f" % (c["short_name"],
                                          self.spread[c["character_id"]])
                          for c in rounded[:3]),
                "  ".join("%s sd %.1f" % (c["short_name"],
                                          self.spread[c["character_id"]])
                          for c in rounded[::-1][:3])))
        y += 27

        # ------------------------------------------------------- highlights
        y = section(y, "ATTRIBUTE HIGHLIGHTS (population means)")
        by_mean = sorted(ALL_ATTRS, key=lambda a: self.stats[a]["mean"])
        by_sd = sorted(ALL_ATTRS, key=lambda a: self.stats[a]["stdev"])
        hi_lines = [
            "Highest means: " + "  ".join(
                "%s %.1f" % (a, self.stats[a]["mean"])
                for a in by_mean[::-1][:5]),
            "Lowest means:  " + "  ".join(
                "%s %.1f" % (a, self.stats[a]["mean"])
                for a in by_mean[:5]),
            "Most varied (stdev): " + "  ".join(
                "%s %.1f" % (a, self.stats[a]["stdev"])
                for a in by_sd[::-1][:5]),
            "Most uniform (stdev): " + "  ".join(
                "%s %.1f" % (a, self.stats[a]["stdev"])
                for a in by_sd[:5]),
        ]
        for line in hi_lines:
            text(20, y, line)
            y += 17
        y += 10

        # ------------------------------------------- per-attribute boxplots
        y = section(y, "ATTRIBUTE DISTRIBUTIONS (box = Q1-median-Q3, "
                       "whiskers = min-max, dot = mean)")
        plot_x = 170
        plot_w = width - plot_x - 265
        stat_x = plot_x + plot_w + 12
        text(plot_x, y, "1", size=7, color="#8a959e")
        for tick in (25, 50, 75, 99):
            text(plot_x + (tick - 1) / 98 * plot_w, y, str(tick),
                 size=7, color="#8a959e", anchor="n")
        y += 14
        for group, attrs in GROUPS:
            text(12, y + 2, group.upper(), size=9, bold=True)
            y += 20
            g_top = y
            for attr in attrs:
                s = self.stats[attr]
                cy = y + 12
                sx = lambda v: plot_x + (v - 1) / 98 * plot_w
                text(16, y + 5, attr, size=8)
                cv.create_line(sx(s["min"]), cy, sx(s["max"]), cy,
                               fill="#9aa4ad")
                for w_end in (s["min"], s["max"]):
                    cv.create_line(sx(w_end), cy - 4, sx(w_end), cy + 4,
                                   fill="#9aa4ad")
                color, _l, _sh = band_for(round(s["median"]))
                cv.create_rectangle(sx(s["q1"]), cy - 6, sx(s["q3"]), cy + 6,
                                    fill=color, outline="#5f6a73")
                cv.create_line(sx(s["median"]), cy - 6,
                               sx(s["median"]), cy + 6,
                               fill="#111", width=2)
                cv.create_oval(sx(s["mean"]) - 3, cy - 3,
                               sx(s["mean"]) + 3, cy + 3,
                               fill="white", outline="#111")
                text(stat_x, y + 5,
                     "m %5.1f sd %4.1f | %2d %s - %2d %s"
                     % (s["mean"], s["stdev"], s["min"], s["min_who"],
                        s["max"], s["max_who"]), size=8)
                y += 24
            for tick in (25, 50, 75):
                tx = plot_x + (tick - 1) / 98 * plot_w
                cv.create_line(tx, g_top - 2, tx, y - 8, fill="#e3e7ea")
                cv.tag_lower(cv.find_all()[-1])
            y += 6

        # ----------------------------------------------------- correlations
        y = section(y, "NOTABLE CORRELATIONS (Pearson r across %d "
                       "characters)" % n)
        text(20, y, "Strongest positive:", bold=True, size=9)
        y += 17
        for r, a, b in self.corr_pos:
            text(28, y, "%-20s <-> %-20s  r = %+.2f" % (a, b, r), size=9)
            y += 16
        text(20, y + 4, "Strongest negative:", bold=True, size=9)
        y += 21
        for r, a, b in self.corr_neg:
            text(28, y, "%-20s <-> %-20s  r = %+.2f" % (a, b, r), size=9)
            y += 16
        y += 12

        # ------------------------------------------------------ band census
        total = n * len(ALL_ATTRS)
        y = section(y, "RATING BAND CENSUS (all %d ratings)" % total)
        census = Counter()
        for c in roster:
            for a in ALL_ATTRS:
                census[band_for(c[a])[1]] += 1
        cbar_x, cbar_w = 340, width - 340 - 30
        biggest = max(census.values()) if census else 1
        for (upper, color, label, short), rng in zip(BANDS, BAND_RANGES):
            cnt = census.get(label, 0)
            cv.create_rectangle(20, y + 2, 34, y + 14, fill=color,
                                outline=color)
            text(42, y + 2, "%-14s %-6s %4d ratings (%4.1f%%)"
                 % (label, rng, cnt, 100 * cnt / total), size=8)
            cv.create_rectangle(cbar_x, y + 3,
                                cbar_x + cnt / biggest * cbar_w, y + 13,
                                fill=color, outline=color)
            y += 18
        y += 10

        cv.configure(scrollregion=(0, 0, width, y + 10))


def main():
    if not CSV_PATH.exists():
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(SCRIPT_NAME, "Roster CSV not found:\n%s"
                             % CSV_PATH)
        return
    roster = load_roster(CSV_PATH)
    app = ToonViewer(roster)
    app.mainloop()


if __name__ == "__main__":
    main()
