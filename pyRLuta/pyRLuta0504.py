# pyRL.py
"""
Single-file ASCII combat game: load characters, NPCs, items, actions from CSV,
equip, real-time combat with attack bars, and basic combat resolution.
"""
import csv
import time
import random
import os
import sys

# --- Constants ---
# Determine base directory for CSV files (same directory as script)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOON_CSV = os.path.join(BASE_DIR, 'pyRL_toons.csv')
NPC_CSV = os.path.join(BASE_DIR, 'pyRL_npcs.csv')
ITEM_CSV = os.path.join(BASE_DIR, 'pyRL_items.csv')
ACTION_CSV = os.path.join(BASE_DIR, 'pyRL_actions.csv')
# SAVE_CSV = os.path.join(BASE_DIR, 'pyRL_saved.csv') # Save feature not implemented

REFRESH_RATE = 0.1  # Screen refresh rate in seconds
BAR_FULL = 100      # Value indicating an attack bar is full
PLAYER_DEFAULT_ACTION_ID = 1 # Default action ID for the player

# --- Platform-specific Non-blocking Input ---
try:
    # Windows
    import msvcrt
    def get_char_nonblocking():
        """Gets a single character input without blocking (Windows)."""
        if msvcrt.kbhit():
            try:
                return msvcrt.getch().decode('utf-8')
            except UnicodeDecodeError:
                return None # Handle potential decoding errors
        return None
except ImportError:
    # Unix-like (Linux, macOS)
    import termios, tty, fcntl
    def get_char_nonblocking():
        """Gets a single character input without blocking (Unix-like)."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            # Set non-blocking
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            try:
                char = sys.stdin.read(1)
                return char
            except (IOError, BlockingIOError): # Changed from IOError to BlockingIOError if available / more specific
                return None
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


# --- Utility Functions ---
def load_csv(path):
    """Loads data from a CSV file into a list of dictionaries."""
    try:
        with open(path, mode='r', newline='', encoding='utf-8') as f:
            # Filter out empty rows or rows that are just comments (e.g., starting with '#')
            reader = csv.DictReader(filter(lambda row: row.strip() and not row.strip().startswith('#'), f))
            data = [row for row in reader]
            if not data:
                print(f"Warning: CSV file is empty or contains no data rows: {path}")
                return []
            return data
    except FileNotFoundError:
        print(f"Error: CSV file not found at {path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading CSV file {path}: {e}")
        sys.exit(1)

def roll_chance(percent):
    """Returns True if a random float (0.0 to 1.0) is less than percent/100."""
    return random.random() < (percent / 100.0)

def clear_screen():
    """Clears the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

# --- Data Classes ---
class Action:
    """Represents a combat action (attack, spell, ability)."""
    def __init__(self, id, name, dmg_stat, base, sbuf, sdeb, deb, dur, timing):
        self.id = id
        self.name = name
        self.dmg_stat = dmg_stat  # e.g., 'AtkPw', 'MgcPw' - determines damage source and defense type
        self.base = base          # Base damage/effect value
        self.selfBUFF = sbuf      # Placeholder for self-buff effect ID/name
        self.selfDEBUFF = sdeb    # Placeholder for self-debuff effect ID/name
        self.DEBUFF = deb         # Placeholder for target debuff effect ID/name
        self.duration = dur       # Placeholder for effect duration
        self.timing = timing      # Placeholder for timing (e.g., Instant, Channel)

    @classmethod
    def from_csv_row(cls, r):
        """Creates an Action object from a CSV data row (dictionary)."""
        try:
            return cls(
                id=int(r['actionID']),
                name=r.get('Name', 'Unnamed Action'),
                dmg_stat=r.get('DMG', ''), # Stat used for damage calculation (e.g., AtkPw, MgcPw)
                base=int(r.get('BaseDMG', '0') or 0),
                sbuf=r.get('selfBUFF', ''),
                sdeb=r.get('selfDEBUFF', ''),
                deb=r.get('DEBUFF', ''),
                dur=float(r.get('Duration', '0') or 0),
                timing=r.get('Timing', 'Instant')
            )
        except KeyError as e:
            print(f"Error: Missing expected column '{e}' in actions CSV.")
            sys.exit(1)
        except ValueError as e:
            print(f"Error: Invalid numeric value in actions CSV row {r}: {e}")
            sys.exit(1)

class Item:
    """Represents an equippable item."""
    SLOTS = { # Mapping slot numbers to names (optional, for clarity)
        1: 'head', 2: 'chest', 3: 'legs', 4: 'feet',
        5: 'offhand', 6: 'mainhand', 7: 'neck', 8: 'ring'
    }
    def __init__(self, id, slot, name, b1id, b1add, b2id, b2add, act_id, skill, skamt, skop, type, cooldown):
        self.id = id
        self.slot = slot          # Slot number (e.g., 1 for head)
        self.name = name
        self.bonus1id = b1id      # ID/Name of the first stat bonus (e.g., 'STR', 'HP')
        self.bonus1add = b1add    # Amount of the first bonus
        self.bonus2id = b2id      # ID/Name of the second stat bonus
        self.bonus2add = b2add    # Amount of the second bonus
        self.action_id = act_id   # Action granted by this item (placeholder)
        self.skill_check = skill  # Skill required (placeholder)
        self.skl_amount = skamt   # Skill amount required (placeholder)
        self.skl_op = skop        # Skill check operator (placeholder)
        self.type = type          # Item type (e.g., Weapon, Armor) (placeholder)
        self.cooldown = cooldown  # Item action cooldown (placeholder)

    @classmethod
    def from_csv_row(cls, r):
        """Creates an Item object from a CSV data row (dictionary)."""
        try:
            b1id = r.get('Bonus1id', '')
            b1add = int(r.get('Bonus1add', '0') or 0)
            b2id = r.get('Bonus2id', '')
            b2add = int(r.get('Bonus2add', '0') or 0)
            act_id_str = r.get('ActionID', '')
            act_id = int(act_id_str) if act_id_str.isdigit() else 0
            skamt = int(r.get('SklChkAmount', '0') or 0)
            cooldown_val = r.get('Cooldown', '0')
            cooldown = float(cooldown_val) if cooldown_val else 0.0

            return cls(
                id=int(r['ItemID']),
                slot=int(r['Slot']),
                name=r.get('Name', 'Unnamed Item'),
                b1id=b1id,
                b1add=b1add,
                b2id=b2id,
                b2add=b2add,
                act_id=act_id,
                skill=r.get('SkillCheck', ''),
                skamt=skamt,
                skop=r.get('SklChkOpr', ''),
                type=r.get('Type', ''),
                cooldown=cooldown
            )
        except KeyError as e:
            print(f"Error: Missing expected column '{e}' in items CSV.")
            sys.exit(1)
        except ValueError as e:
            print(f"Error: Invalid numeric value in items CSV row {r}: {e}")
            sys.exit(1)

class Entity:
    """Base class for Players and NPCs."""
    ATTRIBUTE_LIST = [ # Define primary attributes used in calculations
            'STA','STR','AGI','DEX','HIT','BAL','WGT','HEI',
            'INT','WIL','FOR','FOC','PSY','ARC','BLS','MAN','ALC','CUR','COR','SUM','HEX'
        ]
    DERIVED_STATS = [ # Define derived combat stats
        'max_hp', 'atk_pw', 'atk_sp', 'mgc_pw', 'block', 'dodge', 'armor', 'mgc_rs', 'crits'
    ]

    def __init__(self, name):
        self.name = name
        # Base attributes (to be populated by subclasses)
        self.base_attrs = {attr: 0 for attr in self.ATTRIBUTE_LIST}
        # Derived stats (calculated)
        for stat in self.DERIVED_STATS:
            setattr(self, stat, 0)
        self.hp = 0 # Current HP
        self.active_effects = [] # Placeholder for status effects
        self.bar = None # Attack bar, initialized during combat

    def get_stat(self, stat_name):
        """Safely gets a stat value (attribute or derived stat)."""
        return getattr(self, stat_name, 0)

class Player(Entity):
    """Represents the player character."""
    SLOT_NAMES = ['head', 'chest', 'legs', 'feet', 'offhand', 'mainhand', 'neck', 'ring']

    def __init__(self, row, items_by_id):
        """Initializes Player from a CSV row and item dictionary."""
        super().__init__(row.get('Name', 'Player'))
        try:
            # Load base attributes from CSV row
            for k in self.ATTRIBUTE_LIST:
                 self.base_attrs[k] = int(row.get(k, '0') or 0)

            # Equip items
            self.equipment = {slot: None for slot in self.SLOT_NAMES}
            for i, slot_name in enumerate(self.SLOT_NAMES, 1):
                item_id_str = row.get(f'Slot{i}')
                if item_id_str and item_id_str.isdigit():
                    item_id = int(item_id_str)
                    if item_id in items_by_id:
                        item = items_by_id[item_id]
                        # Basic check: does item slot match equipment slot name?
                        # This relies on Item.SLOTS mapping numbers to names.
                        if Item.SLOTS.get(item.slot) == slot_name:
                             self.equipment[slot_name] = item
                        else:
                             print(f"Warning: Item '{item.name}' (ID {item.id}) has slot {item.slot}, expected slot for '{slot_name}'. Skipping.")
                    else:
                        print(f"Warning: Item ID {item_id} not found for slot {slot_name}. Skipping.")

            self.compute_derived_stats()
            self.hp = self.max_hp # Start with full health

        except KeyError as e:
            print(f"Error: Missing expected column '{e}' in toons CSV for player {self.name}.")
            sys.exit(1)
        except ValueError as e:
            print(f"Error: Invalid numeric value in toons CSV for player {self.name}: {e}")
            sys.exit(1)

    def compute_derived_stats(self):
        """Calculates derived stats based on base attributes and equipment."""
        # Start with base attributes
        current_attrs = self.base_attrs.copy()

        # Add bonuses from equipped items
        for item in self.equipment.values():
            if item:
                if item.bonus1id in current_attrs:
                    current_attrs[item.bonus1id] += item.bonus1add
                # Handle potential direct bonus to derived stats (e.g., item gives +10 max_hp)
                elif hasattr(self, item.bonus1id):
                     setattr(self, item.bonus1id, getattr(self, item.bonus1id, 0) + item.bonus1add)
                # Repeat for bonus 2
                if item.bonus2id in current_attrs:
                    current_attrs[item.bonus2id] += item.bonus2add
                elif hasattr(self, item.bonus2id):
                     setattr(self, item.bonus2id, getattr(self, item.bonus2id, 0) + item.bonus2add)

        # Calculate derived stats based on potentially modified attributes
        # (Using the formulas from the original code)
        attrs = current_attrs # Use the adjusted attributes for calculations
        self.max_hp = (50 + 5 * attrs['STA'] + 2 * attrs['STR'] + 2 * attrs['WIL'] +
                       attrs['FOR'] + attrs['FOC'])
        # Add any direct max_hp bonuses collected earlier
        self.max_hp += getattr(self, 'max_hp', 0) if 'max_hp' not in attrs else 0

        # Ensure HP doesn't exceed new max_hp if called mid-game (though not currently done)
        if hasattr(self, 'hp'):
            self.hp = min(self.hp, self.max_hp)

        # Using original formulas - adjust these as per your game design needs
        self.atk_pw = sum(attrs[s] for s in ['STR', 'STR', 'AGI', 'DEX', 'BAL'])
        self.atk_sp = attrs['AGI'] # Higher AGI potentially means faster attacks now
        self.mgc_pw = sum(attrs[s] for s in ['INT', 'INT', 'MAN', 'ARC', 'WIL'])
        self.block  = sum(attrs[s] for s in ['STR', 'FOR', 'INT', 'BAL', 'WIL'])
        self.dodge  = sum(attrs[s] for s in ['FOC', 'AGI', 'DEX', 'BAL', 'PSY'])
        self.armor  = sum(attrs[s] for s in ['STR', 'FOR', 'STA', 'AGI', 'BLS'])
        self.mgc_rs = sum(attrs[s] for s in ['PSY', 'BLS', 'WIL', 'MAN', 'FOR'])
        self.crits  = sum(attrs[s] for s in ['HIT', 'HIT', 'HIT', 'ARC', 'FOC'])

        # Apply any direct bonuses to derived stats from items again (if any were stored on self)
        for stat in self.DERIVED_STATS:
             if stat != 'max_hp' and hasattr(self, stat) and stat not in attrs: # Avoid double counting max_hp
                 setattr(self, stat, getattr(self, stat, 0)) # Ensure the value is set

class NPC(Entity):
    """Represents a Non-Player Character (opponent)."""
    def __init__(self, row, items_by_id): # items_by_id not used currently for NPCs but kept for signature consistency
        """Initializes NPC from a CSV row."""
        super().__init__(row.get('Name', 'NPC'))
        try:
            self.level = int(row.get('Level', '1') or 1)
            self.max_hp = int(row.get('HP', '10') or 10)
            self.hp = self.max_hp # Start full health
            self.atk_pw = int(row.get('AtkPw', '5') or 5)
            self.atk_sp = int(row.get('AtkSp', '5') or 5) # Higher is faster now
            self.mgc_pw = int(row.get('MgcPw', '0') or 0)
            self.block  = int(row.get('Block', '0') or 0)
            self.dodge  = int(row.get('Dodge', '0') or 0)
            self.armor  = int(row.get('Armor', '0') or 0)
            self.mgc_rs = int(row.get('MgcRs', '0') or 0)
            self.crits  = int(row.get('Crits', '0') or 0)
            self.xp_yield = int(row.get('XPYield', '0') or 0) # Placeholder

            # Load loot item IDs (placeholder)
            self.loot_ids = []
            for i in range(1, 6):
                item_id_str = row.get(f'Item{i}ID')
                if item_id_str and item_id_str.isdigit():
                    self.loot_ids.append(int(item_id_str))

            # Load action sequence
            self.sequence = []
            for i in range(1, 10): # Max 9 actions in sequence
                action_id_str = row.get(f'act{i}')
                if action_id_str and action_id_str.isdigit():
                    self.sequence.append(int(action_id_str))
            if not self.sequence: # Default to basic attack if no sequence defined
                 self.sequence = [1] # Assuming Action ID 1 is a basic attack
            self.seq_idx = 0

            # Load dialogue texts
            self.text_start = row.get('TextStart', f"{self.name} attacks!")
            self.text_death = row.get('TextDeath', f"{self.name} collapses!")
            self.text_win   = row.get('TextWin', f"{self.name} stands victorious.")

        except KeyError as e:
            print(f"Error: Missing expected column '{e}' in npcs CSV for NPC {self.name}.")
            sys.exit(1)
        except ValueError as e:
            print(f"Error: Invalid numeric value in npcs CSV for NPC {self.name}: {e}")
            sys.exit(1)

class AttackBar:
    """Represents the readiness progress for an entity's action."""
    def __init__(self, speed_stat):
        """Initializes the bar."""
        self.fill = 0
        # Speed stat determines how quickly the bar fills. Higher speed = faster fill.
        # Adjust the multiplier (e.g., 10) to balance combat speed.
        self.speed = speed_stat * 10 # Example scaling factor
        if self.speed <= 0:
            print("Warning: Entity speed is zero or negative, attack bar will not fill.")
            self.speed = 1 # Prevent division by zero / ensure minimal progress

    def update(self, delta_time):
        """Updates the fill amount based on time elapsed."""
        if self.speed > 0:
            self.fill += delta_time * self.speed
            self.fill = min(self.fill, BAR_FULL) # Cap at full

    def is_ready(self):
        """Checks if the bar is full."""
        return self.fill >= BAR_FULL

    def reset(self):
        """Resets the bar fill, potentially leaving some overflow."""
        # self.fill = 0 # Simple reset
        self.fill -= BAR_FULL # Reset allowing overflow to carry over (can lead to faster subsequent attacks)
        self.fill = max(0, self.fill) # Ensure fill doesn't go negative

# --- Combat Logic ---
def resolve_attack(attacker, defender, action_id, actions_by_id):
    """Calculates the outcome of an attack action."""
    result = {'damage': 0, 'crit': False, 'dodged': False, 'mitigated': 0, 'log': ""}
    action = actions_by_id.get(action_id)

    if not action:
        result['log'] = f"{attacker.name} tries an invalid action ({action_id})!"
        return result

    # 1. Dodge Check
    # Dodge chance based on defender's dodge stat vs attacker's HIT? (Using simple dodge % for now)
    dodge_chance_pct = defender.get_stat('dodge') # Simple percentage
    if roll_chance(dodge_chance_pct):
        result['dodged'] = True
        result['log'] = f"{defender.name} dodges {attacker.name}'s {action.name}!"
        return result

    # 2. Calculate Base Damage
    # Determine attacker's relevant power stat based on action type
    attack_power = 0
    if action.dmg_stat == 'AtkPw':
        attack_power = attacker.get_stat('atk_pw')
    elif action.dmg_stat == 'MgcPw':
        attack_power = attacker.get_stat('mgc_pw')
    # Add more conditions if other damage stats exist (e.g., 'TrueDmg')

    raw_damage = action.base + attack_power # Simple damage formula: base + relevant power
    if raw_damage <= 0: raw_damage = 1 # Ensure at least 1 potential damage before mitigation

    # 3. Critical Hit Check
    crit_chance_pct = attacker.get_stat('crits')
    is_crit = roll_chance(crit_chance_pct)
    if is_crit:
        raw_damage *= 2  # Double damage on crit (adjust multiplier as needed)
        result['crit'] = True

    # 4. Mitigation (Block/Armor/Resistance)
    defense_stat = 0
    if action.dmg_stat == 'AtkPw': # Physical damage resisted by Armor
        defense_stat = defender.get_stat('armor')
        # Could also incorporate Block chance here to negate damage entirely or partially
    elif action.dmg_stat == 'MgcPw': # Magical damage resisted by Magic Resist
        defense_stat = defender.get_stat('mgc_rs')

    # Original mitigation formula: random reduction based on defense
    # mitigation_percent = random.uniform(0, defense_stat) / 100.0
    # mitigated_amount = raw_damage * mitigation_percent

    # Alternative mitigation: Simple percentage reduction (e.g., each point of defense reduces damage by 0.1%)
    # reduction_factor = defense_stat * 0.001 # Example: 100 armor = 10% reduction
    # reduction_factor = max(0, min(reduction_factor, 0.9)) # Cap reduction (e.g., at 90%)
    # mitigated_amount = raw_damage * reduction_factor

    # Another Alternative: Flat reduction capped by damage
    # mitigated_amount = min(raw_damage -1, defense_stat // 10) # Example: 1 damage penetrates

    # Using original formula for consistency with provided code:
    mitigation_roll = random.uniform(0, defense_stat) # Roll based on defense
    # Let's interpret this roll as a direct reduction, capped at raw_damage - 1
    # This is just one interpretation, the original was a percentage.
    # mitigated_amount = min(raw_damage - 1, int(mitigation_roll / 2)) # Example scaling
    # Reverting to original percentage interpretation:
    mitigation_percent = mitigation_roll / (mitigation_roll + 100) # More standard % reduction formula
    mitigated_amount = raw_damage * mitigation_percent

    final_damage = max(1, int(raw_damage - mitigated_amount)) # Ensure at least 1 damage goes through unless blocked/dodged
    result['damage'] = final_damage
    result['mitigated'] = int(mitigated_amount)

    # 5. Apply Damage
    defender.hp = max(0, defender.hp - final_damage)

    # 6. Generate Log Message
    crit_str = " (CRIT!)" if result['crit'] else ""
    result['log'] = (f"{attacker.name}'s {action.name} hits {defender.name} "
                     f"for {result['damage']} damage{crit_str}.")
                     # f" ({result['mitigated']} mitigated).") # Optional: add mitigation info

    # --- TODO: Apply Status Effects (Buffs/Debuffs) ---
    # if action.selfBUFF: apply_effect(attacker, action.selfBUFF, action.duration)
    # if action.DEBUFF: apply_effect(defender, action.DEBUFF, action.duration)

    return result

# --- UI and Game Flow ---
def display_menu(options, prompt):
    """Displays a numbered menu and returns the chosen index."""
    if not options:
        print("No options available.")
        return -1
    print("-" * 20)
    for i, opt in enumerate(options):
        print(f"{i + 1}. {opt}")
    print("-" * 20)
    choice = -1
    while choice < 0 or choice >= len(options):
        try:
            raw_input = input(f"{prompt} (1-{len(options)}): ")
            choice = int(raw_input) - 1
            if choice < 0 or choice >= len(options):
                print("Invalid choice, please try again.")
        except ValueError:
            print("Invalid input, please enter a number.")
    return choice

def render_hud(player, enemy, combat_log):
    """Clears screen and draws the combat interface."""
    clear_screen()

    def get_bar_string(entity):
        """Creates a text representation of the entity's attack bar."""
        if not entity.bar: return "[NO BAR]"
        fill_ratio = entity.bar.fill / BAR_FULL
        filled_width = int(fill_ratio * 10)
        empty_width = 10 - filled_width
        # Use block characters for the bar
        bar_str = '■' * filled_width + '□' * empty_width
        # Display percentage (optional)
        # percent_str = f"{int(entity.bar.fill)}%"
        # return f"[{bar_str}] {percent_str}"
        return f"[{bar_str}]" # Simpler bar

    # Player Info
    print(f"{player.name} [HP: {player.hp}/{player.max_hp}]")
    print(f"ATK Bar: {get_bar_string(player)}")
    print("-" * 30)
    # Enemy Info
    print(f"{enemy.name} [HP: {enemy.hp}/{enemy.max_hp}]")
    print(f"ATK Bar: {get_bar_string(enemy)}")
    print("=" * 30)

    # Combat Log (Last N messages)
    print("Combat Log:")
    log_display_count = 5
    for message in combat_log[-log_display_count:]:
        print(f"- {message}")
    print("-" * 30)
    print("Controls: [1] Attack | (Press key during your turn)") # Basic controls reminder

def choose_character(toon_data, items_by_id):
    """Prompts the player to select a character."""
    print("Available Characters:")
    names = [t.get('Name', 'Unnamed Toon') for t in toon_data]
    chosen_index = display_menu(names, "Choose your character")
    if chosen_index == -1:
        print("No characters available to choose.")
        return None
    return Player(toon_data[chosen_index], items_by_id)

def choose_opponent(npc_data, items_by_id):
    """Prompts the player to select an opponent."""
    print("\nAvailable Opponents:")
    names = [n.get('Name', 'Unnamed NPC') for n in npc_data]
    chosen_index = display_menu(names, "Choose your opponent")
    if chosen_index == -1:
        print("No opponents available to choose.")
        return None
    return NPC(npc_data[chosen_index], items_by_id)

def simulate_combat(player, enemy, actions_by_id):
    """Runs the main real-time combat loop."""
    if not player or not enemy:
        print("Error: Cannot start combat without both player and enemy.")
        return False

    # Initialize Attack Bars
    player.bar = AttackBar(player.get_stat('atk_sp'))
    enemy.bar = AttackBar(enemy.get_stat('atk_sp'))

    combat_log = [f"Combat starts between {player.name} and {enemy.name}!"]
    if hasattr(enemy, 'text_start') and enemy.text_start:
        combat_log.append(f"{enemy.name}: {enemy.text_start}")

    last_time = time.time()
    player_turn = False # Flag to indicate if player can act

    while player.hp > 0 and enemy.hp > 0:
        # Time delta calculation
        current_time = time.time()
        delta_time = current_time - last_time
        last_time = current_time

        # Update Attack Bars
        player.bar.update(delta_time)
        enemy.bar.update(delta_time)

        # --- Player Action ---
        if player.bar.is_ready():
            player_turn = True # Indicate player can act
            # Non-blocking input check
            key = get_char_nonblocking()
            if key:
                action_id_to_use = PLAYER_DEFAULT_ACTION_ID # Default action
                if key == '1': # Currently only key '1' triggers the default action
                    pass # Use default action_id
                # --- TODO: Add mapping for other keys to other actions ---
                # elif key == '2': action_id_to_use = player.get_action_id_for_slot(2) ... etc.

                if action_id_to_use:
                    result = resolve_attack(player, enemy, action_id_to_use, actions_by_id)
                    combat_log.append(result['log'])
                    player.bar.reset()
                    player_turn = False # Action taken, turn ends
                else:
                     combat_log.append("Invalid action key pressed.")

        # --- Enemy Action ---
        if enemy.bar.is_ready():
            # Select action from sequence
            if not enemy.sequence:
                combat_log.append(f"{enemy.name} has no actions!")
                enemy.bar.reset() # Prevent spamming logs
            else:
                action_id = enemy.sequence[enemy.seq_idx]
                if action_id in actions_by_id:
                    result = resolve_attack(enemy, player, action_id, actions_by_id)
                    combat_log.append(result['log'])
                else:
                     combat_log.append(f"{enemy.name} tried unknown action ID: {action_id}")

                # Advance sequence index
                enemy.seq_idx = (enemy.seq_idx + 1) % len(enemy.sequence)
                enemy.bar.reset()

        # --- Update Effects (Placeholder) ---
        # update_effects(player, delta_time)
        # update_effects(enemy, delta_time)

        # --- Render ---
        render_hud(player, enemy, combat_log)
        if player_turn:
             print("YOUR TURN! Press '1' to attack.") # Prompt player

        # --- Game Speed Control ---
        time.sleep(REFRESH_RATE)

    # --- Combat End ---
    render_hud(player, enemy, combat_log) # Show final state
    if player.hp <= 0:
        print("\n--- DEFEAT ---")
        if hasattr(enemy, 'text_win') and enemy.text_win:
            print(f"{enemy.name}: {enemy.text_win}")
        return False
    else: # enemy.hp <= 0
        print("\n--- VICTORY! ---")
        if hasattr(enemy, 'text_death') and enemy.text_death:
            print(f"{enemy.name}: {enemy.text_death}")
        # --- TODO: Grant XP and Loot ---
        # print(f"You gained {enemy.xp_yield} XP.")
        # award_loot(player, enemy.loot_ids, items_by_id)
        return True

# --- Main Execution ---
def main():
    """Main function to load data and run the game loop."""
    print("Loading game data...")
    try:
        # Load data from CSVs
        toon_data = load_csv(TOON_CSV)
        npc_data = load_csv(NPC_CSV)
        item_data = load_csv(ITEM_CSV)
        action_data = load_csv(ACTION_CSV)

        if not toon_data or not npc_data or not item_data or not action_data:
             print("Error: Essential data files are missing or empty. Exiting.")
             sys.exit(1)

        # Process data into usable formats
        items_by_id = {item.id: item for item in (Item.from_csv_row(r) for r in item_data)}
        actions_by_id = {action.id: action for action in (Action.from_csv_row(r) for r in action_data)}

        print("Data loaded successfully.")

    except Exception as e:
        print(f"An error occurred during data loading: {e}")
        sys.exit(1)

    # Game Loop
    while True:
        clear_screen()
        print("=== pyRL Combat Simulator ===")

        # Character Selection
        player = choose_character(toon_data, items_by_id)
        if not player: break # Exit if no character chosen

        # Opponent Selection
        enemy = choose_opponent(npc_data, items_by_id)
        if not enemy: break # Exit if no opponent chosen

        # Start Combat
        simulate_combat(player, enemy, actions_by_id)

        # Ask to play again
        play_again = input("\nPlay again? (y/n): ").lower()
        if play_again != 'y':
            break

    print("Exiting pyRL. Thanks for playing!")

if __name__ == "__main__":
    main()