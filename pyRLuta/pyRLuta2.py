import csv
import os
import random
import time
import threading
import sys
from time import sleep

# Platform-specific keyboard input handling
if os.name == 'nt':  # Windows
    import msvcrt
    def getch_non_blocking():
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            try:
                return ch.decode('utf-8').upper()
            except:
                return None
        return None
else:  # Unix/Linux/Mac
    import termios
    import tty
    import select
    
    def setup_terminal():
        # Save terminal settings
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setraw(fd)
        return fd, old_settings
    
    def restore_terminal(fd, old_settings):
        # Restore terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    
    def getch_non_blocking():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                ch = sys.stdin.read(1)
                return ch.upper()
            return None
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

# Constants
REFRESH_RATE = 0.1  # seconds between updates
BAR_LENGTH = 20     # visual length of attack bar
COMBAT_LOG_SIZE = 3 # number of combat log entries to show

# Global variables
running = True
combat_log = []
current_player = None
current_enemy = None
queued_action = 'A'  # Default action is melee attack

# Data storage
characters = []  # Will be loaded from pyRLuta.csv
enemies = []     # Will be loaded from pyRL_npcs.csv
items = []       # Will be loaded from pyRL_items.csv
actions = []     # Will be loaded from pyRL_actions.csv

# Classes
class Character:
    def __init__(self, char_id, name, stats):
        self.id = char_id
        self.name = name
        self.stats = stats
        self.hp = 50 + (5 * stats.get('STA', 0)) + stats.get('STR', 0) + (2 * stats.get('WIL', 0)) + stats.get('FOR', 0) + stats.get('BLS', 0)
        self.max_hp = self.hp
        self.attack_bar = 0  # 0-100%
        self.equipment = [None] * 8  # 8 equipment slots
        self.active_effects = []  # Maximum of 2 effects
        
        # Calculate derived stats
        self.recalculate_stats()
    
    def recalculate_stats(self):
        # Calculate derived stats based on attributes and equipment
        stats = self.stats.copy()
        
        # Add bonuses from equipment
        for item in self.equipment:
            if item:
                if 'Bonus1id' in item and 'Bonus1add' in item:
                    stat = item['Bonus1id']
                    value = int(item['Bonus1add'])
                    stats[stat] = stats.get(stat, 0) + value
                
                if 'Bonus2id' in item and 'Bonus2add' in item:
                    stat = item['Bonus2id']
                    value = int(item['Bonus2add'])
                    stats[stat] = stats.get(stat, 0) + value
        
        # Calculate combat stats
        self.atkpw = (stats.get('STR', 0) * 2 + stats.get('AGI', 0) + stats.get('DEX', 0) + stats.get('BAL', 0)) / 5
        self.atksp = (stats.get('AGI', 0) * 2 + stats.get('DEX', 0) + stats.get('WIL', 0) + stats.get('FOC', 0)) / 5
        self.mgcpw = (stats.get('INT', 0) * 2 + stats.get('MAN', 0) + stats.get('ARC', 0) + stats.get('WIL', 0)) / 5
        self.block = (stats.get('STR', 0) + stats.get('FOR', 0) + stats.get('INT', 0) + stats.get('BAL', 0) + stats.get('WIL', 0)) / 5
        self.dodge = (stats.get('FOC', 0) + stats.get('AGI', 0) + stats.get('DEX', 0) + stats.get('BAL', 0) + stats.get('PSY', 0)) / 5
        self.armor = (stats.get('STR', 0) + stats.get('FOR', 0) + stats.get('STA', 0) + stats.get('AGI', 0) + stats.get('BLS', 0)) / 5
        self.mgcrs = (stats.get('PSY', 0) + stats.get('BLS', 0) + stats.get('WIL', 0) + stats.get('MAN', 0) + stats.get('FOR', 0)) / 5
    
    def update_attack_bar(self):
        if self.hp <= 0:
            return
            
        # Calculate fill time based on AtkSp
        fill_rate = 1.0 / (1.2 + (5.0 - 1.2) * (1 - self.atksp / 100))
        self.attack_bar += fill_rate * REFRESH_RATE * 100
        
        # Check for attack execution
        if self.attack_bar >= 100:
            self.execute_attack()
            self.attack_bar = 0  # Reset attack bar
    
    def execute_attack(self):
        global queued_action, combat_log
        
        if self == current_player:
            # Player attack logic
            attack_key = queued_action
            action_name = self.get_action_name(attack_key)
            damage, damage_type = self.calculate_damage(attack_key)
            
            # Apply damage to enemy
            actual_damage = current_enemy.take_damage(damage, damage_type)
            
            # Add to combat log
            combat_log.append(f"{self.name} used {action_name} for {actual_damage} damage!")
            if len(combat_log) > COMBAT_LOG_SIZE:
                combat_log.pop(0)
        else:
            # Enemy attack logic - get next attack from sequence
            action_num = self.action_sequence[self.current_action_idx]
            action_name = f"Attack {action_num}"
            damage, damage_type = self.calculate_damage(action_num)
            
            # Apply damage to player
            actual_damage = current_player.take_damage(damage, damage_type)
            
            # Add to combat log
            combat_log.append(f"{self.name} used {action_name} for {actual_damage} damage!")
            if len(combat_log) > COMBAT_LOG_SIZE:
                combat_log.pop(0)
            
            # Move to next action in sequence
            self.current_action_idx = (self.current_action_idx + 1) % len(self.action_sequence)
    
    def get_action_name(self, key):
        # Map key to action name based on equipment and default actions
        key_map = {
            'A': "Basic Melee",
            'S': "Magic Attack",
            'D': "Neck Effect" if self.equipment[6] else "Soothe",
            'Z': self.equipment[5]['Action'] if self.equipment[5] and 'Action' in self.equipment[5] else "Kick",
            'X': self.equipment[4]['Action'] if self.equipment[4] and 'Action' in self.equipment[4] else "Off-hand",
            'C': self.equipment[7]['Action'] if self.equipment[7] and 'Action' in self.equipment[7] else "Ring Effect"
        }
        return key_map.get(key, "Unknown Action")
    
    def calculate_damage(self, action_key):
        # Calculate damage based on action and stats
        if isinstance(action_key, int):
            # Enemy action
            base_damage = self.atkpw if action_key % 2 == 0 else self.mgcpw
            damage_type = "melee" if action_key % 2 == 0 else "magic"
            return base_damage * 1.2, damage_type
        else:
            # Player action
            if action_key == 'A':
                return self.atkpw * 1.0, "melee"
            elif action_key == 'S':
                return self.mgcpw * 1.1, "magic"
            elif action_key == 'D':
                # Necklace effect
                return self.mgcpw * 0.8, "magic"
            elif action_key == 'Z':
                # Main hand
                if self.equipment[5]:
                    dmg_stat = self.equipment[5].get('DMG', 'STR')
                    dmg_type = self.equipment[5].get('Type', 'melee')
                    base = self.stats.get(dmg_stat, 10)
                    return base * 1.2, dmg_type
                return self.atkpw * 0.9, "melee"
            elif action_key == 'X':
                # Off hand
                if self.equipment[4]:
                    dmg_stat = self.equipment[4].get('DMG', 'STR')
                    dmg_type = self.equipment[4].get('Type', 'melee')
                    base = self.stats.get(dmg_stat, 10)
                    return base * 1.0, dmg_type
                return self.atkpw * 0.7, "melee"
            elif action_key == 'C':
                # Ring effect
                return self.mgcpw * 0.7, "magic"
            return 5, "melee"  # Default
    
    def take_damage(self, damage, damage_type):
        # Check dodge first
        dodge_chance = min(self.dodge / 10, 10)  # Max 10% dodge chance
        if random.random() * 100 < dodge_chance:
            combat_log.append(f"{self.name} dodged the attack!")
            return 0
        
        # Apply mitigation based on damage type
        if damage_type == "melee":
            mitigation_stat = self.block
            mitigation_pct = random.randint(1, int(mitigation_stat)) / 100
        else:  # magic
            mitigation_stat = self.mgcrs
            mitigation_pct = random.randint(1, int(mitigation_stat)) / 100
        
        mitigated_damage = damage * mitigation_pct
        actual_damage = max(1, int(damage - mitigated_damage))  # Minimum 1 damage
        
        self.hp -= actual_damage
        self.hp = max(0, self.hp)  # Prevent negative HP
        
        return actual_damage

class Enemy(Character):
    def __init__(self, enemy_id, name, hp, atkpw, atksp, mgcpw, block, dodge, armor, mgcrs, 
                 item1id, item2id, item3id, item4id, item5id, xp_yield, 
                 text_start, text_death, text_win):
        self.id = enemy_id
        self.name = name
        self.hp = int(hp)
        self.max_hp = self.hp
        self.atkpw = float(atkpw)
        self.atksp = float(atksp)
        self.mgcpw = float(mgcpw)
        self.block = float(block)
        self.dodge = float(dodge)
        self.armor = float(armor)
        self.mgcrs = float(mgcrs)
        self.item_drops = [item1id, item2id, item3id, item4id, item5id]
        self.drop_chances = [30, 30, 30, 8, 2]  # Percentages
        self.xp_yield = int(xp_yield)
        self.text_start = text_start
        self.text_death = text_death
        self.text_win = text_win
        self.attack_bar = 0
        self.active_effects = []
        
        # Enemy attack sequence (cyclic)
        self.action_sequence = [1, 1, 2, 1, 3, 1, 2, 1, 3]
        self.current_action_idx = 0
        
        # Placeholder stats dict for compatibility with Character class methods
        self.stats = {
            'STR': int(atkpw / 2),
            'AGI': int(atksp / 2),
            'INT': int(mgcpw / 2),
            'FOR': int(block / 2),
            'DEX': int(dodge / 2),
            'STA': int(armor / 2),
            'PSY': int(mgcrs / 2),
            'BAL': int(dodge / 2),
            'WIL': int(block / 2),
            'FOC': int(atksp / 2),
            'MAN': int(mgcpw / 2),
            'BLS': int(mgcrs / 2)
        }
        
        self.equipment = [None] * 8

# Functions
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def load_characters():
    global characters
    try:
        with open('pyRLuta.csv', 'r', newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Extract character stats from CSV row
                stats = {
                    'STA': int(row.get('STA', 0)),
                    'STR': int(row.get('STR', 0)),
                    'AGI': int(row.get('AGI', 0)),
                    'DEX': int(row.get('DEX', 0)),
                    'HIT': int(row.get('HIT', 0)),
                    'BAL': int(row.get('BAL', 0)),
                    'WGT': int(row.get('WGT', 0)),
                    'HEI': int(row.get('HEI', 0)),
                    'INT': int(row.get('INT', 0)),
                    'MAN': int(row.get('MAN', 0)),
                    'WIL': int(row.get('WIL', 0)),
                    'FOR': int(row.get('FOR', 0)),
                    'FOC': int(row.get('FOC', 0)),
                    'PSY': int(row.get('PSY', 0)),
                    'ARC': int(row.get('ARC', 0)),
                    'BLS': int(row.get('BLS', 0)),
                    'ALC': int(row.get('ALC', 0)),
                    'CUR': int(row.get('CUR', 0)),
                    'COR': int(row.get('COR', 0)),
                    'SUM': int(row.get('SUM', 0)),
                    'HEX': int(row.get('HEX', 0))
                }
                
                char = Character(row['ID'], row['Name'], stats)
                characters.append(char)
    except FileNotFoundError:
        print("Character file not found. Creating sample characters...")
        # Create sample characters if file doesn't exist
        stats1 = {'STA': 10, 'STR': 12, 'AGI': 8, 'DEX': 10, 'INT': 6, 'WIL': 7, 'FOR': 9}
        stats2 = {'STA': 7, 'STR': 6, 'AGI': 10, 'DEX': 12, 'INT': 14, 'WIL': 10, 'FOR': 6}
        
        characters = [
            Character(1, "Warrior", stats1),
            Character(2, "Mage", stats2)
        ]

def load_enemies():
    global enemies
    try:
        with open('pyRL_npcs.csv', 'r', newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                enemy = Enemy(
                    row['npcID'], row['Name'], 
                    row['HP'], row['AtkPw'], row['AtkSp'],
                    row['MgcPw'], row['Block'], row['Dodge'],
                    row['Armor'], row['MgcRs'],
                    row['Item1ID'], row['Item2ID'], row['Item3ID'],
                    row['Item4ID'], row['Item5ID'], row['XPYield'],
                    row['TextStart'], row['TextDeath'], row['TextWin']
                )
                enemies.append(enemy)
    except FileNotFoundError:
        print("Enemy file not found. Creating sample enemies...")
        # Create sample enemies if file doesn't exist
        enemies = [
            Enemy(1, "Goblin", 80, 15, 30, 5, 20, 25, 15, 10, 
                  1, 2, 3, 8, 11, 10, 
                  "A goblin appears!", "The goblin falls!", "You have been defeated!"),
            Enemy(2, "Skeleton", 100, 20, 20, 15, 30, 15, 30, 20,
                  3, 4, 5, 9, 12, 15,
                  "Bones rattle as a skeleton steps forth!", "The skeleton crumbles to dust!", "The skeleton has slain you!")
        ]

def load_items():
    global items
    try:
        with open('pyRL_items.csv', 'r', newline='') as file:
            reader = csv.DictReader(file)
            items = list(reader)
    except FileNotFoundError:
        print("Items file not found. Creating sample items...")
        # Create sample items if file doesn't exist
        items = [
            {'ItemID': '1', 'Slot': '1', 'Name': 'Iron Helmet', 'Bonus1id': 'STA', 'Bonus1add': '1', 'Bonus2id': 'STR', 'Bonus2add': '1'},
            {'ItemID': '2', 'Slot': '2', 'Name': 'Iron Breastplate', 'Bonus1id': 'FOR', 'Bonus1add': '1', 'Bonus2id': 'STA', 'Bonus2add': '1'},
            {'ItemID': '5', 'Slot': '5', 'Name': 'Wooden Shield', 'Bonus1id': 'STA', 'Bonus1add': '3', 'Bonus2id': 'AGI', 'Bonus2add': '-1', 'Action': 'Bash', 'DMG': 'STR', 'Type': 'melee'},
            {'ItemID': '6', 'Slot': '6', 'Name': 'Wooden Stick', 'Bonus1id': 'STR', 'Bonus1add': '1', 'Bonus2id': 'AGI', 'Bonus1add': '1', 'Action': 'Snurp', 'DMG': 'AGI', 'Type': 'melee'}
        ]

def select_character():
    global current_player
    
    clear_screen()
    print("=== Character Selection ===")
    for i, char in enumerate(characters):
        print(f"{i+1}. {char.name}")
    
    while True:
        try:
            choice = int(input("\nSelect your character (number): "))
            if 1 <= choice <= len(characters):
                current_player = characters[choice-1]
                break
            else:
                print("Invalid choice. Try again.")
        except ValueError:
            print("Please enter a number.")
    
    # Equip some starter items for testing
    if len(items) >= 4:  # Make sure we have items to equip
        current_player.equipment[0] = items[0]  # Helmet
        current_player.equipment[1] = items[1]  # Chest
        current_player.equipment[4] = items[2]  # Shield
        current_player.equipment[5] = items[3]  # Weapon
        
        current_player.recalculate_stats()

def select_enemy():
    global current_enemy
    
    # For now, just pick a random enemy
    if enemies:
        current_enemy = random.choice(enemies)
    else:
        # Create a default enemy if none loaded
        current_enemy = Enemy(999, "Training Dummy", 100, 10, 20, 10, 15, 10, 20, 15,
                         0, 0, 0, 0, 0, 5,
                         "A training dummy appears!", "The dummy falls apart!", "How did you lose to a dummy?")
    
    print(f"\n{current_enemy.text_start}")
    input("Press Enter to begin combat...")

def draw_hp_bar(current, maximum, width=20):
    filled = int(width * (current / maximum))
    bar = '█' * filled + ' ' * (width - filled)
    return f"[{bar}]"

def draw_attack_bar(percentage, width=20):
    filled = int(width * (percentage / 100))
    bar = '■' * filled + ' ' * (width - filled)
    return f"[{bar}]"

def display_combat_ui():
    clear_screen()
    
    # Player status
    player_hp_bar = draw_hp_bar(current_player.hp, current_player.max_hp)
    player_atk_bar = draw_attack_bar(current_player.attack_bar)
    
    # Enemy status
    enemy_hp_bar = draw_hp_bar(current_enemy.hp, current_enemy.max_hp)
    enemy_atk_bar = draw_attack_bar(current_enemy.attack_bar)
    
    # Get current queued action name
    queued_action_name = current_player.get_action_name(queued_action)
    
    # Combat stats
    p_stats = f"AtkPw: {current_player.atkpw:.1f} | AtkSp: {current_player.atksp:.1f} | MgcPw: {current_player.mgcpw:.1f}"
    p_stats += f"\nBlock: {current_player.block:.1f} | Dodge: {current_player.dodge:.1f}% | Armor: {current_player.armor:.1f} | MgcRs: {current_player.mgcrs:.1f}"
    
    e_stats = f"AtkPw: {current_enemy.atkpw:.1f} | AtkSp: {current_enemy.atksp:.1f} | MgcPw: {current_enemy.mgcpw:.1f}"
    e_stats += f"\nBlock: {current_enemy.block:.1f} | Dodge: {current_enemy.dodge:.1f}% | Armor: {current_enemy.armor:.1f} | MgcRs: {current_enemy.mgcrs:.1f}"
    
    # Format and display UI
    print(f"{'=' * 60}")
    print(f"[{current_player.name}] HP: {current_player.hp}/{current_player.max_hp} {player_hp_bar}")
    print(f"ATK BAR: {player_atk_bar} {current_player.attack_bar:.0f}%")
    print(f"Queued: {queued_action_name} ({queued_action})")
    print(p_stats)
    print(f"\n{'-' * 60}")
    print(f"[{current_enemy.name}] HP: {current_enemy.hp}/{current_enemy.max_hp} {enemy_hp_bar}")
    print(f"ATK BAR: {enemy_atk_bar} {current_enemy.attack_bar:.0f}%")
    print(e_stats)
    print(f"{'=' * 60}")
    
    # Combat log
    print("\nCombat Log:")
    for entry in combat_log:
        print(f"- {entry}")
    
    # Controls reminder
    print(f"\n{'-' * 60}")
    print("Controls: A=Basic Melee | S=Magic | D=Neck | Z=Main-Hand | X=Off-Hand | C=Ring | Q=Quit")

def check_combat_end():
    if current_player.hp <= 0:
        clear_screen()
        print(f"\n{current_enemy.text_win}")
        print("Game Over!")
        input("Press Enter to exit...")
        return True
    
    if current_enemy.hp <= 0:
        clear_screen()
        print(f"\n{current_enemy.text_death}")
        print(f"You gained {current_enemy.xp_yield} XP!")
        
        # Roll for loot
        print("\nLoot:")
        got_loot = False
        for i in range(5):
            if random.random() * 100 < current_enemy.drop_chances[i]:
                item_id = current_enemy.item_drops[i]
                if item_id != '0':
                    # Find item by ID
                    for item in items:
                        if item['ItemID'] == item_id:
                            print(f"- {item['Name']}")
                            got_loot = True
                            break
        
        if not got_loot:
            print("- Nothing of value")
        
        input("\nPress Enter to continue...")
        return True
    
    return False

def handle_input():
    global queued_action, running
    
    key = getch_non_blocking()
    if key is not None:
        if key in ['A', 'S', 'D', 'Z', 'X', 'C']:
            queued_action = key
        elif key == 'Q':
            running = False

def update_game():
    # Handle user input
    handle_input()
    
    # Update attack bars
    current_player.update_attack_bar()
    current_enemy.update_attack_bar()
    
    # Display UI
    display_combat_ui()
    
    # Check for combat end
    return check_combat_end()

def combat_loop():
    global running
    
    while running:
        combat_end = update_game()
        if combat_end:
            running = False
            break
        
        time.sleep(REFRESH_RATE)

def main():
    global running
    
    # Load game data
    print("Loading game data...")
    load_characters()
    load_enemies()
    load_items()
    
    # Select character
    select_character()
    
    # Select enemy
    select_enemy()
    
    try:
        # Setup terminal for Unix systems
        if os.name != 'nt':
            fd, old_settings = setup_terminal()
        
        # Start combat
        combat_loop()
    
    except KeyboardInterrupt:
        running = False
    finally:
        # Restore terminal settings for Unix systems
        if os.name != 'nt' and 'fd' in locals() and 'old_settings' in locals():
            restore_terminal(fd, old_settings)
    
    print("Exiting game...")

if __name__ == "__main__":
    main()