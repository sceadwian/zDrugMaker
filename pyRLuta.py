import csv
import time
import os
import random
import sys
import threading
import msvcrt  # For Windows keyboard input

# Global variables
characters = []
enemies = []
items = []
actions = []
selected_character = None
current_enemy = None
game_running = True
queued_action = 'A'  # Default action
last_key_pressed = None

# ASCII graphics settings
BAR_WIDTH = 30
REFRESH_RATE = 0.1  # seconds between screen updates

# File paths
CHARACTER_FILE = 'pyRLuta.csv'
ENEMY_FILE = 'pyRL_npcs.csv'
ITEM_FILE = 'pyRL_items.csv'
ACTION_FILE = 'pyRL_actions.csv'

# Classes
class Character:
    def __init__(self, id, name, attributes):
        self.id = id
        self.name = name
        self.attributes = attributes
        self.equipment = [None] * 8
        self.hp = self.calculate_hp()
        self.max_hp = self.hp
        self.attack_bar = 0
        self.effects = []  # Max 2 active effects
        self.stats = self.calculate_stats()
        self.last_damage_dealt = 0
        self.last_damage_taken = 0
        self.fill_time = self.calculate_fill_time()
        
    def calculate_hp(self):
        sta = self.attributes.get('STA', 5)
        str_attr = self.attributes.get('STR', 5)
        wil = self.attributes.get('WIL', 5)
        bls = self.attributes.get('BLS', 0)
        for_attr = self.attributes.get('FOR', 5)
        
        return 50 + (10 * sta) + (2 * str_attr) + (2 * wil) + bls + for_attr
    
    def calculate_stats(self):
        """Calculate derived combat stats based on attributes"""
        stats = {}
        
        # Helper function to get weighted average
        def weighted_avg(attr_list):
            total = 0
            for attr in attr_list:
                total += self.attributes.get(attr, 5)
            return total / len(attr_list)
        
        # Calculate stats
        stats['AtkPw'] = weighted_avg(['STR', 'STR', 'AGI', 'DEX', 'BAL'])
        stats['AtkSp'] = weighted_avg(['AGI', 'AGI', 'DEX', 'WIL', 'FOC'])
        stats['MgcPw'] = weighted_avg(['INT', 'INT', 'MAN', 'ARC', 'WIL'])
        stats['Block'] = weighted_avg(['STR', 'FOR', 'INT', 'BAL', 'WIL'])
        stats['Dodge'] = weighted_avg(['FOC', 'AGI', 'DEX', 'BAL', 'PSY'])
        stats['Armor'] = weighted_avg(['STR', 'FOR', 'STA', 'AGI', 'BLS'])
        stats['MgcRs'] = weighted_avg(['PSY', 'BLS', 'WIL', 'MAN', 'FOR'])
        
        # Apply equipment bonuses
        for item in self.equipment:
            if item:
                # Apply item bonuses
                pass
        
        return stats
    
    def calculate_fill_time(self):
        """Calculate attack bar fill time based on AtkSp"""
        # Formula: FillTime = 1.2 + (5.0 - 1.2) * (1 - AtkSp / 100)
        atk_sp = self.stats['AtkSp']
        return 1.2 + (5.0 - 1.2) * (1 - atk_sp / 100)
    
    def update_attack_bar(self, delta_time):
        """Update the attack bar based on elapsed time"""
        if self.attack_bar < 100:
            # Progress is percentage points per second
            progress_rate = 100 / self.fill_time
            self.attack_bar += progress_rate * delta_time
            if self.attack_bar > 100:
                self.attack_bar = 100
    
    def execute_action(self, target):
        """Execute the currently queued action"""
        global queued_action
        
        damage = 0
        effect = None
        
        # Reset attack bar
        self.attack_bar = 0
        
        # Determine action based on queued key
        if queued_action == 'A':  # Basic melee
            damage = self.stats['AtkPw'] * 1.0
            action_name = "Basic Melee"
            
        elif queued_action == 'S':  # Magic attack
            damage = self.stats['MgcPw'] * 1.0
            action_name = "Magic Attack"
            
        elif queued_action == 'Z' and self.equipment[5]:  # Main-hand weapon
            item = self.equipment[5]
            action_name = f"{item['Name']} - {item['Action']}"
            # Scale damage based on item's DMG attribute
            scaling_attr = item['DMG']
            damage = self.attributes.get(scaling_attr, 5) * 1.2
            
        elif queued_action == 'X' and self.equipment[4]:  # Off-hand
            item = self.equipment[4]
            action_name = f"{item['Name']} - {item['Action']}"
            scaling_attr = item['DMG']
            damage = self.attributes.get(scaling_attr, 5) * 0.8
            
        elif queued_action == 'D' and self.equipment[6]:  # Necklace
            item = self.equipment[6]
            action_name = f"{item['Name']} effect"
            # Apply effect or buff
            effect = "Buff"
            damage = self.stats['MgcPw'] * 0.5
            
        elif queued_action == 'C' and self.equipment[7]:  # Ring
            item = self.equipment[7]
            action_name = f"{item['Name']} effect"
            # Apply effect or buff
            effect = "Buff"
            damage = self.stats['MgcPw'] * 0.5
            
        else:
            action_name = "Missed Attack"
            damage = 0
        
        # Apply damage reduction
        final_damage = self.apply_damage(target, damage, action_name)
        self.last_damage_dealt = final_damage
        
        # Update display with action results
        return action_name, final_damage, effect
    
    def apply_damage(self, target, damage, action_name):
        """Apply damage to target with mitigation checks"""
        # Check for dodge
        dodge_chance = min(target.stats['Dodge'] / 10, 10)  # Cap at 10%
        if random.random() * 100 < dodge_chance:
            print(f"{target.name} dodged the {action_name}!")
            return 0
        
        # Apply mitigation based on attack type
        if 'Magic' in action_name:
            # Magic resistance
            max_reduction = target.stats['MgcRs']
            actual_reduction = random.randint(1, int(max_reduction)) / 100
            mitigated = damage * actual_reduction
            final_damage = max(1, damage - mitigated)
        else:
            # Physical armor/block
            max_reduction = target.stats['Block']
            actual_reduction = random.randint(1, int(max_reduction)) / 100
            mitigated = damage * actual_reduction
            final_damage = max(1, damage - mitigated)
        
        # Round damage to integer
        final_damage = int(final_damage)
        target.hp -= final_damage
        target.last_damage_taken = final_damage
        
        # Check if target is defeated
        if target.hp <= 0:
            target.hp = 0
            
        return final_damage

class Enemy(Character):
    def __init__(self, id, name, hp, atk_pw, atk_sp, mgc_pw, block, dodge, armor, mgc_rs, 
                 item_drops, xp_yield, text_start, text_death, text_win, action_sequence):
        # Initialize with base stats instead of attributes
        self.id = id
        self.name = name
        self.hp = hp
        self.max_hp = hp
        self.attack_bar = 0
        self.effects = []
        
        # Directly set stats
        self.stats = {
            'AtkPw': atk_pw,
            'AtkSp': atk_sp,
            'MgcPw': mgc_pw,
            'Block': block,
            'Dodge': dodge,
            'Armor': armor,
            'MgcRs': mgc_rs
        }
        
        self.item_drops = item_drops
        self.xp_yield = xp_yield
        self.text_start = text_start
        self.text_death = text_death
        self.text_win = text_win
        self.action_sequence = action_sequence
        self.current_action_index = 0
        self.fill_time = self.calculate_fill_time()
        self.last_damage_dealt = 0
        self.last_damage_taken = 0
        
    def next_action(self):
        """Get the next action in the sequence"""
        action_id = self.action_sequence[self.current_action_index]
        self.current_action_index = (self.current_action_index + 1) % len(self.action_sequence)
        return action_id
    
    def execute_action(self, target):
        """Execute the enemy's next action from its sequence"""
        # Reset attack bar
        self.attack_bar = 0
        
        # Get next action from sequence
        action_id = self.next_action()
        
        # Simple implementation - just do damage based on enemy's attack power
        if action_id == 1:  # Melee attack
            damage = self.stats['AtkPw']
            action_name = "Enemy Melee"
        elif action_id == 2:  # Magic attack
            damage = self.stats['MgcPw']
            action_name = "Enemy Magic"
        elif action_id == 3:  # Special attack
            damage = max(self.stats['AtkPw'], self.stats['MgcPw']) * 1.2
            action_name = "Enemy Special"
        else:
            damage = self.stats['AtkPw'] * 0.8
            action_name = "Enemy Weak Attack"
        
        # Apply damage reduction
        final_damage = self.apply_damage(target, damage, action_name)
        self.last_damage_dealt = final_damage
        
        return action_name, final_damage, None

# Utility functions
def clear_screen():
    """Clear the console screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def load_characters():
    """Load character data from CSV"""
    global characters
    try:
        with open(CHARACTER_FILE, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Extract basic info
                char_id = row['CharacterID']
                name = row['Name']
                
                # Extract attributes
                attributes = {}
                attribute_cols = ['STA', 'STR', 'AGI', 'DEX', 'HIT', 'BAL', 'WGT', 'HEI',
                                 'INT', 'MAN', 'WIL', 'FOR', 'FOC', 'PSY',
                                 'ARC', 'BLS', 'ALC', 'CUR', 'COR', 'SUM', 'HEX']
                
                for attr in attribute_cols:
                    if attr in row:
                        attributes[attr] = int(row[attr])
                
                # Create character
                char = Character(char_id, name, attributes)
                characters.append(char)
                
        print(f"Loaded {len(characters)} characters")
        
    except FileNotFoundError:
        print(f"Error: {CHARACTER_FILE} not found. Creating sample character...")
        # Create a sample character
        sample_attributes = {
            'STA': 10, 'STR': 8, 'AGI': 7, 'DEX': 6, 'HIT': 5, 'BAL': 6, 
            'INT': 5, 'MAN': 5, 'WIL': 6, 'FOR': 7, 'FOC': 6, 'PSY': 4,
            'ARC': 3, 'BLS': 2, 'ALC': 1
        }
        char = Character("1", "Warrior", sample_attributes)
        characters.append(char)

def load_enemies():
    """Load enemy data from CSV"""
    global enemies
    try:
        with open(ENEMY_FILE, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Extract enemy info
                enemy_id = row['EnemyID']
                name = row['Name']
                hp = int(row['HP'])
                atk_pw = int(row['AtkPw'])
                atk_sp = int(row['AtkSp'])
                mgc_pw = int(row['MgcPw'])
                block = int(row['Block'])
                dodge = int(row['Dodge'])
                armor = int(row['Armor'])
                mgc_rs = int(row['MgcRs'])
                
                # Extract item drops
                item_drops = [
                    int(row['Item1ID']) if 'Item1ID' in row else None,
                    int(row['Item2ID']) if 'Item2ID' in row else None,
                    int(row['Item3ID']) if 'Item3ID' in row else None,
                    int(row['Item4ID']) if 'Item4ID' in row else None,
                    int(row['Item5ID']) if 'Item5ID' in row else None
                ]
                
                xp_yield = int(row['XPYield']) if 'XPYield' in row else 10
                text_start = row['TextStart'] if 'TextStart' in row else f"{name} appears!"
                text_death = row['TextDeath'] if 'TextDeath' in row else f"{name} is defeated!"
                text_win = row['TextWin'] if 'TextWin' in row else "You have been defeated!"
                
                # Extract action sequence (or use default)
                action_sequence = [1, 1, 1, 2, 1, 1, 3, 1, 2]  # Default sequence
                if 'ActionSequence' in row:
                    try:
                        action_sequence = [int(x) for x in row['ActionSequence'].split(',')]
                    except:
                        pass
                
                # Create enemy
                enemy = Enemy(enemy_id, name, hp, atk_pw, atk_sp, mgc_pw, block, dodge, armor, mgc_rs,
                             item_drops, xp_yield, text_start, text_death, text_win, action_sequence)
                enemies.append(enemy)
                
        print(f"Loaded {len(enemies)} enemies")
        
    except FileNotFoundError:
        print(f"Error: {ENEMY_FILE} not found. Creating sample enemies...")
        # Create sample enemies
        goblin = Enemy("1", "Goblin", 50, 5, 60, 2, 10, 15, 5, 5, 
                      [1, 2, 3, 4, 5], 10, "A goblin appears!", "The goblin dies!", 
                      "The goblin defeated you!", [1, 1, 1, 2, 1, 1, 3, 1, 2])
        enemies.append(goblin)
        
        skeleton = Enemy("2", "Skeleton", 75, 7, 40, 3, 20, 5, 15, 10,
                        [2, 3, 4, 5, 6], 15, "A skeleton rises!", "The skeleton crumbles!", 
                        "The skeleton has defeated you!", [1, 2, 1, 1, 3, 1, 2, 2, 1])
        enemies.append(skeleton)

def load_items():
    """Load item data from CSV"""
    global items
    try:
        with open(ITEM_FILE, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                items.append(row)
        print(f"Loaded {len(items)} items")
    except FileNotFoundError:
        print(f"Error: {ITEM_FILE} not found")

def load_actions():
    """Load action data from CSV"""
    global actions
    try:
        with open(ACTION_FILE, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                actions.append(row)
        print(f"Loaded {len(actions)} actions")
    except FileNotFoundError:
        print(f"Error: {ACTION_FILE} not found")

def select_character():
    """Display character selection menu"""
    global selected_character
    
    clear_screen()
    print("==== CHARACTER SELECTION ====")
    
    for i, char in enumerate(characters):
        print(f"{i+1}. {char.name} (HP: {char.hp}, STR: {char.attributes.get('STR', 0)}, AGI: {char.attributes.get('AGI', 0)})")
    
    while True:
        try:
            choice = int(input("\nSelect a character (number): "))
            if 1 <= choice <= len(characters):
                selected_character = characters[choice-1]
                break
            else:
                print("Invalid selection. Try again.")
        except ValueError:
            print("Please enter a number.")
    
    return selected_character

def select_enemy():
    """Select a random enemy to fight"""
    global current_enemy
    if enemies:
        current_enemy = random.choice(enemies)
    else:
        # Create a default enemy if none are loaded
        current_enemy = Enemy("0", "Training Dummy", 50, 5, 50, 0, 10, 5, 10, 5,
                             [], 5, "A training dummy appears!", "The dummy breaks!", 
                             "How did you lose to a dummy?", [1, 1, 1, 1, 1, 1, 1, 1, 1])
    
    return current_enemy

def render_bar(value, max_value, width):
    """Render a progress bar with ASCII characters"""
    fill_width = int(width * (value / max_value))
    empty_width = width - fill_width
    return '[' + '■' * fill_width + ' ' * empty_width + ']'

def render_combat_ui():
    """Render the combat UI with ASCII graphics"""
    clear_screen()
    
    # Header
    print("=" * 60)
    print("ASCII ROGUELIKE COMBAT SIMULATOR")
    print("=" * 60)
    
    # Player character display
    player = selected_character
    bar_percentage = int(player.attack_bar)
    player_bar = render_bar(player.attack_bar, 100, BAR_WIDTH)
    
    print(f"\n[{player.name}] HP: {player.hp}/{player.max_hp}   ATK BAR: {player_bar} {bar_percentage}%")
    print(f"Queued: {action_key_to_name(queued_action)} ({queued_action})")
    print(f"Stats: AtkPw: {int(player.stats['AtkPw'])} | AtkSp: {int(player.stats['AtkSp'])} | MgcPw: {int(player.stats['MgcPw'])}")
    print(f"       Block: {int(player.stats['Block'])} | Dodge: {int(player.stats['Dodge'])} | Armor: {int(player.stats['Armor'])} | MgcRs: {int(player.stats['MgcRs'])}")
    
    if player.last_damage_dealt > 0:
        print(f"Last attack dealt: {player.last_damage_dealt} damage")
    if player.last_damage_taken > 0:
        print(f"Last damage taken: {player.last_damage_taken}")
    
    # Enemy display
    enemy = current_enemy
    enemy_bar_percentage = int(enemy.attack_bar)
    enemy_bar = render_bar(enemy.attack_bar, 100, BAR_WIDTH)
    
    print("\n" + "-" * 60)
    print(f"\n[{enemy.name}] HP: {enemy.hp}/{enemy.max_hp}   ATK BAR: {enemy_bar} {enemy_bar_percentage}%")
    print(f"Next: Enemy Action #{enemy.action_sequence[enemy.current_action_index]}")
    
    if enemy.last_damage_dealt > 0:
        print(f"Last attack dealt: {enemy.last_damage_dealt} damage")
    if enemy.last_damage_taken > 0:
        print(f"Last damage taken: {enemy.last_damage_taken}")
    
    # Controls
    print("\n" + "-" * 60)
    print("\nCONTROLS:")
    print("A = Basic melee | S = Magic attack | D = Necklace effect | Z = Main-hand weapon | X = Off-hand weapon | C = Ring effect | Q = Quit")

def action_key_to_name(key):
    """Convert action key to descriptive name"""
    actions = {
        'A': 'Basic Melee',
        'S': 'Magic Attack',
        'Z': 'Main-hand Weapon',
        'X': 'Off-hand Weapon',
        'D': 'Necklace Effect',
        'C': 'Ring Effect'
    }
    return actions.get(key, 'Unknown')

def keyboard_input_thread():
    """Thread to handle keyboard input without blocking"""
    global queued_action, game_running
    
    while game_running:
        if msvcrt.kbhit():
            key = msvcrt.getch().decode('utf-8').upper()
            
            # Check valid action keys
            if key in ['A', 'S', 'D', 'Z', 'X', 'C']:
                queued_action = key
            elif key == 'Q':
                game_running = False
        
        time.sleep(0.05)  # Small delay to prevent CPU hogging

def simulate_combat():
    """Main combat simulation loop"""
    global game_running, selected_character, current_enemy
    
    last_time = time.time()
    combat_log = []
    
    # Start keyboard input thread
    input_thread = threading.Thread(target=keyboard_input_thread)
    input_thread.daemon = True
    input_thread.start()
    
    # Print combat start text
    clear_screen()
    print(current_enemy.text_start)
    time.sleep(2)
    
    # Main combat loop
    while game_running:
        current_time = time.time()
        delta_time = current_time - last_time
        last_time = current_time
        
        # Update attack bars
        selected_character.update_attack_bar(delta_time)
        current_enemy.update_attack_bar(delta_time)
        
        # Check if player's attack bar is full
        if selected_character.attack_bar >= 100:
            action_name, damage, effect = selected_character.execute_action(current_enemy)
            combat_log.append(f"{selected_character.name} used {action_name} for {damage} damage!")
            
            # Check if enemy is defeated
            if current_enemy.hp <= 0:
                render_combat_ui()
                print("\n" + "-" * 60)
                print(f"\n{current_enemy.text_death}")
                print(f"You gained {current_enemy.xp_yield} XP!")
                
                # Check for item drops
                for item_id in current_enemy.item_drops:
                    if item_id is not None:
                        drop_chance = 0
                        if current_enemy.item_drops.index(item_id) < 3:
                            drop_chance = 30  # Common items (30%)
                        elif current_enemy.item_drops.index(item_id) == 3:
                            drop_chance = 8   # Uncommon item (8%)
                        else:
                            drop_chance = 2   # Rare item (2%)
                            
                        if random.randint(1, 100) <= drop_chance:
                            # Find item by ID
                            for item in items:
                                if int(item['ItemID']) == item_id:
                                    print(f"You found {item['Name']}!")
                                    break
                
                time.sleep(3)
                game_running = False
                break
        
        # Check if enemy's attack bar is full
        if current_enemy.attack_bar >= 100:
            action_name, damage, effect = current_enemy.execute_action(selected_character)
            combat_log.append(f"{current_enemy.name} used {action_name} for {damage} damage!")
            
            # Check if player is defeated
            if selected_character.hp <= 0:
                render_combat_ui()
                print("\n" + "-" * 60)
                print(f"\n{current_enemy.text_win}")
                time.sleep(3)
                game_running = False
                break
        
        # Render UI
        render_combat_ui()
        
        # Show last 3 combat log entries
        print("\nCOMBAT LOG:")
        for entry in combat_log[-3:]:
            print(entry)
        
        # Control refresh rate
        time.sleep(REFRESH_RATE)

def main():
    """Main game function"""
    global selected_character, current_enemy, game_running
    
    # Load game data
    print("Loading game data...")
    load_characters()
    load_enemies()
    load_items()
    load_actions()
    
    # Character selection
    selected_character = select_character()
    
    # Select enemy
    current_enemy = select_enemy()
    
    # Combat simulation
    simulate_combat()
    
    print("\nThank you for playing!")
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()