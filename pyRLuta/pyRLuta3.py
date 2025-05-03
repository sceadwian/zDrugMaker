import random
import time
import os
import csv
import math
import sys
from datetime import datetime

# Constants
REFRESH_RATE = 0.1  # seconds

# Attributes and Stats
class Attributes:
    def __init__(self):
        # Physical attributes
        self.STA = 10  # Stamina
        self.STR = 10  # Strength
        self.AGI = 10  # Agility
        self.DEX = 10  # Dexterity
        self.HIT = 10  # Accuracy
        self.BAL = 10  # Balance
        self.WGT = 70  # Weight (Kg)
        self.HEI = 175  # Height (cm)
        
        # Mental attributes
        self.INT = 10  # Intellect
        self.WIL = 10  # Willpower
        self.FOR = 10  # Fortitude
        self.FOC = 10  # Focus
        self.PSY = 10  # Psyche
        
        # Magical attributes
        self.ARC = 10  # Arcane (raw magic inclination)
        self.BLS = 10  # Blessing (divine favor)
        self.MAN = 10  # Mana
        self.ALC = 10  # Alchemy
        
        # Forbidden attributes
        self.CUR = 10  # Cursing Power
        self.COR = 10  # Corruption
        self.SUM = 10  # Summoning Power
        self.HEX = 10  # Hex Defense and Attack Ability
    
    def calculate_hp(self):
        return 50 + (5 * self.STA) + (2 * self.STR) + (2 * self.WIL) + self.FOR + self.FOC + self.BLS
    
    def calculate_atkpw(self):
        return self.STR + self.STR + self.AGI + self.DEX + self.BAL
    
    def calculate_atksp(self):
        return self.AGI + self.AGI + self.DEX + self.WIL + self.FOC
    
    def calculate_mgcpw(self):
        return self.INT + self.INT + self.MAN + self.ARC + self.WIL
    
    def calculate_block(self):
        return self.STR + self.FOR + self.INT + self.BAL + self.WIL
    
    def calculate_dodge(self):
        return self.FOC + self.AGI + self.DEX + self.BAL + self.PSY
    
    def calculate_armor(self):
        return self.STR + self.FOR + self.STA + self.AGI + self.BLS
    
    def calculate_mgcrs(self):
        return self.PSY + self.BLS + self.WIL + self.MAN + self.FOR
    
    def calculate_crits(self):
        return self.HIT + self.HIT + self.HIT + self.ARC + self.FOC
    
    def to_dict(self):
        return {attr: getattr(self, attr) for attr in dir(self) if not attr.startswith('__') and not callable(getattr(self, attr))}


class Item:
    def __init__(self, id, slot, name, bonus1id, bonus1add, bonus2id, bonus2add, 
                 action_id=None, action=None, skill_check=None, attack_type=None):
        self.id = id
        self.slot = slot
        self.name = name
        self.bonus1id = bonus1id
        self.bonus1add = bonus1add
        self.bonus2id = bonus2id
        self.bonus2add = bonus2add
        self.action_id = action_id
        self.action = action
        self.skill_check = skill_check
        self.attack_type = attack_type
    
    def __str__(self):
        return f"{self.name} (+{self.bonus1add} {self.bonus1id}, +{self.bonus2add} {self.bonus2id})"


class Action:
    def __init__(self, id, name, base_dmg, scaling_stat, damage_type, description, effect=None):
        self.id = id
        self.name = name
        self.base_dmg = base_dmg
        self.scaling_stat = scaling_stat
        self.damage_type = damage_type
        self.description = description
        self.effect = effect
    
    def __str__(self):
        return f"{self.name} ({self.base_dmg} {self.damage_type} dmg)"


class Character:
    def __init__(self, name):
        self.name = name
        self.attributes = Attributes()
        self.hp = self.attributes.calculate_hp()
        self.max_hp = self.hp
        self.xp = 0
        self.level = 1
        self.equipment = {
            1: None,  # Head
            2: None,  # Chest
            3: None,  # Legs
            4: None,  # Feet
            5: None,  # Off-Hand (X)
            6: None,  # Main-Hand (Z)
            7: None,  # Neck (D)
            8: None   # Ring (C)
        }
        self.buffs = []
        self.debuffs = []
        self.attack_bar = 0
        self.queued_action = 'A'  # Default to basic attack
        self.default_actions = {
            'A': Action(1, "Punch", 3, "AtkPw", "melee", "A basic punch"),
            'S': Action(2, "Curse", 2, "MgcPw", "magic", "A basic curse"),
            'D': Action(3, "Soothe", 0, "MgcPw", "magic", "A calming spell that heals 5 HP", "heal"),
            'Z': Action(4, "Kick", 4, "AtkPw", "melee", "A powerful kick"),
            'X': None,  # Will be defined by equipment
            'C': None   # Will be defined by equipment
        }
        self.combat_log = []
        self.kills = 0
        self.damage_done = 0
        self.damage_received = 0
    
    def update_stats(self):
        """Recalculate all stats based on attributes and equipment"""
        self.max_hp = self.attributes.calculate_hp()
        
        # Apply equipment bonuses
        for slot, item in self.equipment.items():
            if item:
                if hasattr(self.attributes, item.bonus1id):
                    setattr(self.attributes, item.bonus1id, 
                            getattr(self.attributes, item.bonus1id) + item.bonus1add)
                if hasattr(self.attributes, item.bonus2id):
                    setattr(self.attributes, item.bonus2id, 
                            getattr(self.attributes, item.bonus2id) + item.bonus2add)
                
                # Set equipment actions
                if slot == 5 and item.action:  # Off-Hand
                    self.default_actions['X'] = game_actions.get(item.action_id)
                elif slot == 6 and item.action:  # Main-Hand
                    self.default_actions['Z'] = game_actions.get(item.action_id)
                elif slot == 7 and item.action:  # Neck
                    self.default_actions['D'] = game_actions.get(item.action_id)
                elif slot == 8 and item.action:  # Ring
                    self.default_actions['C'] = game_actions.get(item.action_id)
    
    def equip_item(self, item):
        """Equip an item if it passes the skill check"""
        if item.skill_check:
            required_stat = getattr(self.attributes, item.skill_check)
            if required_stat < 10:  # Example threshold
                return False, f"You need at least 10 {item.skill_check} to equip {item.name}"
        
        self.equipment[item.slot] = item
        self.update_stats()
        return True, f"Equipped {item.name}"
    
    def get_action(self, key):
        """Get the appropriate action based on key press"""
        return self.default_actions.get(key)
    
    def update_attack_bar(self, delta_time):
        """Update the attack bar based on attack speed"""
        attack_speed = self.attributes.calculate_atksp()
        fill_time = 1.2 + (5.0 - 1.2) * (1 - attack_speed / 100)
        self.attack_bar += (delta_time / fill_time) * 100
        return self.attack_bar >= 100
    
    def execute_action(self, target):
        """Execute the currently queued action"""
        action = self.get_action(self.queued_action)
        if not action:
            self.combat_log.append(f"{self.name} has no action queued!")
            self.attack_bar = 0
            return
        
        # Determine base damage
        if action.scaling_stat == "AtkPw":
            base_damage = action.base_dmg + (self.attributes.calculate_atkpw() / 10)
        elif action.scaling_stat == "MgcPw":
            base_damage = action.base_dmg + (self.attributes.calculate_mgcpw() / 10)
        else:
            # Specific attribute scaling
            base_damage = action.base_dmg + (getattr(self.attributes, action.scaling_stat) / 2)
        
        # Check for special effects
        if action.effect == "heal":
            heal_amount = int(5 + (self.attributes.calculate_mgcpw() / 20))
            self.hp = min(self.max_hp, self.hp + heal_amount)
            self.combat_log.append(f"{self.name} used {action.name} and healed for {heal_amount} HP!")
            self.attack_bar = 0
            return
        
        # Check dodge
        dodge_chance = target.attributes.calculate_dodge() / 10
        if random.random() < (dodge_chance / 100):
            self.combat_log.append(f"{target.name} dodged {self.name}'s {action.name}!")
            self.attack_bar = 0
            return
        
        # Check critical hit
        crit_chance = self.attributes.calculate_crits() / 3
        is_crit = random.random() < (crit_chance / 100)
        damage_multiplier = 2.0 if is_crit else 1.0
        
        # Apply mitigation
        if action.damage_type == "melee":
            mitigation = random.uniform(0.01, target.attributes.calculate_block() / 100)
        else:  # magic
            mitigation = random.uniform(0.01, target.attributes.calculate_mgcrs() / 100)
        
        mitigation = min(0.75, mitigation)  # Cap mitigation at 75%
        
        # Calculate final damage
        final_damage = max(1, int(base_damage * damage_multiplier * (1 - mitigation)))
        
        # Apply damage
        target.hp -= final_damage
        target.damage_received += final_damage
        self.damage_done += final_damage
        
        # Log the outcome
        crit_text = " [CRITICAL!]" if is_crit else ""
        self.combat_log.append(f"{self.name} hit {target.name} with {action.name} for {final_damage} damage{crit_text}!")
        
        # Reset attack bar
        self.attack_bar = 0
    
    def is_dead(self):
        return self.hp <= 0


class Enemy(Character):
    def __init__(self, name, hp, atkpw, atksp, mgcpw, block, dodge, armor, mgcrs, crits, action_sequence, xp_yield):
        super().__init__(name)
        self.hp = hp
        self.max_hp = hp
        self.attack_sequence = action_sequence
        self.current_action_index = 0
        self.xp_yield = xp_yield
        
        # Override calculated stats with provided values
        # This is a simplification for enemies
        self._atkpw = atkpw
        self._atksp = atksp
        self._mgcpw = mgcpw
        self._block = block
        self._dodge = dodge
        self._armor = armor
        self._mgcrs = mgcrs
        self._crits = crits
    
    def get_next_action(self):
        action_id = self.attack_sequence[self.current_action_index]
        self.current_action_index = (self.current_action_index + 1) % len(self.attack_sequence)
        return game_actions.get(action_id)
    
    def execute_action(self, target):
        action = self.get_next_action()
        if not action:
            self.combat_log.append(f"{self.name} has no action!")
            self.attack_bar = 0
            return
        
        # Determine base damage
        if action.scaling_stat == "AtkPw":
            base_damage = action.base_dmg + (self._atkpw / 10)
        elif action.scaling_stat == "MgcPw":
            base_damage = action.base_dmg + (self._mgcpw / 10)
        else:
            # Default scaling
            base_damage = action.base_dmg + 1
        
        # Check for special effects
        if action.effect == "heal":
            heal_amount = int(5 + (self._mgcpw / 20))
            self.hp = min(self.max_hp, self.hp + heal_amount)
            self.combat_log.append(f"{self.name} used {action.name} and healed for {heal_amount} HP!")
            self.attack_bar = 0
            return
        
        # Check dodge
        dodge_chance = target.attributes.calculate_dodge() / 10
        if random.random() < (dodge_chance / 100):
            self.combat_log.append(f"{target.name} dodged {self.name}'s {action.name}!")
            self.attack_bar = 0
            return
        
        # Check critical hit
        crit_chance = self._crits / 3
        is_crit = random.random() < (crit_chance / 100)
        damage_multiplier = 2.0 if is_crit else 1.0
        
        # Apply mitigation
        if action.damage_type == "melee":
            mitigation = random.uniform(0.01, target.attributes.calculate_block() / 100)
        else:  # magic
            mitigation = random.uniform(0.01, target.attributes.calculate_mgcrs() / 100)
        
        mitigation = min(0.75, mitigation)  # Cap mitigation at 75%
        
        # Calculate final damage
        final_damage = max(1, int(base_damage * damage_multiplier * (1 - mitigation)))
        
        # Apply damage
        target.hp -= final_damage
        target.damage_received += final_damage
        self.damage_done += final_damage
        
        # Log the outcome
        crit_text = " [CRITICAL!]" if is_crit else ""
        self.combat_log.append(f"{self.name} hit {target.name} with {action.name} for {final_damage} damage{crit_text}!")
        
        # Reset attack bar
        self.attack_bar = 0
    
    def update_attack_bar(self, delta_time):
        """Update the attack bar based on attack speed"""
        fill_time = 1.2 + (5.0 - 1.2) * (1 - self._atksp / 100)
        self.attack_bar += (delta_time / fill_time) * 100
        return self.attack_bar >= 100


class Game:
    def __init__(self):
        self.player = None
        self.current_enemy = None
        self.items = {}
        self.actions = {}
        self.enemies = []
        self.combat_active = False
        self.last_time = time.time()
        self.input_buffer = None
    
    def clear_screen(self):
        """Clear the console screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def initialize_game_data(self):
        """Initialize game data with sample values"""
        # Sample actions
        self.actions = {
            1: Action(1, "Punch", 3, "AtkPw", "melee", "A basic punch"),
            2: Action(2, "Curse", 2, "MgcPw", "magic", "A basic curse"),
            3: Action(3, "Soothe", 0, "MgcPw", "magic", "A calming spell that heals 5 HP", "heal"),
            4: Action(4, "Kick", 4, "AtkPw", "melee", "A powerful kick"),
            5: Action(5, "Fireball", 6, "MgcPw", "magic", "A powerful magical attack"),
            6: Action(6, "Bash", 5, "STR", "melee", "A shield bash attack"),
            7: Action(7, "Cleave", 7, "STR", "melee", "A wide sweeping attack"),
            8: Action(8, "Snurp", 4, "AGI", "melee", "A quick jab"),
            9: Action(9, "Zap", 3, "ARC", "magic", "A small lightning bolt"),
            10: Action(10, "Drain", 2, "MgcPw", "magic", "Drains life from the target", "leech"),
            11: Action(11, "Stab", 6, "DEX", "melee", "A precise stabbing attack"),
            12: Action(12, "Slash", 5, "STR", "melee", "A slashing attack"),
            20: Action(20, "Shadow Bolt", 7, "CUR", "magic", "A bolt of shadow energy"),
            21: Action(21, "Arcane Shot", 5, "ARC", "magic", "A shot of pure arcane energy")
        }
        
        # Sample items
        self.items = {
            1: Item(1, 1, "Iron Helmet", "STR", 1, "STA", 1),
            2: Item(2, 2, "Iron Breastplate", "FOR", 1, "STA", 1),
            3: Item(3, 3, "Iron Leggings", "FOR", 1, "STA", 1),
            4: Item(4, 4, "Iron Boots", "BAL", 1, "STA", 1),
            5: Item(5, 1, "Witch Hat", "MAN", 1, "ARC", 1),
            6: Item(6, 2, "Robe", "INT", 1, "STA", 1),
            7: Item(7, 3, "Magic Thong", "ALC", 1, "COR", 1),
            8: Item(8, 4, "Sandals", "INT", 1, "AGI", 1),
            9: Item(9, 5, "Wooden Stick", "STR", 1, "AGI", 1, 8, "Snurp", "AGI", "melee"),
            10: Item(10, 6, "Wooden Shield", "STA", 3, "AGI", -1, 6, "Bash", "STR", "melee"),
            11: Item(11, 7, "Pendant of Focus", "FOC", 3, "INT", 1),
            12: Item(12, 8, "Bronze Ring", "STR", 1, "WIL", 1),
            13: Item(13, 5, "Snakey Stick", "INT", 1, "MAN", 1, 21, "Arcane Shot", "ARC", "magic"),
            14: Item(14, 6, "Silver Dagger", "DEX", 2, "AGI", 1, 11, "Stab", "DEX", "melee"),
            15: Item(15, 7, "Shitty Necklace", "INT", 1, "FOC", 1),
            16: Item(16, 8, "Iron Ring", "INT", 1, "WIL", 1)
        }
        
        # Sample enemies
        self.enemies = [
            {
                "name": "Goblin Scout",
                "hp": 30,
                "atkpw": 20,
                "atksp": 25,
                "mgcpw": 10,
                "block": 15,
                "dodge": 20,
                "armor": 15,
                "mgcrs": 10,
                "crits": 15,
                "action_sequence": [1, 1, 1, 4, 1, 4, 1, 1, 4],
                "xp_yield": 10
            },
            {
                "name": "Skeleton Warrior",
                "hp": 40,
                "atkpw": 25,
                "atksp": 15,
                "mgcpw": 5,
                "block": 20,
                "dodge": 10,
                "armor": 25,
                "mgcrs": 15,
                "crits": 10,
                "action_sequence": [1, 7, 1, 1, 6, 1, 7, 1, 6],
                "xp_yield": 15
            },
            {
                "name": "Dark Apprentice",
                "hp": 25,
                "atkpw": 10,
                "atksp": 20,
                "mgcpw": 30,
                "block": 10,
                "dodge": 15,
                "armor": 10,
                "mgcrs": 25,
                "crits": 20,
                "action_sequence": [2, 5, 2, 3, 2, 5, 2, 20, 3],
                "xp_yield": 20
            }
        ]
        
        # Make actions available globally
        global game_actions
        game_actions = self.actions
    
    def create_player(self, name):
        """Create a new player character"""
        self.player = Character(name)
        
        # Give some starting equipment
        self.player.equip_item(self.items[1])  # Iron Helmet
        self.player.equip_item(self.items[2])  # Iron Breastplate
        self.player.equip_item(self.items[3])  # Iron Leggings
        self.player.equip_item(self.items[4])  # Iron Boots
        self.player.equip_item(self.items[10])  # Wooden Shield
        
        return self.player
    
    def spawn_enemy(self):
        """Spawn a random enemy from the enemy list"""
        enemy_data = random.choice(self.enemies)
        enemy = Enemy(
            enemy_data["name"],
            enemy_data["hp"],
            enemy_data["atkpw"],
            enemy_data["atksp"],
            enemy_data["mgcpw"],
            enemy_data["block"],
            enemy_data["dodge"],
            enemy_data["armor"],
            enemy_data["mgcrs"],
            enemy_data["crits"],
            enemy_data["action_sequence"],
            enemy_data["xp_yield"]
        )
        self.current_enemy = enemy
        return enemy
    
    def handle_input(self, key):
        """Handle player input during combat"""
        if key in ['A', 'S', 'D', 'Z', 'X', 'C']:
            action = self.player.get_action(key)
            if action:
                self.player.queued_action = key
                return f"Queued: {action.name} ({key})"
            else:
                return f"No action available for key {key}"
        return "Invalid key"
    
    def draw_attack_bar(self, value, width=20):
        """Draw an ASCII attack bar"""
        filled = int(value / 100 * width)
        bar = "["
        for i in range(width):
            if i < filled:
                bar += "■"
            else:
                bar += " "
        bar += f"] {int(value)}%"
        return bar
    
    def draw_combat_hud(self):
        """Draw the combat HUD"""
        p_action = self.player.get_action(self.player.queued_action)
        p_action_name = p_action.name if p_action else "None"
        
        e_next_action = self.current_enemy.get_next_action()
        e_action_name = e_next_action.name if e_next_action else "None"
        
        hud = f"""
[{self.player.name}] HP: {self.player.hp}/{self.player.max_hp}   ATK BAR: {self.draw_attack_bar(self.player.attack_bar)}
Queued: {p_action_name} ({self.player.queued_action})
AtkPw: {self.player.attributes.calculate_atkpw()} / AtkSp: {self.player.attributes.calculate_atksp()} / MgcPw: {self.player.attributes.calculate_mgcpw()}
Block: {self.player.attributes.calculate_block()} / Dodge: {self.player.attributes.calculate_dodge()} / Armor: {self.player.attributes.calculate_armor()} / MgcRs: {self.player.attributes.calculate_mgcrs()} / Crits: {self.player.attributes.calculate_crits()}

[{self.current_enemy.name}] HP: {self.current_enemy.hp}/{self.current_enemy.max_hp}   ATK BAR: {self.draw_attack_bar(self.current_enemy.attack_bar)}
Next Attack: {e_action_name}
AtkPw: {self.current_enemy._atkpw} / AtkSp: {self.current_enemy._atksp} / MgcPw: {self.current_enemy._mgcpw}
Block: {self.current_enemy._block} / Dodge: {self.current_enemy._dodge} / Armor: {self.current_enemy._armor} / MgcRs: {self.current_enemy._mgcrs} / Crits: {self.current_enemy._crits}
"""
        return hud
    
    def draw_combat_log(self):
        """Draw the combat log with the last few entries"""
        log = "\nCombat Log:\n"
        for entry in self.player.combat_log[-5:]:
            log += f"- {entry}\n"
        return log
    
    def draw_controls(self):
        """Draw the controls help"""
        controls = """
Controls:
A = Basic melee attack
S = Magic attack
D = Necklace ability
Z = Main-hand weapon ability
X = Off-hand weapon ability
C = Ring ability
Q = Quit combat
"""
        return controls
    
    def simulate_combat(self, delta_time):
        """Simulate one step of combat"""
        # Update player attack bar
        if self.player.update_attack_bar(delta_time):
            self.player.execute_action(self.current_enemy)
        
        # Update enemy attack bar
        if not self.current_enemy.is_dead() and self.current_enemy.update_attack_bar(delta_time):
            self.current_enemy.execute_action(self.player)
        
        # Check for combat end
        if self.current_enemy.is_dead():
            self.player.xp += self.current_enemy.xp_yield
            self.player.kills += 1
            self.combat_active = False
            return True, f"You defeated the {self.current_enemy.name} and gained {self.current_enemy.xp_yield} XP!"
        
        if self.player.is_dead():
            self.combat_active = False
            return True, "You have been defeated!"
        
        return False, ""
    
    def roll_loot(self):
        """Roll for loot drops"""
        # Simplified loot roll
        roll = random.random()
        if roll < 0.30:  # Common (30%)
            slot = random.randint(1, 3)
            items = [item for item in self.items.values() if item.slot == slot]
            return random.choice(items) if items else None
        elif roll < 0.38:  # Uncommon (8%)
            slot = 4
            items = [item for item in self.items.values() if item.slot == slot]
            return random.choice(items) if items else None
        elif roll < 0.40:  # Rare (2%)
            slot = 5
            items = [item for item in self.items.values() if item.slot == slot]
            return random.choice(items) if items else None
        else:
            return None
    
    def start_combat(self):
        """Start combat with a random enemy"""
        self.spawn_enemy()
        self.combat_active = True
        self.player.combat_log = []
        self.player.combat_log.append(f"Combat started against {self.current_enemy.name}!")
        self.last_time = time.time()
    
    def main_loop(self):
        """Main game loop"""
        self.clear_screen()
        print("Welcome to ASCII Roguelike!")
        player_name = input("Enter your character name: ")
        self.create_player(player_name)
        
        running = True
        while running:
            if not self.combat_active:
                self.clear_screen()
                print(f"{self.player.name} (Level {self.player.level}, XP: {self.player.xp})")
                print(f"HP: {self.player.hp}/{self.player.max_hp}")
                print(f"Kills: {self.player.kills}")
                print("\nEquipment:")
                for slot, item in sorted(self.player.equipment.items()):
                    slot_name = {1: "Head", 2: "Chest", 3: "Legs", 4: "Feet", 
                                5: "Off-Hand", 6: "Main-Hand", 7: "Neck", 8: "Ring"}[slot]
                    print(f"{slot_name}: {item if item else 'Empty'}")
                
                print("\nWhat do you want to do?")
                print("1. Fight next enemy")
                print("2. View attributes")
                print("3. View all items")
                print("4. Quit game")
                
                choice = input("> ")
                
                if choice == "1":
                    self.start_combat()
                elif choice == "2":
                    self.clear_screen()
                    print(f"{self.player.name}'s Attributes:")
                    for attr, value in self.player.attributes.to_dict().items():
                        print(f"{attr}: {value}")
                    print("\nDerived Stats:")
                    print(f"Attack Power: {self.player.attributes.calculate_atkpw()}")
                    print(f"Attack Speed: {self.player.attributes.calculate_atksp()}")
                    print(f"Magic Power: {self.player.attributes.calculate_mgcpw()}")
                    print(f"Block: {self.player.attributes.calculate_block()}")
                    print(f"Dodge: {self.player.attributes.calculate_dodge()}")
                    print(f"Armor: {self.player.attributes.calculate_armor()}")
                    print(f"Magic Resistance: {self.player.attributes.calculate_mgcrs()}")
                    print(f"Critical Hit: {self.player.attributes.calculate_crits()}")
                    input("\nPress Enter to continue...")
                elif choice == "3":
                    self.clear_screen()
                    print("Available Items:")
                    for id, item in sorted(self.items.items()):
                        print(f"{id}. {item}")
                    input("\nPress Enter to continue...")
                elif choice == "4":
                    running = False
                    self.save_leaderboard()
                    print("Thanks for playing!")
                else:
                    print("Invalid choice!")
            else:
                # Combat mode
                current_time = time.time()
                delta_time = current_time - self.last_time
                self.last_time = current_time
                
                # Process combat simulation
                combat_ended, message = self.simulate_combat(delta_time)
                
                if combat_ended:
                    print(message)
                    if self.current_enemy.is_dead() and not self.player.is_dead():
                        # Roll for loot
                        loot = self.roll_loot()
                        if loot:
                            success, msg = self.player.equip_item(loot)
                            print(msg)
                    input("Press Enter to continue...")
                    continue
                
                # Draw the current state
                self.clear_screen()
                print(self.draw_combat_hud())
                print(self.draw_combat_log())
                print(self.draw_controls())
                
                # Get player input (non-blocking if possible)
                if self.input_buffer:
                    input_key = self.input_buffer
                    self.input_buffer = None
                    print(self.handle_input(input_key.upper()))
                
                if not hasattr(self, 'input_thread') or not self.input_thread.is_alive():
                    try:
                        import msvcrt  # Windows
                        if msvcrt.kbhit():
                            key = msvcrt.getch().decode('utf-8').upper()
                            if key == 'Q':
                                self.combat_active = False
                                print("Combat aborted!")
                                input("Press Enter to continue...")
                            elif key in ['A', 'S', 'D', 'Z', 'X', 'C']:
                                print(self.handle_input(key))
                    except ImportError:
                        # For non-Windows systems, use a simpler approach
                        import select
                        
                        def input_with_timeout(timeout):
                            """Input with timeout for Unix systems"""
                            ready, _, _ = select.select([sys.stdin], [], [], timeout)
                            if ready:
                                return sys.stdin.readline().rstrip('\n')
                            return None
                        
                        key = input_with_timeout(0.1)
                        if key:
                            if key.upper() == 'Q':
                                self.combat_active = False
                                print("Combat aborted!")
                                input("Press Enter to continue...")
                            elif key.upper() in ['A', 'S', 'D', 'Z', 'X', 'C']:
                                print(self.handle_input(key.upper()))
                
                time.sleep(REFRESH_RATE)
    
    def save_leaderboard(self):
        """Save player stats to the leaderboard"""
        leaderboard_file = "pyRL_leaderboard.csv"
        
        # Check if file exists and create it with headers if not
        file_exists = os.path.isfile(leaderboard_file)
        
        with open(leaderboard_file, 'a', newline='') as f:
            writer = csv.writer(f)
            
            if not file_exists:
                headers = ["timestamp", "toon_name", "level", "kills", "damage_done", "damage_received"]
                for slot in range(1, 9):
                    headers.append(f"item{slot}")
                
                # Add all attributes
                for attr in sorted(self.player.attributes.to_dict().keys()):
                    headers.append(attr)
                
                writer.writerow(headers)
            
            # Create row with player data
            row = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                self.player.name,
                self.player.level,
                self.player.kills,
                self.player.damage_done,
                self.player.damage_received
            ]
            
            # Add equipment
            for slot in range(1, 9):
                item = self.player.equipment.get(slot)
                row.append(item.name if item else "None")
            
            # Add all attributes
            for attr, value in sorted(self.player.attributes.to_dict().items()):
                row.append(value)
            
            writer.writerow(row)


def main():
    """Main entry point for the game"""
    game = Game()
    game.initialize_game_data()
    
    try:
        game.main_loop()
    except KeyboardInterrupt:
        print("\nGame terminated by user.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Save player data if it exists
        if game.player:
            game.save_leaderboard()


if __name__ == "__main__":
    main()