import random

# =========================
# Config & Constants
# =========================
SIM_CYCLES = 15            # number of cycles (days)
RNG_SEED = 12345           # set None for full randomness

# Verbosity
VERBOSE_ACTIONS = True     # print every action in detail
VERBOSE_TICK = True        # per-cycle header and footer summaries
VERBOSE_INVENTORY_EVENTS = True
VERBOSE_TRADES = True
VERBOSE_BLOCKS = True

# ASCII dashboard
ASCII_DASHBOARD = True
DASHBOARD_TOP_N = 6
BAR_WIDTH = 26

STARTING_CREDITS_PER_TOON = 2
STARTING_CREDITS_MERCHANT = 5

# Energy & Charge model
BASE_ENERGY = 100
BASE_LIFE = 100
BASE_CHARGE = 100
BASE_BATTERY = 100

# Energy/charge use per cycle (before actions)
def energy_cost_from_metabolism(metabolism):
    return max(1, 21 - metabolism)  # from spec

def charge_cost_from_stamina(stamina):
    return max(1, 25 - stamina)     # from spec

# Self-focused effects
EAT_ENERGY_RESTORE = 25
REST_CHARGE_RESTORE = 20
HEAL_LIFE_RESTORE = 20

# Items (canonical names)
SUBSTRATE   = "Substrate"
TOOL        = "Tool"
BUILDING    = "Buildingbits"
MEALBITS    = "Mealbits"
BEAD        = "Bead"
JOULES      = "Joules"
WOODBITS    = "Woodbits"
PLANKBITS   = "Plankbits"
SIGNALBITS  = "Signalbits"
MAPBIT      = "Mapbit"
BITNAPSE    = "Bitnapse"
BUGS        = "Bugs"
BUGPATCH    = "Bugpatch"
VISTA       = "Vista"

ALL_ITEMS = [SUBSTRATE, TOOL, BUILDING, MEALBITS, BEAD, JOULES, WOODBITS, PLANKBITS,
             SIGNALBITS, MAPBIT, BITNAPSE, BUGS, BUGPATCH, VISTA]

# Professions
RESOURCE_ROLES = ["Gatherer", "Miner", "Farmer", "Lumberjack", "Signalist", "Crawler"]
PROCESS_ROLES  = ["Constructor", "Refiner", "Craftsman", "Codehealer", "Echokeeper"]
KNOWLEDGE_ROLES= ["Cartographer", "Dreamweaver", "Digital Landscaper", "Cook"]
SUPPORT_ROLES  = ["Merchant"]

ALL_PROFESSIONS = RESOURCE_ROLES + PROCESS_ROLES + KNOWLEDGE_ROLES + SUPPORT_ROLES

# Resource outputs
RESOURCE_OUTPUT = {
    "Gatherer": JOULES,
    "Miner": SUBSTRATE,
    "Farmer": MEALBITS,
    "Lumberjack": WOODBITS,
    "Signalist": SIGNALBITS,
    "Crawler": BUGS,
}

# Professional recipes (inputs -> outputs)
# Note: Refiner has a special recipe Substrate -> +1 credit (not an item)
PROFESSIONAL_RECIPES = {
    "Craftsman": [
        ({SUBSTRATE: 1}, {TOOL: 1}),  # Path 1
    ],
    "Constructor": [
        ({TOOL: 1}, {BUILDING: 1}),         # Path 1
        ({PLANKBITS: 1}, {BUILDING: 1}),    # Path 5
    ],
    "Refiner": [
        ({WOODBITS: 1}, {PLANKBITS: 1}),  # Path 5
        # Special: {SUBSTRATE:1} -> +1 credit (handled separately)
    ],
    "Cook": [
        ({MEALBITS: 1}, {BEAD: 1}),  # Path 2
    ],
    "Cartographer": [
        ({SIGNALBITS: 1}, {MAPBIT: 1}),  # Path 6
    ],
    "Dreamweaver": [
        ({SIGNALBITS: 1}, {BITNAPSE: 1}),  # Path 7
    ],
    "Digital Landscaper": [
        ({BUILDING: 1}, {VISTA: 1}),  # Path 1/5 consumer
    ],
    "Codehealer": [
        ({BUGS: 1}, {BUGPATCH: 1}),  # Path 8
    ],
    # Echokeeper is mood-support; Merchant is special; Resource roles are simple harvesters.
}

# Interaction library: "Compliment"
INTERACTIONS = {
    "Compliment": {
        "requires": lambda initiator: initiator.attr("Extraversion") > 10,
        "outcomes": [
            ("Sincere Gratitude", 60,
             {"A_mood": +3, "B_mood": +5, "rel": +2, "drift": ("Openness", +1)}),
            ("Awkward Response", 30,
             {"A_mood": -1, "B_mood": -1, "rel": 0}),
            ("Suspicious Reaction", 5,
             {"A_mood": -2, "B_mood": -2, "rel": -2}),
            ("Fart", 5,
             {"A_mood": +1, "B_mood": 0, "rel": +1}),
        ],
        # Target personality check: dislike if Agreeableness < 5 for positive outcomes
        "target_check": lambda target, label: (
            True if label in ["Awkward Response", "Suspicious Reaction", "Fart"]
            else target.attr("Agreeableness") >= 5
        ),
    }
}

def weighted_choice(pairs):
    if not pairs:
        return None
    total = sum(w for _, w in pairs)
    if total <= 0:
        return pairs[0][0]
    r = random.uniform(0, total)
    cum = 0.0
    for item, weight in pairs:
        cum += weight
        if r <= cum:
            return item
    return pairs[-1][0]

# =========================
# ASCII helpers
# =========================
def bar(current, maximum, width=BAR_WIDTH):
    maximum = max(1, maximum)
    filled = int(round((current / float(maximum)) * width))
    filled = max(0, min(width, filled))
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"

def short(name, n=10):
    return name if len(name) <= n else (name[:n-3] + "...")


# =========================
# Toon & Inventory
# =========================
class Inventory:
    """
    3-slot inventory: each slot is a distinct item type; counts are unlimited.
    """
    def __init__(self, max_types=3):
        self.max_types = max_types
        self._store = {}  # item -> count

    def count_types(self):
        return len(self._store)

    def qty(self, item):
        return self._store.get(item, 0)

    def can_add_type(self, item):
        return item in self._store or self.count_types() < self.max_types

    def add(self, item, n=1):
        if self.can_add_type(item):
            self._store[item] = self._store.get(item, 0) + n
            return True
        return False

    def remove(self, item, n=1):
        if self.qty(item) >= n:
            self._store[item] -= n
            if self._store[item] == 0:
                del self._store[item]
            return True
        return False

    def items(self):
        return dict(self._store)

class Toon:
    def __init__(self, name, profession, rnd):
        self.name = name
        self.profession = profession

        # Core states
        self.energy = BASE_ENERGY
        self.life = BASE_LIFE
        self.charge = BASE_CHARGE
        self.battery = BASE_BATTERY
        self.mood = 100
        self.credits = 0
        self.blocks = 0

        # Flags
        self.done = False
        self.needs_resource = set()  # strings of item names needed

        # Relations & Inventory
        self.relations = {}  # other_name -> int
        self.inv = Inventory(max_types=3)

        # Random attributes (1-20)
        self.attributes = {k: rnd.randint(7, 14) for k in [
            "Stamina","Metabolism","Strength","Perception","Speed","Intelligence","Creativity",
            "Logic","Technique","Dedication","Industriousness","Hacking","Harmony","Precision",
            "Vision","Alignment","Openness","Conscientiousness","Extraversion","Agreeableness",
            "Neuroticism"
        ]}

        # Seed credits
        base = STARTING_CREDITS_MERCHANT if profession == "Merchant" else STARTING_CREDITS_PER_TOON
        self.credits = base

        # For ASCII: remember last action
        self.last_action = "-"

    def attr(self, name):
        return self.attributes.get(name, 10)

    def add_relation(self, other, delta):
        v = self.relations.get(other, 0)
        self.relations[other] = v + delta

    def action_weights(self):
        # Base 1:1:1 → modulated by personality
        C = self.attr("Conscientiousness")  # favors Professional
        E = self.attr("Extraversion")       # favors Interactive
        # Self-focus gets a small boost when Neuroticism high (self-care) and when energy/charge low
        N = self.attr("Neuroticism")

        w_self = 1.0 + (N - 10) * 0.05
        if self.energy < 40: w_self += 0.7
        if self.charge < 40: w_self += 0.7

        w_prof = 1.0 * (0.5 + C/20.0)
        w_inter = 1.0 * (0.5 + E/20.0)

        return [("Self", max(0.1, w_self)),
                ("Professional", max(0.1, w_prof)),
                ("Interactive", max(0.1, w_inter))]

    def energy_tick(self):
        # Consume energy & charge each cycle baseline
        e_cost = energy_cost_from_metabolism(self.attr("Metabolism"))
        c_cost = charge_cost_from_stamina(self.attr("Stamina"))

        self.energy -= e_cost
        self.charge -= c_cost

        if self.energy < 0:
            # spill damage into life
            self.life += self.energy
            self.energy = 0

        if self.charge < 0:
            # discharge beyond 0 erodes battery
            self.battery = max(0, self.battery - 1)
            self.charge = 0

    def try_mint_block(self, cycle):
        minted = 0
        while self.credits >= 10:
            self.credits -= 10
            self.blocks += 1
            minted += 1
            if VERBOSE_BLOCKS:
                print(f">>> DESTINYBLOCK #{self.blocks}: c{cycle:03d}_{self.name}_{self.profession}")
        return minted

    # Inventory helpers with logging
    def add_item(self, item, n=1):
        ok = self.inv.add(item, n)
        if ok and VERBOSE_INVENTORY_EVENTS:
            print(f"      [INV] {self.name} +{n} {item} (now {self.inv.qty(item)})")
        elif not ok and VERBOSE_INVENTORY_EVENTS:
            print(f"      [INV] {self.name} could not store {item} (3-type limit) → dropped")
        return ok

    def consume_item(self, item, n=1):
        ok = self.inv.remove(item, n)
        if ok and VERBOSE_INVENTORY_EVENTS:
            print(f"      [INV] {self.name} -{n} {item} (now {self.inv.qty(item)})")
        return ok

# =========================
# World / Simulation
# =========================
class World:
    STARTER_INPUTS_BY_PROF = {
        "Craftsman": [SUBSTRATE],
        "Constructor": [TOOL, PLANKBITS],
        "Refiner": [WOODBITS, SUBSTRATE],
        "Cook": [MEALBITS],
        "Cartographer": [SIGNALBITS],
        "Dreamweaver": [SIGNALBITS],
        "Digital Landscaper": [BUILDING],
        "Codehealer": [BUGS],
        # Echokeeper: no material inputs by design
        # Merchant: no mandatory inputs
    }

    def __init__(self, seed=None):
        if seed is not None:
            random.seed(seed)
        self.rnd = random.Random(seed)

        self.toons = []
        self.blocks_total = 0
        self.block_log = []  # strings like "c005_toon0000001_Miner"

        self.trades_this_cycle = 0

        self._init_population()

    def _init_population(self):
        # 2 toons per profession
        counter = 1
        for prof in ALL_PROFESSIONS:
            for _ in range(2):
                name = f"toon{counter:07d}"
                t = Toon(name, prof, self.rnd)
                self.toons.append(t)
                # seed starting resources for processors/knowledge roles, + Joules for all
                self._seed_starting_items(t)
                counter += 1

    def _seed_starting_items(self, t):
        """Give each professional at least 5 of their input resources, and give *every* toon 5 Joules.
        Respects the 3-type inventory limit (inputs first, then Joules)."""
        inputs = self.STARTER_INPUTS_BY_PROF.get(t.profession, [])
        for it in inputs:
            t.add_item(it, 5)
        t.add_item(JOULES, 5)

    # ===== Utility lookups =====
    def by_name(self, name):
        for t in self.toons:
            if t.name == name:
                return t
        return None

    def not_done(self, exclude=None):
        return [t for t in self.toons if not t.done and t is not exclude]

    def sample_targets(self, k, exclude=None, must_not_done=True):
        pool = [t for t in self.toons if (not must_not_done or not t.done) and t is not exclude]
        n = min(k, len(pool))
        return self.rnd.sample(pool, n) if n > 0 else []

    # ===== Economy helpers =====
    def award_block(self, toon, cycle):
        self.blocks_total += 1
        self.block_log.append(f"c{cycle:03d}_{toon.name}_{toon.profession}")

    def merchant_buy_from_producer(self, merchant, item):
        producers = self.toons[:]
        self.rnd.shuffle(producers)
        for p in producers:
            if p is merchant:
                continue
            if p.inv.qty(item) > 0 and merchant.credits >= 1:
                p.consume_item(item, 1)
                merchant.add_item(item, 1)
                merchant.credits -= 1
                p.credits += 1
                self.trades_this_cycle += 1
                if VERBOSE_TRADES:
                    print(f"    [TRADE] {merchant.name} bought 1 {item} from {p.name} for 1 credit "
                          f"(M:{merchant.credits} → P:{p.credits})")
                return True
        return False

    def merchant_deliver(self, merchant, needy):
        for needed in list(needy.needs_resource):
            if merchant.inv.qty(needed) == 0:
                self.merchant_buy_from_producer(merchant, needed)

            if merchant.inv.qty(needed) > 0 and needy.credits >= 1:
                merchant.consume_item(needed, 1)
                needy.add_item(needed, 1)
                needy.needs_resource.discard(needed)

                merchant.credits += 1
                needy.credits -= 1
                self.trades_this_cycle += 1
                if VERBOSE_TRADES:
                    print(f"    [TRADE] {merchant.name} sold 1 {needed} to {needy.name} for 1 credit "
                          f"(M:{merchant.credits}, {needy.name}:{needy.credits})")
                return True
        return False

    # ===== Action Implementations =====
    def do_self_focused(self, t):
        if t.energy <= 40 and t.inv.qty(JOULES) > 0:
            choice = "eat"
        elif t.charge <= 40:
            choice = "rest"
        elif t.life <= 70 and t.inv.qty(BUGPATCH) > 0:
            choice = "heal"
        else:
            choice = "idle"  # Replaced "train" with "idle"

        t.last_action = f"Self:{choice}"
        if VERBOSE_ACTIONS:
            print(f"  [Self]  {t.name} ({t.profession}) chooses {choice}")

        if choice == "eat":
            if t.consume_item(JOULES, 1):
                t.energy = min(BASE_ENERGY, t.energy + EAT_ENERGY_RESTORE)
                t.mood += 1
        elif choice == "rest":
            if t.battery > 0:
                t.charge = min(BASE_CHARGE, t.charge + REST_CHARGE_RESTORE)
                t.mood += 1
        elif choice == "heal":
            if t.consume_item(BUGPATCH, 1):
                t.life = min(BASE_LIFE, t.life + HEAL_LIFE_RESTORE)
                t.mood += 2
        elif choice == "idle":
            # The toon does nothing, this block replaces the "train" logic.
            pass

    def do_professional(self, t):
        prof = t.profession

        if prof in RESOURCE_ROLES:
            out = RESOURCE_OUTPUT[prof]
            t.last_action = f"Work:harvest {out}"
            if VERBOSE_ACTIONS:
                print(f"  [Work]  {t.name} ({prof}) harvests {out}")
            t.add_item(out, 1)
            return

        if prof == "Refiner":
            if t.inv.qty(WOODBITS) > 0:
                t.last_action = f"Work:refine {WOODBITS}->{PLANKBITS}"
                if VERBOSE_ACTIONS:
                    print(f"  [Work]  {t.name} (Refiner) refines {WOODBITS}→{PLANKBITS}")
                t.consume_item(WOODBITS, 1)
                t.add_item(PLANKBITS, 1)
                return
            if t.inv.qty(SUBSTRATE) > 0:
                t.last_action = f"Work:monetize {SUBSTRATE}"
                t.consume_item(SUBSTRATE, 1)
                t.credits += 1
                if VERBOSE_ACTIONS:
                    print(f"  [Work]  {t.name} (Refiner) monetizes {SUBSTRATE} → +1 credit (now {t.credits})")
                return
            needed = WOODBITS if t.inv.qty(WOODBITS) == 0 else SUBSTRATE
            t.needs_resource.add(needed)
            t.last_action = f"Work:needs {needed}"
            if VERBOSE_ACTIONS:
                print(f"  [Work]  {t.name} (Refiner) lacks {needed} → needs_resource set")
            return

        if prof == "Echokeeper":
            targets = self.sample_targets(1, exclude=t, must_not_done=False)
            if targets:
                target = targets[0]
                delta = 3
                target.mood += delta
                t.last_action = f"Work:soothe {target.name}"
                if VERBOSE_ACTIONS:
                    print(f"  [Work]  {t.name} (Echokeeper) soothes {target.name} mood +{delta} (now {target.mood})")
            else:
                t.last_action = "Work:soothe none"
                if VERBOSE_ACTIONS:
                    print(f"  [Work]  {t.name} (Echokeeper) finds no one to soothe")
            return

        if prof == "Merchant":
            needy_pool = [x for x in self.toons if x.needs_resource]
            self.rnd.shuffle(needy_pool)
            for needy in needy_pool:
                if self.merchant_deliver(t, needy):
                    t.last_action = f"Work:deliver to {needy.name}"
                    return
            t.last_action = "Work:no-trade"
            if VERBOSE_ACTIONS:
                print(f"  [Work]  {t.name} (Merchant) found no viable trade (stock {t.inv.items()}, credits {t.credits})")
            return

        # Knowledge/processors with recipes
        recs = PROFESSIONAL_RECIPES.get(prof, [])
        for inputs, outputs in recs:
            can = all(t.inv.qty(it) >= n for it, n in inputs.items())
            if can:
                for it, n in inputs.items():
                    t.consume_item(it, n)
                for ot, n in outputs.items():
                    t.last_action = f"Work:craft {ot}"
                    if VERBOSE_ACTIONS:
                        items_str = " + ".join([f"{n} {ot}" for ot, n in outputs.items()])
                        print(f"  [Work]  {t.name} ({prof}) crafts {items_str}")

                    t.add_item(ot, n)
                return

        if recs:
            needed_any = []
            for inputs, _ in recs:
                for it, n in inputs.items():
                    if t.inv.qty(it) < n:
                        needed_any.append(it)
            for it in needed_any:
                t.needs_resource.add(it)
            t.last_action = f"Work:needs {set(needed_any)}"
            if needed_any and VERBOSE_ACTIONS:
                print(f"  [Work]  {t.name} ({prof}) lacks {set(needed_any)} → needs_resource set")
        else:
            t.last_action = "Work:idle"
            if VERBOSE_ACTIONS:
                print(f"  [Work]  {t.name} ({prof}) has no defined recipe; idles")

    def do_interactive(self, t):
        candidates = self.sample_targets(10, exclude=t, must_not_done=True)
        if not candidates:
            t.last_action = "Social:none→self"
            if VERBOSE_ACTIONS:
                print(f"  [Social] {t.name} finds no available targets → fallback to self-focused")
            self.do_self_focused(t)
            return

        def rel_to(x):
            return t.relations.get(x.name, 0)

        target = max(candidates, key=lambda x: abs(rel_to(x)))

        label = "Compliment"
        spec = INTERACTIONS[label]
        if not spec["requires"](t):
            t.last_action = "Social:gate→self"
            if VERBOSE_ACTIONS:
                print(f"  [Social] {t.name} fails personality gate for {label} → fallback to self-focused")
            self.do_self_focused(t)
            return

        outcome_label = None
        for _ in range(5):
            outcomes = [(lab, wt) for (lab, wt, _) in spec["outcomes"]]
            pick = weighted_choice(outcomes)
            if spec["target_check"](target, pick):
                outcome_label = pick
                break
        if outcome_label is None:
            outcome_label = spec["outcomes"][0][0]

        eff = None
        for (lab, wt, effects) in spec["outcomes"]:
            if lab == outcome_label:
                eff = effects
                break

        t.last_action = f"Social:{label}->{outcome_label}@{target.name}"
        if VERBOSE_ACTIONS:
            print(f"  [Social] {t.name} → {target.name}: {label} → {outcome_label}")

        A_delta = eff.get("A_mood", 0)
        B_delta = eff.get("B_mood", 0)
        t.mood += A_delta
        target.mood += B_delta

        rel_delta = eff.get("rel", 0)
        t.add_relation(target.name, rel_delta)
        target.add_relation(t.name, rel_delta)

        drift = eff.get("drift")
        if drift:
            attr, d = drift
            if target.attr("Openness") >= 8 and target.attributes[attr] < 20:
                target.attributes[attr] += d
                if VERBOSE_ACTIONS:
                    print(f"      [Drift] {target.name} {attr} {('+' if d>0 else '')}{d} → {target.attributes[attr]}")

    # ======== ASCII Dashboard ========
    def needs_counter(self):
        counts = {}
        for t in self.toons:
            for need in t.needs_resource:
                counts[need] = counts.get(need, 0) + 1
        return counts

    def ascii_dashboard(self, c, minted_this_cycle):
        if not ASCII_DASHBOARD:
            return
        print("""
+==================== CHAIN-STATE DASHBOARD ====================+""")
        print(f"Cycle {c:03d}")
        # Blocks line
        print(f"Blocks {bar(self.blocks_total, max(10, self.blocks_total))}  total:{self.blocks_total}  (+{minted_this_cycle})")
        # Trades line
        print(f"Trades {bar(self.trades_this_cycle, max(10, self.trades_this_cycle))}  this cycle:{self.trades_this_cycle}")

        # Needs snapshot
        needz = self.needs_counter()
        if needz:
            pairs = sorted(needz.items(), key=lambda kv: (-kv[1], kv[0]))
            s = ", ".join([f"{k}:{v}" for k, v in pairs[:8]])
            print(f"Needs  {{ {s} }}")
        else:
            print("Needs  { none }")

        # Top toons by credits
        top = sorted(self.toons, key=lambda x: x.credits, reverse=True)[:DASHBOARD_TOP_N]
        print("""
Top Toons (by credits)""")
        print("NAME        PROF              E          C          M        $  Last Action")
        for t in top:
            e = bar(t.energy, BASE_ENERGY)
            ch = bar(t.charge, BASE_CHARGE)
            m = bar(t.mood, 200)  # mood can drift >100; cap vis at 200
            print(f"{short(t.name,10):10}  {short(t.profession,16):16}  {e}  {ch}  {m}  {t.credits:3d}  {short(t.last_action, 28)}")

        # Inventory histogram: top 8 items by total qty
        inv_totals = {}
        for t in self.toons:
            for it, q in t.inv.items().items():
                inv_totals[it] = inv_totals.get(it, 0) + q
        leaders = sorted(inv_totals.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
        if leaders:
            print("""
Inventory Leaders""")
            maxq = max(1, max(q for _, q in leaders))
            for k, v in leaders:
                print(f"{short(k,14):14} {bar(v, maxq)}  {v}")

        # Recent blocks (tail)
        tail = self.block_log[-8:]
        if tail:
            print("""
Recent Blocks:""")
            for line in tail:
                print("  ", line)
        print("+===============================================================+\n")

    # ======== One cycle ========
    def run_cycle(self, c):
        # Reset done flags & counters
        for t in self.toons:
            t.done = False
            t.last_action = "-"
        self.trades_this_cycle = 0

        # Shuffle execution order
        order = self.toons[:]
        self.rnd.shuffle(order)

        if VERBOSE_TICK:
            print(f"\n==== CYCLE {c:03d} ====")

        prev_blocks_total = self.blocks_total

        # Baseline energy/charge tick at cycle start
        for t in order:
            t.energy_tick()

        # Each toon acts (except merchants can target 'done' toons when trading)
        for t in order:
            if t.life <= 0:
                if VERBOSE_ACTIONS:
                    print(f"  [SKIP]  {t.name} is incapacitated (life<=0)")
                t.done = True
                continue

            if t.done:
                continue

            choice = weighted_choice(t.action_weights())

            if choice == "Self":
                self.do_self_focused(t)
            elif choice == "Professional":
                self.do_professional(t)
            else:
                self.do_interactive(t)

            t.done = True

            minted = t.try_mint_block(c)
            if minted:
                self.blocks_total += minted
                for _ in range( minted):
                    self.block_log.append(f"c{c:03d}_{t.name}_{t.profession}")

        minted_this_cycle = self.blocks_total - prev_blocks_total

        # End-of-cycle housekeeping Print compact summary
        if VERBOSE_TICK:
            top = sorted(self.toons, key=lambda x: x.credits, reverse=True)[:5]
            inv_totals = {}
            for t in self.toons:
                for it, q in t.inv.items().items():
                    inv_totals[it] = inv_totals.get(it, 0) + q

            print("---- End of Cycle Summary ----")
            # THIS IS THE CORRECTED LINE:
            print(f"Destinyblocks total so far: {self.blocks_total} (+{minted_this_cycle})")
            print("Top credits:")
            for x in top:
                print(f"  {x.name} ({x.profession}) -> {x.credits}")
            nonzero = [(k, v) for k, v in inv_totals.items() if v > 0]
            nonzero.sort(key=lambda kv: (-kv[1], kv[0]))
            if nonzero:
                print("Inventory totals (nonzero):")
                for k, v in nonzero:
                    print(f"  {k}: {v}")

        # ASCII Dashboard
        self.ascii_dashboard(c, minted_this_cycle)

    def run(self, cycles):
        for c in range(1, cycles + 1):
            self.run_cycle(c)


# =========================
# Entrypoint
# =========================
if __name__ == "__main__":
    world = World(seed=RNG_SEED)
    world.run(SIM_CYCLES)