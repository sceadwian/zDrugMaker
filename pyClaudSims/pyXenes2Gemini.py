#!/usr/bin/env python3
"""
Dynasty Faction Simulator - starting prototype
Python 3, standard library only.

This is meant as a playable foundation, not a finished game.
It includes:
- 4 factions
- ruling families
- inherited traits and personality traits
- tile/resource economy
- council roles
- yearly political, adult, and child events
- births, deaths, aging
- simple NPC simulation
- final report written to a timestamped txt file

Run:
    python dynasty_faction_sim_start.py

Quick non-interactive smoke test:
    python dynasty_faction_sim_start.py --demo
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
import os
import random
import sys
from typing import Dict, List, Optional, Tuple


# -----------------------------
# Basic data
# -----------------------------

RESOURCE_NAMES = ["food", "wood", "stone", "iron", "gold", "herbs", "faith"]

INHERITED_TRAITS = [
    "intelligence",
    "strength",
    "fertility",
    "health",
    "charisma",
    "attractiveness",
    "aggression",
    "stability",
]

PERSONALITY_TRAITS = [
    "conscientiousness",
    "openness",
    "extraversion",
    "agreeableness",
    "neuroticism",
    "faith",
    "loyalty",
    "ambition",
    "discipline",
    "empathy",
    "deception",
    "political_skill",
    "prestige",
    "spying_ability",
    "wisdom",
    "confidence",
    "trustworthiness",
]

SKILLS = [
    "combat_skill",
    "stewardship",
    "diplomacy",
    "engineering",
    "commerce",
    "scholarship",
    "priesthood",
    "spymastery",
]

COUNCIL_ROLES = [
    "Marshal",
    "Steward",
    "Engineer",
    "Merchant",
    "Spymaster",
    "Diplomat",
    "Scholar",
    "High Priest",
    "Heir",
]

ROLE_PRIMARY_SKILL = {
    "Marshal": "combat_skill",
    "Steward": "stewardship",
    "Engineer": "engineering",
    "Merchant": "commerce",
    "Spymaster": "spymastery",
    "Diplomat": "diplomacy",
    "Scholar": "scholarship",
    "High Priest": "priesthood",
    "Heir": "political_skill",
}

RACE_CODES = {
    "Human": "H",
    "Naga": "N",
    "Birdpeople": "B",
    "Morfigo": "M",
    "Noffinoff": "F",
    "Konforme": "K",
}

CODE_TO_RACE = {v: k for k, v in RACE_CODES.items()}

RACE_BONUSES = {
    "Human": {"political_skill": 5, "stewardship": 5},
    "Naga": {"deception": 6, "spymastery": 5},
    "Birdpeople": {"openness": 6, "diplomacy": 5},
    "Morfigo": {"strength": 5, "combat_skill": 5},
    "Noffinoff": {"commerce": 7, "gold": 2},
    "Konforme": {"discipline": 6, "engineering": 5},
}

RELIGIONS = [
    "Faith of the Templars",
    "Didi Code",
    "Sand Creed",
    "Book of the Dead",
    "Pale Face",
    "Verdant Mother",
]

TILE_LIBRARY = {
    "Capital": {"food": 4, "wood": 2, "gold": 4, "defence": 4},
    "Grassland": {"food": 4, "defence": 0},
    "Forest": {"wood": 3, "food": 1, "defence": 0},
    "Hills": {"iron": 2, "stone": 1, "defence": 2},
    "Mountain": {"stone": 2, "gold": 1, "defence": 4},
    "Lake/River": {"food": 3, "defence": 1},
    "Plains": {"food": 3, "wood": 1, "defence": 0},
    "Swamp": {"herbs": 2, "defence": 2},
    "Desert": {"gold": 3, "defence": 1},
    "Holy Site": {"faith": 4, "defence": 1},
    "Farmland": {"food": 5, "defence": 0},
    "Volcano": {"stone": 2, "iron": 2, "defence": 2},
    "Ancient Ruins": {"faith": 2, "stone": 1, "defence": 1},
}

COMMON_TILES = [
    "Grassland",
    "Forest",
    "Hills",
    "Mountain",
    "Lake/River",
    "Plains",
    "Swamp",
    "Desert",
]

RARE_TILES = ["Holy Site", "Farmland", "Volcano", "Ancient Ruins"]

MALE_NAMES = [
    "Aldren", "Branik", "Cedric", "Dorian", "Eldric", "Faelan", "Gareth", "Hadrian",
    "Ivar", "Jorren", "Kael", "Lucan", "Merek", "Nolan", "Orin", "Perrin",
    "Quint", "Rovan", "Soren", "Tavian", "Ulric", "Veyran", "Wystan", "Yorick",
]

FEMALE_NAMES = [
    "Alyra", "Brenna", "Cerys", "Dahlia", "Elowen", "Freya", "Giselle", "Helena",
    "Isolde", "Jessa", "Kiera", "Liora", "Mira", "Nadia", "Ophelia", "Petra",
    "Quilla", "Rowena", "Selene", "Talia", "Una", "Vera", "Winra", "Ysara",
]

HOUSE_NAMES = ["Ashvale", "Nightsand", "Riverthorn", "Highmere", "Dawnspire", "Blackreed"]


# -----------------------------
# Utility functions
# -----------------------------


def clamp(value: int, low: int = 0, high: int = 99) -> int:
    return max(low, min(high, int(value)))


def roll(rng: random.Random, chance: float) -> bool:
    """chance is 0.0 to 1.0."""
    return rng.random() < chance


def stat_band(value: int) -> str:
    if value >= 80:
        return "excellent"
    if value >= 65:
        return "strong"
    if value >= 45:
        return "average"
    if value >= 30:
        return "weak"
    return "poor"


def weighted_choice(rng: random.Random, choices: List[Tuple[str, int]]) -> str:
    total = sum(weight for _, weight in choices)
    pick = rng.randint(1, total)
    running = 0
    for item, weight in choices:
        running += weight
        if pick <= running:
            return item
    return choices[-1][0]


def choose_from_menu(prompt: str, options: List[str], auto: bool = False, default_index: int = 0) -> int:
    """Return selected index."""
    if auto:
        print(f"{prompt} [auto: {options[default_index]}]")
        return default_index

    while True:
        print("\n" + prompt)
        for i, option in enumerate(options, start=1):
            print(f"  {i}. {option}")
        raw = input("Choose: ").strip()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return idx
        print("Invalid choice. Enter a number from the list.")


def pause(auto: bool = False) -> None:
    if not auto:
        input("\nPress Enter to continue...")


# -----------------------------
# Core classes
# -----------------------------


@dataclass
class Character:
    id: int
    name: str
    sex: str
    age: int
    genes: List[str]
    traits: Dict[str, int]
    skills: Dict[str, int]
    role: Optional[str] = None
    alive: bool = True
    spouse_id: Optional[int] = None
    children_ids: List[int] = field(default_factory=list)
    parents: Tuple[Optional[int], Optional[int]] = (None, None)
    cause_of_death: Optional[str] = None

    @property
    def race(self) -> str:
        counts: Dict[str, int] = {}
        for gene in self.genes:
            counts[gene] = counts.get(gene, 0) + 1
        # Tie-breaker: first gene wins, matching your plan.
        best_gene = self.genes[0]
        best_count = counts[best_gene]
        for gene in self.genes:
            if counts[gene] > best_count:
                best_gene = gene
                best_count = counts[gene]
        return CODE_TO_RACE.get(best_gene, "Unknown")

    @property
    def is_child(self) -> bool:
        return self.alive and self.age < 16

    @property
    def is_adult(self) -> bool:
        return self.alive and self.age >= 16

    def get_trait(self, name: str) -> int:
        return self.traits.get(name, 0)

    def get_skill(self, name: str) -> int:
        if name in self.skills:
            return self.skills[name]
        return self.traits.get(name, 0)

    def change_trait(self, name: str, amount: int) -> None:
        self.traits[name] = clamp(self.traits.get(name, 50) + amount)

    def change_skill(self, name: str, amount: int) -> None:
        self.skills[name] = clamp(self.skills.get(name, 20) + amount)

    def short_line(self) -> str:
        role = self.role if self.role else "No role"
        return f"{self.id}: {self.name}, {self.sex}, age {self.age}, {self.race}, {role}"

    def top_stats(self, n: int = 5) -> str:
        combined = {}
        combined.update(self.traits)
        combined.update(self.skills)
        top = sorted(combined.items(), key=lambda item: item[1], reverse=True)[:n]
        return ", ".join(f"{k} {v}" for k, v in top)


@dataclass
class Faction:
    name: str
    race: str
    religion: str
    characters: List[Character]
    tiles: List[str]
    resources: Dict[str, int]
    population: int
    political_points: int = 5
    piety: int = 0
    relations: Dict[str, int] = field(default_factory=dict)
    history: List[str] = field(default_factory=list)

    def living_characters(self) -> List[Character]:
        return [c for c in self.characters if c.alive]

    def living_adults(self) -> List[Character]:
        return [c for c in self.characters if c.is_adult]

    def children(self) -> List[Character]:
        return [c for c in self.characters if c.is_child]

    def character_by_id(self, character_id: Optional[int]) -> Optional[Character]:
        if character_id is None:
            return None
        for c in self.characters:
            if c.id == character_id:
                return c
        return None

    def ruler(self) -> Optional[Character]:
        rulers = [c for c in self.characters if c.alive and c.role == "King/Queen"]
        if rulers:
            return rulers[0]
        adults = self.living_adults()
        if adults:
            adults.sort(key=lambda c: (c.get_trait("prestige"), c.age), reverse=True)
            adults[0].role = "King/Queen"
            self.history.append(f"{adults[0].name} became ruler by necessity.")
            return adults[0]
        return None

    def role_holder(self, role: str) -> Optional[Character]:
        for c in self.characters:
            if c.alive and c.role == role:
                return c
        return None

    def add_history(self, year: int, text: str) -> None:
        self.history.append(f"Year {year}: {text}")

    def total_tile_defence(self) -> int:
        return sum(TILE_LIBRARY[t].get("defence", 0) for t in self.tiles)

    def summary(self) -> str:
        res = ", ".join(f"{r}:{self.resources.get(r, 0)}" for r in RESOURCE_NAMES)
        return (
            f"House {self.name} | {self.race} | {self.religion}\n"
            f"Population: {self.population} | Political points: {self.political_points} | Piety: {self.piety}\n"
            f"Tiles: {', '.join(self.tiles)}\n"
            f"Resources: {res}"
        )


@dataclass
class Game:
    year: int
    factions: List[Faction]
    player_index: int
    next_character_id: int
    max_years: int = 30
    auto: bool = False
    rng_seed: Optional[int] = None

    def rng(self) -> random.Random:
        # For normal play, keep using module-level randomness.
        # For demo, use a stable seed passed during creation.
        if not hasattr(self, "_rng"):
            self._rng = random.Random(self.rng_seed)
        return self._rng

    @property
    def player(self) -> Faction:
        return self.factions[self.player_index]

    def get_new_character_id(self) -> int:
        self.next_character_id += 1
        return self.next_character_id


# -----------------------------
# Character/faction generation
# -----------------------------


def random_stat(rng: random.Random, low: int = 25, high: int = 75) -> int:
    # Triangular distribution gives more middling characters and fewer extremes.
    return clamp(round(rng.triangular(low, high, 50)))


def apply_race_bonuses(character: Character) -> None:
    bonuses = RACE_BONUSES.get(character.race, {})
    for key, amount in bonuses.items():
        if key in character.traits:
            character.change_trait(key, amount)
        elif key in character.skills:
            character.change_skill(key, amount)


def make_genes_for_race(race: str) -> List[str]:
    code = RACE_CODES[race]
    return [code, code, code, code]


def inherit_genes(rng: random.Random, parent_a: Character, parent_b: Character) -> List[str]:
    # Two genes from each parent.
    return rng.sample(parent_a.genes, 2) + rng.sample(parent_b.genes, 2)


def make_character(
    rng: random.Random,
    character_id: int,
    name: str,
    sex: str,
    age: int,
    race: str,
    role: Optional[str] = None,
) -> Character:
    traits = {trait: random_stat(rng) for trait in INHERITED_TRAITS + PERSONALITY_TRAITS}
    skills = {skill: random_stat(rng, 10, 60) for skill in SKILLS}
    c = Character(
        id=character_id,
        name=name,
        sex=sex,
        age=age,
        genes=make_genes_for_race(race),
        traits=traits,
        skills=skills,
        role=role,
    )
    apply_race_bonuses(c)
    return c


def inherited_value(rng: random.Random, a: int, b: int) -> int:
    # Average of parents, plus random variation.
    return clamp(round((a + b) / 2 + rng.randint(-12, 12)))


def make_child(
    game: Game,
    faction: Faction,
    mother: Character,
    father: Character,
    age: int = 0,
) -> Character:
    rng = game.rng()
    sex = "F" if roll(rng, 0.5) else "M"
    name = rng.choice(FEMALE_NAMES if sex == "F" else MALE_NAMES)
    traits: Dict[str, int] = {}
    skills: Dict[str, int] = {}

    for trait in INHERITED_TRAITS:
        traits[trait] = inherited_value(rng, mother.get_trait(trait), father.get_trait(trait))

    # Personality starts semi-random, nudged by parents but less directly inherited.
    for trait in PERSONALITY_TRAITS:
        parent_mean = round((mother.get_trait(trait) + father.get_trait(trait)) / 2)
        random_component = random_stat(rng, 20, 80)
        traits[trait] = clamp(round(parent_mean * 0.35 + random_component * 0.65 + rng.randint(-8, 8)))

    # Children start with low skills.
    for skill in SKILLS:
        skills[skill] = clamp(rng.randint(0, 20) + traits.get("intelligence", 50) // 10)

    child = Character(
        id=game.get_new_character_id(),
        name=name,
        sex=sex,
        age=age,
        genes=inherit_genes(rng, mother, father),
        traits=traits,
        skills=skills,
        parents=(mother.id, father.id),
    )
    apply_race_bonuses(child)
    mother.children_ids.append(child.id)
    father.children_ids.append(child.id)
    faction.characters.append(child)
    faction.add_history(game.year, f"{mother.name} and {father.name} had a child: {child.name}.")
    return child


def make_starting_family(rng: random.Random, race: str, id_start: int) -> Tuple[List[Character], int]:
    next_id = id_start

    def new_id() -> int:
        nonlocal next_id
        next_id += 1
        return next_id

    king = make_character(rng, new_id(), rng.choice(MALE_NAMES), "M", 30, race, role="King/Queen")
    queen = make_character(rng, new_id(), rng.choice(FEMALE_NAMES), "F", 30, race, role=None)
    king.spouse_id = queen.id
    queen.spouse_id = king.id

    daughter1 = make_character(rng, new_id(), rng.choice(FEMALE_NAMES), "F", 3, race)
    son1 = make_character(rng, new_id(), rng.choice(MALE_NAMES), "M", 9, race)
    son2 = make_character(rng, new_id(), rng.choice(MALE_NAMES), "M", 11, race)
    daughter2 = make_character(rng, new_id(), rng.choice(FEMALE_NAMES), "F", 13, race)

    for child in [daughter1, son1, son2, daughter2]:
        child.parents = (queen.id, king.id)
        queen.children_ids.append(child.id)
        king.children_ids.append(child.id)

    return [king, queen, daughter1, son1, son2, daughter2], next_id


def random_tiles(rng: random.Random) -> List[str]:
    tiles = ["Capital"]
    for _ in range(5):
        if roll(rng, 0.12):
            tiles.append(rng.choice(RARE_TILES))
        else:
            tiles.append(rng.choice(COMMON_TILES))
    return tiles


def make_faction(rng: random.Random, name: str, race: str, religion: str, id_start: int) -> Tuple[Faction, int]:
    family, next_id = make_starting_family(rng, race, id_start)
    resources = {r: 0 for r in RESOURCE_NAMES}
    resources.update({"food": 25, "wood": 12, "stone": 8, "iron": 6, "gold": 12, "herbs": 2, "faith": 0})
    faction = Faction(
        name=name,
        race=race,
        religion=religion,
        characters=family,
        tiles=random_tiles(rng),
        resources=resources,
        population=8,
        political_points=5,
        piety=0,
    )
    return faction, next_id


def create_new_game(auto: bool = False) -> Game:
    seed = 7 if auto else None
    rng = random.Random(seed)
    races = list(RACE_CODES.keys())
    religions = RELIGIONS[:]
    rng.shuffle(races)
    rng.shuffle(religions)

    next_id = 0
    factions: List[Faction] = []
    for i in range(4):
        faction, next_id = make_faction(
            rng,
            name=HOUSE_NAMES[i],
            race=races[i],
            religion=religions[i],
            id_start=next_id,
        )
        factions.append(faction)

    # Initialize relations.
    for faction in factions:
        for other in factions:
            if faction.name == other.name:
                continue
            base = 0
            if faction.religion == other.religion:
                base += 15
            if faction.race == other.race:
                base += 8
            faction.relations[other.name] = base

    game = Game(
        year=1,
        factions=factions,
        player_index=0,
        next_character_id=next_id,
        max_years=30,
        auto=auto,
        rng_seed=seed,
    )
    return game


# -----------------------------
# Display helpers
# -----------------------------


def print_banner(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def print_faction_status(faction: Faction) -> None:
    print_banner(f"House {faction.name}")
    print(faction.summary())
    print("\nCouncil and family:")
    for c in faction.living_characters():
        print(f"  {c.short_line()} | top: {c.top_stats(3)}")


def print_relations(game: Game, faction: Faction) -> None:
    print("\nRelations:")
    for other_name, value in sorted(faction.relations.items()):
        print(f"  {other_name}: {value}")


# -----------------------------
# Council management
# -----------------------------


def auto_assign_roles(faction: Faction) -> None:
    # Preserve ruler. Clear all other council roles.
    for c in faction.characters:
        if c.role != "King/Queen":
            c.role = None

    adults = [c for c in faction.living_adults() if c.role != "King/Queen"]
    used_ids = set()
    for role in COUNCIL_ROLES:
        skill = ROLE_PRIMARY_SKILL[role]
        candidates = [c for c in adults if c.id not in used_ids]
        if not candidates:
            break
        best = max(candidates, key=lambda c: c.get_skill(skill))
        best.role = role
        used_ids.add(best.id)


def manage_council(faction: Faction, auto: bool = False) -> None:
    if auto:
        auto_assign_roles(faction)
        return

    while True:
        print_banner("Council Management")
        print("Current roles:")
        ruler = faction.ruler()
        if ruler:
            print(f"  King/Queen: {ruler.name}")
        for role in COUNCIL_ROLES:
            holder = faction.role_holder(role)
            print(f"  {role}: {holder.name if holder else '-'}")

        options = ["Assign/change a role", "Clear a role", "Done"]
        choice = choose_from_menu("What do you want to do?", options, auto=False)
        if choice == 2:
            return

        if choice == 0:
            role_idx = choose_from_menu("Choose role:", COUNCIL_ROLES, auto=False)
            role = COUNCIL_ROLES[role_idx]
            adults = [c for c in faction.living_adults() if c.role != "King/Queen"]
            if not adults:
                print("No available adults.")
                pause()
                continue
            print("\nAvailable adults:")
            for c in adults:
                primary = ROLE_PRIMARY_SKILL[role]
                print(f"  {c.id}. {c.name}, age {c.age}, current role: {c.role or '-'}, {primary}: {c.get_skill(primary)}")
            raw = input("Enter character ID: ").strip()
            if not raw.isdigit():
                print("Invalid ID.")
                pause()
                continue
            char = faction.character_by_id(int(raw))
            if not char or not char.is_adult or char.role == "King/Queen":
                print("That character cannot take this role.")
                pause()
                continue
            # Clear same role from current holder and old role from selected character.
            for c in faction.characters:
                if c.role == role:
                    c.role = None
            char.role = role
            print(f"Assigned {char.name} as {role}.")
            pause()

        elif choice == 1:
            role_idx = choose_from_menu("Clear which role?", COUNCIL_ROLES, auto=False)
            role = COUNCIL_ROLES[role_idx]
            holder = faction.role_holder(role)
            if holder:
                holder.role = None
                print(f"Cleared {role}.")
            else:
                print("That role is already empty.")
            pause()


# -----------------------------
# Economy and yearly mechanics
# -----------------------------


def role_bonus(faction: Faction, role: str, divisor: int = 20) -> int:
    holder = faction.role_holder(role)
    if not holder:
        return 0
    skill_name = ROLE_PRIMARY_SKILL[role]
    return max(1, holder.get_skill(skill_name) // divisor)


def produce_resources(game: Game, faction: Faction) -> None:
    produced = {r: 0 for r in RESOURCE_NAMES}
    for tile in faction.tiles:
        data = TILE_LIBRARY[tile]
        for resource in RESOURCE_NAMES:
            produced[resource] += data.get(resource, 0)

    # Council bonuses.
    produced["food"] += role_bonus(faction, "Steward")
    engineer_bonus = role_bonus(faction, "Engineer", divisor=25)
    produced["wood"] += engineer_bonus
    produced["stone"] += engineer_bonus
    produced["gold"] += role_bonus(faction, "Merchant")
    produced["faith"] += role_bonus(faction, "High Priest")

    # Noffinoff racial faction flavour: extra gold if ruler is Noffinoff.
    ruler = faction.ruler()
    if ruler and ruler.race == "Noffinoff":
        produced["gold"] += 2

    for resource, amount in produced.items():
        faction.resources[resource] = faction.resources.get(resource, 0) + amount

    # Food consumption.
    faction.resources["food"] -= faction.population
    if faction.resources["food"] < 0:
        shortage = abs(faction.resources["food"])
        deaths = max(1, shortage // 2)
        faction.population = max(1, faction.population - deaths)
        faction.resources["food"] = 0
        faction.add_history(game.year, f"Food shortage killed {deaths} population.")
    else:
        # Surplus food can increase population gradually.
        if faction.resources["food"] >= 15 and roll(game.rng(), 0.35):
            faction.population += 1
            faction.resources["food"] -= 5
            faction.add_history(game.year, "Food surplus increased population by 1.")

    faction.resources["faith"] = max(0, faction.resources.get("faith", 0))
    faction.piety += faction.resources["faith"]
    faction.political_points += 1 + role_bonus(faction, "Diplomat", divisor=35)


def age_and_mortality(game: Game, faction: Faction) -> None:
    rng = game.rng()
    for c in list(faction.living_characters()):
        c.age += 1

        # Skill growth from assigned role.
        if c.role and c.role in ROLE_PRIMARY_SKILL:
            skill = ROLE_PRIMARY_SKILL[c.role]
            gain = 1
            if c.get_trait("discipline") >= 65:
                gain += 1
            if c.get_trait("intelligence") >= 70 and roll(rng, 0.4):
                gain += 1
            c.change_skill(skill, gain)
            c.change_trait("prestige", 1)

        # Death chance by age and health.
        health = c.get_trait("health")
        if c.age < 50:
            death_chance = 0.002
        elif c.age < 65:
            death_chance = 0.015
        elif c.age < 75:
            death_chance = 0.045
        else:
            death_chance = 0.10
        death_chance *= max(0.25, (100 - health) / 50)

        if roll(rng, death_chance):
            c.alive = False
            c.cause_of_death = "natural causes"
            faction.add_history(game.year, f"{c.name} died of natural causes at age {c.age}.")

    # Succession check.
    ruler = faction.ruler()
    if ruler is None:
        faction.add_history(game.year, "The ruling house has no adult ruler. The faction is collapsing.")


def marriage_and_births(game: Game, faction: Faction) -> None:
    rng = game.rng()
    # Starter system: existing married couples may have children.
    checked_pairs = set()
    for a in faction.living_adults():
        if a.spouse_id is None:
            continue
        b = faction.character_by_id(a.spouse_id)
        if not b or not b.alive or not b.is_adult:
            continue
        pair = tuple(sorted([a.id, b.id]))
        if pair in checked_pairs:
            continue
        checked_pairs.add(pair)

        female = a if a.sex == "F" else b if b.sex == "F" else None
        male = a if a.sex == "M" else b if b.sex == "M" else None
        if not female or not male:
            continue
        if female.age < 16 or female.age > 44:
            continue

        chance = 0.50 * (male.get_trait("fertility") / 50) * (female.get_trait("fertility") / 50)
        chance = max(0.02, min(0.55, chance))
        # Too many children lowers annual chance.
        chance *= max(0.25, 1.0 - len(female.children_ids) * 0.08)
        if roll(rng, chance):
            make_child(game, faction, mother=female, father=male, age=0)


# -----------------------------
# Event system
# -----------------------------


def child_event(game: Game, faction: Faction, child: Character) -> None:
    rng = game.rng()
    event = rng.choice([
        "friend",
        "nightmare",
        "hurt_critter",
        "sibling_help",
        "talent",
        "humiliation",
        "forbidden_curiosity",
        "illness",
        "river",
    ])

    print_banner(f"Child Event: {child.name}, age {child.age}")

    if event == "friend":
        idx = choose_from_menu(
            f"{child.name} makes a new friend among the children of the court.",
            [
                "Encourage the friendship.",
                "Warn the child not to trust too easily.",
                "Turn it into a lesson in diplomacy.",
            ],
            auto=game.auto,
        )
        if idx == 0:
            child.change_trait("extraversion", 3)
            child.change_trait("trustworthiness", 2)
            child.change_trait("loyalty", 1)
            result = f"{child.name} became warmer and more trusting."
        elif idx == 1:
            child.change_trait("deception", 2)
            child.change_trait("trustworthiness", -2)
            child.change_trait("confidence", 1)
            result = f"{child.name} became more guarded."
        else:
            child.change_skill("diplomacy", 3)
            child.change_trait("charisma", 1)
            result = f"{child.name} learned an early diplomatic lesson."

    elif event == "nightmare":
        idx = choose_from_menu(
            f"{child.name} wakes from repeated nightmares.",
            [
                "Comfort the child personally.",
                "Ask the High Priest to interpret the dream.",
                "Tell the child fear must be mastered.",
            ],
            auto=game.auto,
        )
        if idx == 0:
            child.change_trait("stability", 2)
            child.change_trait("loyalty", 2)
            result = f"{child.name} felt protected by family."
        elif idx == 1:
            priest = faction.role_holder("High Priest")
            child.change_trait("faith", 3 if priest else 1)
            child.change_trait("neuroticism", -1 if priest else 1)
            result = f"{child.name} became more spiritually sensitive."
        else:
            child.change_trait("discipline", 3)
            child.change_trait("neuroticism", 2)
            result = f"{child.name} learned discipline, but became more tense."

    elif event == "hurt_critter":
        idx = choose_from_menu(
            f"{child.name} finds a wounded animal near the kitchens.",
            [
                "Teach mercy and help the creature.",
                "Use it as a lesson about survival.",
                "Ignore it; noble children need harder concerns.",
            ],
            auto=game.auto,
        )
        if idx == 0:
            child.change_trait("empathy", 4)
            child.change_trait("agreeableness", 2)
            result = f"{child.name} grew more compassionate."
        elif idx == 1:
            child.change_trait("wisdom", 2)
            child.change_trait("stability", 1)
            child.change_trait("empathy", -1)
            result = f"{child.name} learned a hard practical lesson."
        else:
            child.change_trait("empathy", -3)
            child.change_trait("aggression", 1)
            result = f"{child.name} became slightly colder."

    elif event == "sibling_help":
        idx = choose_from_menu(
            f"{child.name} sees a sibling struggling with lessons.",
            [
                "Encourage helping the sibling.",
                "Push competition between them.",
                "Ask the Scholar to tutor both.",
            ],
            auto=game.auto,
        )
        if idx == 0:
            child.change_trait("loyalty", 3)
            child.change_trait("empathy", 2)
            result = f"{child.name} strengthened family bonds."
        elif idx == 1:
            child.change_trait("ambition", 3)
            child.change_trait("aggression", 2)
            child.change_trait("loyalty", -1)
            result = f"{child.name} became more competitive."
        else:
            scholar = faction.role_holder("Scholar")
            bonus = 4 if scholar else 1
            child.change_skill("scholarship", bonus)
            child.change_trait("intelligence", 1)
            result = f"{child.name} benefited from structured tutoring."

    elif event == "talent":
        talent = rng.choice(SKILLS)
        idx = choose_from_menu(
            f"A courtier notices {child.name} has unusual promise in {talent}.",
            [
                "Invest in training.",
                "Praise the child publicly.",
                "Keep expectations modest.",
            ],
            auto=game.auto,
        )
        if idx == 0:
            cost = 2
            if faction.resources["gold"] >= cost:
                faction.resources["gold"] -= cost
                child.change_skill(talent, 6)
                result = f"Training improved {child.name}'s {talent}."
            else:
                child.change_skill(talent, 2)
                result = f"With little gold available, training was limited."
        elif idx == 1:
            child.change_trait("confidence", 4)
            child.change_trait("ambition", 2)
            result = f"{child.name} became more confident."
        else:
            child.change_trait("discipline", 2)
            child.change_trait("neuroticism", -1)
            result = f"{child.name} stayed grounded."

    elif event == "humiliation":
        idx = choose_from_menu(
            f"{child.name} is publicly humiliated by another noble child.",
            [
                "Tell the child to endure it.",
                "Demand punishment.",
                "Use it as a political lesson.",
            ],
            auto=game.auto,
        )
        if idx == 0:
            child.change_trait("stability", 2)
            child.change_trait("confidence", -1)
            result = f"{child.name} endured the shame."
        elif idx == 1:
            child.change_trait("aggression", 3)
            child.change_trait("loyalty", 1)
            faction.political_points = max(0, faction.political_points - 1)
            result = f"The family defended {child.name}, but spent political capital."
        else:
            child.change_trait("political_skill", 3)
            child.change_trait("deception", 1)
            result = f"{child.name} learned that status is a weapon."

    elif event == "forbidden_curiosity":
        idx = choose_from_menu(
            f"{child.name} is caught reading forbidden material from the archives.",
            [
                "Punish the disobedience.",
                "Encourage curiosity under supervision.",
                "Give the book to the High Priest.",
            ],
            auto=game.auto,
        )
        if idx == 0:
            child.change_trait("discipline", 3)
            child.change_trait("openness", -2)
            result = f"{child.name} became more obedient but less curious."
        elif idx == 1:
            child.change_trait("openness", 4)
            child.change_skill("scholarship", 3)
            child.change_trait("discipline", -1)
            result = f"{child.name}'s curiosity deepened."
        else:
            child.change_trait("faith", 2)
            faction.piety += 2
            result = f"The matter became a religious lesson."

    elif event == "illness":
        idx = choose_from_menu(
            f"{child.name} suffers a childhood illness.",
            [
                "Use herbs and careful rest.",
                "Pray for recovery.",
                "Let the body fight naturally.",
            ],
            auto=game.auto,
        )
        survival = child.get_trait("health") / 120
        if idx == 0 and faction.resources["herbs"] > 0:
            faction.resources["herbs"] -= 1
            survival += 0.25
        elif idx == 1:
            survival += min(0.20, faction.piety / 500)
            faction.piety = max(0, faction.piety - 5)
        else:
            child.change_trait("stability", 1)
        if roll(rng, survival):
            child.change_trait("health", -2)
            child.change_trait("stability", 2)
            result = f"{child.name} survived the illness."
        else:
            child.alive = False
            child.cause_of_death = "childhood illness"
            result = f"{child.name} died from the illness."

    else:  # river
        idx = choose_from_menu(
            f"{child.name} falls into a river during play.",
            [
                "Reward the rescuer and teach caution.",
                "Train the child physically after recovery.",
                "Blame the servants for negligence.",
            ],
            auto=game.auto,
        )
        danger = 0.20 - child.get_trait("health") / 500
        if roll(rng, danger):
            child.alive = False
            child.cause_of_death = "river accident"
            result = f"{child.name} drowned in the river."
        else:
            if idx == 0:
                child.change_trait("wisdom", 2)
                child.change_trait("stability", 1)
            elif idx == 1:
                child.change_trait("strength", 2)
                child.change_skill("combat_skill", 1)
            else:
                child.change_trait("trustworthiness", -2)
                child.change_trait("political_skill", 1)
            result = f"{child.name} survived the accident."

    print("\nResult:", result)
    faction.add_history(game.year, result)
    pause(game.auto)


def adult_event(game: Game, faction: Faction, adult: Character) -> None:
    rng = game.rng()
    event = rng.choice([
        "illness",
        "prayer",
        "temptation",
        "duel",
        "secret",
        "romance",
        "faith_crisis",
        "training",
    ])

    print_banner(f"Adult Event: {adult.name}, age {adult.age}")

    if event == "illness":
        idx = choose_from_menu(
            f"{adult.name} becomes ill.",
            ["Use herbs.", "Pray for recovery.", "Do nothing expensive."],
            auto=game.auto,
        )
        recovery = adult.get_trait("health") / 120
        if idx == 0 and faction.resources["herbs"] > 0:
            faction.resources["herbs"] -= 1
            recovery += 0.25
        elif idx == 1:
            recovery += min(0.20, faction.piety / 600)
            faction.piety = max(0, faction.piety - 5)
        if roll(rng, recovery):
            adult.change_trait("health", -2)
            result = f"{adult.name} recovered, but health declined slightly."
        else:
            adult.alive = False
            adult.cause_of_death = "illness"
            result = f"{adult.name} died from illness."

    elif event == "prayer":
        idx = choose_from_menu(
            f"{adult.name} asks the gods for guidance.",
            ["Pray for food.", "Pray for courage.", "Pray for a child.", "Forbid wasteful superstition."],
            auto=game.auto,
        )
        faith_score = adult.get_trait("faith") + role_bonus(faction, "High Priest", divisor=10)
        success = min(0.65, faith_score / 140 + faction.piety / 1000)
        faction.piety = max(0, faction.piety - 10)
        if idx == 0 and roll(rng, success):
            faction.resources["food"] += 8
            result = "A food blessing was believed to have arrived."
        elif idx == 1 and roll(rng, success):
            adult.change_trait("confidence", 5)
            adult.change_trait("stability", 2)
            result = f"{adult.name} felt strengthened by divine courage."
        elif idx == 2 and roll(rng, success):
            adult.change_trait("fertility", 5)
            result = f"{adult.name} felt blessed with fertility."
        elif idx == 3:
            adult.change_trait("faith", -3)
            faction.political_points += 1
            result = f"{adult.name} rejected the prayer and focused on politics."
        else:
            adult.change_trait("faith", 1)
            result = "No clear miracle occurred, but faith deepened."

    elif event == "temptation":
        idx = choose_from_menu(
            f"{adult.name} is offered a corrupt bargain by a wealthy trader.",
            ["Accept the gold quietly.", "Refuse and expose the trader.", "Use the trader as an informant."],
            auto=game.auto,
        )
        if idx == 0:
            faction.resources["gold"] += 8
            adult.change_trait("deception", 3)
            adult.change_trait("trustworthiness", -4)
            result = f"{adult.name} accepted corruption. Gold increased, trust declined."
        elif idx == 1:
            adult.change_trait("trustworthiness", 4)
            adult.change_trait("prestige", 2)
            faction.political_points += 1
            result = f"{adult.name} gained prestige for refusing corruption."
        else:
            adult.change_skill("spymastery", 3)
            adult.change_trait("deception", 2)
            result = f"{adult.name} turned corruption into intelligence."

    elif event == "duel":
        idx = choose_from_menu(
            f"{adult.name} is challenged to a duel after a feast insult.",
            ["Accept the duel.", "Send the Marshal as champion.", "Defuse the insult diplomatically."],
            auto=game.auto,
        )
        if idx == 0:
            score = adult.get_skill("combat_skill") + adult.get_trait("strength") + rng.randint(-40, 40)
            if score >= 100:
                adult.change_trait("prestige", 5)
                result = f"{adult.name} won the duel and gained prestige."
            else:
                adult.change_trait("health", -8)
                adult.change_trait("confidence", -2)
                result = f"{adult.name} was wounded in the duel."
        elif idx == 1:
            marshal = faction.role_holder("Marshal")
            if marshal:
                score = marshal.get_skill("combat_skill") + marshal.get_trait("strength") + rng.randint(-35, 35)
                if score >= 100:
                    marshal.change_trait("prestige", 4)
                    result = f"{marshal.name} won as champion."
                else:
                    marshal.change_trait("health", -10)
                    result = f"{marshal.name} was wounded as champion."
            else:
                adult.change_trait("prestige", -2)
                result = "There was no Marshal to serve as champion. Prestige suffered."
        else:
            adult.change_skill("diplomacy", 3)
            adult.change_trait("stability", 1)
            result = f"{adult.name} defused the conflict diplomatically."

    elif event == "secret":
        idx = choose_from_menu(
            f"{adult.name} discovers a private secret about another courtier.",
            ["Blackmail them.", "Destroy the evidence.", "Give it to the Spymaster."],
            auto=game.auto,
        )
        if idx == 0:
            faction.political_points += 3
            adult.change_trait("deception", 3)
            adult.change_trait("trustworthiness", -2)
            result = f"{adult.name} gained political leverage through blackmail."
        elif idx == 1:
            adult.change_trait("trustworthiness", 3)
            adult.change_trait("empathy", 2)
            result = f"{adult.name} chose mercy and became more trusted."
        else:
            spy = faction.role_holder("Spymaster")
            if spy:
                spy.change_skill("spymastery", 3)
                faction.political_points += 1
                result = f"{spy.name} turned the secret into intelligence."
            else:
                adult.change_skill("spymastery", 1)
                result = "With no Spymaster, the secret had limited value."

    elif event == "romance":
        if adult.spouse_id is None:
            adult.change_trait("happiness" if "happiness" in adult.traits else "confidence", 2)
            adult.change_trait("attractiveness", 1)
            result = f"{adult.name} becomes the subject of courtly romantic attention."
        else:
            idx = choose_from_menu(
                f"{adult.name} is tempted into infidelity.",
                ["Resist temptation.", "Pursue the affair.", "Confess to spouse."],
                auto=game.auto,
            )
            if idx == 0:
                adult.change_trait("discipline", 3)
                adult.change_trait("trustworthiness", 2)
                result = f"{adult.name} resisted temptation."
            elif idx == 1:
                adult.change_trait("deception", 3)
                adult.change_trait("trustworthiness", -5)
                adult.change_trait("stability", -1)
                result = f"{adult.name} began a dangerous affair."
            else:
                adult.change_trait("trustworthiness", 2)
                adult.change_trait("stability", -2)
                result = f"{adult.name} confessed and the household was shaken."

    elif event == "faith_crisis":
        idx = choose_from_menu(
            f"{adult.name} suffers a crisis of faith.",
            ["Seek counsel from the High Priest.", "Let doubt sharpen wisdom.", "Suppress the doubts publicly."],
            auto=game.auto,
        )
        if idx == 0:
            priest = faction.role_holder("High Priest")
            adult.change_trait("faith", 4 if priest else 1)
            adult.change_trait("stability", 1)
            result = f"{adult.name} found religious reassurance."
        elif idx == 1:
            adult.change_trait("wisdom", 4)
            adult.change_trait("faith", -2)
            result = f"{adult.name} became wiser but less certain."
        else:
            adult.change_trait("deception", 2)
            adult.change_trait("faith", -1)
            faction.political_points += 1
            result = f"{adult.name} hid the crisis for political stability."

    else:  # training
        if adult.role and adult.role in ROLE_PRIMARY_SKILL:
            skill = ROLE_PRIMARY_SKILL[adult.role]
        else:
            skill = rng.choice(SKILLS)
        idx = choose_from_menu(
            f"{adult.name} has an opportunity for serious training in {skill}.",
            ["Pay for expert training.", "Self-train through discipline.", "Ignore it."],
            auto=game.auto,
        )
        if idx == 0 and faction.resources["gold"] >= 3:
            faction.resources["gold"] -= 3
            adult.change_skill(skill, 6)
            result = f"{adult.name}'s {skill} improved significantly."
        elif idx == 1:
            gain = 3 if adult.get_trait("discipline") >= 55 else 1
            adult.change_skill(skill, gain)
            adult.change_trait("discipline", 1)
            result = f"{adult.name} improved through self-training."
        else:
            result = f"{adult.name} ignored the training opportunity."

    print("\nResult:", result)
    faction.add_history(game.year, result)
    pause(game.auto)


def political_event(game: Game, faction: Faction) -> None:
    rng = game.rng()
    rivals = [f for f in game.factions if f.name != faction.name]
    other = rng.choice(rivals)
    event = rng.choice([
        "border_dispute",
        "insult",
        "aid_request",
        "trade_envoy",
        "religious_pressure",
        "raid_opportunity",
    ])

    print_banner("Political Event")

    if event == "border_dispute":
        idx = choose_from_menu(
            f"House {other.name} claims one of your border tiles.",
            [
                "Ignore the claim.",
                "Spend political points to negotiate.",
                "Send the Marshal to threaten them.",
                "Prepare for war.",
            ],
            auto=game.auto,
        )
        if idx == 0:
            faction.relations[other.name] -= 5
            result = f"House {other.name} grows annoyed by your silence."
        elif idx == 1:
            if faction.political_points >= 2:
                faction.political_points -= 2
                faction.relations[other.name] += 8
                result = "Negotiation calmed the border dispute."
            else:
                faction.relations[other.name] -= 3
                result = "You lacked political points. The negotiation failed."
        elif idx == 2:
            marshal = faction.role_holder("Marshal")
            if marshal:
                score = marshal.get_skill("combat_skill") + marshal.get_trait("confidence") + rng.randint(-30, 30)
                if score >= 95:
                    faction.relations[other.name] -= 5
                    faction.political_points += 2
                    result = f"{marshal.name}'s threat worked. You gained leverage."
                else:
                    faction.relations[other.name] -= 12
                    result = f"{marshal.name}'s threat backfired. Relations worsened."
            else:
                faction.relations[other.name] -= 8
                result = "Without a Marshal, the threat sounded hollow."
        else:
            resolve_attack(game, attacker=faction, defender=other, limited=True)
            return

    elif event == "insult":
        idx = choose_from_menu(
            f"A noble from House {other.name} publicly insults your ruler.",
            ["Laugh it off.", "Demand apology.", "Answer with a sharper insult.", "Challenge them."],
            auto=game.auto,
        )
        ruler = faction.ruler()
        if idx == 0:
            faction.relations[other.name] += 2
            if ruler:
                ruler.change_trait("stability", 1)
                ruler.change_trait("prestige", -1)
            result = "You avoided escalation, but looked slightly weak."
        elif idx == 1:
            if faction.political_points >= 1:
                faction.political_points -= 1
                faction.relations[other.name] += 4
                if ruler:
                    ruler.change_trait("prestige", 1)
                result = "A formal apology was extracted."
            else:
                result = "You lacked political leverage and gained nothing."
        elif idx == 2:
            faction.relations[other.name] -= 8
            if ruler:
                ruler.change_trait("prestige", 2)
                ruler.change_trait("aggression", 1)
            result = "Your counterinsult delighted your court and angered theirs."
        else:
            marshal = faction.role_holder("Marshal") or ruler
            if marshal:
                score = marshal.get_skill("combat_skill") + rng.randint(-35, 35)
                if score > 70:
                    faction.relations[other.name] -= 6
                    marshal.change_trait("prestige", 4)
                    result = f"{marshal.name} won the challenge."
                else:
                    marshal.change_trait("health", -8)
                    faction.relations[other.name] -= 4
                    result = f"{marshal.name} was injured in the challenge."
            else:
                result = "No one could answer the challenge."

    elif event == "aid_request":
        idx = choose_from_menu(
            f"House {other.name} asks for food aid after a poor harvest.",
            ["Send food.", "Demand gold in exchange.", "Refuse.", "Use the request to humiliate them."],
            auto=game.auto,
        )
        if idx == 0:
            if faction.resources["food"] >= 6:
                faction.resources["food"] -= 6
                faction.relations[other.name] += 12
                result = "Your aid improved relations."
            else:
                result = "You did not have enough food to send meaningful aid."
        elif idx == 1:
            if other.resources["gold"] >= 4 and faction.resources["food"] >= 4:
                faction.resources["food"] -= 4
                faction.resources["gold"] += 4
                faction.relations[other.name] += 2
                result = "You traded food for gold."
            else:
                result = "The exchange failed due to limited resources."
        elif idx == 2:
            faction.relations[other.name] -= 4
            result = "You refused the request."
        else:
            faction.political_points += 2
            faction.relations[other.name] -= 15
            result = "You gained domestic leverage by humiliating them."

    elif event == "trade_envoy":
        idx = choose_from_menu(
            "A trade envoy arrives offering exchange rates: 3 gold for 1 resource, or 2 resources for 3 gold.",
            ["Buy food.", "Buy wood.", "Buy stone.", "Sell herbs.", "Decline."],
            auto=game.auto,
        )
        if idx in [0, 1, 2]:
            resource = ["food", "wood", "stone"][idx]
            merchant = faction.role_holder("Merchant")
            cost = 2 if merchant else 3
            if faction.resources["gold"] >= cost:
                faction.resources["gold"] -= cost
                faction.resources[resource] += 1
                result = f"You bought 1 {resource} for {cost} gold."
            else:
                result = "You lacked enough gold to buy."
        elif idx == 3:
            if faction.resources["herbs"] >= 2:
                faction.resources["herbs"] -= 2
                faction.resources["gold"] += 3
                result = "You sold herbs for gold."
            else:
                result = "You lacked enough herbs to sell."
        else:
            result = "You declined the trade envoy."

    elif event == "religious_pressure":
        idx = choose_from_menu(
            f"Priests of {other.religion} pressure your court to respect their rites.",
            ["Respect their rites.", "Assert your own religion.", "Invite debate.", "Suppress them."],
            auto=game.auto,
        )
        if idx == 0:
            faction.relations[other.name] += 7
            faction.piety += 2
            result = "Tolerance improved relations."
        elif idx == 1:
            faction.piety += 8
            faction.relations[other.name] -= 5
            result = "Your faithful approved, but relations worsened."
        elif idx == 2:
            scholar = faction.role_holder("Scholar")
            priest = faction.role_holder("High Priest")
            bonus = (scholar.get_skill("scholarship") if scholar else 20) + (priest.get_skill("priesthood") if priest else 20)
            if bonus + rng.randint(-30, 30) > 90:
                faction.piety += 5
                faction.relations[other.name] += 5
                result = "The debate impressed both courts."
            else:
                faction.relations[other.name] -= 3
                result = "The debate ended in confusion and irritation."
        else:
            faction.piety += 4
            faction.relations[other.name] -= 14
            result = "Suppression pleased zealots and angered outsiders."

    else:  # raid_opportunity
        idx = choose_from_menu(
            f"Scouts report House {other.name} has a weakly defended border storehouse.",
            ["Raid it.", "Do nothing.", "Warn them and seek favour."],
            auto=game.auto,
        )
        if idx == 0:
            resolve_attack(game, attacker=faction, defender=other, limited=True)
            return
        elif idx == 1:
            result = "You ignored the opportunity."
        else:
            faction.relations[other.name] += 10
            faction.political_points += 1
            result = "Your warning improved relations."

    print("\nResult:", result)
    faction.add_history(game.year, result)
    pause(game.auto)


def resolve_attack(game: Game, attacker: Faction, defender: Faction, limited: bool = False) -> None:
    rng = game.rng()
    print_banner("Conflict")

    attacker_marshal = attacker.role_holder("Marshal")
    defender_marshal = defender.role_holder("Marshal")

    attacker_score = (
        attacker.population * 4
        + attacker.resources.get("iron", 0) * 2
        + attacker.resources.get("gold", 0)
        + attacker.political_points * 2
        + rng.randint(-20, 30)
    )
    if attacker_marshal:
        attacker_score += attacker_marshal.get_skill("combat_skill") // 2
        attacker_score += attacker_marshal.get_trait("strength") // 3

    defender_score = (
        defender.population * 4
        + defender.total_tile_defence() * 5
        + defender.resources.get("stone", 0) * 2
        + rng.randint(-20, 30)
    )
    if defender_marshal:
        defender_score += defender_marshal.get_skill("combat_skill") // 2
        defender_score += defender_marshal.get_trait("strength") // 3

    if limited:
        attacker_score = int(attacker_score * 0.75)

    print(f"Attack score: {attacker_score}")
    print(f"Defence score: {defender_score}")

    if attacker_score > defender_score:
        stolen_gold = min(defender.resources.get("gold", 0), rng.randint(2, 8))
        stolen_food = min(defender.resources.get("food", 0), rng.randint(2, 8))
        defender.resources["gold"] -= stolen_gold
        defender.resources["food"] -= stolen_food
        attacker.resources["gold"] += stolen_gold
        attacker.resources["food"] += stolen_food
        attacker.political_points += 1
        attacker.relations[defender.name] = attacker.relations.get(defender.name, 0) - 15
        defender.relations[attacker.name] = defender.relations.get(attacker.name, 0) - 20

        if not limited and len(defender.tiles) > 1:
            captured = defender.tiles.pop()
            attacker.tiles.append(captured)
            result = f"{attacker.name} defeated {defender.name} and captured {captured}."
        else:
            result = f"{attacker.name} won the raid and seized {stolen_gold} gold and {stolen_food} food."
    else:
        attacker_loss = rng.randint(1, 3)
        defender_loss = rng.randint(0, 2)
        attacker.population = max(1, attacker.population - attacker_loss)
        defender.population = max(1, defender.population - defender_loss)
        attacker.relations[defender.name] = attacker.relations.get(defender.name, 0) - 10
        defender.relations[attacker.name] = defender.relations.get(attacker.name, 0) - 15
        result = f"{defender.name} held firm. {attacker.name} lost {attacker_loss} population."

    print("\nResult:", result)
    attacker.add_history(game.year, result)
    defender.add_history(game.year, result)
    pause(game.auto)


# -----------------------------
# Player actions
# -----------------------------


def use_piety_menu(faction: Faction, auto: bool = False) -> None:
    gifts = [
        (10, "Food blessing", "food", 8),
        (50, "Fertility blessing for ruler", "fertility", 8),
        (100, "High Priest skill boost", "priesthood", 8),
        (200, "Defence blessing", "stone", 8),
        (500, "Great material blessing", "wood", 20),
    ]
    options = [f"{cost} piety: {name}" for cost, name, _, _ in gifts] + ["Cancel"]
    idx = choose_from_menu(f"You have {faction.piety} piety. Choose divine gift:", options, auto=auto, default_index=len(options)-1)
    if idx == len(options) - 1:
        return
    cost, name, target, amount = gifts[idx]
    if faction.piety < cost:
        print("Not enough piety.")
        pause(auto)
        return
    faction.piety -= cost
    if target in faction.resources:
        faction.resources[target] += amount
        print(f"{name}: +{amount} {target}.")
    elif target == "fertility":
        ruler = faction.ruler()
        if ruler:
            ruler.change_trait("fertility", amount)
            print(f"{name}: {ruler.name} gains +{amount} fertility.")
    elif target == "priesthood":
        priest = faction.role_holder("High Priest")
        if priest:
            priest.change_skill("priesthood", amount)
            print(f"{name}: {priest.name} gains +{amount} priesthood.")
        else:
            faction.resources["faith"] += 5
            print("No High Priest. Faith stock increased instead.")
    pause(auto)


def manual_trade(faction: Faction, auto: bool = False) -> None:
    merchant = faction.role_holder("Merchant")
    buy_cost = 2 if merchant else 3
    options = ["Buy food", "Buy wood", "Buy stone", "Buy iron", "Buy herbs", "Cancel"]
    idx = choose_from_menu(f"Trade menu. Buy cost: {buy_cost} gold per resource.", options, auto=auto, default_index=len(options)-1)
    if idx == len(options) - 1:
        return
    resource = ["food", "wood", "stone", "iron", "herbs"][idx]
    if faction.resources["gold"] >= buy_cost:
        faction.resources["gold"] -= buy_cost
        faction.resources[resource] += 1
        print(f"Bought 1 {resource} for {buy_cost} gold.")
    else:
        print("Not enough gold.")
    pause(auto)


def player_year_menu(game: Game) -> bool:
    faction = game.player
    while True:
        options = [
            "View faction status",
            "View relations",
            "Manage council",
            "Trade",
            "Use piety",
            "Advance to next year",
            "Quit and write report",
        ]
        idx = choose_from_menu("Yearly action menu:", options, auto=game.auto, default_index=5)
        if idx == 0:
            print_faction_status(faction)
            pause(game.auto)
        elif idx == 1:
            print_relations(game, faction)
            pause(game.auto)
        elif idx == 2:
            manage_council(faction, auto=game.auto)
        elif idx == 3:
            manual_trade(faction, auto=game.auto)
        elif idx == 4:
            use_piety_menu(faction, auto=game.auto)
        elif idx == 5:
            return True
        else:
            return False


# -----------------------------
# NPC simulation
# -----------------------------


def npc_take_action(game: Game, faction: Faction) -> None:
    rng = game.rng()
    auto_assign_roles(faction)

    # Basic AI: if starving, buy food if possible.
    if faction.resources["food"] < faction.population and faction.resources["gold"] >= 3:
        faction.resources["gold"] -= 3
        faction.resources["food"] += 2
        faction.add_history(game.year, "Bought emergency food.")

    # Occasionally raid a rival if aggressive ruler/marshal.
    ruler = faction.ruler()
    marshal = faction.role_holder("Marshal")
    aggression = (ruler.get_trait("aggression") if ruler else 40) + (marshal.get_trait("aggression") if marshal else 0) // 2
    if roll(rng, max(0.02, aggression / 1200)):
        possible = [f for f in game.factions if f.name != faction.name]
        target = min(possible, key=lambda f: faction.relations.get(f.name, 0))
        # Resolve silently but still with same mechanics would print; use a simplified silent raid.
        if faction.population + rng.randint(0, 10) > target.population + rng.randint(0, 10):
            stolen = min(target.resources["gold"], rng.randint(1, 4))
            target.resources["gold"] -= stolen
            faction.resources["gold"] += stolen
            faction.relations[target.name] = faction.relations.get(target.name, 0) - 8
            target.relations[faction.name] = target.relations.get(faction.name, 0) - 10
            faction.add_history(game.year, f"Raided House {target.name} for {stolen} gold.")


# -----------------------------
# Saving/reporting
# -----------------------------


def write_report(game: Game) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"{timestamp}_DynastyFactionSimOutput.txt"
    path = os.path.join(os.getcwd(), filename)

    lines: List[str] = []
    lines.append("Dynasty Faction Simulator Report")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Final year: {game.year}")
    lines.append("")

    for faction in game.factions:
        lines.append("=" * 70)
        lines.append(f"House {faction.name}")
        lines.append("=" * 70)
        lines.append(faction.summary())
        lines.append("")
        lines.append("Living characters:")
        for c in faction.living_characters():
            spouse = faction.character_by_id(c.spouse_id)
            spouse_text = spouse.name if spouse else "-"
            lines.append(
                f"- {c.name}, {c.sex}, age {c.age}, race {c.race}, role {c.role or '-'}, "
                f"spouse {spouse_text}, top stats: {c.top_stats(6)}"
            )
        dead = [c for c in faction.characters if not c.alive]
        if dead:
            lines.append("")
            lines.append("Dead characters:")
            for c in dead:
                lines.append(f"- {c.name}, died age {c.age}, cause: {c.cause_of_death}")
        lines.append("")
        lines.append("History:")
        for item in faction.history[-80:]:
            lines.append(f"- {item}")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def save_game_json(game: Game, filename: str = "dynasty_save.json") -> None:
    """
    Optional starter save function. This is not used by default, but it shows
    how to serialize the core state using only the standard library.
    """
    data = asdict(game)
    # _rng is not a dataclass field, so no need to remove it.
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# -----------------------------
# Main game loop
# -----------------------------


def run_year(game: Game) -> bool:
    faction = game.player
    rng = game.rng()

    print_banner(f"YEAR {game.year}")

    # At beginning, let player configure council.
    if game.year == 1:
        print("You begin with a small ruling family. Only adults can hold council roles.")
        manage_council(faction, auto=game.auto)

    # Economy and aging for all factions.
    for f in game.factions:
        produce_resources(game, f)
        age_and_mortality(game, f)
        marriage_and_births(game, f)

    # NPC decisions.
    for i, f in enumerate(game.factions):
        if i != game.player_index:
            npc_take_action(game, f)

    print_faction_status(faction)

    # Player political event.
    political_event(game, faction)

    # Player character events: one child/adult event each if possible.
    living_children = faction.children()
    living_adults = [c for c in faction.living_adults() if c.role != "King/Queen"] or faction.living_adults()

    if living_children:
        child_event(game, faction, rng.choice(living_children))
    if living_adults:
        adult_event(game, faction, rng.choice(living_adults))

    # End-year menu.
    keep_playing = player_year_menu(game)
    game.year += 1
    return keep_playing


def main() -> None:
    auto = "--demo" in sys.argv
    game = create_new_game(auto=auto)

    print_banner("Dynasty Faction Simulator - Starting Prototype")
    print("No external libraries. Terminal-based. You control the first house.")
    print("This prototype is intentionally small so you can expand it.")

    while game.year <= game.max_years:
        keep_playing = run_year(game)
        if not keep_playing:
            break
        if auto and game.year > 3:
            # Demo mode only runs a few years so it does not spam your terminal.
            break

    report_path = write_report(game)
    print_banner("Simulation Ended")
    print(f"Report written to: {report_path}")


if __name__ == "__main__":
    main()
