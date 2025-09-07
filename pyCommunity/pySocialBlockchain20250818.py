# ===== Destinyblock Society Simulation (verbose edition; no external libs) =====
from dataclasses import dataclass, field
import random
from typing import Dict, List, Optional, Tuple

# ----------------------------- Config -----------------------------
VERBOSE_LEVEL = 2   # 0=quiet, 1=cycle summaries, 2=per-action + summaries
SEED = 42
CYCLES = 60

# ----------------------------- Constants -----------------------------
PROFESSIONS = [
    # Resource roles
    "Gatherer", "Miner", "Farmer", "Lumberjack", "Signalist", "Crawler",
    # Processing roles
    "Constructor", "Refiner", "Craftsman", "Echokeeper",
    # Knowledge roles
    "Cartographer", "Dreamweaver", "Digital Landscaper", "Cook", "Codehealer",
    # Support
    "Merchant",
]

# Items
SUBSTRATE = "Substrate"
TOOL = "Tool"
BUILDINGBITS = "Buildingbits"
MEALBITS = "Mealbits"
BEAD = "Bead"
JOULES = "Joules"
WOODBITS = "Woodbits"
PLANKBITS = "Plankbits"
SIGNALBITS = "Signalbits"
MAPBIT = "Mapbit"
BITNAPSE = "Bitnapse"
BUGS = "Bugs"
BUGPATCH = "Bugpatch"
ECHO = "Echo"

ALL_ITEMS = {
    SUBSTRATE, TOOL, BUILDINGBITS, MEALBITS, BEAD, JOULES, WOODBITS,
    PLANKBITS, SIGNALBITS, MAPBIT, BITNAPSE, BUGS, BUGPATCH, ECHO
}

# Profession recipes
PRO_RECIPES: Dict[str, List[Tuple[List[str], Optional[str]]]] = {
    "Gatherer": [ ([], JOULES) ],
    "Miner":    [ ([], SUBSTRATE) ],
    "Farmer":   [ ([], MEALBITS) ],
    "Lumberjack":[ ([], WOODBITS) ],
    "Signalist":[ ([], SIGNALBITS) ],
    "Crawler":  [ ([], BUGS) ],

    "Craftsman":[ ([SUBSTRATE], TOOL) ],
    "Refiner":  [ ([SUBSTRATE], None),           # Substrate -> +1 credit
                  ([WOODBITS], PLANKBITS) ],
    "Constructor":[ ([TOOL], BUILDINGBITS),
                    ([PLANKBITS], BUILDINGBITS) ],
    "Cook":     [ ([MEALBITS], BEAD) ],
    "Cartographer":[ ([SIGNALBITS], MAPBIT) ],
    "Dreamweaver":[ ([SIGNALBITS], BITNAPSE) ],
    "Codehealer":[ ([BUGS], BUGPATCH) ],
    "Echokeeper":[ ([SIGNALBITS], ECHO) ],
    "Digital Landscaper":[ ([BUILDINGBITS], None) ],  # mood buff
    "Merchant": []
}

ROLE_ATTRS: Dict[str, List[str]] = {
    "Miner": ["Strength", "Dedication"],
    "Lumberjack": ["Strength", "Industriousness", "Hacking"],
    "Farmer": ["Industriousness", "Harmony"],
    "Gatherer": ["Perception", "Speed"],
    "Signalist": ["Perception", "Intelligence"],
    "Crawler": ["Precision", "Speed"],

    "Craftsman": ["Technique", "Precision"],
    "Refiner": ["Industriousness", "Technique"],
    "Constructor": ["Logic", "Technique"],
    "Cook": ["Dedication", "Vision"],
    "Cartographer": ["Logic"],
    "Dreamweaver": ["Creativity", "Intelligence", "Hacking"],
    "Codehealer": ["Vision", "Intelligence"],
    "Echokeeper": ["Harmony"],
    "Digital Landscaper": ["Creativity", "Vision"],

    "Merchant": ["Agreeableness", "Extraversion"]
}

# -------------------------- Utility --------------------------
def clamp(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else hi if v > hi else v

def chance(p: float) -> bool:
    return random.random() < p

def weighted_choice(weights: List[Tuple[str, float]]) -> str:
    total = sum(w for _, w in weights)
    r = random.random() * total
    upto = 0.0
    for label, w in weights:
        upto += w
        if r <= upto:
            return label
    return weights[-1][0]

def attrib_score(attrs: Dict[str, int], names: List[str]) -> float:
    if not names:
        return 10.0
    return sum(attrs.get(n, 10) for n in names) / len(names)

# ----------------------------- Data -----------------------------
@dataclass
class Toon:
    name: str
    profession: str
    life: int = 100
    energy: int = 100
    battery: int = 100
    charge: int = 100
    mood: int = 100

    Stamina: int = 10
    Metabolism: int = 10
    Strength: int = 10
    Perception: int = 10
    Speed: int = 10
    Intelligence: int = 10
    Creativity: int = 10
    Logic: int = 10
    Technique: int = 10
    Dedication: int = 10
    Industriousness: int = 10
    Hacking: int = 10
    Harmony: int = 10
    Precision: int = 10
    Vision: int = 10

    Alignment: int = 10
    Openness: int = 10
    Conscientiousness: int = 10
    Extraversion: int = 10
    Agreeableness: int = 10
    Neuroticism: int = 10

    relationships: Dict[str, int] = field(default_factory=dict)
    inventory: Dict[str, int] = field(default_factory=dict)   # ≤3 item types
    credits: int = 0
    needs_resource: Optional[str] = None
    done: bool = False

    # Inventory
    def inventory_space_ok(self, item: str) -> bool:
        return (item in self.inventory) or (len(self.inventory) < 3)

    def add_item(self, item: str, qty: int = 1) -> bool:
        if not self.inventory_space_ok(item):
            return False
        self.inventory[item] = self.inventory.get(item, 0) + qty
        return True

    def has_item(self, item: str, qty: int = 1) -> bool:
        return self.inventory.get(item, 0) >= qty

    def remove_item(self, item: str, qty: int = 1) -> bool:
        if self.has_item(item, qty):
            self.inventory[item] -= qty
            if self.inventory[item] <= 0:
                del self.inventory[item]
            return True
        return False

    def add_relationship(self, other: str, delta: int):
        self.relationships[other] = self.relationships.get(other, 0) + delta

    # Vital mechanics
    def energy_consumption_per_cycle(self) -> int:
        return max(1, 21 - self.Metabolism)

    def charge_consumption_per_cycle(self) -> int:
        return max(1, 25 - self.Stamina)

    def tick_consumption(self):
        self.energy = max(0, self.energy - self.energy_consumption_per_cycle())
        self.charge = max(0, self.charge - self.charge_consumption_per_cycle())
        self.life = max(1, self.life - 1)
        self.battery = max(1, self.battery - 1)
        self.energy = min(self.energy, self.life)
        self.charge = min(self.charge, self.battery)

    def rest(self):
        self.charge = self.battery

    def eat(self):
        if self.remove_item(JOULES, 1):
            restored = 10
            self.energy = min(self.life, self.energy + restored)
            mood_delta = max(1, 4 - (self.Neuroticism // 6))
            self.mood = clamp(self.mood + mood_delta, 0, 200)
            return True
        return False

    def heal(self):
        if self.remove_item(BUGPATCH, 1):
            self.life = min(100, self.life + 10)
            self.energy = min(self.energy + 5, self.life)
            return True
        return False

    def train(self):
        trainables = [
            "Strength","Perception","Speed","Intelligence","Creativity","Logic",
            "Technique","Dedication","Industriousness","Hacking","Harmony",
            "Precision","Vision","Stamina","Metabolism"
        ]
        key = random.choice(trainables)
        p = 0.20 + (self.Openness - 10) * 0.015
        if chance(max(0.05, min(0.35, p))):
            val = getattr(self, key)
            setattr(self, key, clamp(val + 1, 1, 20))
        self.energy = max(0, self.energy - 5)
        self.charge = max(0, self.charge - 5)

    def pro_yield_bonus(self) -> int:
        avg = attrib_score(self.__dict__, ROLE_ATTRS.get(self.profession, []))
        return 1 if avg >= 14 else 0

# ---------------------- Interaction System ----------------------
class InteractionLib:
    @staticmethod
    def pick_interaction() -> str:
        return random.choice(["Compliment"])

    @staticmethod
    def can_do(name: str, actor: Toon) -> bool:
        if name == "Compliment":
            return actor.Extraversion > 10
        return True

    @staticmethod
    def do(name: str, actor: Toon, target: Toon) -> Tuple[bool,bool,str]:
        note = ""
        if name == "Compliment":
            outcomes = [
                ("Sincere Gratitude", 0.60),
                ("Awkward Response", 0.30),
                ("Suspicious Reaction", 0.05),
                ("Fart", 0.05),
            ]
            result = weighted_choice(outcomes)
            if result in ("Suspicious Reaction",) and target.Agreeableness > 12 and chance(0.6):
                result = "Awkward Response"
            if result == "Sincere Gratitude":
                actor.mood = clamp(actor.mood + 3, 0, 200)
                target.mood = clamp(target.mood + 5, 0, 200)
                if chance(0.30 + (actor.Agreeableness-10)*0.02):
                    target.Openness = clamp(target.Openness + 1, 1, 20)
                actor.add_relationship(target.name, +2)
                target.add_relationship(actor.name, +2)
            elif result == "Awkward Response":
                actor.mood = clamp(actor.mood + 1, 0, 200)
                target.mood = clamp(target.mood + 1, 0, 200)
                actor.add_relationship(target.name, +1)
                target.add_relationship(actor.name, +1)
            elif result == "Suspicious Reaction":
                swing = 2 + (actor.Neuroticism // 6)
                actor.mood = clamp(actor.mood - swing, 0, 200)
                target.mood = clamp(target.mood - 1, 0, 200)
                actor.add_relationship(target.name, -2)
                target.add_relationship(actor.name, -1)
            else:
                actor.mood = clamp(actor.mood + 2, 0, 200)
                target.mood = clamp(target.mood + 2, 0, 200)
                actor.add_relationship(target.name, +1)
                target.add_relationship(actor.name, +1)
            note = f"Interaction=Compliment outcome={result}"
        return True, True, note

# --------------------------- World ---------------------------
@dataclass
class DestinyBlock:
    height: int
    cycle: int
    who: str
    profession: str

class World:
    def __init__(self, seed: Optional[int] = None, verbose_level: int = 1):
        if seed is not None:
            random.seed(seed)
        self.toons: List[Toon] = []
        self.blocks: List[DestinyBlock] = []
        self.cycle: int = 0
        self.v = verbose_level
        self._next_id = 1
        # per-cycle trackers
        self.reset_trackers()

    # ---------- logging ----------
    def log(self, msg: str):
        if self.v >= 2:
            print(msg)

    def log_cycle(self, msg: str):
        if self.v >= 1:
            print(msg)

    def reset_trackers(self):
        self.trades = 0
        self.items_produced: Dict[str,int] = {}
        self.items_consumed: Dict[str,int] = {}
        self.prof_credits_delta: Dict[str,int] = {}

    def add_prod(self, item: str, qty: int):
        if item:
            self.items_produced[item] = self.items_produced.get(item, 0) + qty

    def add_cons(self, item: str, qty: int):
        if item:
            self.items_consumed[item] = self.items_consumed.get(item, 0) + qty

    # ---------- init ----------
    def create_population(self):
        for prof in professions_twice():
            name = self._gen_name()
            t = self._new_toon(name, prof)
            self.toons.append(t)

    def _gen_name(self) -> str:
        s = str(self._next_id).zfill(7)
        self._next_id += 1
        return "toon" + s

    def _new_toon(self, name: str, profession: str) -> Toon:
        def rattr():
            base = random.randint(6, 14)
            if chance(0.10): base += 2
            if chance(0.10): base -= 2
            return clamp(base, 1, 20)
        kwargs = {
            "Stamina": rattr(), "Metabolism": rattr(), "Strength": rattr(),
            "Perception": rattr(), "Speed": rattr(), "Intelligence": rattr(),
            "Creativity": rattr(), "Logic": rattr(), "Technique": rattr(),
            "Dedication": rattr(), "Industriousness": rattr(), "Hacking": rattr(),
            "Harmony": rattr(), "Precision": rattr(), "Vision": rattr(),
            "Alignment": clamp(random.randint(8, 12) + random.randint(-2, 2), 1, 20),
            "Openness": rattr(), "Conscientiousness": rattr(), "Extraversion": rattr(),
            "Agreeableness": rattr(), "Neuroticism": rattr(),
        }
        return Toon(name=name, profession=profession, **kwargs)

    # ---------- loop ----------
    def run(self, cycles: int = 50):
        for c in range(1, cycles + 1):
            self.cycle = c
            self.reset_trackers()
            self.log_cycle(f"\n=== Cycle {c} ===")

            # reset "done"
            for t in self.toons:
                t.done = False

            # act in random order
            order = self.toons[:]
            random.shuffle(order)
            if self.v >= 2:
                names = ", ".join(f"{t.name}:{t.profession}" for t in order)
                print(f"[order] {names}")

            for t in order:
                if t.done:
                    continue
                self._act(t)

            # maintenance & destinyblocks after all actions
            for t in self.toons:
                before = t.credits
                self._maybe_mint_block(t)
                t.tick_consumption()
                delta = t.credits - before
                if delta != 0:
                    self.prof_credits_delta[t.profession] = self.prof_credits_delta.get(t.profession, 0) + delta

            # end-of-cycle summary
            self._cycle_summary()

        # final summary
        self._final_summary()

    # ---------- actions ----------
    def _act(self, t: Toon):
        act_type = self._decide_action_type(t)
        if act_type == "Interactive":
            if not self._attempt_interactive(t):
                self.log(f"[{self.cycle}] {t.name}:{t.profession} INTERACT fallback -> Self")
                self._do_self_focused(t)
        elif act_type == "Professional":
            did = self._do_professional(t)
            if not did:
                self.log(f"[{self.cycle}] {t.name}:{t.profession} PRO lacked inputs -> needs={t.needs_resource} fallback Self")
                self._do_self_focused(t)
        else:
            self._do_self_focused(t)

    def _decide_action_type(self, t: Toon) -> str:
        base = 1.0
        w_self = base
        w_prof = base + (t.Conscientiousness - 10) * 0.12
        w_int  = base + (t.Extraversion - 10) * 0.12
        if t.mood < 60:
            w_self += 0.3
        w_self = max(0.1, w_self); w_prof = max(0.1, w_prof); w_int = max(0.1, w_int)
        choice = weighted_choice([("Self", w_self), ("Professional", w_prof), ("Interactive", w_int)])
        self.log(f"[{self.cycle}] {t.name}:{t.profession} choose={choice} mood={t.mood} E={t.energy}/{t.life} C={t.charge}/{t.battery} cr={t.credits} inv={dict(t.inventory)}")
        return choice

    # ----- self-focused -----
    def _do_self_focused(self, t: Toon):
        acted = False
        if t.energy <= max(5, t.life // 3) and t.has_item(JOULES, 1):
            acted = t.eat()
            self.log(f"[{self.cycle}] {t.name}:{t.profession} SELF eat +energy (Joules-1) -> E={t.energy}/{t.life}, mood={t.mood}")
        elif t.charge <= max(5, t.battery // 3):
            t.rest(); acted = True
            self.log(f"[{self.cycle}] {t.name}:{t.profession} SELF rest -> Charge={t.charge}/{t.battery}")
        elif t.life <= 70 and t.has_item(BUGPATCH, 1):
            acted = t.heal()
            self.log(f"[{self.cycle}] {t.name}:{t.profession} SELF heal (Bugpatch-1) -> Life={t.life}, Energy={t.energy}")
            self.add_cons(BUGPATCH, 1)
        else:
            before = (t.Stamina, t.Metabolism, t.Strength, t.Intelligence, t.Openness)
            t.train(); acted = True
            after = (t.Stamina, t.Metabolism, t.Strength, t.Intelligence, t.Openness)
            self.log(f"[{self.cycle}] {t.name}:{t.profession} SELF train -> attrs(before={before} after={after}) E={t.energy} C={t.charge}")
        t.done = True
        return acted

    # ----- professional -----
    def _do_professional(self, t: Toon) -> bool:
        if t.profession == "Merchant":
            did = self._merchant_trade(t)
            t.done = True
            return did

        recipes = PRO_RECIPES.get(t.profession, [])
        random.shuffle(recipes)

        for inputs, output in recipes:
            if not inputs:
                qty = 1 + t.pro_yield_bonus()
                if output and t.inventory_space_ok(output):
                    t.add_item(output, qty)
                    self.add_prod(output, qty)
                    self.log(f"[{self.cycle}] {t.name}:{t.profession} PRO produced {output} +{qty}")
                    t.done = True
                    return True
                continue

            need_ok = all(t.has_item(item, 1) for item in inputs)
            if need_ok:
                for item in inputs:
                    t.remove_item(item, 1)
                    self.add_cons(item, 1)

                if t.profession == "Refiner" and output is None:
                    before = t.credits
                    t.credits += 1
                    self.log(f"[{self.cycle}] {t.name}:{t.profession} PRO refine Substrate -> +1 credit (now {t.credits})")
                    delta = t.credits - before
                    if delta:
                        self.prof_credits_delta[t.profession] = self.prof_credits_delta.get(t.profession, 0) + delta
                    t.done = True
                    return True

                if t.profession == "Digital Landscaper" and output is None:
                    t.mood = clamp(t.mood + 3, 0, 200)
                    self.log(f"[{self.cycle}] {t.name}:{t.profession} PRO landscaped (Buildingbits-1) mood+3 -> {t.mood}")
                    t.done = True
                    return True

                qty = 1 + (1 if chance(0.15 + (attrib_score(t.__dict__, ROLE_ATTRS.get(t.profession, [])) - 10) * 0.03) else 0)
                if output and t.inventory_space_ok(output):
                    t.add_item(output, qty)
                    self.add_prod(output, qty)
                    self.log(f"[{self.cycle}] {t.name}:{t.profession} PRO crafted {output} +{qty} (consumed {inputs})")
                    t.done = True
                    return True
                else:
                    self.log(f"[{self.cycle}] {t.name}:{t.profession} PRO output {output} lost (no inv slot)")
                    continue

        if recipes:
            for inputs, output in recipes:
                for item in inputs:
                    if not t.has_item(item, 1):
                        t.needs_resource = item
                        break
                if t.needs_resource:
                    break
        return False

    def _merchant_trade(self, merchant: Toon) -> bool:
        candidates = [x for x in self.toons if (x.needs_resource is not None) and (x.name != merchant.name)]
        if not candidates:
            merchant.mood = clamp(merchant.mood + 1, 0, 200)
            self.log(f"[{self.cycle}] {merchant.name}:{merchant.profession} PRO no buyers; tidy inventory (mood={merchant.mood})")
            return False

        random.shuffle(candidates)
        for target in candidates:
            need = target.needs_resource
            if need and merchant.has_item(need, 1):
                if target.credits >= 1:
                    merchant.remove_item(need, 1)
                    target.credits -= 1
                    merchant.credits += 1
                    if target.inventory_space_ok(need):
                        target.add_item(need, 1)
                        target.needs_resource = None
                        self.trades += 1
                        self.log(f"[{self.cycle}] TRADE {merchant.name} -> {target.name}: {need} for 1 credit | merch_cr={merchant.credits} target_cr={target.credits}")
                        return True
                else:
                    self.log(f"[{self.cycle}] TRADE FAIL {merchant.name}->{target.name}: needs {need} but target has 0 credits")
        return False

    # ----- interactive -----
    def _attempt_interactive(self, actor: Toon) -> bool:
        others = [t for t in self.toons if (t.name != actor.name) and (not t.done)]
        if not others:
            return False
        sample = random.sample(others, min(10, len(others)))
        best = None
        best_score = -9999
        for cand in sample:
            rel = actor.relationships.get(cand.name, 0)
            score = abs(rel)
            if score > best_score:
                best = cand; best_score = score
        if best is None:
            best = random.choice(sample)

        name = InteractionLib.pick_interaction()
        if not InteractionLib.can_do(name, actor):
            return False

        _, _, note = InteractionLib.do(name, actor, best)
        self.log(f"[{self.cycle}] {actor.name}:{actor.profession} INTERACT with {best.name}:{best.profession} -> {note} | rel({actor.name}->{best.name})={actor.relationships.get(best.name,0)}")
        actor.done = True
        best.done = True
        return True

    # ----- destinyblocks -----
    def _maybe_mint_block(self, t: Toon):
        while t.credits >= 10:
            t.credits -= 10
            height = len(self.blocks) + 1
            b = DestinyBlock(height=height, cycle=self.cycle, who=t.name, profession=t.profession)
            self.blocks.append(b)
            print(f"{self.cycle}#{t.name}_{t.profession}")  # required ledger line

    # ----- summaries -----
    def _cycle_summary(self):
        # needs flags snapshot
        needs = {}
        for x in self.toons:
            if x.needs_resource:
                needs[x.needs_resource] = needs.get(x.needs_resource, 0) + 1

        if self.v >= 1:
            # compact item lines
            def fmt_items(d: Dict[str,int]) -> str:
                parts = [f"{k}:{v}" for k,v in sorted(d.items()) if v]
                return ", ".join(parts) if parts else "-"

            prof_cr = ", ".join(f"{k}:{v:+d}" for k,v in sorted(self.prof_credits_delta.items()) if v)
            self.log_cycle(f"[cycle {self.cycle} summary] trades={self.trades} creditsΔ[{prof_cr if prof_cr else '-'}] produced[{fmt_items(self.items_produced)}] consumed[{fmt_items(self.items_consumed)}] needs[{fmt_items(needs)}]")

    def _final_summary(self):
        print("\n==== Simulation Summary ====")
        print(f"Cycles: {self.cycle}")
        print(f"Destinyblocks: {len(self.blocks)}")
        richest = sorted(self.toons, key=lambda x: x.credits, reverse=True)[:5]
        print("Top credits:")
        for t in richest[:5]:
            print(f"  {t.name} ({t.profession}) -> {t.credits}")
        counts: Dict[str, int] = {k: 0 for k in ALL_ITEMS}
        for t in self.toons:
            for item, n in t.inventory.items():
                counts[item] = counts.get(item, 0) + n
        print("Inventory totals (nonzero):")
        for item, n in counts.items():
            if n:
                print(f"  {item}: {n}")

def professions_twice() -> List[str]:
    out = []
    for p in PROFESSIONS:
        out.append(p); out.append(p)
    return out

# ------------------------------ Runner ------------------------------
if __name__ == "__main__":
    random.seed(SEED)
    world = World(seed=SEED, verbose_level=VERBOSE_LEVEL)
    world.create_population()
    world.run(cycles=CYCLES)
