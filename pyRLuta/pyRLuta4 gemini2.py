#!/usr/bin/env python3
import csv
import os
import sys
import time
import random
import threading
import queue
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Union, Set
import json

# --- Force cwd to script's folder so CSVs are always found here ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# --- Constants ---
REFRESH_RATE    = 0.1
HUD_WIDTH       = 80  # Increased width for better visual experience
COMBAT_LOG_SIZE = 15  # Increased log size for better history
CLEAR_CMD       = 'cls' if os.name == 'nt' else 'clear'
VERSION         = "1.1.0"

# --- Script-relative CSV paths ---
TOONS_FILE       = os.path.join(BASE_DIR, 'pyRL_toons.csv')
SAVED_FILE       = os.path.join(BASE_DIR, 'pyRL_saved.csv')
NPCS_FILE        = os.path.join(BASE_DIR, 'pyRL_npcs.csv')
ITEMS_FILE       = os.path.join(BASE_DIR, 'pyRL_items.csv')
ACTIONS_FILE     = os.path.join(BASE_DIR, 'pyRL_actions.csv')
LEADERBOARD_FILE = os.path.join(BASE_DIR, 'pyRL_leaderboard.csv')

# --- Color support for terminals that support ANSI ---
COLOR_ENABLED = True  # Set to False if terminal doesn't support colors
class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'

    @staticmethod
    def colorize(text, color):
        if not COLOR_ENABLED:
            return text
        return f"{color}{text}{Colors.RESET}"

# --- Global lookups populated at runtime ---
ALL_ITEMS: Dict[int, Dict] = {}
ALL_ACTIONS: Dict[str, Dict] = {}
DEFAULT_ACTION_KEYS: Dict[str, Optional[str]] = {}

@dataclass
class StatusEffect:
    id: str
    name: str
    stat: str
    value: int
    duration: float
    source: str

@dataclass
class CombatStats:
    AtkPw: int = 0
    AtkSp: int = 0
    MgcPw: int = 0
    Block: int = 0
    Dodge: int = 0
    Armor: int = 0
    MgcRs: int = 0
    Crits: int = 0
    
    def __getitem__(self, key):
        return getattr(self, key, 0)
    
    def __setitem__(self, key, value):
        if hasattr(self, key):
            setattr(self, key, value)

@dataclass
class CombatLog:
    messages: List[str] = field(default_factory=list)
    max_size: int = COMBAT_LOG_SIZE
    
    def add(self, msg: str, color=None):
        if color and COLOR_ENABLED:
            msg = Colors.colorize(msg, color)
        self.messages.append(msg)
        if len(self.messages) > self.max_size:
            self.messages = self.messages[-self.max_size:]
    
    def clear(self):
        self.messages.clear()

    def get_messages(self):
        return self.messages

combat_log = CombatLog(max_size=COMBAT_LOG_SIZE)

# --- Utility: CSV load/save ---
def load_csv(filename):
    data = []
    try:
        with open(filename, mode='r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                processed = {}
                for k, v in row.items():
                    if k is None:
                        continue
                    if v is None or v == '':
                        processed[k] = None
                    else:
                        try:
                            processed[k] = int(v)
                        except ValueError:
                            try:
                                processed[k] = float(v)
                            except ValueError:
                                processed[k] = v
                data.append(processed)
    except FileNotFoundError:
        print(f"Error: File not found - {filename}")
        return None
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return None
    return data

def save_csv(filename, data, fieldnames=None):
    if not fieldnames and data:
        fieldnames = list(data[0].keys())
    try:
        with open(filename, mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        return True
    except Exception as e:
        print(f"Error saving to {filename}: {e}")
        return False

# --- Data Initialization ---
def initialize_data():
    global ALL_ITEMS, ALL_ACTIONS, DEFAULT_ACTION_KEYS

    print(Colors.colorize(f"Loading game data for pyRL {VERSION}...", Colors.CYAN))
    items_data = load_csv(ITEMS_FILE)
    actions_data = load_csv(ACTIONS_FILE)
    if not items_data or not actions_data:
        print(Colors.colorize("Failed to load essential game data. Exiting.", Colors.RED))
        sys.exit(1)

    sample = actions_data[0]
    id_key = next((k for k in sample if k.lower() == 'actionid'), None)
    if id_key is None:
        print(Colors.colorize("ERROR: pyRL_actions.csv is missing an ActionID column.", Colors.RED))
        print(Colors.colorize(f"  Available columns: {', '.join(sample.keys())}", Colors.YELLOW))
        sys.exit(1)

    for rec in actions_data:
        rec['ActionID'] = rec.pop(id_key)

    ALL_ITEMS = {item['ItemID']: item for item in items_data}
    ALL_ACTIONS = {str(act['ActionID']): act for act in actions_data}

    name_to_id = {act['Name'].lower(): str(aid) for aid, act in ALL_ACTIONS.items()}
    DEFAULT_ACTION_KEYS = {
        'A': name_to_id.get('punch'),
        'S': name_to_id.get('curse'),
        'Z': name_to_id.get('kick'),
        'X': None,
        'D': None,
        'C': None
    }

    print(Colors.colorize("Data loaded successfully.", Colors.GREEN))

# --- Character Definition ---
class Character:
    def __init__(self, data, is_player=False):
        self.is_player = is_player
        self.data = data
        self.save_id = data.get('SaveID')

        self.attributes = {
            'STA': data.get('STA', 0), 'STR': data.get('STR', 0),
            'AGI': data.get('AGI', 0), 'DEX': data.get('DEX', 0),
            'HIT': data.get('HIT', 0), 'BAL': data.get('BAL', 0),
            'WGT': data.get('WGT', 0), 'HEI': data.get('HEI', 0),
            'INT': data.get('INT', 0), 'WIL': data.get('WIL', 0),
            'FOR': data.get('FOR', 0), 'FOC': data.get('FOC', 0),
            'PSY': data.get('PSY', 0), 'ARC': data.get('ARC', 0),
            'BLS': data.get('BLS', 0), 'MAN': data.get('MAN', 0),
            'ALC': data.get('ALC', 0), 'CUR': data.get('CUR', 0),
            'COR': data.get('COR', 0), 'SUM': data.get('SUM', 0),
            'HEX': data.get('HEX', 0)
        }

        self.equipment_ids = {
            1: data.get('Head'),  2: data.get('Chest'),
            3: data.get('Legs'),  4: data.get('Feet'),
            5: data.get('OffHand'),6: data.get('MainHand'),
            7: data.get('Neck'),  8: data.get('Ring')
        }
        self.equipment = {}

        self.max_hp = 0
        self.current_hp = 0
        self.stats = CombatStats()
        self.attack_bar = 0.0
        self.queued_action_key = 'A' if is_player else None
        self.status_effects: List[StatusEffect] = []
        self.action_cooldowns = {}
        self.combat_log_buffer = []

        if not is_player:
            seq = data.get('ActionSequence', '')
            self.action_sequence = [s.strip() for s in seq.split(',')] if seq else []
            self.current_action_index = 0

        self.xp = data.get('XP', 0)
        self.xp_yield = data.get('XPYield', 0)
        self.loot_tiers = {
            1: data.get('LootTableTier1'), 2: data.get('LootTableTier2'),
            3: data.get('LootTableTier3'), 4: data.get('LootTableTier4'),
            5: data.get('LootTableTier5')
        }

        self.resolve_equipment()
        self.calculate_stats()
        self.current_hp = self.max_hp

    def resolve_equipment(self):
        self.equipment = {}
        for slot, iid in self.equipment_ids.items():
            if iid:
                self.equipment[slot] = ALL_ITEMS.get(iid)

    def get_attribute_bonus(self, name):
        bonus = 0
        for item in self.equipment.values():
            if not item:
                continue
            if item.get('Bonus1') == name:
                bonus += item.get('BonusValue1', 0)
            if item.get('Bonus2') == name:
                bonus += item.get('BonusValue2', 0)
        for eff in self.status_effects:
            if eff.stat == name:
                bonus += eff.value
        return bonus

    def get_stat_bonus(self, stat):
        bonus = 0
        for item in self.equipment.values():
            if not item:
                continue
            if item.get('Bonus1') == stat:
                bonus += item.get('BonusValue1', 0)
            if item.get('Bonus2') == stat:
                bonus += item.get('BonusValue2', 0)
        for eff in self.status_effects:
            if eff.stat == stat:
                bonus += eff.value
        return bonus

    def get_final_attribute(self, name):
        if not name:
            return 0
        return max(0, self.attributes.get(name, 0) + self.get_attribute_bonus(name))

    def calculate_stats(self):
        sta, str_, agi = (self.get_final_attribute(x) for x in ('STA', 'STR', 'AGI'))
        dex, hit, bal = (self.get_final_attribute(x) for x in ('DEX', 'HIT', 'BAL'))
        int_, wil, for_ = (self.get_final_attribute(x) for x in ('INT', 'WIL', 'FOR'))
        foc, psy, arc = (self.get_final_attribute(x) for x in ('FOC', 'PSY', 'ARC'))
        bls, man = self.get_final_attribute('BLS'), self.get_final_attribute('MAN')

        base_hp = 50 + (5 * sta) + (2 * str_) + (2 * wil) + for_ + foc + bls
        self.max_hp = math.ceil(base_hp)

        self.stats.AtkPw = str_ + str_ + agi + dex + bal + self.get_stat_bonus('AtkPw')
        self.stats.AtkSp = agi + agi + dex + wil + foc + self.get_stat_bonus('AtkSp')
        self.stats.MgcPw = int_ + int_ + man + arc + wil + self.get_stat_bonus('MgcPw')
        self.stats.Block = str_ + for_ + int_ + bal + wil + self.get_stat_bonus('Block')
        self.stats.Dodge = foc + agi + dex + bal + psy + self.get_stat_bonus('Dodge')
        self.stats.Armor = str_ + for_ + sta + agi + bls + self.get_stat_bonus('Armor')
        self.stats.MgcRs = psy + bls + wil + man + for_ + self.get_stat_bonus('MgcRs')
        self.stats.Crits = hit + hit + hit + arc + foc + self.get_stat_bonus('Crits')

        self.stats.AtkSp = max(1, self.stats.AtkSp)
        self.stats.Crits = max(0, self.stats.Crits)

    def get_attack_fill_time(self):
        atk_sp = self.stats.AtkSp
        norm = max(1, min(atk_sp, 100))
        ft = 1.2 + (5.0 - 1.2) * (1 - norm / 100.0)
        return max(0.1, ft)

    def update_attack_bar(self, dt):
        inc = (100.0 / self.get_attack_fill_time()) * dt
        self.attack_bar = min(100.0, self.attack_bar + inc)

    def update_cooldowns(self, dt):
        to_remove = []
        for aid, tleft in self.action_cooldowns.items():
            self.action_cooldowns[aid] -= dt
            if self.action_cooldowns[aid] <= 0:
                to_remove.append(aid)
        for aid in to_remove:
            del self.action_cooldowns[aid]

    def update_status_effects(self, dt):
        expired, recalc = [], False
        for eff in self.status_effects:
            eff.duration -= dt
            if eff.duration <= 0:
                expired.append(eff)
                recalc = True
        if recalc:
            for e in expired:
                self.add_log(f"{e.name} wore off.")
            self.status_effects = [e for e in self.status_effects if e not in expired]
            self.calculate_stats()

    def add_log(self, msg):
        self.combat_log_buffer.append(msg)

    def get_and_clear_log_buffer(self):
        buf = list(self.combat_log_buffer)
        self.combat_log_buffer.clear()
        return buf

    def take_damage(self, amt):
        self.current_hp = max(0, self.current_hp - amt)
        return self.current_hp <= 0

    def heal(self, amt):
        self.current_hp = min(self.max_hp, self.current_hp + amt)

    def start_cooldown(self, aid, duration):
        if duration and duration > 0:
            self.action_cooldowns[str(aid)] = duration

    def add_status_effect(self, eid, name, stat, val, dur, src):
        if len(self.status_effects) >= 3:
            self.add_log(f"Cannot apply {name}: Max status effects reached.")
            return False
        for i, e in enumerate(self.status_effects):
            if e.id == eid:
                self.status_effects[i] = StatusEffect(eid, name, stat, val, dur, src)
                self.add_log(f"{self.data['Name']} refreshes {name}.")
                self.calculate_stats()
                return True
        self.status_effects.append(StatusEffect(eid, name, stat, val, dur, src))
        self.add_log(f"{self.data['Name']} is affected by {name}.")
        self.calculate_stats()
        return True

    def get_action_for_key(self, key):
        aid = None
        if key in ('A', 'S'):
            aid = DEFAULT_ACTION_KEYS.get(key)
        elif key == 'Z':
            item = self.equipment.get(6)
            aid = item.get('ActionID') if item else DEFAULT_ACTION_KEYS.get('Z')
        elif key == 'X':
            item = self.equipment.get(5)
            aid = item.get('ActionID') if item else DEFAULT_ACTION_KEYS.get('X')
        elif key == 'D':
            item = self.equipment.get(7)
            aid = item.get('ActionID') if item else DEFAULT_ACTION_KEYS.get('D')
        elif key == 'C':
            item =	self.equipment.get(8)
            aid = item.get('ActionID') if item else DEFAULT_ACTION_KEYS.get('C')
        if not aid:
            return None
        aid = str(aid)
        if aid not in ALL_ACTIONS:
            self.add_log(f"Action ID '{aid}' not found!")
            return None
        if aid in self.action_cooldowns:
            cd = self.action_cooldowns[aid]
            self.add_log(f"Action {ALL_ACTIONS[aid]['Name']} is on cooldown ({cd:.1f}s left)." )
            return None
        return ALL_ACTIONS[aid]

    def get_npc_action(self):
        if not getattr(self, 'action_sequence', []):
            fallback = DEFAULT_ACTION_KEYS.get('A')
            return ALL_ACTIONS.get(fallback)
        aid = self.action_sequence[self.current_action_index]
        self.current_action_index = (self.current_action_index + 1) % len(self.action_sequence)
        aid = str(aid)
        if aid not in ALL_ACTIONS:
            self.add_log(f"NPC Action ID '{aid}' not found; falling back to punch.")
            aid = DEFAULT_ACTION_KEYS.get('A')
        if aid in self.action_cooldowns:
            cd = self.action_cooldowns[aid]
            self.add_log(f"NPC Action {ALL_ACTIONS[aid]['Name']} is on cooldown ({cd:.1f}s left)." )
            return None
        return ALL_ACTIONS.get(aid)

    def get_name(self):
        return self.data.get('Name', 'Unknown')

    def get_equipment_actions(self):
        actions = {}
        for slot, item in self.equipment.items():
            if item and 'ActionID' in item:
                aid = str(item['ActionID'])
                if aid in ALL_ACTIONS:
                    name = ALL_ACTIONS[aid]['Name']
                    key = None
                    if slot == 6: key = 'Z'
                    elif slot == 5: key = 'X'
                    elif slot == 7: key = 'D'
                    elif slot == 8: key = 'C'
                    if key:
                        actions[key] = name
        return actions

# --- Input Thread ---
player_input_queue = queue.Queue()
def non_blocking_input_reader():
    if os.name == 'nt':
        import msvcrt
        while True:
            if msvcrt.kbhit():
                ch = msvcrt.getch().decode('utf-8', errors='ignore').upper()
                player_input_queue.put(ch)
            time.sleep(0.05)
    else:
        import tty, termios, select
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while True:
                if select.select([sys.stdin], [], [], 0.05) == ([sys.stdin], [], []):
                    ch = sys.stdin.read(1).upper()
                    player_input_queue.put(ch)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

# --- Combat Resolution ---
total_player_damage = 0
total_enemy_damage = 0
combat_start_time = 0

def add_to_combat_log(msg, color=None):
    combat_log.add(msg, color)

def make_bar(cur, maxv, w, color_fill=None, color_empty=None):
    if maxv == 0:
        return "[" + " "*w + "]"
    pct = cur / maxv
    filled = int(pct * w)
    if color_fill and color_empty and COLOR_ENABLED:
        return "[" + Colors.colorize("■"*filled, color_fill) + Colors.colorize(" "*(w-filled), color_empty) + "]"
    return "[" + "■"*filled + " "*(w-filled) + "]"

def display_hud(player, enemy, queued):
    os.system(CLEAR_CMD)
    elapsed = time.time() - combat_start_time
    p_dps = total_player_damage / elapsed if elapsed > 0 else 0
    e_dps = total_enemy_damage / elapsed if elapsed > 0 else 0

    def get_hp_color(cur, maxv):
        ratio = cur / maxv if maxv>0 else 0
        if ratio <= 0.25:
            return Colors.RED
        if ratio <= 0.5:
            return Colors.YELLOW
        return Colors.GREEN

    # Player HUD
    p_color = get_hp_color(player.current_hp, player.max_hp)
    p_bar = make_bar(player.current_hp, player.max_hp, 30, color_fill=p_color, color_empty=Colors.WHITE)
    a_bar = make_bar(player.attack_bar, 100, 30, color_fill=Colors.CYAN, color_empty=Colors.WHITE)
    print("="*HUD_WIDTH)
    print(f"{Colors.BOLD}[{player.get_name()}]{Colors.RESET} HP:{player.current_hp}/{player.max_hp} {p_bar}    DPS:{p_dps:.1f}")
    print(f"Queued:{queued}    AtkBar:{a_bar} {player.attack_bar:.0f}%")
    stats = player.stats
    print(f"Stats: AtkPw:{stats.AtkPw}  AtkSp:{stats.AtkSp}  Block:{stats.Block}  Dodge:{stats.Dodge}  MgcRs:{stats.MgcRs}  Crits:{stats.Crits}")

    # Enemy HUD
    e_color = get_hp_color(enemy.current_hp, enemy.max_hp)
    e_bar = make_bar(enemy.current_hp, enemy.max_hp, 30, color_fill=e_color, color_empty=Colors.WHITE)
    en_ab = make_bar(enemy.attack_bar, 100, 30, color_fill=Colors.MAGENTA, color_empty=Colors.WHITE)
    next_id = None
    if hasattr(enemy, 'action_sequence') and enemy.action_sequence:
        next_id = str(enemy.action_sequence[enemy.current_action_index])
    next_name = ALL_ACTIONS.get(next_id, {}).get('Name','Unknown') if next_id else 'N/A'
    print("-"*HUD_WIDTH)
    print(f"{Colors.BOLD}[{enemy.get_name()}]{Colors.RESET} HP:{enemy.current_hp}/{enemy.max_hp} {e_bar}    Next:{next_name}    DPS:{e_dps:.1f}")
    es = enemy.stats
    print(f"Stats: AtkPw:{es.AtkPw}  AtkSp:{es.AtkSp}  Block:{es.Block}  Dodge:{es.Dodge}  MgcRs:{es.MgcRs}  Crits:{es.Crits}")
    print("="*HUD_WIDTH)

    # Combat Log
    print(Colors.BOLD + "Combat Log:" + Colors.RESET)
    for m in combat_log.get_messages():
        print("- " + m)
    print("="*HUD_WIDTH)

    # Controls
    base_ctrls = ["[A] Melee","[S] Magic"]
    eq_ctrls = [f"[{k}] {v}" for k,v in player.get_equipment_actions().items()]
    print("Controls: " + " | ".join(base_ctrls + eq_ctrls))
    print("="*HUD_WIDTH)

# --- Combat Simulation ---
def simulate_combat(player, enemy):
    global combat_start_time, total_player_damage, total_enemy_damage
    combat_log.clear()
    player.attack_bar = enemy.attack_bar = 0.0
    player.action_cooldowns = {}
    enemy.action_cooldowns  = {}
    player.status_effects = []
    enemy.status_effects  = []
    player.calculate_stats()
    enemy.calculate_stats()
    player.current_hp = player.max_hp
    enemy.current_hp  = enemy.max_hp
    total_player_damage = total_enemy_damage = 0
    combat_start_time = time.time()
    last_time = combat_start_time

    t = threading.Thread(target=non_blocking_input_reader, daemon=True)
    t.start()

    queued_act = player.get_action_for_key(player.queued_action_key)
    queued_name = queued_act['Name'] if queued_act else "None"

    while player.current_hp>0 and enemy.current_hp>0:
        now = time.time()
        dt  = now - last_time
        last_time = now

        # Handle input
        while not player_input_queue.empty():
            ch = player_input_queue.get()
            if ch in ['A','S','Z','X','D','C']:
                act = player.get_action_for_key(ch)
                if act:
                    player.queued_action_key = ch
                    queued_name = act['Name']
                    add_to_combat_log(f"Player queues {queued_name}.", Colors.BLUE)

        # Update state
        player.update_attack_bar(dt)
        enemy.update_attack_bar(dt)
        player.update_cooldowns(dt)
        enemy.update_cooldowns(dt)
        player.update_status_effects(dt)
        enemy.update_status_effects(dt)

        # Player action
        if player.attack_bar >= 100:
            act = player.get_action_for_key(player.queued_action_key)
            if act:
                resolve_action(player, enemy, act)
                player.attack_bar -= 100
                if enemy.current_hp <= 0:
                    display_hud(player, enemy, queued_name)
                    break
            else:
                add_to_combat_log(f"Player action ({queued_name}) failed.", Colors.YELLOW)
                player.attack_bar = 0

        # Enemy action
        if enemy.current_hp>0 and enemy.attack_bar>=100:
            act = enemy.get_npc_action()
            if act:
                resolve_action(enemy, player, act)
                enemy.attack_bar -= 100
                if player.current_hp<=0:
                    display_hud(player, enemy, queued_name)
                    break
            else:
                add_to_combat_log("Enemy action failed.", Colors.YELLOW)
                enemy.attack_bar = 0

        # Transfer logs
        for msg in player.get_and_clear_log_buffer():
            add_to_combat_log(f"[P] {msg}", Colors.WHITE)
        for msg in enemy.get_and_clear_log_buffer():
            add_to_combat_log(f"[E] {msg}", Colors.WHITE)

        display_hud(player, enemy, queued_name)

        # Frame limit
        wait = REFRESH_RATE - (time.time()-now)
        if wait>0:
            time.sleep(wait)

    display_hud(player, enemy, queued_name)
    print(Colors.BOLD + "== Combat End ==" + Colors.RESET)
    if player.current_hp<=0:
        print(Colors.RED + f"*** {player.get_name()} has been defeated by {enemy.get_name()}! ***" + Colors.RESET)
        return False
    else:
        print(Colors.GREEN + f"*** {player.get_name()} defeated {enemy.get_name()}! ***" + Colors.RESET)
        return True

# --- Post-Combat Loot & XP ---
def handle_loot_and_xp(player, enemy):
    print(Colors.BOLD + "-- Rewards --" + Colors.RESET)
    # XP
    xp = enemy.xp_yield
    player.xp += xp
    player.data['XP'] = player.xp
    print(Colors.CYAN + f"Gained {xp} XP! Total XP: {player.xp}" + Colors.RESET)

    # Loot roll logic (same as before)
    roll = random.uniform(0,100)
    tier = None
    if roll<2: tier=5
    elif roll<10: tier=4
    elif roll<40: tier=3
    elif roll<70: tier=2
    else: tier=1
    chosen = enemy.loot_tiers.get(tier)
    if not chosen or chosen not in ALL_ITEMS:
        print("No loot drop.")
        return
    item = ALL_ITEMS[chosen]

    print(Colors.BOLD + f"Loot Found: {item['Name']} (Slot {item.get('Slot')})" + Colors.RESET)
    bonuses=[]
    if item.get('Bonus1'): bonuses.append(f"{item['Bonus1']} {item.get('BonusValue1',0):+}")
    if item.get('Bonus2'): bonuses.append(f"{item['Bonus2']} {item.get('BonusValue2',0):+}")
    if bonuses:
        print("Bonuses: " + ", ".join(bonuses))
    else:
        print("Bonuses: None")

    while True:
        choice = input("Equip this item? (Y/N): ").upper()
        if choice=='Y':
            slot = item.get('Slot')
            player.equipment_ids[slot] = chosen
            player.resolve_equipment()
            player.calculate_stats()
            player.current_hp = min(player.current_hp, player.max_hp)
            print(Colors.GREEN + f"Equipped {item['Name']}!" + Colors.RESET)
            break
        elif choice=='N':
            print("Kept current equipment.")
            break

# --- Saving Character ---
def save_character_data(player):
    if not player.is_player or not player.save_id:
        return
    try:
        rows=[]
        fieldnames=[]
        try:
            with open(SAVED_FILE, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []
                for r in reader:
                    rows.append(r)
        except FileNotFoundError:
            fieldnames = list(player.data.keys())

        updated=False
        for i,r in enumerate(rows):
            if str(r.get('SaveID'))==str(player.save_id):
                for fn in fieldnames:
                    if fn in player.data:
                        r[fn] = player.data[fn]
                r['XP'] = player.xp
                rows[i]=r
                updated=True
                break
        if not updated:
            print(Colors.YELLOW + f"SaveID {player.save_id} not found." + Colors.RESET)
            return
        with open(SAVED_FILE, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(Colors.CYAN + f"Character {player.get_name()} saved." + Colors.RESET)
    except Exception as e:
        print(Colors.RED + f"Error saving: {e}" + Colors.RESET)

# --- Character Selection ---
def select_character(is_saved: bool):
    source = SAVED_FILE if is_saved else TOONS_FILE
    data = load_csv(source)
    if not data:
        print(f"No characters in {source}.")
        return None
    print(Colors.BOLD + ("Saved Characters" if is_saved else "Default Characters") + Colors.RESET)
    for i,d in enumerate(data,1):
        name = d.get('Name','Unnamed')
        sid  = f"(ID:{d.get('SaveID')})" if is_saved else ''
        xp   = f"XP:{d.get('XP',0)}" if is_saved else ''
        print(f"{i}. {name} {sid} {xp}")
    while True:
        c=input("Choose (number): ")
        if c.isdigit():
            idx=int(c)-1
            if 0<=idx<len(data):
                return data[idx]

# --- Opponent Selection ---
def select_opponent():
    data = load_csv(NPCS_FILE)
    if not data:
        print(f"No opponents in {NPCS_FILE}.")
        return None
    print(Colors.BOLD + "Opponents" + Colors.RESET)
    for i,d in enumerate(data,1): print(f"{i}. {d.get('Name','Unnamed')}")
    while True:
        c=input("Choose (number): ")
        if c.isdigit():
            idx=int(c)-1
            if 0<=idx<len(data):
                return data[idx]

# --- Main Game Loop ---
def main():
    initialize_data()
    while True:
        print(Colors.BOLD + f"--- pyRL Combat v{VERSION} ---" + Colors.RESET)
        player_data=None
        saved=False
        while not player_data:
            print("1) Default Characters    2) Saved Characters")
            c=input("Source (1/2): ")
            if c=='1': player_data=select_character(False)
            if c=='2':
                player_data=select_character(True)
                saved=True
        player=Character(player_data, True)
        print(f"You chose {player.get_name()}.")

        opponent_data=None
        while not opponent_data:
            opponent_data=select_opponent()
        enemy=Character(opponent_data, False)
        print(f"Facing {enemy.get_name()}.")
        input("Press Enter to begin...")

        won=simulate_combat(player, enemy)
        if won:
            handle_loot_and_xp(player, enemy)
            if saved:
                save_character_data(player)
        else:
            print(Colors.RED + "Game Over!" + Colors.RESET)

        again=input("Play again? (Y/N): ").upper()
        if again!='Y': break
    print(Colors.CYAN + "Thanks for playing!" + Colors.RESET)

if __name__=="__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(Colors.RED + f"Fatal error: {e}" + Colors.RESET)
        traceback.print_exc()
        input("Press Enter to exit.")
