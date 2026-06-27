"""
ClaudFootyPrototype.py
A text-based five-a-side soccer tournament simulator.
"""

import csv
import os
import random
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CSV_NAME_FILE = "toon_names_.csv"

NUM_USER_POOL_PLAYERS = 20
NUM_CPU_TEAMS = 3
CPU_PLAYERS_PER_TEAM = 5

TRAIT_MIN = 1
TRAIT_MAX = 20

MATCH_MINUTES = 40
BASE_EVENTS_PER_TEAM = 8
EVENT_RANDOM_RANGE = 2

WIN_POINTS = 3
DRAW_POINTS = 1
LOSS_POINTS = 0

GOAL_MARGIN = 2.5
LUCKY_GOAL_CHANCE = 0.03
SHOCKING_MISS_CHANCE = 0.04

PLAY_BY_PLAY_DELAY = 0.4

DEFAULT_USER_TEAM_NAME = "Northbridge Foxes"

CPU_TEAM_NAMES = [
    "Blubberfats",
    "Loofie Athletics",
    "Geometry United",
]

TRAITS = [
    "Speed", "Stamina", "Strength", "Agility",
    "Shooting", "Passing", "Dribbling", "Tackling", "Marking", "Goalkeeping",
    "Vision", "Composure", "Discipline", "Teamwork", "Aggression",
]

FALLBACK_MALE_NAMES = [
    "Aaron", "Ben", "Carlos", "David", "Eddie",
    "Frank", "George", "Harry", "Ivan", "Jack",
    "Karl", "Leo", "Marcus", "Nathan", "Oscar",
    "Paul", "Quinn", "Ryan", "Sam", "Tom",
]

FALLBACK_LAST_NAMES = [
    "Adams", "Baker", "Clark", "Davis", "Evans",
    "Ford", "Grant", "Hall", "Irwin", "Jones",
    "King", "Lee", "Moore", "Nash", "Owen",
    "Park", "Quinn", "Reed", "Smith", "Turner",
]

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Player:
    id: int
    first_name: str
    last_name: str
    team_name: str
    assigned_role: str
    age: int
    traits: Dict[str, int]

    goals: int = 0
    shots: int = 0
    saves: int = 0
    goals_allowed: int = 0
    tackles: int = 0
    key_passes: int = 0
    fouls: int = 0
    yellow_cards: int = 0
    red_cards: int = 0

    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@dataclass
class Team:
    name: str
    players: List[Player]
    controlled_by_user: bool = False

    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0

    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against


@dataclass
class MatchResult:
    team_a: Team
    team_b: Team
    goals_a: int
    goals_b: int
    scorers_a: List[Tuple[Player, int]]
    scorers_b: List[Tuple[Player, int]]
    events: List[str]
    is_final: bool = False
    went_to_penalties: bool = False
    penalty_score_a: int = 0
    penalty_score_b: int = 0
    winner: Optional[Team] = None


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def format_rating(value: float) -> str:
    return f"{value:.1f}"


def pause(prompt: str = "Press Enter to continue...") -> None:
    input(f"\n{prompt}")


# ---------------------------------------------------------------------------
# Name loading
# ---------------------------------------------------------------------------

def load_name_bank(csv_path: str) -> Tuple[List[str], List[str]]:
    male_first_names: List[str] = []
    last_names: List[str] = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Normalize headers so "Male_First_Name", " last_name ", etc. still match.
            if reader.fieldnames:
                reader.fieldnames = [(h or "").strip().lower() for h in reader.fieldnames]
            for row in reader:
                m = (row.get("male_first_name") or "").strip()
                ln = (row.get("last_name") or "").strip()
                if m:
                    male_first_names.append(m)
                if ln:
                    last_names.append(ln)
        male_first_names = list(dict.fromkeys(male_first_names))
        last_names = list(dict.fromkeys(last_names))
    except Exception:
        pass

    if len(male_first_names) < 10:
        male_first_names = FALLBACK_MALE_NAMES[:]
    if len(last_names) < 10:
        last_names = FALLBACK_LAST_NAMES[:]

    return male_first_names, last_names


# ---------------------------------------------------------------------------
# Trait generation
# ---------------------------------------------------------------------------

def roll_trait() -> int:
    return round((random.randint(1, 20) + random.randint(1, 20) + random.randint(1, 20)) / 3)


def generate_traits() -> Dict[str, int]:
    return {t: roll_trait() for t in TRAITS}


ROLE_BIAS_MAP: Dict[str, Dict[str, int]] = {
    "goalie": {
        "Goalkeeping": 3, "Agility": 3, "Composure": 3,
        "Strength": 1, "Vision": 1,
    },
    "defender": {
        "Tackling": 3, "Marking": 3,
        "Strength": 2, "Discipline": 2,
        "Speed": 1, "Passing": 1,
    },
    "attacker": {
        "Shooting": 3, "Dribbling": 3,
        "Agility": 2, "Speed": 2,
        "Passing": 1, "Vision": 1, "Composure": 1,
    },
}

# Single source of truth pairing a lowercase trait-bias key (used during
# generation) with its capitalized assigned_role value (used everywhere else).
# Keeping both in one map prevents the two casings from drifting apart.
BIAS_TO_ROLE: Dict[str, str] = {
    "goalie": "Goalie",
    "defender": "Defender",
    "attacker": "Attacker",
}


def apply_role_bias(traits: Dict[str, int], role_bias: Optional[str]) -> Dict[str, int]:
    if role_bias is None or role_bias not in ROLE_BIAS_MAP:
        return traits
    bonuses = ROLE_BIAS_MAP[role_bias]
    result = dict(traits)
    for trait, bonus in bonuses.items():
        result[trait] = int(clamp(result[trait] + bonus, TRAIT_MIN, TRAIT_MAX))
    return result


# ---------------------------------------------------------------------------
# Ratings
# ---------------------------------------------------------------------------

def goalie_rating(player: Player) -> float:
    t = player.traits
    return (
        t["Goalkeeping"] * 0.40 +
        t["Agility"] * 0.20 +
        t["Composure"] * 0.15 +
        t["Strength"] * 0.10 +
        t["Vision"] * 0.10 +
        t["Stamina"] * 0.05
    )


def defender_rating(player: Player) -> float:
    t = player.traits
    return (
        t["Tackling"] * 0.25 +
        t["Marking"] * 0.25 +
        t["Strength"] * 0.15 +
        t["Discipline"] * 0.10 +
        t["Speed"] * 0.10 +
        t["Passing"] * 0.10 +
        t["Stamina"] * 0.05
    )


def attacker_rating(player: Player) -> float:
    t = player.traits
    return (
        t["Shooting"] * 0.25 +
        t["Agility"] * 0.15 +
        t["Dribbling"] * 0.15 +
        t["Speed"] * 0.15 +
        t["Composure"] * 0.10 +
        t["Passing"] * 0.10 +
        t["Vision"] * 0.10
    )


def overall_rating(player: Player) -> float:
    t = player.traits
    return (
        t["Speed"] * 0.08 + t["Stamina"] * 0.06 + t["Strength"] * 0.06 +
        t["Agility"] * 0.08 + t["Shooting"] * 0.10 + t["Passing"] * 0.10 +
        t["Dribbling"] * 0.08 + t["Tackling"] * 0.10 + t["Marking"] * 0.10 +
        t["Goalkeeping"] * 0.08 + t["Vision"] * 0.08 + t["Composure"] * 0.08 +
        t["Discipline"] * 0.05 + t["Teamwork"] * 0.05 + t["Aggression"] * 0.02
    )


def best_fit(player: Player) -> str:
    gk = goalie_rating(player)
    df = defender_rating(player)
    at = attacker_rating(player)
    if gk >= df and gk >= at:
        return "Goalie"
    elif df >= at:
        return "Defender"
    else:
        return "Attacker"


def top_key_traits(player: Player, n: int = 3) -> str:
    sorted_traits = sorted(player.traits.items(), key=lambda x: x[1], reverse=True)
    return ", ".join(f"{k} {v}" for k, v in sorted_traits[:n])


# ---------------------------------------------------------------------------
# Player generation
# ---------------------------------------------------------------------------

_used_names: set = set()


def generate_player(
    player_id: int,
    team_name: str,
    first_names: List[str],
    last_names: List[str],
    role_bias: Optional[str] = None,
    assigned_role: str = "Unassigned",
) -> Player:
    for _ in range(50):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        full = f"{fn} {ln}"
        if full not in _used_names:
            _used_names.add(full)
            break
    else:
        fn = random.choice(first_names)
        ln = random.choice(last_names)

    age = random.randint(18, 34)
    traits = generate_traits()
    traits = apply_role_bias(traits, role_bias)

    return Player(
        id=player_id,
        first_name=fn,
        last_name=ln,
        team_name=team_name,
        assigned_role=assigned_role,
        age=age,
        traits=traits,
    )


def generate_user_player_pool(first_names: List[str], last_names: List[str]) -> List[Player]:
    pool: List[Player] = []
    # 3 goalie-biased, 7 defender-biased, 7 attacker-biased, 3 balanced
    biases = (
        ["goalie"] * 3 +
        ["defender"] * 7 +
        ["attacker"] * 7 +
        [None] * 3
    )
    random.shuffle(biases)
    for i, bias in enumerate(biases, start=1):
        p = generate_player(i, "TBD", first_names, last_names, role_bias=bias)
        pool.append(p)
    return pool


def generate_cpu_team(team_name: str, first_names: List[str], last_names: List[str]) -> Team:
    players: List[Player] = []
    biases = ["goalie", "defender", "defender", "attacker", "attacker"]
    for i, bias in enumerate(biases, start=1):
        p = generate_player(i, team_name, first_names, last_names,
                            role_bias=bias, assigned_role=BIAS_TO_ROLE[bias])
        players.append(p)
    return Team(name=team_name, players=players)


# ---------------------------------------------------------------------------
# Display utilities
# ---------------------------------------------------------------------------

def _player_row(p: Player, show_role: bool = False) -> str:
    gk = format_rating(goalie_rating(p))
    df = format_rating(defender_rating(p))
    at = format_rating(attacker_rating(p))
    ov = format_rating(overall_rating(p))
    kt = top_key_traits(p)
    name = p.full_name()[:22].ljust(22)
    if show_role:
        role = p.assigned_role[:4].ljust(4)
        return f"{role} {name} {p.age:>3}  {gk:>5} {df:>5} {at:>5} {ov:>5}  {kt}"
    else:
        pid = str(p.id).zfill(2)
        bf = best_fit(p)[:8].ljust(8)
        return f"{pid}  {name} {p.age:>3}  {gk:>5} {df:>5} {at:>5} {ov:>5}  {bf}  {kt}"


def display_player_pool(players: List[Player]) -> None:
    print("\nYOUR PLAYER POOL\n")
    print(f"{'ID':<4} {'Name':<22} {'Age':>3}  {'GK':>5} {'DEF':>5} {'ATT':>5} {'OVR':>5}  {'Best Fit':<8}  Key Traits")
    print("-" * 90)
    for p in players:
        print(_player_row(p, show_role=False))


def display_team(team: Team) -> None:
    print(f"\n{team.name.upper()}\n")
    print(f"{'Role':<4} {'Name':<22} {'Age':>3}  {'GK':>5} {'DEF':>5} {'ATT':>5} {'OVR':>5}  Key Traits")
    print("-" * 85)
    for p in team.players:
        print(_player_row(p, show_role=True))


def display_player_detail(player: Player) -> None:
    t = player.traits
    print(f"\n{player.full_name()}, age {player.age}")
    print(f"Assigned role: {player.assigned_role}")
    print(f"Best fit: {best_fit(player)}")
    print(f"\nRatings:")
    print(f"  Goalie:   {format_rating(goalie_rating(player))}")
    print(f"  Defender: {format_rating(defender_rating(player))}")
    print(f"  Attacker: {format_rating(attacker_rating(player))}")
    print(f"  Overall:  {format_rating(overall_rating(player))}")
    print(f"\nPhysical:")
    print(f"  Speed {t['Speed']}, Stamina {t['Stamina']}, Strength {t['Strength']}, Agility {t['Agility']}")
    print(f"\nTechnical:")
    print(f"  Shooting {t['Shooting']}, Passing {t['Passing']}, Dribbling {t['Dribbling']}")
    print(f"  Tackling {t['Tackling']}, Marking {t['Marking']}, Goalkeeping {t['Goalkeeping']}")
    print(f"\nMental:")
    print(f"  Vision {t['Vision']}, Composure {t['Composure']}, Discipline {t['Discipline']}")
    print(f"  Teamwork {t['Teamwork']}, Aggression {t['Aggression']}")


def display_standings(teams: List[Team]) -> None:
    print("\nGROUP STANDINGS\n")
    print(f"{'Pos':<4} {'Team':<22} {'P':>3} {'W':>3} {'D':>3} {'L':>3} {'GF':>4} {'GA':>4} {'GD':>4} {'Pts':>4}")
    print("-" * 60)
    sorted_teams = sort_standings(teams)
    for i, t in enumerate(sorted_teams, start=1):
        gd = t.goal_difference()
        gd_str = f"+{gd}" if gd > 0 else str(gd)
        print(f"{i:<4} {t.name:<22} {t.played:>3} {t.wins:>3} {t.draws:>3} {t.losses:>3} {t.goals_for:>4} {t.goals_against:>4} {gd_str:>4} {t.points:>4}")


def display_match_result(result: MatchResult) -> None:
    if result.went_to_penalties:
        print(f"\n{result.team_a.name} {result.goals_a} - {result.goals_b} {result.team_b.name}  "
              f"(Pens: {result.penalty_score_a}-{result.penalty_score_b})")
    else:
        print(f"\n{result.team_a.name} {result.goals_a} - {result.goals_b} {result.team_b.name}")


def display_round_results(results: List[MatchResult]) -> None:
    for r in results:
        display_match_result(r)


# ---------------------------------------------------------------------------
# Team ratings
# ---------------------------------------------------------------------------

def _get_role_players(team: Team, role: str) -> List[Player]:
    return [p for p in team.players if p.assigned_role == role]


def calculate_team_ratings(team: Team) -> Dict[str, float]:
    attackers = _get_role_players(team, "Attacker")
    defenders = _get_role_players(team, "Defender")
    goalies = _get_role_players(team, "Goalie")
    non_goalies = [p for p in team.players if p.assigned_role != "Goalie"]
    all_players = team.players

    def avg(lst: List[float]) -> float:
        return sum(lst) / len(lst) if lst else 10.0

    att_ratings = [attacker_rating(p) for p in attackers]
    def_ratings = [defender_rating(p) for p in defenders]
    gk_rating_val = goalie_rating(goalies[0]) if goalies else 10.0

    def_pass_vis = [(p.traits["Passing"] + p.traits["Vision"]) / 2 for p in defenders]
    att_press = [(p.traits["Tackling"] + p.traits["Aggression"] + p.traits["Stamina"]) / 3 for p in attackers]
    teamwork_all = [p.traits["Teamwork"] for p in all_players]
    stamina_all = [p.traits["Stamina"] for p in all_players]
    discipline_all = [p.traits["Discipline"] for p in all_players]
    passing_ng = [p.traits["Passing"] for p in non_goalies]
    vision_ng = [p.traits["Vision"] for p in non_goalies]
    composure_all = [p.traits["Composure"] for p in all_players]
    aggression_all = [p.traits["Aggression"] for p in all_players]

    attack = (
        avg(att_ratings) * 0.65 +
        avg(def_pass_vis) * 0.20 +
        avg(teamwork_all) * 0.10 +
        avg(stamina_all) * 0.05
    )
    defense = (
        avg(def_ratings) * 0.65 +
        avg(att_press) * 0.15 +
        avg(teamwork_all) * 0.10 +
        avg(discipline_all) * 0.10
    )
    control = (
        avg(passing_ng) * 0.35 +
        avg(vision_ng) * 0.25 +
        avg(teamwork_all) * 0.25 +
        avg(composure_all) * 0.15
    )
    chaos = (
        avg(aggression_all) * 0.40 +
        (20 - avg(discipline_all)) * 0.40 +
        (20 - avg(composure_all)) * 0.20
    )

    return {
        "attack": attack,
        "defense": defense,
        "goalkeeping": gk_rating_val,
        "control": control,
        "chaos": chaos,
    }


def display_team_comparison(team_a: Team, team_b: Team) -> None:
    ra = calculate_team_ratings(team_a)
    rb = calculate_team_ratings(team_b)
    print("\nTEAM COMPARISON\n")
    labels = [("Attack", "attack"), ("Defense", "defense"), ("Goalkeeping", "goalkeeping"),
              ("Control", "control"), ("Chaos", "chaos")]
    for label, key in labels:
        print(f"  {team_a.name}: {label:<14} {ra[key]:>5.1f}   |   {team_b.name}: {label:<14} {rb[key]:>5.1f}")


# ---------------------------------------------------------------------------
# Match simulation
# ---------------------------------------------------------------------------

EVENT_TYPES = ["patient_buildup", "fast_break", "long_shot", "defensive_mistake", "set_piece", "scramble"]


def choose_event_type(attacking_team: Team, defending_team: Team) -> str:
    rat = calculate_team_ratings(attacking_team)
    rdf = calculate_team_ratings(defending_team)
    chaos = (rat["chaos"] + rdf["chaos"]) / 2
    weights = [3, 2, 2, 1, 1, 1]
    # boost fast_break for speed teams, defensive_mistake for chaotic teams
    if rat["attack"] > 14:
        weights[1] += 1
    if chaos > 10:
        weights[3] += 1
        weights[5] += 1
    return random.choices(EVENT_TYPES, weights=weights, k=1)[0]


def choose_shooter(team: Team, event_type: str) -> Player:
    attackers = _get_role_players(team, "Attacker")
    defenders = _get_role_players(team, "Defender")
    non_goalies = [p for p in team.players if p.assigned_role != "Goalie"]

    if event_type == "set_piece":
        key = lambda p: p.traits["Shooting"] + p.traits["Strength"] + p.traits["Composure"]
        return max(non_goalies, key=key)
    elif event_type == "scramble":
        weights = [p.traits["Aggression"] + p.traits["Composure"] + p.traits["Agility"] for p in non_goalies]
        return random.choices(non_goalies, weights=weights, k=1)[0]
    elif event_type == "long_shot":
        pool = attackers if random.random() < 0.65 else defenders
        if not pool:
            pool = non_goalies
        return random.choice(pool)
    else:
        if attackers and random.random() < 0.80:
            return random.choice(attackers)
        pool = defenders if defenders else non_goalies
        return random.choice(pool)


def choose_defender(team: Team) -> Player:
    defenders = _get_role_players(team, "Defender")
    if defenders:
        return random.choice(defenders)
    return random.choice([p for p in team.players if p.assigned_role != "Goalie"])


def get_goalie(team: Team) -> Player:
    goalies = _get_role_players(team, "Goalie")
    return goalies[0] if goalies else team.players[0]


def _event_type_quality_mod(event_type: str, rat_a: Dict, rat_b: Dict) -> float:
    if event_type == "patient_buildup":
        return 0.03 if rat_a["control"] > rat_b["control"] else 0.0
    elif event_type == "fast_break":
        # Bonus only when the attack outpaces the defense (a real speed advantage).
        return 0.05 if rat_a["attack"] > rat_b["defense"] else 0.0
    elif event_type == "long_shot":
        return -0.12
    elif event_type == "defensive_mistake":
        return 0.12
    elif event_type == "set_piece":
        return 0.04
    elif event_type == "scramble":
        return random.uniform(-0.05, 0.10)
    return 0.0


def simulate_event(
    attacking_team: Team,
    defending_team: Team,
    minute: int,
    watch: bool = False,
) -> Optional[Tuple[bool, str, Optional[Player], Optional[Player]]]:
    """Returns (goal, event_text, scorer, goalie_who_saved) or None if broken down."""
    rat_a = calculate_team_ratings(attacking_team)
    rat_d = calculate_team_ratings(defending_team)

    event_type = choose_event_type(attacking_team, defending_team)
    chance_score = rat_a["attack"] + random.uniform(-5, 5)
    defense_score = rat_d["defense"] + random.uniform(-5, 5)

    goalie = get_goalie(defending_team)
    def_player = choose_defender(defending_team)

    if chance_score <= defense_score - 2:
        # Attack breaks down
        templates = [
            f"{attacking_team.name} try to build, but {def_player.full_name()} reads it well.",
            f"A move from {attacking_team.name} fizzles out.",
            f"{def_player.full_name()} steps in and breaks up the attack.",
        ]
        # Check for foul
        foul_risk = clamp(
            def_player.traits["Aggression"] * 0.015 + (20 - def_player.traits["Discipline"]) * 0.015,
            0.02, 0.35
        )
        if random.random() < foul_risk:
            def_player.fouls += 1
            foul_text = f"{minute}'  Foul by {def_player.full_name()}!"
            yc_chance = clamp(0.20 + def_player.traits["Aggression"] * 0.01 - def_player.traits["Discipline"] * 0.005, 0, 1)
            rc_chance = 0.02 if def_player.traits["Aggression"] > 16 and def_player.traits["Discipline"] < 8 else 0.005
            card_text = ""
            if random.random() < rc_chance:
                def_player.red_cards += 1
                card_text = f" RED CARD for {def_player.full_name()}!"
            elif random.random() < yc_chance:
                def_player.yellow_cards += 1
                card_text = f" Yellow card for {def_player.full_name()}."
            return (False, foul_text + card_text, None, None)
        else:
            def_player.tackles += 1
            txt = f"{minute}'  {random.choice(templates)}"
            return (False, txt, None, None)

    # Attack becomes a chance
    quality = 0.50
    quality += (rat_a["attack"] - rat_d["defense"]) * 0.025
    quality += _event_type_quality_mod(event_type, rat_a, rat_d)
    quality += random.uniform(-0.15, 0.15)
    quality = clamp(quality, 0.10, 0.90)

    shooter = choose_shooter(attacking_team, event_type)
    shooter.shots += 1

    # Credit the chance to a teammate (weighted by Passing + Vision), if any.
    passers = [p for p in attacking_team.players
               if p.assigned_role != "Goalie" and p is not shooter]
    if passers:
        weights = [p.traits["Passing"] + p.traits["Vision"] for p in passers]
        random.choices(passers, weights=weights, k=1)[0].key_passes += 1

    # Shocking miss
    if random.random() < SHOCKING_MISS_CHANCE:
        miss_templates = [
            f"{minute}'  {shooter.full_name()} blazes it over from close range!",
            f"{minute}'  Incredible miss by {shooter.full_name()}!",
            f"{minute}'  {shooter.full_name()} somehow misses an open goal!",
        ]
        return (False, random.choice(miss_templates), None, None)

    # Lucky goal
    if random.random() < LUCKY_GOAL_CHANCE:
        shooter.goals += 1
        goalie.goals_allowed += 1
        return (True, f"{minute}'  A fortunate deflection falls to {shooter.full_name()}... it's in! GOAL!", shooter, None)

    # Regular shot resolution
    t_s = shooter.traits
    shot_score = (
        t_s["Shooting"] * 0.45 + t_s["Composure"] * 0.20 +
        t_s["Agility"] * 0.15 + t_s["Dribbling"] * 0.10 +
        t_s["Strength"] * 0.05 + t_s["Vision"] * 0.05
    )
    shot_score *= (0.75 + quality * 0.5)

    t_g = goalie.traits
    save_score = (
        t_g["Goalkeeping"] * 0.50 + t_g["Agility"] * 0.20 +
        t_g["Composure"] * 0.15 + t_g["Strength"] * 0.10 +
        t_g["Vision"] * 0.05
    )

    shot_roll = shot_score + random.uniform(-6, 6)
    save_roll = save_score + random.uniform(-6, 6)

    if shot_roll > save_roll + GOAL_MARGIN:
        shooter.goals += 1
        goalie.goals_allowed += 1
        goal_templates = [
            f"{minute}'  {shooter.full_name()} breaks free and finishes! GOAL!",
            f"{minute}'  {shooter.full_name()} smashes it past {goalie.full_name()}! GOAL!",
            f"{minute}'  {shooter.full_name()} keeps calm and slots it home! GOAL!",
            f"{minute}'  {shooter.full_name()} finds the corner! GOAL!",
        ]
        return (True, random.choice(goal_templates), shooter, None)
    else:
        goalie.saves += 1
        save_templates = [
            f"{minute}'  {shooter.full_name()} shoots... saved by {goalie.full_name()}.",
            f"{minute}'  {shooter.full_name()} fires low... {goalie.full_name()} gets down well.",
            f"{minute}'  {shooter.full_name()} tries to place it, but {goalie.full_name()} holds on.",
            f"{minute}'  {shooter.full_name()} hits it first time... strong save by {goalie.full_name()}.",
        ]
        return (False, random.choice(save_templates), None, goalie)


def simulate_match(
    team_a: Team,
    team_b: Team,
    watch: bool = False,
    is_final: bool = False,
) -> MatchResult:
    rat_a = calculate_team_ratings(team_a)
    rat_b = calculate_team_ratings(team_b)

    def event_count(my_rat: Dict, opp_rat: Dict) -> int:
        edge = my_rat["control"] - opp_rat["control"]
        bonus = round(clamp(edge / 5, -2, 2))
        n = BASE_EVENTS_PER_TEAM + random.randint(-EVENT_RANDOM_RANGE, EVENT_RANDOM_RANGE) + bonus
        return max(4, n)

    events_a = event_count(rat_a, rat_b)
    events_b = event_count(rat_b, rat_a)

    total_events = events_a + events_b
    minutes = sorted(random.sample(range(1, MATCH_MINUTES + 1), min(total_events, MATCH_MINUTES)))

    goals_a = 0
    goals_b = 0
    scorers_a: List[Tuple[Player, int]] = []
    scorers_b: List[Tuple[Player, int]] = []
    # each entry: (minute, text, is_goal, scored_by_a)
    all_events: List[Tuple[int, str, bool, bool]] = []

    teams_sequence: List[Tuple[Team, Team]] = (
        [(team_a, team_b)] * events_a + [(team_b, team_a)] * events_b
    )
    random.shuffle(teams_sequence)

    for i, (att, dfc) in enumerate(teams_sequence):
        minute = minutes[i] if i < len(minutes) else random.randint(1, MATCH_MINUTES)
        result = simulate_event(att, dfc, minute, watch)
        if result is None:
            continue
        goal, text, scorer, saved_by = result
        scored_by_a = goal and (att is team_a)
        all_events.append((minute, text, goal, scored_by_a))
        if goal and scorer:
            if att is team_a:
                goals_a += 1
                scorers_a.append((scorer, minute))
            else:
                goals_b += 1
                scorers_b.append((scorer, minute))

    all_events.sort(key=lambda x: x[0])

    if watch:
        current_a = 0
        current_b = 0
        for _, text, is_goal, scored_by_a in all_events:
            print(text)
            time.sleep(PLAY_BY_PLAY_DELAY)
            if is_goal:
                if scored_by_a:
                    current_a += 1
                else:
                    current_b += 1
                print(f"     {team_a.name} {current_a} - {current_b} {team_b.name}")
        print(f"\nFULL TIME")
        print(f"{team_a.name} {goals_a} - {goals_b} {team_b.name}")

    went_to_penalties = False
    penalty_score_a = 0
    penalty_score_b = 0
    winner: Optional[Team] = None

    if goals_a > goals_b:
        winner = team_a
    elif goals_b > goals_a:
        winner = team_b
    elif is_final:
        went_to_penalties = True
        winner, penalty_score_a, penalty_score_b = resolve_penalties(team_a, team_b, watch)

    return MatchResult(
        team_a=team_a,
        team_b=team_b,
        goals_a=goals_a,
        goals_b=goals_b,
        scorers_a=scorers_a,
        scorers_b=scorers_b,
        events=[text for _, text, _, _ in all_events],
        is_final=is_final,
        went_to_penalties=went_to_penalties,
        penalty_score_a=penalty_score_a,
        penalty_score_b=penalty_score_b,
        winner=winner,
    )


def resolve_penalties(
    team_a: Team,
    team_b: Team,
    watch: bool = False,
) -> Tuple[Team, int, int]:
    if watch:
        print("\n--- PENALTY SHOOTOUT ---")

    def penalty_takers(team: Team) -> List[Player]:
        non_goalies = [p for p in team.players if p.assigned_role != "Goalie"]
        weights = [p.traits["Shooting"] + p.traits["Composure"] for p in non_goalies]
        # Return weighted-shuffled list
        takers = []
        pool = list(zip(non_goalies, weights))
        while pool:
            total = sum(w for _, w in pool)
            r = random.uniform(0, total)
            acc = 0
            for i, (p, w) in enumerate(pool):
                acc += w
                if r <= acc:
                    takers.append(p)
                    pool.pop(i)
                    break
        return takers

    takers_a = penalty_takers(team_a)
    takers_b = penalty_takers(team_b)
    gk_a = get_goalie(team_a)
    gk_b = get_goalie(team_b)

    def take_penalty(taker: Player, goalie: Player) -> bool:
        t_s = taker.traits
        ts = t_s["Shooting"] * 0.50 + t_s["Composure"] * 0.35 + t_s["Strength"] * 0.15
        t_g = goalie.traits
        gs = t_g["Goalkeeping"] * 0.50 + t_g["Agility"] * 0.30 + t_g["Composure"] * 0.20
        return (ts + random.uniform(-5, 5)) > (gs + random.uniform(-5, 5)) - 2

    score_a = 0
    score_b = 0
    taken_a = 0
    taken_b = 0

    def decided() -> bool:
        # True once one team can no longer be caught in the best-of-5 phase.
        rem_a = 5 - taken_a
        rem_b = 5 - taken_b
        if score_a > score_b + rem_b:
            return True
        if score_b > score_a + rem_a:
            return True
        return False

    # Best-of-5 phase, kicks taken alternately and stopped as soon as decided.
    for i in range(5):
        ta = takers_a[i % len(takers_a)]
        ra = take_penalty(ta, gk_b)
        taken_a += 1
        if ra:
            score_a += 1
        if watch:
            print(f"  {ta.full_name()}: {'SCORED' if ra else 'MISSED'}  [{score_a}-{score_b}]")
        if decided():
            break

        tb = takers_b[i % len(takers_b)]
        rb = take_penalty(tb, gk_a)
        taken_b += 1
        if rb:
            score_b += 1
        if watch:
            print(f"  {tb.full_name()}: {'SCORED' if rb else 'MISSED'}  [{score_a}-{score_b}]")
        if decided():
            break

    # Sudden death if tied after the best-of-5 phase
    sd_round = 0
    while score_a == score_b:
        sd_round += 1
        ta = takers_a[sd_round % len(takers_a)]
        tb = takers_b[sd_round % len(takers_b)]
        ra = take_penalty(ta, gk_b)
        rb = take_penalty(tb, gk_a)
        if ra:
            score_a += 1
        if rb:
            score_b += 1
        if watch:
            res_a = "SCORED" if ra else "MISSED"
            res_b = "SCORED" if rb else "MISSED"
            print(f"  SD {sd_round}: {ta.full_name()}: {res_a}  |  {tb.full_name()}: {res_b}  [{score_a}-{score_b}]")
        if ra != rb:
            break

    winner = team_a if score_a > score_b else team_b
    if watch:
        print(f"\n{winner.name} win on penalties {score_a}-{score_b}!")
    return winner, score_a, score_b


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------

def update_standings(result: MatchResult) -> None:
    a = result.team_a
    b = result.team_b
    a.played += 1
    b.played += 1
    a.goals_for += result.goals_a
    a.goals_against += result.goals_b
    b.goals_for += result.goals_b
    b.goals_against += result.goals_a

    if result.goals_a > result.goals_b:
        a.wins += 1
        a.points += WIN_POINTS
        b.losses += 1
        b.points += LOSS_POINTS
    elif result.goals_b > result.goals_a:
        b.wins += 1
        b.points += WIN_POINTS
        a.losses += 1
        a.points += LOSS_POINTS
    else:
        a.draws += 1
        b.draws += 1
        a.points += DRAW_POINTS
        b.points += DRAW_POINTS


def sort_standings(teams: List[Team]) -> List[Team]:
    return sorted(
        teams,
        key=lambda t: (
            -t.points,
            -(t.goal_difference()),
            -t.goals_for,
            -t.wins,
            t.name,
        ),
    )


# ---------------------------------------------------------------------------
# Tournament schedule
# ---------------------------------------------------------------------------

def create_group_schedule(teams: List[Team]) -> List[List[Tuple[Team, Team]]]:
    """Double round-robin for 4 teams = 6 rounds, 2 matches each."""
    a, b, c, d = teams[0], teams[1], teams[2], teams[3]
    rounds = [
        [(a, b), (c, d)],
        [(a, c), (b, d)],
        [(a, d), (b, c)],
        [(b, a), (d, c)],
        [(c, a), (d, b)],
        [(d, a), (c, b)],
    ]
    return rounds


def play_group_stage(
    teams: List[Team],
    user_team: Team,
) -> List[MatchResult]:
    schedule = create_group_schedule(teams)
    all_results: List[MatchResult] = []

    for round_num, round_fixtures in enumerate(schedule, start=1):
        print(f"\n{'='*60}")
        print(f"ROUND {round_num}")
        print(f"{'='*60}")
        round_results: List[MatchResult] = []

        for team_a, team_b in round_fixtures:
            involves_user = (team_a is user_team or team_b is user_team)

            if involves_user:
                # Ensure user team is team_a for display consistency
                if team_b is user_team:
                    team_a, team_b = team_b, team_a

                print(f"\nNEXT MATCH: {team_a.name} vs {team_b.name}")
                display_team(team_a)
                print()
                display_team(team_b)
                display_team_comparison(team_a, team_b)
                pause("Press Enter to simulate the match...")
                print(f"\n=== {team_a.name} vs {team_b.name} ===\n")
                result = simulate_match(team_a, team_b, watch=True, is_final=False)
            else:
                result = simulate_match(team_a, team_b, watch=False, is_final=False)
                print(f"\n  {team_a.name} {result.goals_a} - {result.goals_b} {team_b.name}")

            update_standings(result)
            round_results.append(result)
            all_results.append(result)

        print("\n")
        display_standings(teams)
        pause()

    return all_results


# ---------------------------------------------------------------------------
# Final
# ---------------------------------------------------------------------------

def play_final(
    finalist_a: Team,
    finalist_b: Team,
    user_team: Team,
) -> MatchResult:
    print(f"\n{'='*60}")
    print("TOURNAMENT FINAL")
    print(f"{'='*60}")
    print(f"\n{finalist_a.name}  vs  {finalist_b.name}\n")

    involves_user = (finalist_a is user_team or finalist_b is user_team)
    watch = involves_user

    if not involves_user:
        ans = input("Watch the final? (Y/N): ").strip().upper()
        watch = ans == "Y"

    if watch:
        if finalist_b is user_team:
            finalist_a, finalist_b = finalist_b, finalist_a
        display_team(finalist_a)
        print()
        display_team(finalist_b)
        display_team_comparison(finalist_a, finalist_b)
        pause("Press Enter to simulate the final...")
        print(f"\n=== {finalist_a.name} vs {finalist_b.name} (FINAL) ===\n")

    result = simulate_match(finalist_a, finalist_b, watch=watch, is_final=True)

    if not watch:
        print(f"\nFINAL RESULT: {finalist_a.name} {result.goals_a} - {result.goals_b} {finalist_b.name}")
        if result.went_to_penalties:
            print(f"(Penalties: {result.penalty_score_a}-{result.penalty_score_b})")

    return result


# ---------------------------------------------------------------------------
# User selection
# ---------------------------------------------------------------------------

def select_user_team(player_pool: List[Player], team_name: str) -> Team:
    pool_by_id = {p.id: p for p in player_pool}

    while True:
        display_player_pool(player_pool)

        print("\nEnter a player ID to inspect details, or S to start selecting your team.")
        while True:
            cmd = input("> ").strip().upper()
            if cmd == "S":
                break
            try:
                pid = int(cmd)
                if pid in pool_by_id:
                    display_player_detail(pool_by_id[pid])
                else:
                    print("Invalid ID.")
            except ValueError:
                print("Enter a number or S.")

        print("\nSELECT YOUR TOURNAMENT TEAM")
        selected: Dict[str, Optional[Player]] = {"Goalie": None, "Defender1": None, "Defender2": None,
                                                   "Attacker1": None, "Attacker2": None}
        prompts = [
            ("Goalie", "Choose your goalie ID: "),
            ("Defender1", "Choose defender 1 ID: "),
            ("Defender2", "Choose defender 2 ID: "),
            ("Attacker1", "Choose attacker 1 ID: "),
            ("Attacker2", "Choose attacker 2 ID: "),
        ]
        used_ids: set = set()
        valid = True

        for slot, prompt in prompts:
            while True:
                try:
                    pid = int(input(prompt).strip())
                    if pid not in pool_by_id:
                        print("Invalid ID. Try again.")
                    elif pid in used_ids:
                        print("Already selected. Choose a different player.")
                    else:
                        selected[slot] = pool_by_id[pid]
                        used_ids.add(pid)
                        break
                except ValueError:
                    print("Enter a number.")

        # Assign roles
        role_map = [
            ("Goalie", "Goalie"),
            ("Defender1", "Defender"),
            ("Defender2", "Defender"),
            ("Attacker1", "Attacker"),
            ("Attacker2", "Attacker"),
        ]
        chosen: List[Player] = []
        for slot, role in role_map:
            p = selected[slot]
            p.assigned_role = role
            p.team_name = team_name
            chosen.append(p)

        print("\nYOUR TOURNAMENT TEAM\n")
        for p in chosen:
            role_short = {"Goalie": "GK", "Defender": "DF", "Attacker": "AT"}.get(p.assigned_role, "??")
            print(f"  {role_short}: {p.full_name()}")

        confirm = input("\nConfirm this team? (Y/N): ").strip().upper()
        if confirm == "Y":
            return Team(name=team_name, players=chosen, controlled_by_user=True)
        else:
            # Reset roles
            for p in chosen:
                p.assigned_role = "Unassigned"
                p.team_name = "TBD"


# ---------------------------------------------------------------------------
# Output file
# ---------------------------------------------------------------------------

def build_output_text(
    teams: List[Team],
    user_team: Team,
    match_results: List[MatchResult],
    final_result: MatchResult,
    champion: Team,
) -> str:
    lines: List[str] = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append("CLAUDFOOTY PROTOTYPE TOURNAMENT SUMMARY")
    lines.append(f"Generated: {now_str}")
    lines.append("")
    lines.append(f"Champion: {champion.name}")
    lines.append("")
    if final_result.went_to_penalties:
        lines.append(
            f"Final: {final_result.team_a.name} {final_result.goals_a} - {final_result.goals_b} "
            f"{final_result.team_b.name}  (Pens: {final_result.penalty_score_a}-{final_result.penalty_score_b})"
        )
    else:
        lines.append(f"Final: {final_result.team_a.name} {final_result.goals_a} - {final_result.goals_b} {final_result.team_b.name}")

    lines.append("")
    lines.append("=" * 60)
    lines.append("GROUP STAGE STANDINGS")
    lines.append("=" * 60)
    lines.append(f"{'Pos':<4} {'Team':<22} {'P':>3} {'W':>3} {'D':>3} {'L':>3} {'GF':>4} {'GA':>4} {'GD':>4} {'Pts':>4}")
    for i, t in enumerate(sort_standings(teams), 1):
        gd = t.goal_difference()
        gd_str = f"+{gd}" if gd > 0 else str(gd)
        lines.append(f"{i:<4} {t.name:<22} {t.played:>3} {t.wins:>3} {t.draws:>3} {t.losses:>3} {t.goals_for:>4} {t.goals_against:>4} {gd_str:>4} {t.points:>4}")

    lines.append("")
    lines.append("=" * 60)
    lines.append("MATCH RESULTS")
    lines.append("=" * 60)

    schedule = create_group_schedule(teams)
    # We'll just list results in order
    for round_num, (rnd, result) in enumerate(zip(schedule, match_results), 1):
        if round_num == 1 or (round_num > 1 and match_results[round_num - 2] != result):
            pass
    # Re-list results grouped
    num_group_results = len(match_results)
    for i in range(0, num_group_results, 2):
        rnd = i // 2 + 1
        lines.append(f"\nRound {rnd}:")
        for r in match_results[i:i+2]:
            if r.went_to_penalties:
                lines.append(f"  {r.team_a.name} {r.goals_a} - {r.goals_b} {r.team_b.name}  (Pens {r.penalty_score_a}-{r.penalty_score_b})")
            else:
                lines.append(f"  {r.team_a.name} {r.goals_a} - {r.goals_b} {r.team_b.name}")

    lines.append(f"\nFinal:")
    if final_result.went_to_penalties:
        lines.append(f"  {final_result.team_a.name} {final_result.goals_a} - {final_result.goals_b} {final_result.team_b.name}  (Pens {final_result.penalty_score_a}-{final_result.penalty_score_b})")
    else:
        lines.append(f"  {final_result.team_a.name} {final_result.goals_a} - {final_result.goals_b} {final_result.team_b.name}")

    lines.append("")
    lines.append("=" * 60)
    lines.append("TEAM STATS")
    lines.append("=" * 60)
    for t in sort_standings(teams):
        gd = t.goal_difference()
        gd_str = f"+{gd}" if gd > 0 else str(gd)
        lines.append(f"\n{t.name}")
        lines.append(f"  Played: {t.played}  Wins: {t.wins}  Draws: {t.draws}  Losses: {t.losses}")
        lines.append(f"  Goals For: {t.goals_for}  Goals Against: {t.goals_against}  GD: {gd_str}")
        lines.append(f"  Group Points: {t.points}")

    lines.append("")
    lines.append("=" * 60)
    lines.append("USER TEAM: SELECTED FIVE")
    lines.append("=" * 60)
    lines.append(f"\nTeam: {user_team.name}\n")

    for p in user_team.players:
        role_str = {"Goalie": "GK", "Defender": "DF", "Attacker": "AT"}.get(p.assigned_role, p.assigned_role)
        lines.append(f"{role_str} - {p.full_name()}")
        lines.append(f"  Age: {p.age}")
        lines.append(f"  Ratings:")
        lines.append(f"    Goalie:   {format_rating(goalie_rating(p))}")
        lines.append(f"    Defender: {format_rating(defender_rating(p))}")
        lines.append(f"    Attacker: {format_rating(attacker_rating(p))}")
        lines.append(f"    Overall:  {format_rating(overall_rating(p))}")
        lines.append(f"  Traits:")
        for trait in TRAITS:
            lines.append(f"    {trait}: {p.traits[trait]}")
        lines.append(f"  Tournament Stats:")
        lines.append(f"    Goals: {p.goals}  Shots: {p.shots}  Saves: {p.saves}  Goals Allowed: {p.goals_allowed}")
        lines.append(f"    Tackles: {p.tackles}  Key Passes: {p.key_passes}  Fouls: {p.fouls}")
        lines.append(f"    Yellow Cards: {p.yellow_cards}  Red Cards: {p.red_cards}")
        lines.append("")

    lines.append("=" * 60)
    lines.append("TOP SCORERS")
    lines.append("=" * 60)
    all_players: List[Player] = []
    for t in teams:
        all_players.extend(t.players)
    scorers = sorted([p for p in all_players if p.goals > 0], key=lambda x: -x.goals)
    for p in scorers[:10]:
        lines.append(f"  {p.full_name()} ({p.team_name}): {p.goals} goals")

    lines.append("")
    lines.append("=" * 60)
    lines.append("TOP GOALKEEPERS")
    lines.append("=" * 60)
    keepers = sorted([p for p in all_players if p.assigned_role == "Goalie"], key=lambda x: -x.saves)
    for p in keepers:
        lines.append(f"  {p.full_name()} ({p.team_name}): {p.saves} saves, {p.goals_allowed} conceded")

    return "\n".join(lines)


def generate_output_file(
    teams: List[Team],
    user_team: Team,
    match_results: List[MatchResult],
    final_result: MatchResult,
    champion: Team,
) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"{timestamp}_ClaudFootyPrototypeOutput.txt"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(script_dir, filename)

    content = build_output_text(teams, user_team, match_results, final_result, champion)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filename


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("\n" + "=" * 60)
    print("CLAUDFOOTY PROTOTYPE")
    print("=" * 60)
    print("\n1. Start new tournament")
    print("2. Quit")
    choice = input("\n> ").strip()
    if choice != "1":
        print("Goodbye.")
        return

    # Load names
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, CSV_NAME_FILE)
    male_first_names, last_names = load_name_bank(csv_path)

    # Team naming
    raw = input(f"\nEnter your team name, or press Enter for '{DEFAULT_USER_TEAM_NAME}': ").strip()
    user_team_name = raw if raw else DEFAULT_USER_TEAM_NAME

    # Generate user pool
    print("\nGenerating your 20-player pool...")
    user_pool = generate_user_player_pool(male_first_names, last_names)

    print("\nYour 20-player pool has been generated.")
    print("Review the players and choose your tournament five.\n")

    # User selection
    user_team = select_user_team(user_pool, user_team_name)

    # Generate CPU teams
    print("\nGenerating CPU teams...")
    cpu_teams: List[Team] = []
    for name in CPU_TEAM_NAMES:
        cpu_teams.append(generate_cpu_team(name, male_first_names, last_names))

    all_teams = [user_team] + cpu_teams

    print(f"\n{'='*60}")
    print("TOURNAMENT BEGINS")
    print(f"{'='*60}")
    print(f"\nTeams:")
    for t in all_teams:
        tag = " (YOU)" if t.controlled_by_user else ""
        print(f"  {t.name}{tag}")

    pause("\nPress Enter to start the group stage...")

    # Group stage
    group_results = play_group_stage(all_teams, user_team)

    # Final
    sorted_teams = sort_standings(all_teams)
    finalist_a = sorted_teams[0]
    finalist_b = sorted_teams[1]

    print(f"\n{'='*60}")
    print("GROUP STAGE COMPLETE")
    print(f"{'='*60}")
    print(f"\nFinalists: {finalist_a.name}  vs  {finalist_b.name}")

    final_result = play_final(finalist_a, finalist_b, user_team)
    champion = final_result.winner

    print(f"\n{'='*60}")
    print("TOURNAMENT CHAMPION")
    print(f"{'='*60}")
    print(f"\n  *** {champion.name} ***\n")

    print("Final standings (group stage):")
    display_standings(all_teams)

    # Output file
    filename = generate_output_file(all_teams, user_team, group_results, final_result, champion)
    print(f"\nTournament summary written to:\n  {filename}")

    pause("\nPress Enter to view the full tournament report...")
    print()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    report_path = os.path.join(script_dir, filename)
    with open(report_path, encoding="utf-8") as f:
        print(f.read())

    pause("Press Enter to close ClaudFooty...")
    print("\nThanks for playing. See you next tournament.\n")


if __name__ == "__main__":
    main()
