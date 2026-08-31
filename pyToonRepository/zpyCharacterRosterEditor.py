#!/usr/bin/env python3
"""
zpyCharacterRosterEditor.py

A standard-library Python 3 GUI for viewing and editing the zpy Universal
Character Master CSV roster.

Naming convention:
    Older scripts may use pyNameOfScript.
    Scripts using the universal zpy character schema should use zpyNameOfScript.

Default CSV discovery:
    The editor looks in the same folder as this script for:
        1. .universal_characters_master.csv
        2. universal_characters_master.csv

Core features:
    - Load a zpy roster CSV.
    - Visualize identity, political orientation, dynamic age, and attributes.
    - Edit identity fields, description, and all 1-99 attributes.
    - Add, duplicate, and delete characters.
    - Validate before saving.
    - Save over the current roster.
    - Save As to a manually chosen file.
    - Save New Version with a timestamped filename.
    - Preserve extra CSV columns not currently known to the zpy schema.

Dependencies:
    Python standard library only: csv, datetime, pathlib, tkinter.
"""

from __future__ import annotations

import csv
import random
import re
import tkinter as tk
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


APP_NAME = "zpyCharacterRosterEditor"
SCHEMA_NAME = "zpy"
SCHEMA_VERSION = "1.1"
DEFAULT_CSV_CANDIDATES = [
    ".universal_characters_master.csv",
    "universal_characters_master.csv",
]

RELIGION_CHOICES = [
    "Christian",
    "Atheist",
    "Muslim",
    "Hindu",
    "Buddhist",
    "Jewish",
    "Sikh",
    "Shinto",
    "Jain",
    "Taoist",
    "Rastafari",
    "Jedi",
    "Cylon",
    "Fremen",
    "Animist",
    "Sauron-worshipper",
]
SEX_CHOICES = ["", "F", "M", "X", "Other"]
SPECIES_DEFAULT = "human"


IDENTITY_FIELDS = [
    "schema_version",
    "character_id",
    "first_name",
    "last_name",
    "display_name",
    "short_name",
    "sex",
    "birth_year",
    "nationality",
    "religion",
    "left2right",
    "evil2good",
    "species",
    "height_cm",
    "weight_kg",
    "description",
]


PHYSICAL_ATTRS = [
    ("strength", "Strength"),
    ("stamina", "Stamina"),
    ("speed", "Speed"),
    ("agility", "Agility"),
    ("coordination", "Coordination"),
    ("dexterity", "Dexterity"),
    ("balance", "Balance"),
    ("recovery", "Recovery"),
    ("resilience", "Resilience"),
    ("metabolism", "Metabolism"),
    ("lifespan", "Lifespan"),
]

COGNITIVE_ATTRS = [
    ("intelligence", "Intelligence"),
    ("perception", "Perception"),
    ("focus", "Focus"),
    ("memory", "Memory"),
    ("creativity", "Creativity"),
    ("learning", "Learning"),
    ("technical_aptitude", "Technical Aptitude"),
    ("tactical_awareness", "Tactical Awareness"),
]

PSYCHOLOGICAL_ATTRS = [
    ("willpower", "Willpower"),
    ("faith", "Faith"),
    ("courage", "Courage"),
    ("composure", "Composure"),
    ("discipline", "Discipline"),
    ("determination", "Determination"),
    ("adaptability", "Adaptability"),
    ("patience", "Patience"),
    ("risk_assessment", "Risk Assessment"),
]

SOCIAL_ATTRS = [
    ("charisma", "Charisma"),
    ("empathy", "Empathy"),
    ("conversation", "Conversation"),
    ("deception", "Deception"),
    ("loyalty", "Loyalty"),
    ("aggression", "Aggression"),
]

ATTRIBUTE_GROUPS = [
    ("Physical Attributes", PHYSICAL_ATTRS),
    ("Cognitive Attributes", COGNITIVE_ATTRS),
    ("Psychological Attributes", PSYCHOLOGICAL_ATTRS),
    ("Social & Behavioural Attributes", SOCIAL_ATTRS),
]

ATTRIBUTE_FIELDS = [
    attr_key
    for _group_name, attr_list in ATTRIBUTE_GROUPS
    for attr_key, _attr_label in attr_list
]

SCHEMA_FIELDS = IDENTITY_FIELDS + ATTRIBUTE_FIELDS

RATING_FIELDS = ["left2right", "evil2good"] + ATTRIBUTE_FIELDS
MEASUREMENT_FIELDS = ["height_cm", "weight_kg"]
INTEGER_FIELDS = ["birth_year"] + RATING_FIELDS + MEASUREMENT_FIELDS

ATTRIBUTE_LABELS = {
    attr_key: attr_label
    for _group_name, attr_list in ATTRIBUTE_GROUPS
    for attr_key, attr_label in attr_list
}

ORIGIN_BASE_RATING = 55
ORIGIN_TRAIT_WEIGHTS = [10, 8, 6, 4, 2]

ORIGIN_BACKGROUNDS = {
    "Academic": {
        "intelligence": 7,
        "learning": 5,
        "memory": 3,
        "strength": -5,
        "aggression": -5,
        "stamina": -5,
    },
    "Athlete": {
        "stamina": 7,
        "coordination": 5,
        "speed": 3,
        "memory": -5,
        "deception": -5,
        "faith": -5,
    },
    "Artisan": {
        "dexterity": 7,
        "creativity": 5,
        "patience": 3,
        "aggression": -5,
        "speed": -5,
        "tactical_awareness": -5,
    },
    "Caregiver": {
        "empathy": 7,
        "patience": 5,
        "resilience": 3,
        "aggression": -7,
        "deception": -5,
        "speed": -3,
    },
    "Entertainer": {
        "charisma": 7,
        "conversation": 5,
        "creativity": 3,
        "discipline": -5,
        "risk_assessment": -5,
        "technical_aptitude": -5,
    },
    "Nomad": {
        "adaptability": 7,
        "resilience": 5,
        "perception": 3,
        "memory": -5,
        "loyalty": -5,
        "technical_aptitude": -5,
    },
    "Soldier": {
        "discipline": 7,
        "tactical_awareness": 5,
        "courage": 3,
        "creativity": -5,
        "empathy": -5,
        "conversation": -5,
    },
    "Street Survivor": {
        "perception": 7,
        "adaptability": 5,
        "deception": 3,
        "faith": -5,
        "patience": -5,
        "loyalty": -5,
    },
}

# Every answer changes exactly three attributes and has a net change of zero.
# Across the 20 selected answers this produces exactly 60 attribute changes,
# with all 34 character attributes represented at least once.
ORIGIN_QUESTIONS = [
    {
        "prompt": "You notice danger before anyone else. What do you do?",
        "answers": [
            ("Study it before acting", {"intelligence": 4, "risk_assessment": 2, "courage": -6}),
            ("Step forward immediately", {"courage": 6, "risk_assessment": -4, "intelligence": -2}),
            ("Move everyone to safety", {"risk_assessment": 6, "courage": -4, "intelligence": -2}),
        ],
    },
    {
        "prompt": "A stranger asks for help but may be hiding something. How do you respond?",
        "answers": [
            ("Trust their feelings", {"empathy": 6, "deception": -4, "charisma": -2}),
            ("Charm out the truth", {"charisma": 6, "empathy": -4, "deception": -2}),
            ("Conceal your doubts and investigate", {"deception": 6, "charisma": -4, "empathy": -2}),
        ],
    },
    {
        "prompt": "Your community must cross difficult terrain. What role do you take?",
        "answers": [
            ("Carry the heaviest supplies", {"strength": 6, "agility": -4, "stamina": -2}),
            ("Scout the quickest route", {"agility": 6, "strength": -4, "stamina": -2}),
            ("Keep a steady pace all day", {"stamina": 6, "agility": -4, "strength": -2}),
        ],
    },
    {
        "prompt": "A machine nobody understands stops working. What is your approach?",
        "answers": [
            ("Diagnose it methodically", {"technical_aptitude": 6, "creativity": -4, "patience": -2}),
            ("Invent an unconventional repair", {"creativity": 6, "technical_aptitude": -4, "patience": -2}),
            ("Test one possibility at a time", {"patience": 6, "creativity": -4, "technical_aptitude": -2}),
        ],
    },
    {
        "prompt": "Two groups you care about become rivals. Where do you stand?",
        "answers": [
            ("Remain fiercely loyal to your own", {"loyalty": 6, "adaptability": -4, "aggression": -2}),
            ("Adapt and seek common ground", {"adaptability": 6, "loyalty": -4, "aggression": -2}),
            ("Force the dispute to a conclusion", {"aggression": 6, "adaptability": -4, "loyalty": -2}),
        ],
    },
    {
        "prompt": "Something moves at the edge of your vision. How do you react?",
        "answers": [
            ("Watch for the smallest detail", {"perception": 6, "speed": -4, "focus": -2}),
            ("Concentrate and identify it", {"focus": 6, "speed": -4, "perception": -2}),
            ("Sprint to intercept it", {"speed": 6, "focus": -4, "perception": -2}),
        ],
    },
    {
        "prompt": "A tense meeting is falling apart. What do you contribute?",
        "answers": [
            ("Keep everyone to the agreed rules", {"discipline": 6, "conversation": -4, "willpower": -2}),
            ("Talk until people understand each other", {"conversation": 6, "discipline": -4, "willpower": -2}),
            ("Refuse to let the meeting fail", {"willpower": 6, "conversation": -4, "discipline": -2}),
        ],
    },
    {
        "prompt": "You are learning a precise physical craft. What comes most naturally?",
        "answers": [
            ("Synchronizing every movement", {"coordination": 6, "dexterity": -4, "balance": -2}),
            ("Performing delicate handwork", {"dexterity": 6, "balance": -4, "coordination": -2}),
            ("Remaining stable under pressure", {"balance": 6, "coordination": -4, "dexterity": -2}),
        ],
    },
    {
        "prompt": "You must master a complicated new strategy. How do you learn it?",
        "answers": [
            ("Absorb new lessons rapidly", {"learning": 6, "memory": -4, "tactical_awareness": -2}),
            ("Memorize every established pattern", {"memory": 6, "tactical_awareness": -4, "learning": -2}),
            ("Study how choices alter the whole field", {"tactical_awareness": 6, "learning": -4, "memory": -2}),
        ],
    },
    {
        "prompt": "After a serious setback, what gets you moving again?",
        "answers": [
            ("Endure whatever comes next", {"resilience": 6, "recovery": -4, "metabolism": -2}),
            ("Rest and rebuild carefully", {"recovery": 6, "resilience": -4, "metabolism": -2}),
            ("Rely on your body's natural energy", {"metabolism": 6, "recovery": -4, "resilience": -2}),
        ],
    },
    {
        "prompt": "A long effort offers no guarantee of success. What sustains you?",
        "answers": [
            ("Belief that the effort has meaning", {"faith": 6, "composure": -4, "determination": -2}),
            ("Calm control of your emotions", {"composure": 6, "determination": -4, "faith": -2}),
            ("A refusal to stop", {"determination": 6, "faith": -4, "composure": -2}),
        ],
    },
    {
        "prompt": "How do you think about your future?",
        "answers": [
            ("Protect a long and healthy life", {"lifespan": 6, "risk_assessment": -4, "stamina": -2}),
            ("Build endurance for years of work", {"stamina": 6, "lifespan": -4, "risk_assessment": -2}),
            ("Avoid dangers that shorten lives", {"risk_assessment": 6, "stamina": -4, "lifespan": -2}),
        ],
    },
    {
        "prompt": "Someone publicly insults a vulnerable person. What do you do?",
        "answers": [
            ("Explain why the insult is wrong", {"intelligence": 6, "aggression": -4, "empathy": -2}),
            ("Comfort the person who was hurt", {"empathy": 6, "intelligence": -4, "aggression": -2}),
            ("Confront the offender directly", {"aggression": 6, "empathy": -4, "intelligence": -2}),
        ],
    },
    {
        "prompt": "You are given an important project with no instructions. What comes first?",
        "answers": [
            ("Imagine what it could become", {"creativity": 6, "discipline": -4, "technical_aptitude": -2}),
            ("Determine the tools and mechanisms", {"technical_aptitude": 6, "creativity": -4, "discipline": -2}),
            ("Create a strict working schedule", {"discipline": 6, "technical_aptitude": -4, "creativity": -2}),
        ],
    },
    {
        "prompt": "A friend asks you to keep a dangerous secret. What matters most?",
        "answers": [
            ("Having the courage to challenge them", {"courage": 6, "loyalty": -4, "deception": -2}),
            ("Remaining loyal despite the risk", {"loyalty": 6, "deception": -4, "courage": -2}),
            ("Hiding what you know convincingly", {"deception": 6, "courage": -4, "loyalty": -2}),
        ],
    },
    {
        "prompt": "You arrive alone at an unfamiliar social gathering. What do you do?",
        "answers": [
            ("Make a memorable entrance", {"charisma": 6, "patience": -4, "conversation": -2}),
            ("Begin conversations with everyone", {"conversation": 6, "charisma": -4, "patience": -2}),
            ("Observe quietly until the right moment", {"patience": 6, "conversation": -4, "charisma": -2}),
        ],
    },
    {
        "prompt": "A physical contest begins without warning. What is your advantage?",
        "answers": [
            ("Raw power", {"strength": 6, "speed": -4, "agility": -2}),
            ("Explosive quickness", {"speed": 6, "agility": -4, "strength": -2}),
            ("Evasive movement", {"agility": 6, "strength": -4, "speed": -2}),
        ],
    },
    {
        "prompt": "Your original plan becomes impossible. What happens next?",
        "answers": [
            ("Notice an overlooked opportunity", {"perception": 6, "adaptability": -4, "focus": -2}),
            ("Concentrate on the original objective", {"focus": 6, "perception": -4, "adaptability": -2}),
            ("Reshape the plan immediately", {"adaptability": 6, "focus": -4, "perception": -2}),
        ],
    },
    {
        "prompt": "You suffer a hard fall during an urgent task. What helps most?",
        "answers": [
            ("Controlling your movement", {"coordination": 6, "recovery": -4, "balance": -2}),
            ("Staying upright through impact", {"balance": 6, "coordination": -4, "recovery": -2}),
            ("Getting back up immediately", {"recovery": 6, "balance": -4, "coordination": -2}),
        ],
    },
    {
        "prompt": "You decide to become excellent at a difficult subject. What drives progress?",
        "answers": [
            ("Retaining everything you study", {"memory": 6, "willpower": -4, "learning": -2}),
            ("Improving with every attempt", {"learning": 6, "memory": -4, "willpower": -2}),
            ("Continuing when study becomes painful", {"willpower": 6, "learning": -4, "memory": -2}),
        ],
    },
]

# Preference questions intentionally raise the overall average. Every choice
# adds 10 to one attribute and subtracts 2 from another, for a net gain of 8.
ORIGIN_FAVORITE_QUESTIONS = [
    {
        "prompt": "Which kind of fictional character is usually your favourite?",
        "answers": [
            ("The brilliant inventor", {"technical_aptitude": 10, "strength": -2}),
            ("The fearless warrior", {"courage": 10, "patience": -2}),
            ("The compassionate healer", {"empathy": 10, "aggression": -2}),
            ("The clever detective", {"perception": 10, "faith": -2}),
            ("The charming rogue", {"charisma": 10, "loyalty": -2}),
        ],
    },
    {
        "prompt": "Which food sounds best right now?",
        "answers": [
            ("A hearty stew", {"stamina": 10, "speed": -2}),
            ("A fiery curry", {"courage": 10, "composure": -2}),
            ("Fresh fruit", {"metabolism": 10, "resilience": -2}),
            ("An elaborate dessert", {"creativity": 10, "discipline": -2}),
            ("Freshly baked bread", {"patience": 10, "charisma": -2}),
        ],
    },
    {
        "prompt": "Which colour appeals to you most?",
        "answers": [
            ("Red", {"aggression": 10, "patience": -2}),
            ("Blue", {"composure": 10, "aggression": -2}),
            ("Green", {"empathy": 10, "deception": -2}),
            ("Gold", {"charisma": 10, "risk_assessment": -2}),
            ("Purple", {"creativity": 10, "discipline": -2}),
        ],
    },
    {
        "prompt": "Which animal would you most want as a companion?",
        "answers": [
            ("Wolf", {"loyalty": 10, "conversation": -2}),
            ("Owl", {"intelligence": 10, "strength": -2}),
            ("Cat", {"agility": 10, "loyalty": -2}),
            ("Horse", {"stamina": 10, "dexterity": -2}),
            ("Dolphin", {"conversation": 10, "composure": -2}),
        ],
    },
    {
        "prompt": "How would you most enjoy spending a free afternoon?",
        "answers": [
            ("Reading a book", {"memory": 10, "speed": -2}),
            ("Building something", {"technical_aptitude": 10, "charisma": -2}),
            ("Playing a sport", {"coordination": 10, "focus": -2}),
            ("Painting or writing", {"creativity": 10, "risk_assessment": -2}),
            ("Meeting friends", {"conversation": 10, "discipline": -2}),
        ],
    },
    {
        "prompt": "Which kind of weather feels most inspiring?",
        "answers": [
            ("Bright sunshine", {"composure": 10, "perception": -2}),
            ("A thunderstorm", {"courage": 10, "risk_assessment": -2}),
            ("Falling snow", {"resilience": 10, "speed": -2}),
            ("Steady rain", {"focus": 10, "charisma": -2}),
            ("A powerful wind", {"adaptability": 10, "balance": -2}),
        ],
    },
    {
        "prompt": "Which place would you most like to explore?",
        "answers": [
            ("An ancient library", {"learning": 10, "aggression": -2}),
            ("A busy workshop", {"dexterity": 10, "empathy": -2}),
            ("A deep forest", {"perception": 10, "technical_aptitude": -2}),
            ("A remote mountain", {"resilience": 10, "conversation": -2}),
            ("A crowded market", {"charisma": 10, "focus": -2}),
        ],
    },
    {
        "prompt": "Which style of music would you choose first?",
        "answers": [
            ("Classical", {"focus": 10, "aggression": -2}),
            ("Rock", {"determination": 10, "patience": -2}),
            ("Jazz", {"adaptability": 10, "discipline": -2}),
            ("Folk", {"faith": 10, "deception": -2}),
            ("Electronic", {"technical_aptitude": 10, "empathy": -2}),
        ],
    },
    {
        "prompt": "Which kind of game is most appealing?",
        "answers": [
            ("Chess or strategy", {"tactical_awareness": 10, "agility": -2}),
            ("Puzzles and riddles", {"intelligence": 10, "stamina": -2}),
            ("Racing", {"risk_assessment": 10, "patience": -2}),
            ("A team sport", {"loyalty": 10, "deception": -2}),
            ("Role-playing adventures", {"creativity": 10, "strength": -2}),
        ],
    },
    {
        "prompt": "Which useful object would you prefer to carry?",
        "answers": [
            ("A sturdy hammer", {"strength": 10, "dexterity": -2}),
            ("A precision knife", {"dexterity": 10, "strength": -2}),
            ("A detailed map", {"tactical_awareness": 10, "faith": -2}),
            ("A personal journal", {"memory": 10, "speed": -2}),
            ("A versatile multi-tool", {"adaptability": 10, "focus": -2}),
        ],
    },
]

HOUSEHOLD_CHOICES = {
    "Leo": {"intelligence": 10},
    "Jojo": {"aggression": 10},
    "Athena": {"creativity": 15, "discipline": -5},
    "Elliot": {"technical_aptitude": 5, "determination": 10, "courage": -5},
    "Evander": {"strength": 15, "resilience": -5},
    "Alice": {
        "willpower": 5,
        "patience": -5,
        "aggression": 5,
        "metabolism": 5,
        "stamina": 5,
    },
    "Gerald": {"metabolism": 20, "lifespan": -10},
    "Catherine": {"lifespan": -5, "balance": 15},
}


def get_rating_color(value: int) -> str:
    """Return a colour reflecting the zpy 1-99 rating band."""
    if value <= 9:
        return "#991B1B"
    if value <= 24:
        return "#DC2626"
    if value <= 39:
        return "#D97706"
    if value <= 59:
        return "#4B5563"
    if value <= 74:
        return "#65A30D"
    if value <= 89:
        return "#16A34A"
    if value <= 98:
        return "#0D9488"
    return "#7C3AED"


def get_rating_desc(value: int) -> str:
    """Return a compact textual interpretation of a zpy 1-99 rating."""
    if value <= 9:
        return "Extremely low"
    if value <= 24:
        return "Very low"
    if value <= 39:
        return "Below average"
    if value <= 59:
        return "Average range"
    if value <= 74:
        return "Above average"
    if value <= 89:
        return "Excellent"
    if value <= 98:
        return "Exceptional"
    return "Maximum (99)"


def get_political_label(value: int) -> str:
    """Return a compact political-orientation label for left2right."""
    if value <= 15:
        return "Far Left"
    if value <= 39:
        return "Left-Leaning"
    if value <= 44:
        return "Center-Left"
    if value <= 56:
        return "Political Centre"
    if value <= 61:
        return "Center-Right"
    if value <= 84:
        return "Right-Leaning"
    return "Far Right"


def get_moral_label(value: int) -> str:
    """Return a compact moral-alignment label for evil2good."""
    if value <= 15:
        return "Profoundly Evil"
    if value <= 39:
        return "Evil-Leaning"
    if value <= 44:
        return "Morally Troubled"
    if value <= 56:
        return "Morally Neutral"
    if value <= 61:
        return "Good-Leaning"
    if value <= 84:
        return "Good"
    return "Profoundly Good"


def safe_int(value: object, default: int | None = None) -> int | None:
    """Convert a CSV value to int, returning default on failure."""
    try:
        text = str(value).strip()
        if text == "":
            return default
        return int(float(text))
    except (TypeError, ValueError):
        return default


def clean_cell(value: object) -> str:
    """Normalize a CSV cell to a stripped string."""
    if value is None:
        return ""
    return str(value).strip()


def canonicalize_religion(value: object) -> str:
    """Return the roster's preferred capitalization for a known religion."""
    cleaned = clean_cell(value)
    matches = {choice.casefold(): choice for choice in RELIGION_CHOICES}
    return matches.get(cleaned.casefold(), cleaned)


def format_origin_effects(effects: dict[str, int]) -> str:
    """Return a readable summary of one balanced Origin Story answer."""
    return ", ".join(
        f"{ATTRIBUTE_LABELS[field]} {change:+d}"
        for field, change in effects.items()
    )


def calculate_average_rank_curve(
    characters: list[dict[str, str]],
) -> list[float] | None:
    """Return the average low-to-high attribute curve of original roster rows."""

    def valid_profiles(rows: list[dict[str, str]]) -> list[list[int]]:
        profiles: list[list[int]] = []
        for character in rows:
            values = [safe_int(character.get(field), None) for field in ATTRIBUTE_FIELDS]
            if any(value is None or not 1 <= value <= 99 for value in values):
                continue
            profiles.append(sorted(int(value) for value in values if value is not None))
        return profiles

    original_rows = [
        character
        for character in characters
        if clean_cell(character.get("schema_version", "")) == "1.0"
    ]
    profiles = valid_profiles(original_rows)
    if not profiles:
        profiles = valid_profiles(characters)
    if not profiles:
        return None

    return [
        sum(profile[position] for profile in profiles) / len(profiles)
        for position in range(len(ATTRIBUTE_FIELDS))
    ]


def mould_middle_scores_to_average_curve(
    scores: dict[str, int],
    ranked_fields: list[str],
    average_rank_curve: list[float] | None,
) -> dict[str, int]:
    """Nudge middle ratings toward the average roster shape at constant total."""
    if average_rank_curve is None or len(average_rank_curve) != len(ATTRIBUTE_FIELDS):
        return dict(scores)

    adjusted = dict(scores)
    middle_fields = ranked_fields[5:-5]
    values = [adjusted[field] for field in middle_fields]
    curve = average_rank_curve[5:-5]
    if not values:
        return adjusted

    current_mean = sum(values) / len(values)
    curve_mean = sum(curve) / len(curve)
    normalized_curve = [current_mean + (value - curve_mean) for value in curve]

    # Blend halfway toward the aggregate curve. Both sequences are ordered and
    # have the same mean, so the targets preserve rank and total power.
    targets = [
        (current + target) / 2.0
        for current, target in zip(values, normalized_curve)
    ]
    lower_bound = adjusted[ranked_fields[4]]
    upper_bound = adjusted[ranked_fields[-5]]
    targets = [max(lower_bound, min(upper_bound, target)) for target in targets]

    # Transfer points only within the middle group. Every +1 is paired with a
    # -1, top/bottom values remain frozen, and the established ordering cannot flip.
    for _transfer in range(2000):
        donors = [
            index
            for index, value in enumerate(values)
            if value > targets[index] + 0.5
            and value - 1 >= lower_bound
            and (index == 0 or value - 1 >= values[index - 1])
        ]
        receivers = [
            index
            for index, value in enumerate(values)
            if value < targets[index] - 0.5
            and value + 1 <= upper_bound
            and (index == len(values) - 1 or value + 1 <= values[index + 1])
        ]
        if not donors or not receivers:
            break

        valid_pairs: list[tuple[int, int]] = []
        for donor in donors:
            for receiver in receivers:
                if donor == receiver:
                    continue
                trial = list(values)
                trial[donor] -= 1
                trial[receiver] += 1
                if trial == sorted(trial):
                    valid_pairs.append((donor, receiver))
        if not valid_pairs:
            break

        donor, receiver = max(
            valid_pairs,
            key=lambda pair: (
                values[pair[0]] - targets[pair[0]]
                + targets[pair[1]] - values[pair[1]]
            ),
        )
        values[donor] -= 1
        values[receiver] += 1

    for field, value in zip(middle_fields, values):
        adjusted[field] = value
    return adjusted


def apply_origin_final_adjustments(
    scores: dict[str, int],
    positive_traits: list[str],
    average_rank_curve: list[float] | None = None,
) -> dict[str, int]:
    """Apply final specialization boosts and penalties, constrained to 1-99."""
    adjusted = dict(scores)
    schema_position = {
        field: position for position, field in enumerate(ATTRIBUTE_FIELDS)
    }

    # Rank once so tied values cannot place the same attribute in both groups.
    ranked = sorted(
        ATTRIBUTE_FIELDS,
        key=lambda field: (adjusted[field], schema_position[field]),
    )
    lowest_five = ranked[:5]
    highest_five = ranked[-5:]

    for field in highest_five:
        value = adjusted[field]
        if value < 80:
            adjusted[field] = 80 + (value % 10)
        elif value < 90:
            adjusted[field] = 90 + (value % 10)

    for field in lowest_five:
        adjusted[field] -= 5

    adjusted = mould_middle_scores_to_average_curve(
        adjusted,
        ranked,
        average_rank_curve,
    )

    # The weakest of the five selected positive traits becomes the defining
    # strong suit after every other score change has been applied.
    strong_suit = min(
        positive_traits,
        key=lambda field: (adjusted[field], schema_position[field]),
    )
    adjusted[strong_suit] = 99

    return {
        field: max(1, min(99, value))
        for field, value in adjusted.items()
    }


def calculate_origin_scores(
    answer_indices: list[int],
    favorite_answer_indices: list[int],
    background_choice: str,
    positive_traits: list[str],
    negative_traits: list[str],
    correct_math_answers: int,
    household_choice: str,
    average_rank_curve: list[float] | None = None,
) -> dict[str, int]:
    """Calculate final Origin Story ratings from the completed questionnaire."""
    if len(answer_indices) != len(ORIGIN_QUESTIONS):
        raise ValueError("Every Origin Story question must have an answer.")
    if len(favorite_answer_indices) != len(ORIGIN_FAVORITE_QUESTIONS):
        raise ValueError("Every preference question must have an answer.")
    if background_choice not in ORIGIN_BACKGROUNDS:
        raise ValueError("A formative background is required.")
    if len(positive_traits) != 5 or len(set(positive_traits)) != 5:
        raise ValueError("Exactly five different positive traits are required.")
    if len(negative_traits) != 5 or len(set(negative_traits)) != 5:
        raise ValueError("Exactly five different negative traits are required.")
    if set(positive_traits) & set(negative_traits):
        raise ValueError("Positive and negative traits cannot overlap.")
    if not 0 <= correct_math_answers <= 2:
        raise ValueError("The number of correct math answers must be from zero to two.")
    if household_choice not in HOUSEHOLD_CHOICES:
        raise ValueError("A household choice is required.")

    scores = {field: ORIGIN_BASE_RATING for field in RATING_FIELDS}

    for question, answer_index in zip(ORIGIN_QUESTIONS, answer_indices):
        answers = question["answers"]
        if answer_index not in range(len(answers)):
            raise ValueError("An Origin Story answer is invalid.")
        _answer_text, effects = answers[answer_index]
        for field, change in effects.items():
            scores[field] += change

    for question, answer_index in zip(
        ORIGIN_FAVORITE_QUESTIONS,
        favorite_answer_indices,
    ):
        answers = question["answers"]
        if answer_index not in range(len(answers)):
            raise ValueError("A preference answer is invalid.")
        _answer_text, effects = answers[answer_index]
        for field, change in effects.items():
            scores[field] += change

    for field, change in ORIGIN_BACKGROUNDS[background_choice].items():
        scores[field] += change

    for field, change in zip(positive_traits, ORIGIN_TRAIT_WEIGHTS):
        scores[field] += change
    for field, change in zip(negative_traits, ORIGIN_TRAIT_WEIGHTS):
        scores[field] -= change

    # Recalculate the weakest attribute after each correct answer. If several
    # are tied, the stable schema order determines which receives the point bonus.
    for _correct_answer in range(correct_math_answers):
        weakest = min(ATTRIBUTE_FIELDS, key=lambda field: scores[field])
        scores[weakest] += 2

    for field, change in HOUSEHOLD_CHOICES[household_choice].items():
        scores[field] += change

    return apply_origin_final_adjustments(
        scores,
        positive_traits,
        average_rank_curve,
    )


class OriginStoryWizard(tk.Toplevel):
    """Modal questionnaire that creates a schema 1.1 character record."""

    BACKGROUND_STEP = 1
    QUESTIONS_FIRST_STEP = BACKGROUND_STEP + 1
    FAVORITES_FIRST_STEP = QUESTIONS_FIRST_STEP + len(ORIGIN_QUESTIONS)
    POSITIVE_TRAITS_STEP = FAVORITES_FIRST_STEP + len(ORIGIN_FAVORITE_QUESTIONS)
    NEGATIVE_TRAITS_STEP = POSITIVE_TRAITS_STEP + 1
    MATH_STEP = NEGATIVE_TRAITS_STEP + 1
    LAST_STEP = MATH_STEP + 1
    TOTAL_STEPS = LAST_STEP + 1

    def __init__(
        self,
        parent: tk.Tk,
        fieldnames: list[str],
        character_id: str,
        average_rank_curve: list[float] | None,
    ) -> None:
        super().__init__(parent)
        self.parent = parent
        self.fieldnames = fieldnames
        self.character_id = character_id
        self.average_rank_curve = average_rank_curve
        self.result: dict[str, str] | None = None
        self.correct_math_answers = 0
        self.step = 0

        self.title("Origin Story Character Creator")
        self.geometry("820x690")
        self.minsize(720, 600)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.basic_vars = {
            "first_name": tk.StringVar(),
            "last_name": tk.StringVar(),
            "display_name": tk.StringVar(),
            "species": tk.StringVar(value=SPECIES_DEFAULT),
            "religion": tk.StringVar(value=RELIGION_CHOICES[0]),
            "nationality": tk.StringVar(),
            "birth_year": tk.StringVar(value="2000"),
            "height_cm": tk.StringVar(value="170"),
            "weight_kg": tk.StringVar(value="70"),
            "sex": tk.StringVar(),
        }
        self.background_var = tk.StringVar()
        self.answer_vars = [tk.IntVar(value=-1) for _question in ORIGIN_QUESTIONS]
        self.favorite_answer_vars = [
            tk.IntVar(value=-1) for _question in ORIGIN_FAVORITE_QUESTIONS
        ]
        self.positive_vars = [tk.StringVar() for _slot in range(5)]
        self.negative_vars = [tk.StringVar() for _slot in range(5)]
        self.math_problems = [
            (random.randint(1, 9999), random.randint(1, 9999))
            for _problem in range(2)
        ]
        self.math_vars = [tk.StringVar() for _problem in range(2)]
        self.household_var = tk.StringVar()

        self.progress_var = tk.StringVar()
        self.heading_var = tk.StringVar()

        top = ttk.Frame(self, padding=(18, 14, 18, 8))
        top.pack(fill="x")
        ttk.Label(
            top,
            textvariable=self.heading_var,
            font=("Arial", 16, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            top,
            textvariable=self.progress_var,
            foreground="#475569",
        ).pack(anchor="w", pady=(3, 0))

        separator = ttk.Separator(self, orient="horizontal")
        separator.pack(fill="x")

        self.content = ttk.Frame(self, padding=18)
        self.content.pack(fill="both", expand=True)

        nav = ttk.Frame(self, padding=(18, 8, 18, 14))
        nav.pack(fill="x", side="bottom")
        self.cancel_button = ttk.Button(nav, text="Cancel", command=self.cancel)
        self.cancel_button.pack(side="left")
        self.back_button = ttk.Button(nav, text="Back", command=self.go_back)
        self.back_button.pack(side="right", padx=(6, 0))
        self.next_button = ttk.Button(nav, text="Next", command=self.go_next)
        self.next_button.pack(side="right")

        self.render_step()
        self.grab_set()
        self.focus_force()

    def clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def render_step(self) -> None:
        self.clear_content()
        self.back_button.config(state="disabled" if self.step == 0 else "normal")
        self.next_button.config(text="Create Character" if self.step == self.LAST_STEP else "Next")

        if self.step == 0:
            self.render_basics()
        elif self.step == self.BACKGROUND_STEP:
            self.render_background()
        elif self.QUESTIONS_FIRST_STEP <= self.step < self.FAVORITES_FIRST_STEP:
            self.render_question(self.step - self.QUESTIONS_FIRST_STEP)
        elif self.FAVORITES_FIRST_STEP <= self.step < self.POSITIVE_TRAITS_STEP:
            self.render_favorite_question(self.step - self.FAVORITES_FIRST_STEP)
        elif self.step == self.POSITIVE_TRAITS_STEP:
            self.render_traits(positive=True)
        elif self.step == self.NEGATIVE_TRAITS_STEP:
            self.render_traits(positive=False)
        elif self.step == self.MATH_STEP:
            self.render_math()
        else:
            self.render_household_choice()

    def render_basics(self) -> None:
        self.heading_var.set("Basic Character Information")
        self.progress_var.set(
            f"Step 1 of {self.TOTAL_STEPS} — identity and dimensions"
        )

        ttk.Label(
            self.content,
            text=(
                f"Character ID {self.character_id} and short name "
                f"{self.character_id[-3:]} will be assigned automatically."
            ),
            wraplength=740,
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 14))

        fields = [
            ("first_name", "First Name", "entry"),
            ("last_name", "Last Name", "entry"),
            ("display_name", "Display Name", "entry"),
            ("species", "Species", "entry"),
            ("religion", "Religion", "religion"),
            ("nationality", "Nationality", "entry"),
            ("birth_year", "Birth Year", "entry"),
            ("height_cm", "Height (cm)", "entry"),
            ("weight_kg", "Weight (kg)", "entry"),
            ("sex", "Sex", "sex"),
        ]
        for index, (field, label, widget_type) in enumerate(fields):
            row = index // 2 + 1
            column = (index % 2) * 2
            ttk.Label(self.content, text=f"{label}:", font=("Arial", 9, "bold")).grid(
                row=row,
                column=column,
                sticky="e",
                padx=(0, 7),
                pady=7,
            )
            if widget_type == "religion":
                widget = ttk.Combobox(
                    self.content,
                    textvariable=self.basic_vars[field],
                    values=RELIGION_CHOICES,
                    state="readonly",
                )
            elif widget_type == "sex":
                widget = ttk.Combobox(
                    self.content,
                    textvariable=self.basic_vars[field],
                    values=SEX_CHOICES[1:],
                    state="readonly",
                )
            else:
                widget = ttk.Entry(self.content, textvariable=self.basic_vars[field])
            widget.grid(row=row, column=column + 1, sticky="ew", padx=(0, 18), pady=7)

        self.content.columnconfigure(1, weight=1)
        self.content.columnconfigure(3, weight=1)

    def render_background(self) -> None:
        self.heading_var.set("Formative Background")
        self.progress_var.set(
            f"Step {self.step + 1} of {self.TOTAL_STEPS} — early life"
        )
        ttk.Label(
            self.content,
            text=(
                "Choose the background that best represents the character's upbringing. "
                "Every background strengthens three related attributes and weakens three "
                "others with a net point change of zero."
            ),
            wraplength=740,
        ).pack(anchor="w", pady=(0, 12))

        for background, effects in ORIGIN_BACKGROUNDS.items():
            option = ttk.Frame(self.content, padding=(8, 4))
            option.pack(fill="x", pady=2)
            ttk.Radiobutton(
                option,
                variable=self.background_var,
                value=background,
                text=background,
            ).pack(anchor="w")
            ttk.Label(
                option,
                text=format_origin_effects(effects),
                foreground="#475569",
                wraplength=700,
            ).pack(anchor="w", padx=(25, 0), pady=(1, 0))

    def render_question(self, question_index: int) -> None:
        question = ORIGIN_QUESTIONS[question_index]
        self.heading_var.set(f"Origin Question {question_index + 1} of 20")
        self.progress_var.set(
            f"Step {self.step + 1} of {self.TOTAL_STEPS} — balanced attribute choice"
        )

        ttk.Label(
            self.content,
            text=question["prompt"],
            font=("Arial", 13, "bold"),
            wraplength=740,
            justify="left",
        ).pack(anchor="w", pady=(0, 18))

        for answer_index, (answer_text, effects) in enumerate(question["answers"]):
            option = ttk.Frame(self.content, padding=(8, 7))
            option.pack(fill="x", pady=5)
            ttk.Radiobutton(
                option,
                variable=self.answer_vars[question_index],
                value=answer_index,
                text=answer_text,
            ).pack(anchor="w")
            ttk.Label(
                option,
                text=format_origin_effects(effects),
                foreground="#475569",
                wraplength=700,
            ).pack(anchor="w", padx=(25, 0), pady=(2, 0))

        ttk.Label(
            self.content,
            text="Every answer changes three attributes and always totals exactly zero.",
            font=("Arial", 9, "italic"),
            foreground="#64748B",
        ).pack(anchor="w", pady=(18, 0))

    def render_favorite_question(self, question_index: int) -> None:
        question = ORIGIN_FAVORITE_QUESTIONS[question_index]
        self.heading_var.set(
            f"Preference Question {question_index + 1} of "
            f"{len(ORIGIN_FAVORITE_QUESTIONS)}"
        )
        self.progress_var.set(
            f"Step {self.step + 1} of {self.TOTAL_STEPS} — preference bonus"
        )

        ttk.Label(
            self.content,
            text=question["prompt"],
            font=("Arial", 13, "bold"),
            wraplength=740,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        for answer_index, (answer_text, effects) in enumerate(question["answers"]):
            option = ttk.Frame(self.content, padding=(8, 4))
            option.pack(fill="x", pady=2)
            ttk.Radiobutton(
                option,
                variable=self.favorite_answer_vars[question_index],
                value=answer_index,
                text=answer_text,
            ).pack(anchor="w")
            ttk.Label(
                option,
                text=format_origin_effects(effects),
                foreground="#475569",
                wraplength=700,
            ).pack(anchor="w", padx=(25, 0), pady=(1, 0))

        ttk.Label(
            self.content,
            text="Every preference gives +10 to one attribute and −2 to another (net +8).",
            font=("Arial", 9, "italic"),
            foreground="#64748B",
        ).pack(anchor="w", pady=(12, 0))

    def render_traits(self, positive: bool) -> None:
        direction = "Positive" if positive else "Negative"
        self.heading_var.set(f"Choose Five {direction} Traits")
        self.progress_var.set(
            f"Step {self.step + 1} of {self.TOTAL_STEPS} — "
            + ("ordered bonuses" if positive else "ordered penalties")
        )
        values = [ATTRIBUTE_LABELS[field] for field in ATTRIBUTE_FIELDS]
        variables = self.positive_vars if positive else self.negative_vars
        signs = "+" if positive else "−"

        ttk.Label(
            self.content,
            text=(
                "Order matters. Select five different attributes; the first receives "
                f"{signs}10, followed by {signs}8, {signs}6, {signs}4, and {signs}2."
            ),
            wraplength=740,
        ).pack(anchor="w", pady=(0, 14))

        final_effect = (
            "After all scoring, the lowest of these five positive traits becomes 99."
            if positive
            else "After all scoring, the character's five lowest attributes each lose another 5."
        )
        ttk.Label(
            self.content,
            text=final_effect,
            foreground="#475569",
            font=("Arial", 9, "italic"),
            wraplength=740,
        ).pack(anchor="w", pady=(0, 10))

        grid = ttk.Frame(self.content)
        grid.pack(fill="x")
        grid.columnconfigure(2, weight=1)
        for index, (variable, weight) in enumerate(zip(variables, ORIGIN_TRAIT_WEIGHTS)):
            ttk.Label(grid, text=f"Priority {index + 1}:", font=("Arial", 9, "bold")).grid(
                row=index,
                column=0,
                sticky="e",
                padx=(0, 8),
                pady=7,
            )
            ttk.Label(grid, text=f"{signs}{weight}", width=4).grid(
                row=index,
                column=1,
                sticky="w",
                padx=(0, 8),
            )
            ttk.Combobox(
                grid,
                textvariable=variable,
                values=values,
                state="readonly",
            ).grid(row=index, column=2, sticky="ew", pady=7)

    def render_math(self) -> None:
        self.heading_var.set("Two Addition Questions")
        self.progress_var.set(
            f"Step {self.step + 1} of {self.TOTAL_STEPS} — weakest-attribute bonus"
        )
        ttk.Label(
            self.content,
            text=(
                "Solve each three-decimal-place addition. Every correct answer adds "
                "2 points to the character's current weakest attribute."
            ),
            wraplength=740,
        ).pack(anchor="w", pady=(0, 18))

        grid = ttk.Frame(self.content)
        grid.pack(anchor="w")
        for index, ((left, right), variable) in enumerate(
            zip(self.math_problems, self.math_vars),
            start=1,
        ):
            problem = f"{left / 1000:.3f} + {right / 1000:.3f} ="
            ttk.Label(grid, text=f"{index}. {problem}", font=("Courier New", 13, "bold")).grid(
                row=index - 1,
                column=0,
                sticky="e",
                padx=(0, 10),
                pady=10,
            )
            ttk.Entry(grid, textvariable=variable, width=16).grid(
                row=index - 1,
                column=1,
                sticky="w",
                pady=10,
            )

    def render_household_choice(self) -> None:
        self.heading_var.set("The Most Important Question")
        self.progress_var.set(
            f"Step {self.step + 1} of {self.TOTAL_STEPS} — final household bonus"
        )
        ttk.Label(
            self.content,
            text="Who is the coolest person in the household?",
            font=("Arial", 13, "bold"),
        ).pack(anchor="w", pady=(0, 14))

        ttk.Label(
            self.content,
            text=(
                "At final scoring, the five highest attributes are promoted and the five "
                "lowest lose 5. Those ten values are then frozen while the middle ratings "
                "are gently moulded toward the original roster's aggregate average curve "
                "without changing their total. Finally, the weakest selected positive "
                "trait becomes 99. All ratings remain between 1 and 99."
            ),
            foreground="#475569",
            wraplength=740,
        ).pack(anchor="w", pady=(0, 12))

        for person, effects in HOUSEHOLD_CHOICES.items():
            row = ttk.Frame(self.content)
            row.pack(fill="x", pady=3)
            ttk.Radiobutton(
                row,
                variable=self.household_var,
                value=person,
                text=person,
                width=14,
            ).pack(side="left", anchor="n")
            ttk.Label(
                row,
                text=format_origin_effects(effects),
                foreground="#475569",
                wraplength=580,
            ).pack(side="left", anchor="w", padx=(8, 0))

    def validate_basics(self) -> bool:
        required = {
            "first_name": "First Name",
            "last_name": "Last Name",
            "display_name": "Display Name",
            "species": "Species",
            "religion": "Religion",
            "nationality": "Nationality",
            "birth_year": "Birth Year",
            "height_cm": "Height",
            "weight_kg": "Weight",
            "sex": "Sex",
        }
        missing = [label for field, label in required.items() if not self.basic_vars[field].get().strip()]
        if missing:
            messagebox.showerror(
                "Missing information",
                "Complete these fields:\n" + ", ".join(missing),
                parent=self,
            )
            return False

        numeric_rules = [
            ("birth_year", "Birth Year", 1, 9999),
            ("height_cm", "Height", 1, None),
            ("weight_kg", "Weight", 1, None),
        ]
        for field, label, minimum, maximum in numeric_rules:
            value = safe_int(self.basic_vars[field].get(), None)
            if value is None or value < minimum or (maximum is not None and value > maximum):
                allowed = f"{minimum}–{maximum}" if maximum is not None else f"at least {minimum}"
                messagebox.showerror(
                    "Invalid measurement",
                    f"{label} must be a whole number ({allowed}).",
                    parent=self,
                )
                return False
            self.basic_vars[field].set(str(value))

        self.basic_vars["religion"].set(
            canonicalize_religion(self.basic_vars["religion"].get())
        )
        return True

    def selected_trait_keys(self, variables: list[tk.StringVar]) -> list[str]:
        label_to_field = {label: field for field, label in ATTRIBUTE_LABELS.items()}
        return [label_to_field.get(variable.get(), "") for variable in variables]

    def validate_traits(self, positive: bool) -> bool:
        variables = self.positive_vars if positive else self.negative_vars
        selected = self.selected_trait_keys(variables)
        direction = "positive" if positive else "negative"
        if any(not field for field in selected):
            messagebox.showerror(
                "Incomplete trait selection",
                f"Choose all five {direction} traits.",
                parent=self,
            )
            return False
        if len(set(selected)) != 5:
            messagebox.showerror(
                "Duplicate trait",
                f"Each {direction} trait must be different.",
                parent=self,
            )
            return False
        if not positive:
            positive_selected = set(self.selected_trait_keys(self.positive_vars))
            overlap = positive_selected & set(selected)
            if overlap:
                names = ", ".join(ATTRIBUTE_LABELS[field] for field in ATTRIBUTE_FIELDS if field in overlap)
                messagebox.showerror(
                    "Trait overlap",
                    f"A trait cannot be both positive and negative:\n{names}",
                    parent=self,
                )
                return False
        return True

    def validate_math_entries(self) -> bool:
        for index, variable in enumerate(self.math_vars, start=1):
            if not variable.get().strip():
                messagebox.showerror(
                    "Missing answer",
                    f"Enter an answer for addition question {index}.",
                    parent=self,
                )
                return False
            try:
                Decimal(variable.get().strip())
            except InvalidOperation:
                messagebox.showerror(
                    "Invalid answer",
                    f"Addition answer {index} must be a number.",
                    parent=self,
                )
                return False
        return True

    def count_correct_math_answers(self) -> int:
        correct = 0
        for (left, right), variable in zip(self.math_problems, self.math_vars):
            try:
                submitted = Decimal(variable.get().strip())
            except InvalidOperation:
                continue
            expected = Decimal(left + right) / Decimal(1000)
            if submitted == expected:
                correct += 1
        return correct

    def go_next(self) -> None:
        if self.step == 0 and not self.validate_basics():
            return
        if self.step == self.BACKGROUND_STEP and not self.background_var.get():
            messagebox.showerror(
                "Choose a background",
                "Select one formative background before continuing.",
                parent=self,
            )
            return
        if self.QUESTIONS_FIRST_STEP <= self.step < self.FAVORITES_FIRST_STEP:
            question_index = self.step - self.QUESTIONS_FIRST_STEP
            if self.answer_vars[question_index].get() == -1:
                messagebox.showerror(
                    "Choose an answer",
                    "Select one answer before continuing.",
                    parent=self,
                )
                return
        if self.FAVORITES_FIRST_STEP <= self.step < self.POSITIVE_TRAITS_STEP:
            question_index = self.step - self.FAVORITES_FIRST_STEP
            if self.favorite_answer_vars[question_index].get() == -1:
                messagebox.showerror(
                    "Choose an answer",
                    "Select one preference before continuing.",
                    parent=self,
                )
                return
        if self.step == self.POSITIVE_TRAITS_STEP and not self.validate_traits(positive=True):
            return
        if self.step == self.NEGATIVE_TRAITS_STEP and not self.validate_traits(positive=False):
            return
        if self.step == self.MATH_STEP and not self.validate_math_entries():
            return
        if self.step == self.LAST_STEP:
            if not self.household_var.get():
                messagebox.showerror(
                    "Choose a person",
                    "Select the coolest person in the household.",
                    parent=self,
                )
                return
            self.finish()
            return

        self.step += 1
        self.render_step()

    def go_back(self) -> None:
        if self.step > 0:
            self.step -= 1
            self.render_step()

    def finish(self) -> None:
        positive_traits = self.selected_trait_keys(self.positive_vars)
        negative_traits = self.selected_trait_keys(self.negative_vars)
        self.correct_math_answers = self.count_correct_math_answers()
        scores = calculate_origin_scores(
            [variable.get() for variable in self.answer_vars],
            [variable.get() for variable in self.favorite_answer_vars],
            self.background_var.get(),
            positive_traits,
            negative_traits,
            self.correct_math_answers,
            self.household_var.get(),
            self.average_rank_curve,
        )

        record = {field: "" for field in self.fieldnames}
        record.update(
            {
                "schema_version": SCHEMA_VERSION,
                "character_id": self.character_id,
                "first_name": clean_cell(self.basic_vars["first_name"].get()),
                "last_name": clean_cell(self.basic_vars["last_name"].get()),
                "display_name": clean_cell(self.basic_vars["display_name"].get()),
                "short_name": self.character_id[-3:],
                "sex": clean_cell(self.basic_vars["sex"].get()),
                "birth_year": clean_cell(self.basic_vars["birth_year"].get()),
                "nationality": clean_cell(self.basic_vars["nationality"].get()),
                "religion": canonicalize_religion(self.basic_vars["religion"].get()),
                "species": clean_cell(self.basic_vars["species"].get()),
                "height_cm": clean_cell(self.basic_vars["height_cm"].get()),
                "weight_kg": clean_cell(self.basic_vars["weight_kg"].get()),
                "description": "Character generated through the Origin Story questionnaire.",
            }
        )
        for field, score in scores.items():
            record[field] = str(score)

        self.result = record
        self.grab_release()
        self.destroy()

    def cancel(self) -> None:
        if messagebox.askyesno(
            "Cancel Origin Story",
            "Discard this unfinished Origin Story?",
            parent=self,
        ):
            self.result = None
            self.grab_release()
            self.destroy()


class ZpyCharacterRosterEditor:
    """Viewer/editor for a flat zpy Universal Character Master CSV."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_NAME} - {SCHEMA_NAME} schema editor")
        self.root.geometry("1280x860")
        self.root.minsize(1120, 680)

        self.current_path: Path | None = None
        self.fieldnames: list[str] = list(SCHEMA_FIELDS)
        self.characters: list[dict[str, str]] = []
        self.last_saved_snapshot: list[dict[str, str]] = []
        self.filtered_indices: list[int] = []
        self.current_index: int | None = None

        self.dirty = False
        self.updating_form = False

        self.form_vars: dict[str, tk.StringVar] = {}
        self.attribute_widgets: dict[str, dict[str, object]] = {}

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_args: self.refresh_roster_list())

        self.sim_year_var = tk.StringVar(value=str(datetime.now().year))
        self.sim_year_var.trace_add("write", lambda *_args: self.update_dynamic_age())

        self.status_var = tk.StringVar(value="Ready.")
        self.selected_char_name = tk.StringVar(value="No Character Selected")

        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.load_initial_data()

    # ---------------------------------------------------------------------
    # UI construction
    # ---------------------------------------------------------------------

    def build_ui(self) -> None:
        self.build_banner()
        self.build_workspace()
        self.build_status_bar()

    def build_banner(self) -> None:
        banner = tk.Frame(self.root, bg="#1E293B", padx=15, pady=10)
        banner.pack(fill="x", side="top")

        title_frame = tk.Frame(banner, bg="#1E293B")
        title_frame.pack(side="left", fill="y")

        tk.Label(
            title_frame,
            text="zpy SCHEMA COMPLIANT ROSTER EDITOR",
            font=("Arial", 12, "bold"),
            fg="#F8FAFC",
            bg="#1E293B",
        ).pack(anchor="w")

        tk.Label(
            title_frame,
            text=(
                "Notice: scripts using this universal character schema should adopt "
                "the 'zpy' prefix, e.g. zpyCharacterRosterEditor."
            ),
            font=("Arial", 9, "italic"),
            fg="#94A3B8",
            bg="#1E293B",
        ).pack(anchor="w")

        controls = tk.Frame(banner, bg="#1E293B")
        controls.pack(side="right", fill="y")

        tk.Label(
            controls,
            text="Simulation Year:",
            fg="#F8FAFC",
            bg="#1E293B",
            font=("Arial", 9, "bold"),
        ).pack(side="left", padx=(0, 5))

        tk.Entry(
            controls,
            textvariable=self.sim_year_var,
            width=6,
            justify="center",
        ).pack(side="left", padx=(0, 12))

        self.make_banner_button(controls, "Open CSV", self.load_from_file).pack(
            side="left", padx=3
        )
        self.make_banner_button(controls, "Save", self.save_current).pack(
            side="left", padx=3
        )
        self.make_banner_button(controls, "Save As", self.save_as).pack(
            side="left", padx=3
        )
        self.make_banner_button(controls, "Save New Version", self.save_new_version).pack(
            side="left", padx=3
        )

    def make_banner_button(
        self,
        parent: tk.Widget,
        text: str,
        command,
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg="#0F766E",
            fg="white",
            relief="flat",
            padx=10,
            activebackground="#0D9488",
            activeforeground="white",
        )

    def build_workspace(self) -> None:
        self.paned = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill="both", expand=True, padx=5, pady=5)

        sidebar = ttk.Frame(self.paned, padding=10)
        self.paned.add(sidebar, weight=1)

        right_frame = ttk.Frame(self.paned)
        self.paned.add(right_frame, weight=4)

        self.build_sidebar(sidebar)
        self.build_editor_panel(right_frame)

    def build_sidebar(self, sidebar: ttk.Frame) -> None:
        search_frame = ttk.Frame(sidebar)
        search_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(
            search_frame,
            text="Search Roster:",
            font=("Arial", 9, "bold"),
        ).pack(anchor="w", pady=(0, 2))

        ttk.Entry(search_frame, textvariable=self.search_var).pack(fill="x")

        button_frame = ttk.Frame(sidebar)
        button_frame.pack(fill="x", pady=(0, 8))

        ttk.Button(button_frame, text="Add", command=self.add_character).pack(
            side="left", expand=True, fill="x", padx=(0, 3)
        )
        ttk.Button(button_frame, text="Duplicate", command=self.duplicate_character).pack(
            side="left", expand=True, fill="x", padx=3
        )
        ttk.Button(button_frame, text="Origin Story", command=self.origin_story).pack(
            side="left", expand=True, fill="x", padx=3
        )
        ttk.Button(button_frame, text="Delete", command=self.delete_character).pack(
            side="left", expand=True, fill="x", padx=(3, 0)
        )

        self.lbl_roster_count = ttk.Label(
            sidebar,
            text="Roster:",
            font=("Arial", 9, "bold"),
        )
        self.lbl_roster_count.pack(anchor="w")

        list_container = ttk.Frame(sidebar)
        list_container.pack(fill="both", expand=True)

        self.roster_listbox = tk.Listbox(
            list_container,
            selectmode=tk.SINGLE,
            exportselection=False,
            font=("Courier", 10),
        )
        self.roster_listbox.pack(fill="both", expand=True, side="left")
        self.roster_listbox.bind("<<ListboxSelect>>", self.on_list_select)

        scroll_list = ttk.Scrollbar(
            list_container,
            orient="vertical",
            command=self.roster_listbox.yview,
        )
        scroll_list.pack(fill="y", side="right")
        self.roster_listbox.config(yscrollcommand=scroll_list.set)

        lower_buttons = ttk.Frame(sidebar)
        lower_buttons.pack(fill="x", pady=(8, 0))

        ttk.Button(
            lower_buttons,
            text="Validate Roster",
            command=self.validate_and_report,
        ).pack(fill="x", pady=(0, 4))

        ttk.Button(
            lower_buttons,
            text="Revert From Disk",
            command=self.revert_from_disk,
        ).pack(fill="x")

    def build_editor_panel(self, parent: ttk.Frame) -> None:
        header = tk.Frame(parent, bg="#F1F5F9", pady=8, padx=12)
        header.pack(fill="x")

        tk.Label(
            header,
            textvariable=self.selected_char_name,
            font=("Arial", 16, "bold"),
            bg="#F1F5F9",
            fg="#1E293B",
        ).pack(anchor="w")

        tk.Label(
            header,
            text=(
                "Editable root roster. Save overwrites the current CSV; "
                "Save New Version creates a timestamped copy."
            ),
            font=("Arial", 9, "italic"),
            bg="#F1F5F9",
            fg="#475569",
        ).pack(anchor="w")

        scroll_container = ttk.Frame(parent)
        scroll_container.pack(fill="both", expand=True)

        self.canvas_scroll = tk.Canvas(
            scroll_container,
            borderwidth=0,
            highlightthickness=0,
        )
        scroll_v = ttk.Scrollbar(
            scroll_container,
            orient="vertical",
            command=self.canvas_scroll.yview,
        )
        self.scroll_content = ttk.Frame(self.canvas_scroll, padding=10)

        self.scroll_content.bind(
            "<Configure>",
            lambda _event: self.canvas_scroll.configure(
                scrollregion=self.canvas_scroll.bbox("all")
            ),
        )
        self.canvas_window = self.canvas_scroll.create_window(
            (0, 0),
            window=self.scroll_content,
            anchor="nw",
        )
        self.canvas_scroll.bind(
            "<Configure>",
            lambda event: self.canvas_scroll.itemconfig(
                self.canvas_window,
                width=event.width,
            ),
        )

        self.canvas_scroll.configure(yscrollcommand=scroll_v.set)
        self.canvas_scroll.pack(side="left", fill="both", expand=True)
        scroll_v.pack(side="right", fill="y")

        self.build_identity_editor()
        self.build_attributes_grid()

    def build_identity_editor(self) -> None:
        identity_group = ttk.LabelFrame(
            self.scroll_content,
            text="Identity & Dimensions",
            padding=12,
        )
        identity_group.pack(fill="x", pady=(0, 10))

        grid = ttk.Frame(identity_group)
        grid.pack(fill="x")
        for col in range(8):
            grid.columnconfigure(col, weight=1 if col % 2 == 1 else 0)

        field_layout = [
            ("character_id", "Character ID", 0, 0, "entry"),
            ("short_name", "Short Name", 0, 2, "entry"),
            ("schema_version", "Schema Ver.", 0, 4, "entry"),
            ("sex", "Sex", 0, 6, "sex_combo"),
            ("first_name", "First Name", 1, 0, "entry"),
            ("last_name", "Last Name", 1, 2, "entry"),
            ("display_name", "Display Name", 1, 4, "entry"),
            ("species", "Species", 1, 6, "entry"),
            ("birth_year", "Birth Year", 2, 0, "number"),
            ("dynamic_age", "Dynamic Age", 2, 2, "readonly_label"),
            ("nationality", "Nationality", 2, 4, "entry"),
            ("religion", "Religion", 2, 6, "religion_combo"),
            ("height_cm", "Height cm", 3, 0, "number"),
            ("weight_kg", "Weight kg", 3, 2, "number"),
            ("left2right", "Left→Right", 3, 4, "spin_1_99"),
            ("evil2good", "Evil→Good", 3, 6, "spin_1_99"),
        ]

        for field, label_text, row, col, widget_type in field_layout:
            ttk.Label(
                grid,
                text=f"{label_text}:",
                font=("Arial", 9, "bold"),
            ).grid(row=row, column=col, sticky="e", padx=(8, 5), pady=4)

            if widget_type == "readonly_label":
                self.lbl_dynamic_age = ttk.Label(grid, text="—", font=("Arial", 9, "bold"))
                self.lbl_dynamic_age.grid(row=row, column=col + 1, sticky="w", pady=4)
                continue

            var = tk.StringVar()
            self.form_vars[field] = var
            var.trace_add("write", lambda *_args, f=field: self.on_form_change(f))

            if widget_type == "religion_combo":
                widget = ttk.Combobox(
                    grid,
                    textvariable=var,
                    values=RELIGION_CHOICES,
                    state="normal",
                    width=16,
                )
            elif widget_type == "sex_combo":
                widget = ttk.Combobox(
                    grid,
                    textvariable=var,
                    values=SEX_CHOICES,
                    state="normal",
                    width=10,
                )
            elif widget_type == "spin_1_99":
                widget = tk.Spinbox(
                    grid,
                    from_=1,
                    to=99,
                    width=8,
                    textvariable=var,
                    command=lambda f=field: self.on_form_change(f),
                )
            elif widget_type == "number":
                widget = ttk.Entry(grid, textvariable=var, width=14)
            else:
                widget = ttk.Entry(grid, textvariable=var, width=20)

            widget.grid(row=row, column=col + 1, sticky="ew", pady=4)

        ttk.Label(
            grid,
            text="Political Line:",
            font=("Arial", 9, "bold"),
        ).grid(row=4, column=4, sticky="e", padx=(8, 5), pady=6)

        self.pol_canvas = tk.Canvas(
            grid,
            width=200,
            height=20,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#CBD5E1",
        )
        self.pol_canvas.grid(row=4, column=5, columnspan=2, sticky="w", pady=6)

        self.lbl_pol_value = ttk.Label(grid, text="—")
        self.lbl_pol_value.grid(row=4, column=7, sticky="w", pady=6)

        ttk.Label(
            grid,
            text="Moral Line:",
            font=("Arial", 9, "bold"),
        ).grid(row=5, column=4, sticky="e", padx=(8, 5), pady=6)

        self.moral_canvas = tk.Canvas(
            grid,
            width=200,
            height=20,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#CBD5E1",
        )
        self.moral_canvas.grid(row=5, column=5, columnspan=2, sticky="w", pady=6)

        self.lbl_moral_value = ttk.Label(grid, text="—")
        self.lbl_moral_value.grid(row=5, column=7, sticky="w", pady=6)

        desc_group = ttk.LabelFrame(
            self.scroll_content,
            text="Narrative Profile Description",
            padding=10,
        )
        desc_group.pack(fill="x", pady=(0, 10))

        self.description_text = tk.Text(
            desc_group,
            height=4,
            wrap="word",
            font=("Arial", 10),
        )
        self.description_text.pack(fill="x", expand=True)
        self.description_text.bind("<KeyRelease>", self.on_description_change)

    def build_attributes_grid(self) -> None:
        attr_outer = ttk.Frame(self.scroll_content)
        attr_outer.pack(fill="both", expand=True)

        attr_outer.columnconfigure(0, weight=1)
        attr_outer.columnconfigure(1, weight=1)

        placements = {
            "Physical Attributes": (0, 0),
            "Cognitive Attributes": (0, 1),
            "Psychological Attributes": (1, 0),
            "Social & Behavioural Attributes": (1, 1),
        }

        for group_name, attrs in ATTRIBUTE_GROUPS:
            row, col = placements[group_name]
            group = ttk.LabelFrame(attr_outer, text=group_name, padding=8)
            group.grid(
                row=row,
                column=col,
                sticky="nsew",
                padx=(0, 5) if col == 0 else (5, 0),
                pady=5,
            )
            self.build_attribute_list(group, attrs)

    def build_attribute_list(
        self,
        parent: ttk.LabelFrame,
        attributes: list[tuple[str, str]],
    ) -> None:
        for attr_key, attr_label in attributes:
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=2)

            ttk.Label(row, text=attr_label, width=19, anchor="w").pack(
                side="left",
                padx=(0, 5),
            )

            canvas = tk.Canvas(
                row,
                width=120,
                height=14,
                borderwidth=0,
                highlightthickness=1,
                highlightbackground="#E2E8F0",
            )
            canvas.pack(side="left", padx=(0, 8))

            var = tk.StringVar()
            self.form_vars[attr_key] = var
            var.trace_add("write", lambda *_args, f=attr_key: self.on_form_change(f))

            spinbox = tk.Spinbox(
                row,
                from_=1,
                to=99,
                width=4,
                textvariable=var,
                justify="right",
                command=lambda f=attr_key: self.on_form_change(f),
            )
            spinbox.pack(side="left", padx=(0, 5))

            desc_label = ttk.Label(
                row,
                text="",
                width=15,
                anchor="w",
                font=("Arial", 8, "italic"),
            )
            desc_label.pack(side="left")

            self.attribute_widgets[attr_key] = {
                "canvas": canvas,
                "desc_label": desc_label,
            }

    def build_status_bar(self) -> None:
        status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief="sunken",
            anchor="w",
            padding=(5, 2),
        )
        status_bar.pack(side="bottom", fill="x")

    # ---------------------------------------------------------------------
    # Loading / saving
    # ---------------------------------------------------------------------

    def load_initial_data(self) -> None:
        script_dir = Path(__file__).resolve().parent
        for candidate_name in DEFAULT_CSV_CANDIDATES:
            candidate = script_dir / candidate_name
            if candidate.exists():
                self.load_csv(candidate, ask_if_dirty=False)
                return

        self.characters = []
        self.last_saved_snapshot = []
        self.current_path = None
        self.fieldnames = list(SCHEMA_FIELDS)
        self.refresh_roster_list()
        self.status_var.set(
            "No roster loaded. Place .universal_characters_master.csv or "
            "universal_characters_master.csv beside this script, or use Open CSV."
        )

    def load_from_file(self) -> None:
        if not self.confirm_discard_unsaved_changes():
            return

        file_path = filedialog.askopenfilename(
            title="Open Universal Character Master CSV",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        )
        if not file_path:
            return

        self.load_csv(Path(file_path), ask_if_dirty=False)

    def load_csv(self, path: Path, ask_if_dirty: bool = True) -> None:
        if ask_if_dirty and not self.confirm_discard_unsaved_changes():
            return

        try:
            with path.open("r", encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)
                loaded_headers = list(reader.fieldnames or [])
                rows = list(reader)
        except Exception as exc:
            messagebox.showerror("Error Reading CSV", f"Could not read file:\n{exc}")
            return

        if not loaded_headers:
            messagebox.showerror("Invalid CSV", "The file has no header row.")
            return

        self.fieldnames = self.merge_fieldnames(loaded_headers)
        self.characters = [self.normalize_record(row) for row in rows]
        self.last_saved_snapshot = deepcopy(self.characters)
        self.current_path = path
        self.current_index = None
        self.dirty = False

        self.refresh_roster_list()
        errors = self.validate_roster()
        if errors:
            self.status_var.set(
                f"Loaded {len(self.characters)} characters from {path.name} with "
                f"{len(errors)} validation issue(s)."
            )
            self.show_validation_errors(errors, title="Loaded with validation issues")
        else:
            self.status_var.set(
                f"Loaded {len(self.characters)} zpy character(s) from {path}."
            )

        self.update_window_title()

    def merge_fieldnames(self, loaded_headers: list[str]) -> list[str]:
        cleaned = [header.strip() for header in loaded_headers if header and header.strip()]
        extras = [header for header in cleaned if header not in SCHEMA_FIELDS]
        return list(SCHEMA_FIELDS) + extras

    def normalize_record(self, row: dict[str, object]) -> dict[str, str]:
        record: dict[str, str] = {}
        for field in self.fieldnames:
            record[field] = clean_cell(row.get(field, ""))
        record["religion"] = canonicalize_religion(record.get("religion", ""))
        return record

    def save_current(self) -> None:
        if self.current_path is None:
            self.save_as()
            return
        self.save_to_path(self.current_path)

    def save_as(self) -> None:
        initial_dir = (
            self.current_path.parent
            if self.current_path is not None
            else Path(__file__).resolve().parent
        )
        file_path = filedialog.asksaveasfilename(
            title="Save zpy roster CSV as",
            defaultextension=".csv",
            initialdir=str(initial_dir),
            initialfile="universal_characters_master.csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        )
        if not file_path:
            return
        self.save_to_path(Path(file_path))

    def save_new_version(self) -> None:
        base_dir = (
            self.current_path.parent
            if self.current_path is not None
            else Path(__file__).resolve().parent
        )
        base_name = (
            self.current_path.stem
            if self.current_path is not None
            else "universal_characters_master"
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        version_path = base_dir / f"{base_name}_{timestamp}.csv"
        self.save_to_path(version_path)

    def save_to_path(self, path: Path) -> None:
        self.collect_current_form_edits()

        errors = self.validate_roster()
        if errors:
            self.show_validation_errors(errors, title="Cannot save: validation failed")
            return

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=self.fieldnames,
                    extrasaction="ignore",
                    lineterminator="\n",
                )
                writer.writeheader()
                for character in self.characters:
                    writer.writerow(self.prepare_record_for_save(character))
        except Exception as exc:
            messagebox.showerror("Save failed", f"Could not save file:\n{exc}")
            return

        self.current_path = path
        self.last_saved_snapshot = deepcopy(self.characters)
        self.dirty = False
        self.update_window_title()
        self.status_var.set(f"Saved {len(self.characters)} character(s) to {path}.")
        messagebox.showinfo("Saved", f"Roster saved successfully:\n{path}")

    def prepare_record_for_save(self, record: dict[str, str]) -> dict[str, str]:
        output = {field: clean_cell(record.get(field, "")) for field in self.fieldnames}
        output["religion"] = canonicalize_religion(output.get("religion", ""))

        # Normalize schema version for blank rows while preserving explicit user edits.
        if not output.get("schema_version"):
            output["schema_version"] = SCHEMA_VERSION

        # Ensure numeric values save as integer-looking strings where possible.
        for field in INTEGER_FIELDS:
            value = safe_int(output.get(field), None)
            if value is not None:
                output[field] = str(value)

        return output

    def revert_from_disk(self) -> None:
        if self.current_path is None or not self.current_path.exists():
            if self.last_saved_snapshot:
                if not messagebox.askyesno(
                    "Revert unsaved changes",
                    "No disk file is available. Revert to the last saved in-memory snapshot?",
                ):
                    return
                self.characters = deepcopy(self.last_saved_snapshot)
                self.dirty = False
                self.refresh_roster_list()
                self.update_window_title()
            else:
                messagebox.showinfo("Nothing to revert", "No saved roster is available.")
            return

        if not messagebox.askyesno(
            "Revert from disk",
            "Discard unsaved changes and reload the current CSV from disk?",
        ):
            return

        self.load_csv(self.current_path, ask_if_dirty=False)

    # ---------------------------------------------------------------------
    # Roster editing
    # ---------------------------------------------------------------------

    def origin_story(self) -> None:
        """Create a character through the guided Origin Story questionnaire."""
        wizard = OriginStoryWizard(
            self.root,
            self.fieldnames,
            self.next_character_id(),
            calculate_average_rank_curve(self.characters),
        )
        self.root.wait_window(wizard)
        if wizard.result is None:
            return

        self.characters.append(wizard.result)
        self.current_index = len(self.characters) - 1
        self.mark_dirty(
            "Created a new character through Origin Story. "
            f"Addition answers correct: {wizard.correct_math_answers}/2."
        )
        self.refresh_roster_list(select_index=self.current_index)

    def add_character(self) -> None:
        new_id = self.next_character_id()
        record = {field: "" for field in self.fieldnames}
        record.update(
            {
                "schema_version": SCHEMA_VERSION,
                "character_id": new_id,
                "first_name": "New",
                "last_name": "Character",
                "display_name": "New Character",
                "short_name": new_id[-3:],
                "sex": "",
                "birth_year": "2000",
                "nationality": "",
                "religion": "Atheist",
                "left2right": "50",
                "evil2good": "50",
                "species": SPECIES_DEFAULT,
                "height_cm": "170",
                "weight_kg": "70",
                "description": "New zpy character.",
            }
        )
        for attribute in ATTRIBUTE_FIELDS:
            record[attribute] = "50"

        self.characters.append(record)
        self.current_index = len(self.characters) - 1
        self.mark_dirty("Added new character.")
        self.refresh_roster_list(select_index=self.current_index)

    def duplicate_character(self) -> None:
        if self.current_index is None:
            messagebox.showinfo("No character selected", "Select a character to duplicate.")
            return

        source = deepcopy(self.characters[self.current_index])
        new_id = self.next_character_id()
        source["schema_version"] = SCHEMA_VERSION
        source["character_id"] = new_id
        source["display_name"] = f"{source.get('display_name', 'Character')} Copy"
        source["short_name"] = new_id[-3:]
        self.characters.append(source)
        self.current_index = len(self.characters) - 1
        self.mark_dirty("Duplicated character.")
        self.refresh_roster_list(select_index=self.current_index)

    def delete_character(self) -> None:
        if self.current_index is None:
            messagebox.showinfo("No character selected", "Select a character to delete.")
            return

        character = self.characters[self.current_index]
        label = character.get("display_name") or character.get("character_id") or "this character"
        if not messagebox.askyesno(
            "Delete character",
            f"Delete {label} from the roster?\n\nThis is not final until you save.",
        ):
            return

        del self.characters[self.current_index]
        self.current_index = None
        self.mark_dirty("Deleted character.")
        self.refresh_roster_list()

    def next_character_id(self) -> str:
        max_seen = 0
        pattern = re.compile(r"^CHR(\d+)$", re.IGNORECASE)
        for character in self.characters:
            match = pattern.match(clean_cell(character.get("character_id", "")))
            if match:
                max_seen = max(max_seen, int(match.group(1)))
        return f"CHR{max_seen + 1:04d}"

    # ---------------------------------------------------------------------
    # Form syncing
    # ---------------------------------------------------------------------

    def on_list_select(self, _event) -> None:
        selection = self.roster_listbox.curselection()
        if not selection:
            return

        filtered_position = selection[0]
        if filtered_position >= len(self.filtered_indices):
            return

        self.collect_current_form_edits()
        self.current_index = self.filtered_indices[filtered_position]
        self.display_current_character()

    def display_current_character(self) -> None:
        if self.current_index is None or self.current_index >= len(self.characters):
            self.clear_fields()
            return

        character = self.characters[self.current_index]
        self.updating_form = True

        try:
            for field, var in self.form_vars.items():
                var.set(clean_cell(character.get(field, "")))

            self.description_text.delete("1.0", tk.END)
            self.description_text.insert("1.0", clean_cell(character.get("description", "")))
        finally:
            self.updating_form = False

        display_name = character.get("display_name") or "Unnamed"
        short_name = character.get("short_name") or "—"
        char_id = character.get("character_id") or "NO_ID"
        self.selected_char_name.set(f"{display_name} [{short_name}] — {char_id}")

        self.update_dynamic_age()
        self.draw_political_gradient(safe_int(character.get("left2right"), None))
        self.draw_moral_gradient(safe_int(character.get("evil2good"), None))

        for attr_key in ATTRIBUTE_FIELDS:
            self.draw_attribute_row(attr_key, safe_int(character.get(attr_key), None))

    def clear_fields(self) -> None:
        self.updating_form = True
        try:
            for var in self.form_vars.values():
                var.set("")
            self.description_text.delete("1.0", tk.END)
        finally:
            self.updating_form = False

        self.selected_char_name.set("No Character Selected")
        self.lbl_dynamic_age.config(text="—")
        self.pol_canvas.delete("all")
        self.lbl_pol_value.config(text="—")
        self.moral_canvas.delete("all")
        self.lbl_moral_value.config(text="—")
        for attr_key in ATTRIBUTE_FIELDS:
            self.draw_attribute_row(attr_key, None)

    def collect_current_form_edits(self) -> None:
        if self.current_index is None or self.current_index >= len(self.characters):
            return

        record = self.characters[self.current_index]
        for field, var in self.form_vars.items():
            record[field] = clean_cell(var.get())
        record["religion"] = canonicalize_religion(record.get("religion", ""))
        record["description"] = self.description_text.get("1.0", "end-1c").strip()

    def on_form_change(self, field: str) -> None:
        if self.updating_form:
            return
        if self.current_index is None or self.current_index >= len(self.characters):
            return

        value = clean_cell(self.form_vars[field].get())
        self.characters[self.current_index][field] = value

        if field == "left2right":
            self.draw_political_gradient(safe_int(value, None))
        elif field == "evil2good":
            self.draw_moral_gradient(safe_int(value, None))
        elif field in ATTRIBUTE_FIELDS:
            self.draw_attribute_row(field, safe_int(value, None))
        elif field == "birth_year":
            self.update_dynamic_age()

        if field in {
            "character_id",
            "display_name",
            "short_name",
            "first_name",
            "last_name",
            "nationality",
            "religion",
        }:
            self.update_current_header()
            self.refresh_roster_list(select_index=self.current_index, preserve_scroll=True)

        self.mark_dirty()

    def on_description_change(self, _event) -> None:
        if self.updating_form:
            return
        if self.current_index is None or self.current_index >= len(self.characters):
            return

        self.characters[self.current_index]["description"] = (
            self.description_text.get("1.0", "end-1c").strip()
        )
        self.mark_dirty()

    def update_current_header(self) -> None:
        if self.current_index is None:
            self.selected_char_name.set("No Character Selected")
            return
        character = self.characters[self.current_index]
        display_name = character.get("display_name") or "Unnamed"
        short_name = character.get("short_name") or "—"
        char_id = character.get("character_id") or "NO_ID"
        self.selected_char_name.set(f"{display_name} [{short_name}] — {char_id}")

    def update_dynamic_age(self) -> None:
        if self.current_index is None or self.current_index >= len(self.characters):
            self.lbl_dynamic_age.config(text="—")
            return

        character = self.characters[self.current_index]
        birth_year = safe_int(character.get("birth_year"), None)
        sim_year = safe_int(self.sim_year_var.get(), None)

        if birth_year is None or sim_year is None:
            self.lbl_dynamic_age.config(text="Invalid")
            return

        age = sim_year - birth_year
        if age < 0:
            self.lbl_dynamic_age.config(text=f"{age} yrs (future birth)")
        else:
            self.lbl_dynamic_age.config(text=f"{age} yrs")

    # ---------------------------------------------------------------------
    # Visualization
    # ---------------------------------------------------------------------

    def draw_political_gradient(self, value: int | None) -> None:
        self.pol_canvas.delete("all")
        if value is None:
            self.pol_canvas.create_rectangle(0, 0, 200, 20, fill="#E2E8F0", outline="")
            self.lbl_pol_value.config(text="—")
            return

        value = max(1, min(99, int(value)))
        self.pol_canvas.create_rectangle(0, 0, 75, 20, fill="#3B82F6", outline="")
        self.pol_canvas.create_rectangle(75, 0, 125, 20, fill="#9CA3AF", outline="")
        self.pol_canvas.create_rectangle(125, 0, 200, 20, fill="#EF4444", outline="")
        self.pol_canvas.create_line(100, 0, 100, 20, fill="#FFFFFF", width=2)

        x_pos = ((value - 1) / 98.0) * 200
        self.pol_canvas.create_polygon(
            x_pos - 5,
            0,
            x_pos + 5,
            0,
            x_pos,
            8,
            fill="#1E293B",
        )
        self.pol_canvas.create_polygon(
            x_pos - 5,
            20,
            x_pos + 5,
            20,
            x_pos,
            12,
            fill="#1E293B",
        )
        self.lbl_pol_value.config(text=f"{value} ({get_political_label(value)})")

    def draw_moral_gradient(self, value: int | None) -> None:
        """Draw the evil-to-good moral alignment gradient for evil2good."""
        self.moral_canvas.delete("all")
        if value is None:
            self.moral_canvas.create_rectangle(0, 0, 200, 20, fill="#E2E8F0", outline="")
            self.lbl_moral_value.config(text="—")
            return

        value = max(1, min(99, int(value)))

        # Left = evil, centre = neutral, right = good.
        self.moral_canvas.create_rectangle(0, 0, 75, 20, fill="#111827", outline="")
        self.moral_canvas.create_rectangle(75, 0, 125, 20, fill="#9CA3AF", outline="")
        self.moral_canvas.create_rectangle(125, 0, 200, 20, fill="#22C55E", outline="")
        self.moral_canvas.create_line(100, 0, 100, 20, fill="#FFFFFF", width=2)

        x_pos = ((value - 1) / 98.0) * 200
        self.moral_canvas.create_polygon(
            x_pos - 5,
            0,
            x_pos + 5,
            0,
            x_pos,
            8,
            fill="#F8FAFC",
            outline="#1E293B",
        )
        self.moral_canvas.create_polygon(
            x_pos - 5,
            20,
            x_pos + 5,
            20,
            x_pos,
            12,
            fill="#F8FAFC",
            outline="#1E293B",
        )
        self.lbl_moral_value.config(text=f"{value} ({get_moral_label(value)})")

    def draw_attribute_row(self, attr_key: str, value: int | None) -> None:
        widgets = self.attribute_widgets.get(attr_key)
        if not widgets:
            return

        canvas: tk.Canvas = widgets["canvas"]  # type: ignore[assignment]
        desc_label: ttk.Label = widgets["desc_label"]  # type: ignore[assignment]

        canvas.delete("all")

        if value is None:
            canvas.create_rectangle(0, 0, 120, 14, fill="#E2E8F0", outline="")
            desc_label.config(text="N/A", foreground="#94A3B8")
            return

        value = max(1, min(99, int(value)))
        color = get_rating_color(value)
        percent_width = (value / 99.0) * 120

        canvas.create_rectangle(0, 0, 120, 14, fill="#F1F5F9", outline="")
        canvas.create_rectangle(0, 0, percent_width, 14, fill=color, outline="")
        desc_label.config(text=get_rating_desc(value), foreground=color)

    # ---------------------------------------------------------------------
    # Roster list and search
    # ---------------------------------------------------------------------

    def refresh_roster_list(
        self,
        select_index: int | None = None,
        preserve_scroll: bool = False,
    ) -> None:
        current_yview = self.roster_listbox.yview() if preserve_scroll else None

        search_term = self.search_var.get().strip().lower()
        self.roster_listbox.delete(0, tk.END)
        self.filtered_indices.clear()

        for index, character in enumerate(self.characters):
            searchable = " ".join(
                [
                    character.get("character_id", ""),
                    character.get("display_name", ""),
                    character.get("short_name", ""),
                    character.get("nationality", ""),
                    character.get("religion", ""),
                    character.get("species", ""),
                    character.get("description", ""),
                ]
            ).lower()

            if search_term and search_term not in searchable:
                continue

            self.filtered_indices.append(index)
            display_string = (
                f"{character.get('character_id', '???'):<7} - "
                f"{character.get('display_name', 'Unknown'):<24.24} "
                f"({character.get('short_name', '???'):<3})"
            )
            self.roster_listbox.insert(tk.END, display_string)

        self.lbl_roster_count.config(text=f"Roster Match ({len(self.filtered_indices)}):")

        target_index = select_index
        if target_index is None:
            target_index = self.current_index

        if target_index in self.filtered_indices:
            filtered_position = self.filtered_indices.index(target_index)
            self.roster_listbox.selection_clear(0, tk.END)
            self.roster_listbox.selection_set(filtered_position)
            self.roster_listbox.activate(filtered_position)
            self.current_index = target_index
            self.display_current_character()
        elif self.filtered_indices:
            self.roster_listbox.selection_clear(0, tk.END)
            self.roster_listbox.selection_set(0)
            self.roster_listbox.activate(0)
            self.current_index = self.filtered_indices[0]
            self.display_current_character()
        else:
            self.current_index = None
            self.clear_fields()

        if preserve_scroll and current_yview:
            self.roster_listbox.yview_moveto(current_yview[0])

    # ---------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------

    def validate_and_report(self) -> None:
        self.collect_current_form_edits()
        errors = self.validate_roster()
        if errors:
            self.show_validation_errors(errors, title="Roster validation issues")
        else:
            messagebox.showinfo("Validation passed", "No zpy schema validation errors found.")

    def validate_roster(self) -> list[str]:
        errors: list[str] = []
        ids_seen: dict[str, int] = {}
        allowed_religions = {choice.casefold() for choice in RELIGION_CHOICES}

        for row_index, character in enumerate(self.characters, start=2):
            label = character.get("character_id", f"row {row_index}") or f"row {row_index}"

            char_id = clean_cell(character.get("character_id", ""))
            if not char_id:
                errors.append(f"Row {row_index}: character_id is required.")
            elif char_id in ids_seen:
                errors.append(
                    f"Row {row_index}: duplicate character_id {char_id!r}; "
                    f"first seen on row {ids_seen[char_id]}."
                )
            else:
                ids_seen[char_id] = row_index

            for required_field in ["schema_version", "display_name", "birth_year"]:
                if not clean_cell(character.get(required_field, "")):
                    errors.append(f"{label}: {required_field} is required.")

            religion = clean_cell(character.get("religion", ""))
            if religion and religion.casefold() not in allowed_religions:
                errors.append(
                    f"{label}: religion must be one of "
                    f"{', '.join(RELIGION_CHOICES)}; got {religion!r}."
                )

            for field in RATING_FIELDS:
                value = safe_int(character.get(field), None)
                if value is None:
                    errors.append(f"{label}: {field} must be an integer from 1 to 99.")
                elif not 1 <= value <= 99:
                    errors.append(f"{label}: {field}={value} outside allowed range 1-99.")

            birth_year = safe_int(character.get("birth_year"), None)
            if birth_year is None:
                errors.append(f"{label}: birth_year must be an integer.")
            elif not 1 <= birth_year <= 9999:
                errors.append(f"{label}: birth_year={birth_year} is outside 1-9999.")

            for field in MEASUREMENT_FIELDS:
                value = safe_int(character.get(field), None)
                if value is None:
                    errors.append(f"{label}: {field} must be an integer measurement.")
                elif value <= 0:
                    errors.append(f"{label}: {field} must be greater than zero.")

        return errors

    def show_validation_errors(self, errors: list[str], title: str) -> None:
        max_shown = 40
        text = "\n".join(errors[:max_shown])
        if len(errors) > max_shown:
            text += f"\n\n...and {len(errors) - max_shown} more issue(s)."

        messagebox.showerror(title, text)

    # ---------------------------------------------------------------------
    # Dirty state and window lifecycle
    # ---------------------------------------------------------------------

    def mark_dirty(self, message: str | None = None) -> None:
        if not self.dirty:
            self.dirty = True
            self.update_window_title()
        if message:
            self.status_var.set(message)

    def update_window_title(self) -> None:
        dirty_marker = "*" if self.dirty else ""
        path_text = str(self.current_path) if self.current_path else "No file loaded"
        self.root.title(f"{dirty_marker}{APP_NAME} - {SCHEMA_NAME} schema editor - {path_text}")

    def confirm_discard_unsaved_changes(self) -> bool:
        if not self.dirty:
            return True

        return messagebox.askyesno(
            "Unsaved changes",
            "You have unsaved roster edits. Discard them and continue?",
        )

    def on_close(self) -> None:
        if self.dirty:
            choice = messagebox.askyesnocancel(
                "Unsaved changes",
                "Save changes before closing?",
            )
            if choice is None:
                return
            if choice is True:
                self.save_current()
                if self.dirty:
                    return
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = ZpyCharacterRosterEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
