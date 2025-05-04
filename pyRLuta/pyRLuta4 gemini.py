#code works mostly, health dones go down and i think the attacks are being a bit odd. I think there is a problem where i called some default actions in the evernote
#!/usr/bin/env python3
import csv
import os
import sys
import time
import random
import threading
import queue
import math

# --- Force cwd to script's folder so CSVs are always found here ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# --- Constants ---
REFRESH_RATE    = 0.1
HUD_WIDTH       = 60
COMBAT_LOG_SIZE = 10
CLEAR_CMD       = 'cls' if os.name == 'nt' else 'clear'

# --- Script-relative CSV paths ---
TOONS_FILE       = os.path.join(BASE_DIR, 'pyRL_toons.csv')
SAVED_FILE       = os.path.join(BASE_DIR, 'pyRL_saved.csv')
NPCS_FILE        = os.path.join(BASE_DIR, 'pyRL_npcs.csv')
ITEMS_FILE       = os.path.join(BASE_DIR, 'pyRL_items.csv')
ACTIONS_FILE     = os.path.join(BASE_DIR, 'pyRL_actions.csv')
LEADERBOARD_FILE = os.path.join(BASE_DIR, 'pyRL_leaderboard.csv')

# --- Global lookups populated at runtime ---
ALL_ITEMS           = {}
ALL_ACTIONS         = {}
DEFAULT_ACTION_KEYS = {}

def load_csv(filename):
    data = []
    try:
        with open(filename, mode='r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                processed = {}
                for k, v in row.items():
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

def initialize_data():
    """Load items & actions, detect ActionID column, build lookups & defaults."""
    global ALL_ITEMS, ALL_ACTIONS, DEFAULT_ACTION_KEYS

    print("Loading game data…")
    items_data   = load_csv(ITEMS_FILE)
    actions_data = load_csv(ACTIONS_FILE)
    if not items_data or not actions_data:
        print("Failed to load essential game data. Exiting.")
        sys.exit(1)

    # detect 'actionid' column, case-insensitive
    sample = actions_data[0]
    id_key = next((k for k in sample if k.lower() == 'actionid'), None)
    if id_key is None:
        print("ERROR: pyRL_actions.csv is missing an ActionID column.")
        print("  Available columns:", ", ".join(sample.keys()))
        sys.exit(1)

    # normalize to rec['ActionID']
    for rec in actions_data:
        rec['ActionID'] = rec.pop(id_key)

    ALL_ITEMS   = {item['ItemID']: item for item in items_data}
    ALL_ACTIONS = {act['ActionID']: act for act in actions_data}

    # build defaults by matching on action Name
    name_to_id = {act['Name'].lower(): aid for aid, act in ALL_ACTIONS.items()}
    DEFAULT_ACTION_KEYS = {
        'A': name_to_id.get('punch'),
        'S': name_to_id.get('curse'),
        'Z': name_to_id.get('kick'),
        'X': None,
        'D': None,
        'C': None
    }

    print("Data loaded successfully. Defaults:", DEFAULT_ACTION_KEYS)

class Character:
    def __init__(self, data, is_player=False):
        self.is_player = is_player
        self.data      = data
        self.save_id   = data.get('SaveID')

        # base attributes
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

        # equipment by slot
        self.equipment_ids = {
            1: data.get('Head'),  2: data.get('Chest'),
            3: data.get('Legs'),  4: data.get('Feet'),
            5: data.get('OffHand'),6: data.get('MainHand'),
            7: data.get('Neck'),  8: data.get('Ring')
        }
        self.equipment = {}

        # combat state
        self.max_hp           = 0
        self.current_hp       = 0
        self.stats            = {}
        self.attack_bar       = 0.0
        self.queued_action_key= 'A' if is_player else None
        self.status_effects   = []
        self.action_cooldowns = {}
        self.combat_log_buffer= []

        # NPC sequence
        if not is_player:
            seq = data.get('ActionSequence', '')
            self.action_sequence = [s.strip() for s in seq.split(',')] if seq else []
            self.current_action_index = 0

        # XP & loot
        self.xp        = data.get('XP', 0)
        self.xp_yield  = data.get('XPYield', 0)
        self.loot_tiers= {
            1: data.get('LootTableTier1'), 2: data.get('LootTableTier2'),
            3: data.get('LootTableTier3'), 4: data.get('LootTableTier4'),
            5: data.get('LootTableTier5')
        }

        # finalize
        self.resolve_equipment()
        self.calculate_stats()
        self.current_hp = self.max_hp

    def resolve_equipment(self):
        self.equipment = {}
        for slot, iid in self.equipment_ids.items():
            self.equipment[slot] = ALL_ITEMS.get(iid)

    def get_attribute_bonus(self, name):
        bonus = 0
        for item in self.equipment.values():
            if not item: continue
            if item.get('Bonus1') == name: bonus += item.get('BonusValue1', 0)
            if item.get('Bonus2') == name: bonus += item.get('BonusValue2', 0)
        for eff in self.status_effects:
            if eff['stat'] == name: bonus += eff['value']
        return bonus

    def get_stat_bonus(self, stat):
        bonus = 0
        for item in self.equipment.values():
            if not item: continue
            if item.get('Bonus1') == stat: bonus += item.get('BonusValue1', 0)
            if item.get('Bonus2') == stat: bonus += item.get('BonusValue2', 0)
        for eff in self.status_effects:
            if eff['stat'] == stat: bonus += eff['value']
        return bonus

    def get_final_attribute(self, name):
        return max(0, self.attributes.get(name, 0) + self.get_attribute_bonus(name))

    def calculate_stats(self):
        sta, str_, agi = (self.get_final_attribute(x) for x in ('STA','STR','AGI'))
        dex, hit, bal  = (self.get_final_attribute(x) for x in ('DEX','HIT','BAL'))
        int_, wil, for_ = (self.get_final_attribute(x) for x in ('INT','WIL','FOR'))
        foc, psy, arc = (self.get_final_attribute(x) for x in ('FOC','PSY','ARC'))
        bls, man       = self.get_final_attribute('BLS'), self.get_final_attribute('MAN')

        # HP formula
        base_hp = 50 + (5*sta) + (2*str_) + (2*wil) + for_ + foc + bls
        self.max_hp = int(base_hp)

        # derived stats
        self.stats = {
            'AtkPw': str_ + str_ + agi + dex + bal + self.get_stat_bonus('AtkPw'),
            'AtkSp': agi + agi + dex + wil + foc + self.get_stat_bonus('AtkSp'),
            'MgcPw': int_ + int_ + man + arc + wil + self.get_stat_bonus('MgcPw'),
            'Block': str_ + for_ + int_ + bal + wil + self.get_stat_bonus('Block'),
            'Dodge': foc + agi + dex + bal + psy + self.get_stat_bonus('Dodge'),
            'Armor': str_ + for_ + sta + agi + bls + self.get_stat_bonus('Armor'),
            'MgcRs': psy + bls + wil + man + for_ + self.get_stat_bonus('MgcRs'),
            'Crits': hit + hit + hit + arc + foc + self.get_stat_bonus('Crits')
        }
        # ensure minima
        self.stats['AtkSp']  = max(1, self.stats['AtkSp'])
        self.stats['Crits']  = max(0, self.stats['Crits'])

    def get_attack_fill_time(self):
        atk_sp = self.stats.get('AtkSp', 1)
        norm  = max(1, min(atk_sp, 100))
        ft    = 1.2 + (5.0 - 1.2)*(1 - norm/100.0)
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
            eff['duration'] -= dt
            if eff['duration'] <= 0:
                expired.append(eff)
                recalc = True
        if recalc:
            for e in expired:
                self.add_log(f"{e['name']} wore off.")
            self.status_effects = [e for e in self.status_effects if e not in expired]
            self.calculate_stats()

    def add_log(self, msg):
        self.combat_log_buffer.append(msg)

    def get_and_clear_log_buffer(self):
        buf = self.combat_log_buffer[:]
        self.combat_log_buffer.clear()
        return buf

    def take_damage(self, amt):
        self.current_hp = max(0, self.current_hp - amt)
        return self.current_hp <= 0

    def heal(self, amt):
        self.current_hp = min(self.max_hp, self.current_hp + amt)

    def start_cooldown(self, aid, duration):
        if duration and duration > 0:
            self.action_cooldowns[aid] = duration

    def add_status_effect(self, eid, name, stat, val, dur, src):
        if len(self.status_effects) >= 2:
            self.add_log(f"Cannot apply {name}: Max status effects reached.")
            return False
        for i, e in enumerate(self.status_effects):
            if e['id'] == eid:
                self.status_effects[i] = {'id':eid,'name':name,'stat':stat,'value':val,'duration':dur,'source':src}
                self.add_log(f"{self.data['Name']} refreshes {name}.")
                self.calculate_stats()
                return True
        self.status_effects.append({'id':eid,'name':name,'stat':stat,'value':val,'duration':dur,'source':src})
        self.add_log(f"{self.data['Name']} is affected by {name}.")
        self.calculate_stats()
        return True

    def get_action_for_key(self, key):
        # choose ID
        aid = None
        if key in ('A','S'):
            aid = DEFAULT_ACTION_KEYS.get(key)
        elif key == 'Z':
            item = self.equipment.get(6)
            aid  = item.get('ActionID') if item else DEFAULT_ACTION_KEYS.get('Z')
        elif key == 'X':
            item = self.equipment.get(5)
            aid  = item.get('ActionID') if item else DEFAULT_ACTION_KEYS.get('X')
        elif key == 'D':
            item = self.equipment.get(7)
            aid  = item.get('ActionID') if item else DEFAULT_ACTION_KEYS.get('D')
        elif key == 'C':
            item = self.equipment.get(8)
            aid  = item.get('ActionID') if item else DEFAULT_ACTION_KEYS.get('C')

        if not aid:
            return None
        if aid not in ALL_ACTIONS:
            self.add_log(f"Action ID '{aid}' not found!")
            return None
        if aid in self.action_cooldowns:
            cd = self.action_cooldowns[aid]
            self.add_log(f"Action {ALL_ACTIONS[aid]['Name']} is on cooldown ({cd:.1f}s left).")
            return None
        return ALL_ACTIONS[aid]

    def get_npc_action(self):
        if not getattr(self, 'action_sequence', []):
            fallback = DEFAULT_ACTION_KEYS.get('A')
            return ALL_ACTIONS.get(fallback)
        aid = self.action_sequence[self.current_action_index]
        self.current_action_index = (self.current_action_index + 1) % len(self.action_sequence)
        if aid not in ALL_ACTIONS:
            self.add_log(f"NPC Action ID '{aid}' not found; falling back to punch.")
            aid = DEFAULT_ACTION_KEYS.get('A')
        if aid in self.action_cooldowns:
            cd = self.action_cooldowns[aid]
            self.add_log(f"NPC Action {ALL_ACTIONS[aid]['Name']} is on cooldown ({cd:.1f}s left).")
            return None
        return ALL_ACTIONS.get(aid)

    def get_name(self):
        return self.data.get('Name', 'Unknown')

# non-blocking input thread
player_input_queue = queue.Queue()
def non_blocking_input_reader():
    if os.name == 'nt':
        import msvcrt
        while True:
            if msvcrt.kbhit():
                ch = msvcrt.getch().decode('utf-8').upper()
                player_input_queue.put(ch)
            time.sleep(0.05)
    else:
        import tty, termios, select
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while True:
                if select.select([sys.stdin],[],[],0.05)==([sys.stdin],[],[]):
                    ch = sys.stdin.read(1).upper()
                    player_input_queue.put(ch)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

# combat log
combat_log = []
total_player_damage = 0
total_enemy_damage  = 0
combat_start_time   = 0

def add_to_combat_log(msg):
    global combat_log
    combat_log.append(msg)
    if len(combat_log) > COMBAT_LOG_SIZE:
        combat_log = combat_log[-COMBAT_LOG_SIZE:]

def resolve_action(attacker, target, action):
    global total_player_damage, total_enemy_damage
    if not action:
        attacker.add_log("Action failed (None).")
        return

    name    = action.get('Name','Unknown')
    a_type  = action.get('Type','Melee')
    base_d  = action.get('BaseDamage',0)
    dmg_stat= action.get('DamageStat')
    scale   = action.get('ScalingFactor',0.0)
    eff_stat= action.get('Effect')
    eff_val = action.get('EffectValue')
    eff_dur = action.get('EffectDuration',0)
    eff_tgt = action.get('EffectTarget','Self')

    prefix = f"[{attacker.get_name()}] uses {name}:"
    attacker.add_log(f"Used {name}.")

    # self-effects first
    if eff_stat and eff_tgt=='Self':
        if eff_stat=='HP':
            amt = int(eff_val or 0)
            attacker.heal(amt)
            add_to_combat_log(f"{prefix} Heals self for {amt} HP.")
        else:
            eid = f"{action['ActionID']}_{eff_stat}"
            if attacker.add_status_effect(eid, f"{name} Effect", eff_stat, eff_val, eff_dur, action['ActionID']):
                add_to_combat_log(f"{prefix} Gains {name} effect ({eff_stat} {eff_val:+}).")
            else:
                add_to_combat_log(f"{prefix} Fails to gain {name} effect (max reached).")

    # damage calculation
    final = 0; is_crit=False
    if base_d>0:
        stat_val = attacker.stats.get(dmg_stat,0) if dmg_stat else 0
        scaled   = base_d + (stat_val * scale)

        # dodge check
        dodge_chance = target.stats.get('Dodge',0)/10.0
        if random.uniform(0,100) < dodge_chance:
            add_to_combat_log(f"{prefix} [{target.get_name()}] Dodged!")
            target.add_log("Dodged!")
        else:
            # crit
            crit_chance = attacker.stats.get('Crits',0)/3.0
            if random.uniform(0,100) < crit_chance:
                scaled *= 2; is_crit=True
                add_to_combat_log(f"{prefix} CRITICAL HIT!")

            # mitigation
            if a_type=='Melee':
                block = target.stats.get('Block',0)
                mit   = min(random.uniform(1, max(1,block))/100.0, 0.90)
                final = int(max(0, scaled*(1-mit)))
                mit_str = f"{mit*100:.1f}% Blocked"
            elif a_type=='Magic':
                mrs   = target.stats.get('MgcRs',0)
                mit   = min(random.uniform(1, max(1,mrs))/100.0, 0.90)
                final = int(max(0, scaled*(1-mit)))
                mit_str = f"{mit*100:.1f}% Resisted"
            else:
                final = int(max(0, scaled))
                mit_str="No Mitigation"

            died = target.take_damage(final)
            crit_s = " (Crit!)" if is_crit else ""
            add_to_combat_log(f"{prefix} Hits [{target.get_name()}] for {final} damage{crit_s}. ({mit_str})")
            target.add_log(f"Took {final} damage{crit_s}.")

            if attacker.is_player:
                total_player_damage += final
            else:
                total_enemy_damage += final

            if died:
                add_to_combat_log(f"*** [{target.get_name()}] has been defeated! ***")

    # target-effects
    if eff_stat and eff_tgt=='Target':
        if eff_stat=='HP':
            dmg = int(eff_val)
            died = target.take_damage(dmg)
            add_to_combat_log(f"{prefix} Deals {dmg} direct effect damage to [{target.get_name()}].")
            if died:
                add_to_combat_log(f"*** [{target.get_name()}] has been defeated by the effect! ***")
        else:
            eid = f"{action['ActionID']}_{eff_stat}"
            if target.add_status_effect(eid, f"{name} Effect", eff_stat, eff_val, eff_dur, action['ActionID']):
                add_to_combat_log(f"{prefix} Inflicts {name} effect on [{target.get_name()}] ({eff_stat} {eff_val:+}).")
            else:
                add_to_combat_log(f"{prefix} Fails to inflict {name} effect on [{target.get_name()}] (max reached).")

    # cooldown
    cd = action.get('CooldownTime')
    if cd:
        attacker.start_cooldown(action['ActionID'], cd)

def make_bar(cur, maxv, w):
    if maxv==0: return "[ " + " "*w + " ]"
    pct = cur/maxv
    filled = int(pct*w)
    return "[" + "■"*filled + " "*(w-filled) + "]"

def display_hud(player, enemy, queued):
    os.system(CLEAR_CMD)
    elapsed = time.time() - combat_start_time
    p_dps   = total_player_damage/elapsed if elapsed>0 else 0
    e_dps   = total_enemy_damage/elapsed if elapsed>0 else 0

    print("-"*HUD_WIDTH)
    pbar = make_bar(player.current_hp, player.max_hp,20)
    ab   = make_bar(player.attack_bar,100,20)
    print(f"[{player.get_name()}] HP: {player.current_hp}/{player.max_hp} {pbar}")
    print(f"ATK BAR: {ab} {player.attack_bar:.0f}%")
    print(f"Queued: {queued} ({player.queued_action_key})")
    print(f"DPS: {p_dps:.1f}")
    stats = player.stats
    print(f"Stats: AtkPw:{stats['AtkPw']}/AtkSp:{stats['AtkSp']}/MgcPw:{stats['MgcPw']}/Block:{stats['Block']}/Dodge:{stats['Dodge']}/MgcRs:{stats['MgcRs']}/Crits:{stats['Crits']}")
    effs = [f"{e['name']}({e['duration']:.1f}s)" for e in player.status_effects]
    print("Effects:", ", ".join(effs) if effs else "None")
    print("-"*(HUD_WIDTH//2))

    ebar = make_bar(enemy.current_hp, enemy.max_hp,20)
    eab  = make_bar(enemy.attack_bar,100,20)
    next_id = enemy.action_sequence[enemy.current_action_index] if getattr(enemy,'action_sequence',None) else None
    next_name = ALL_ACTIONS.get(next_id,{}).get('Name','Unknown') if next_id else 'N/A'
    print(f"[{enemy.get_name()}] HP: {enemy.current_hp}/{enemy.max_hp} {ebar}")
    print(f"ATK BAR: {eab} {enemy.attack_bar:.0f}%")
    print(f"Next Action: {next_name}")
    print(f"DPS: {e_dps:.1f}")
    est = enemy.stats
    print(f"Stats: AtkPw:{est['AtkPw']}/AtkSp:{est['AtkSp']}/MgcPw:{est['MgcPw']}/Block:{est['Block']}/Dodge:{est['Dodge']}/MgcRs:{est['MgcRs']}/Crits:{est['Crits']}")
    effs = [f"{e['name']}({e['duration']:.1f}s)" for e in enemy.status_effects]
    print("Effects:", ", ".join(effs) if effs else "None")
    print("-"*HUD_WIDTH)

    print("Combat Log:")
    if not combat_log:
        print("(Log is empty)")
    else:
        for msg in combat_log:
            print(f"- {msg}")
    print("-"*HUD_WIDTH)
    print("Controls: [A] Melee | [S] Magic | [Z] MainHand | [X] OffHand | [D] Neck | [C] Ring")

def simulate_combat(player, enemy):
    global combat_log, combat_start_time, total_player_damage, total_enemy_damage
    combat_log           = []
    player.attack_bar    = enemy.attack_bar    = 0
    player.action_cooldowns = enemy.action_cooldowns = {}
    player.status_effects   = enemy.status_effects   = []
    player.calculate_stats(); enemy.calculate_stats()
    player.current_hp      = player.max_hp
    enemy.current_hp       = enemy.max_hp
    total_player_damage  = total_enemy_damage = 0
    combat_start_time    = time.time()
    last_time            = combat_start_time

    input_thread = threading.Thread(target=non_blocking_input_reader, daemon=True)
    input_thread.start()

    player_action = player.get_action_for_key(player.queued_action_key)
    queued_name   = player_action['Name'] if player_action else "None"

    while player.current_hp>0 and enemy.current_hp>0:
        now = time.time()
        dt  = now - last_time
        last_time = now

        # handle input
        try:
            while not player_input_queue.empty():
                ch = player_input_queue.get_nowait()
                if ch in ['A','S','Z','X','D','C']:
                    act = player.get_action_for_key(ch)
                    if act:
                        player.queued_action_key = ch
                        queued_name = act['Name']
                        add_to_combat_log(f"Player queues {queued_name}.")
        except queue.Empty:
            pass

        # update bars, cooldowns, effects
        player.update_attack_bar(dt); enemy.update_attack_bar(dt)
        player.update_cooldowns(dt); enemy.update_cooldowns(dt)
        player.update_status_effects(dt); enemy.update_status_effects(dt)

        # player turn
        if player.attack_bar>=100:
            act = player.get_action_for_key(player.queued_action_key)
            if act:
                resolve_action(player, enemy, act)
                player.attack_bar -= 100
                if enemy.current_hp<=0:
                    display_hud(player, enemy, queued_name)
                    break
            else:
                add_to_combat_log(f"Player action ({queued_name}) failed (cooldown?).")
                player.attack_bar = 0

        # enemy turn
        if enemy.current_hp>0 and enemy.attack_bar>=100:
            act = enemy.get_npc_action()
            if act:
                resolve_action(enemy, player, act)
                enemy.attack_bar -= 100
                if player.current_hp<=0:
                    display_hud(player, enemy, queued_name)
                    break
            else:
                add_to_combat_log("Enemy action failed (cooldown?).")
                enemy.attack_bar = 0

        # flush buffers
        for m in player.get_and_clear_log_buffer(): add_to_combat_log(f"[P] {m}")
        for m in enemy.get_and_clear_log_buffer():  add_to_combat_log(f"[E] {m}")

        # redraw
        display_hud(player, enemy, queued_name)

        # frame limiter
        wait = REFRESH_RATE - (time.time()-now)
        if wait>0: time.sleep(wait)

    # final
    display_hud(player, enemy, queued_name)
    print("\n" + "="*HUD_WIDTH)
    if player.current_hp<=0:
        print(f"*** {player.get_name()} has been defeated by {enemy.get_name()}! ***")
        return False
    elif enemy.current_hp<=0:
        print(f"*** {player.get_name()} defeated {enemy.get_name()}! ***")
        return True
    else:
        print("Combat ended unexpectedly.")
        return False

def handle_loot_and_xp(player, enemy):
    # award XP
    xp = enemy.xp_yield
    player.xp += xp
    player.data['XP'] = player.xp
    print(f"\nYou gained {xp} XP! Total XP: {player.xp}")

    # loot roll
    roll = random.uniform(0,100)
    tier = None
    if roll<2: tier=5
    elif roll<10: tier=4
    elif roll<40: tier=3
    elif roll<70: tier=2
    elif roll<100: tier=1

    if tier is None:
        print("No item dropped this time.")
        return

    chosen = enemy.loot_tiers.get(tier)
    if not chosen:
        print("No item in that tier; no drop.")
        return

    # try to reroll if un-equippable
    attempts = 0
    orig = chosen
    while attempts<10:
        if chosen in ALL_ITEMS:
            item = ALL_ITEMS[chosen]
            slot = item.get('Slot')
            if slot and player.get_final_attribute(item.get('GearCheck',''))>=item.get('GearCheckAmount',0):
                break
        roll = random.uniform(0,100)
        if roll<2: chosen=enemy.loot_tiers.get(5)
        elif roll<10: chosen=enemy.loot_tiers.get(4)
        elif roll<40: chosen=enemy.loot_tiers.get(3)
        elif roll<70: chosen=enemy.loot_tiers.get(2)
        else: chosen=enemy.loot_tiers.get(1)
        attempts+=1

    if chosen not in ALL_ITEMS:
        print(f"Could not find suitable drop after {attempts} attempts.")
        return

    item = ALL_ITEMS[chosen]
    slot= item.get('Slot')
    cur = player.equipment_ids.get(slot)
    cur_name = ALL_ITEMS.get(cur,{}).get('Name','Nothing') if cur else "Nothing"

    print(f"\n--- Loot Found ---")
    print(f"Item: {item['Name']} (Slot {slot})")
    bonuses=[]
    if item.get('Bonus1'): bonuses.append(f"{item['Bonus1']}: {item.get('BonusValue1',0):+}")
    if item.get('Bonus2'): bonuses.append(f"{item['Bonus2']}: {item.get('BonusValue2',0):+}")
    if item.get('ActionID'): bonuses.append(f"Action: {item['ActionID']}")
    print("Bonuses:", ", ".join(bonuses) if bonuses else "None")
    if item.get('GearCheck'):
        print(f"Requires: {item['GearCheck']} {item.get('SklChkOpr','>=')} {item.get('GearCheckAmount')}. You have {player.get_final_attribute(item['GearCheck'])}")
    print(f"Currently Equipped: {cur_name}")
    print("-"*18)

    while True:
        choice = input(f"Equip {item['Name']}? (Y/N): ").upper()
        if choice=='Y':
            player.equipment_ids[slot] = chosen
            player.resolve_equipment()
            player.calculate_stats()
            player.current_hp = min(player.current_hp, player.max_hp)
            print(f"Equipped {item['Name']}.")
            break
        elif choice=='N':
            print(f"You keep your {cur_name}.")
            break

def save_character_data(player):
    if not player.is_player or not player.save_id:
        return
    try:
        rows, fieldnames = [], []
        try:
            with open(SAVED_FILE, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []
                for row in reader:
                    rows.append(row)
        except FileNotFoundError:
            fieldnames = ['SaveID','Name','STA','STR','AGI','DEX','HIT','BAL','WGT','HEI',
                          'INT','WIL','FOR','FOC','PSY','ARC','BLS','MAN','ALC','CUR',
                          'COR','SUM','HEX','Head','Chest','Legs','Feet','OffHand',
                          'MainHand','Neck','Ring','XP']

        updated = False
        for i, row in enumerate(rows):
            if str(row.get('SaveID')) == str(player.save_id):
                for fn in fieldnames:
                    if fn in player.data:
                        row[fn] = player.data[fn]
                row['XP'] = player.xp
                for slot, key in {1:'Head',2:'Chest',3:'Legs',4:'Feet',
                                  5:'OffHand',6:'MainHand',7:'Neck',8:'Ring'}.items():
                    row[key] = player.equipment_ids.get(slot,'')
                rows[i] = row
                updated = True
                break
        if not updated:
            print(f"Warning: SaveID {player.save_id} not found in {SAVED_FILE}.")
            return

        with open(SAVED_FILE, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Character {player.get_name()} saved.")
    except Exception as e:
        print(f"Error saving to {SAVED_FILE}: {e}")

def select_character(is_saved):
    source = SAVED_FILE if is_saved else TOONS_FILE
    prompt = "Saved Characters" if is_saved else "Default Characters"
    lst = load_csv(source)
    if not lst:
        print(f"No characters in {source}.")
        return None
    print(f"\n--- {prompt} ---")
    for i, d in enumerate(lst,1):
        sid = f"(ID:{d.get('SaveID')})" if is_saved else ""
        xp  = f"XP:{d.get('XP',0)}" if is_saved else ""
        print(f"{i}. {d.get('Name','Unnamed')} {sid} {xp}")
    while True:
        c = input("Choose a character (number): ")
        if not c.isdigit(): continue
        idx = int(c)-1
        if 0<=idx<len(lst):
            return lst[idx]

def select_opponent():
    lst = load_csv(NPCS_FILE)
    if not lst:
        print(f"No opponents in {NPCS_FILE}.")
        return None
    print("\n--- Select Opponent ---")
    for i,d in enumerate(lst,1):
        print(f"{i}. {d.get('Name','Unnamed')}")
    while True:
        c = input("Choose an opponent (number): ")
        if not c.isdigit(): continue
        idx = int(c)-1
        if 0<=idx<len(lst):
            return lst[idx]

def main():
    initialize_data()
    while True:
        print("\n===== pyRL ASCII Combat =====")
        player_data = None
        is_saved    = False
        while not player_data:
            print("\nLoad Character:")
            print("1. Default Characters")
            print("2. Saved Characters")
            choice = input("Choose source (1 or 2): ")
            if choice=='1':
                player_data = select_character(False)
            elif choice=='2':
                player_data = select_character(True)
                is_saved = True
        player = Character(player_data, True)
        print(f"\nYou have chosen: {player.get_name()}")

        enemy_data = None
        while not enemy_data:
            enemy_data = select_opponent()
        enemy = Character(enemy_data, False)
        print(f"Your opponent is: {enemy.get_name()}")
        input("\nPress Enter to start combat...")

        won = simulate_combat(player, enemy)
        if won:
            handle_loot_and_xp(player, enemy)
            if is_saved:
                save_character_data(player)
        else:
            print("\nGame Over!")

        again = input("\nPlay again? (Y/N): ").upper()
        if again != 'Y':
            break
    print("\nThanks for playing!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting game.")
    except Exception as e:
        print("\n--- UNEXPECTED ERROR ---")
        print(f"An error occurred: {e}")
        import traceback; traceback.print_exc()
        input("Press Enter to exit.")
