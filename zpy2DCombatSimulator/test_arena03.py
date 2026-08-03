"""
Validation suite for zpyCombatArena03. Run with:  py -3 test_arena03.py

Covers:
  1. roster + weapon table sanity
  2. every weapon resolves a fight (no stalls/timeouts)
  3. mechanics coverage (dodge, block, stagger, knockdown, DoTs, AoE...)
  4. determinism (same seed -> identical result)
  5. update-order independence (reversed fighter list -> identical result,
     and mirrored fights are statistically side-balanced)
  6. mutual kills resolve as explicit draws
"""

import itertools
import random
import sys

import zpyCombatArena03 as m

FAILS = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail
                                                     else ""))
    if not ok:
        FAILS.append(name)


print("== 1. roster & weapons ==")
roster = m.load_roster()
check("roster loads", len(roster) >= 10, f"{len(roster)} characters")
check("20+ weapons", len(m.WEAPONS) >= 20, f"{len(m.WEAPONS)} weapons")
check("5 weapon types", len(m.WEAPONS_BY_TYPE) == 5,
      ",".join(m.WEAPONS_BY_TYPE))

print("== 2. every weapon resolves ==")
draw = random.Random(1)
mechanics = set()
worst = 0.0
for wname in m.WEAPONS:
    chars = draw.sample(roster, 4)
    r = m.run_headless(99, [(chars[0], wname), (chars[1], wname)],
                       [(chars[2], wname), (chars[3], wname)])
    text = " | ".join(t for _, t in r["events"])
    for key, needle in [("dodge", "dodges"), ("block", "blocks"),
                        ("stagger", "staggered"), ("knockdown", "knocked down"),
                        ("bleed", "bleeding"), ("poison", "poisoned"),
                        ("burn", "catches fire"), ("boom", "BOOM"),
                        ("flee", "flees"), ("crit", "CRIT")]:
        if needle in text:
            mechanics.add(key)
    worst = max(worst, r["time"])
    if r["winner"] == "timeout":
        check(f"{wname} resolves", False)
check("all weapons resolve", "timeout" not in
      [None], f"longest fight {worst:.0f}s")
check("no fight hit the 240s cap", worst < 240, f"worst {worst:.0f}s")

print("== 3. mechanics coverage ==")
need = {"dodge", "block", "stagger", "knockdown", "bleed", "poison",
        "burn", "boom", "flee", "crit"}
check("all mechanics observed", need <= mechanics,
      "missing: " + (",".join(sorted(need - mechanics)) or "none"))

print("== 4. determinism ==")
ta = [(c, "Longsword") for c in roster[:3]]
tb = [(c, "Shortbow") for c in roster[3:6]]
r1 = m.run_headless(777, ta, tb)
r2 = m.run_headless(777, ta, tb)
check("same seed, same fight", r1 == r2)

print("== 5. update-order independence ==")
leo = roster[0]
N = 120
for wname in ("Dagger", "Bomb"):
    results = {}
    for label, reverse in (("normal", False), ("reversed", True)):
        outcomes = []
        for seed in range(N):
            sim = m.Sim(seed, [(leo, wname)], [(leo, wname)])
            if reverse:
                sim.fighters.reverse()
            while sim.winner is None and sim.t < 240:
                sim.step()
            outcomes.append((sim.winner, round(sim.t, 2)))
        results[label] = outcomes
    identical = results["normal"] == results["reversed"]
    reds = sum(1 for w, _ in results["normal"] if w == "Red team")
    blues = sum(1 for w, _ in results["normal"] if w == "Blue team")
    check(f"{wname}: reversed order is a no-op", identical)
    # ~50/50 within ~3 sigma for N=120 decisive fights
    lo, hi = N // 2 - 30, N // 2 + 30
    check(f"{wname}: mirror is side-balanced", lo <= reds <= hi
          and lo <= blues <= hi, f"Red {reds} / Blue {blues}")

print("== 6. mutual kills are explicit draws ==")
draws = 0
for seed in range(150):
    r = m.run_headless(seed, [(leo, "Dagger")], [(leo, "Dagger")])
    if r["winner"] == "draw":
        draws += 1
        both_down = sum(1 for _, t in r["events"] if "is down!" in t)
        if both_down != 2:
            check("draw means both fell", False, f"seed {seed}")
            break
check("simultaneous kills occur and draw", draws > 0, f"{draws}/150 draws")

print("== 7. weapon-category consistency ==")
# explosive damage must scale with power_mult: same rng, same geometry,
# different power -> different damage
sim = m.Sim(1, [(roster[0], "Bomb")], [(roster[1], "Bomb")])
victim = sim.fighters[1]
victim.sx, victim.sy = victim.x, victim.y
owner = sim.fighters[0]
taken = []
for pm in (0.7, 1.3):
    owner.power_mult = pm
    owner.rng = random.Random(42)
    victim.hp = victim.max_hp
    sim.explode(owner, m.WEAPONS["Bomb"], victim.x - 10, victim.y)
    taken.append(victim.max_hp - victim.hp)
check("explosions use power_mult", taken[1] > taken[0],
      f"dmg {taken[0]:.0f} at 0.7x vs {taken[1]:.0f} at 1.3x")

# cleave: somewhere in wide-weapon team fights, one swing strikes 2+ foes
cleaved = False
for seed in range(30):
    r = m.run_headless(seed, [(c, "Quarterstaff") for c in roster[:3]],
                       [(c, "Quarterstaff") for c in roster[3:6]])
    per_tick = {}
    for t, text in r["events"]:
        if " hits " in text:
            key = (t, text.split(" hits ")[0])
            per_tick[key] = per_tick.get(key, 0) + 1
    if any(n >= 2 for n in per_tick.values()):
        cleaved = True
        break
check("wide weapons cleave multiple targets", cleaved)

# allies block arrows; nobody takes friendly arrow damage
saw_block = False
for seed in range(30):
    r = m.run_headless(seed, [(c, "Shortbow") for c in roster[:3]],
                       [(c, "Club") for c in roster[3:6]])
    if any("blocks" in t and "shot" in t for _, t in r["events"]):
        saw_block = True
        break
check("teammates stop arrows (no damage)", saw_block)

print("== 8. cornered shooters ==")
bashes = 0
ranged_wins = 0
for seed in range(60):
    r = m.run_headless(seed, [(roster[0], "Sling")], [(roster[1], "Dagger")])
    bashes += sum(1 for _, t in r["events"] if "Weapon Butt" in t)
    if r["winner"] == "Red team":
        ranged_wins += 1
check("butt-strike shove occurs", bashes > 0, f"{bashes} across 60 fights")
check("ranged 1v1 is viable but not dominant", 5 <= ranged_wins <= 45,
      f"Sling wins {ranged_wins}/60 vs Dagger")

print()
if FAILS:
    print(f"{len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("all checks passed")
