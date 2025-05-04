# pyRL_engine.py – standard‑library ASCII combat prototype (refactored)
# ------------------------------------------------------------------------
# Key fixes applied:
#   • Safe CSV loading (None‑guard)
#   • Bar overflow retained
#   • Probabilities clamped (crit, dodge)
#   • Mitigation lower‑bound 0 %
#   • HP never < 0 when shown
#   • HUD shows key→action map
#   • None‑safe keyboard handling (k may be None)
# ------------------------------------------------------------------------

import csv
import os
import sys
import time
from collections import deque
from typing import Dict, List, Optional
import random

###############################################################
# Convenience utilities
###############################################################

def clear_screen() -> None:
    if sys.stdout.isatty():
        # ANSI clear to reduce flicker; fallback to os.system for dumb terms
        print("\x1b[2J\x1b[H", end="")
    else:
        os.system("cls" if os.name == "nt" else "clear")

# ── Non‑blocking keyboard ────────────────────────────────────
if os.name == "nt":
    import msvcrt  # type: ignore

    def get_key() -> Optional[str]:
        if msvcrt.kbhit():
            key = msvcrt.getch()
            try:
                return key.decode().upper()
            except UnicodeDecodeError:
                return None
        return None
else:
    import termios  # type: ignore
    import tty  # type: ignore
    import select  # type: ignore

    _orig_tty_attrs = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())

    def get_key() -> Optional[str]:
        dr, _, _ = select.select([sys.stdin], [], [], 0)
        if dr:
            return sys.stdin.read(1).upper()
        return None

###############################################################
# CSV helpers (lenient to BOM, spaces, header‑case)
###############################################################

DATA_PATH = os.path.dirname(__file__)


def load_csv(p: str) -> List[Dict[str, str]]:
    """Load a CSV, stripping a UTF‑8 BOM and whitespace; returns list[dict]."""
    with open(p, newline="", encoding="utf-8-sig") as f:
        rdr = csv.DictReader(f)
        rows: List[Dict[str, str]] = []
        for row in rdr:
            clean = {}
            for k, v in row.items():
                k = k.strip()
                clean[k] = v.strip() if v is not None else ""
            rows.append(clean)
        return rows


def find_key(row_like: Dict[str, str], *candidates: str) -> Optional[str]:
    wants = {c.lower() for c in candidates}
    for k in row_like:
        if k.lower() in wants:
            return k
    return None

###############################################################
# Global data tables – tolerate header variants
###############################################################

items_rows = load_csv(os.path.join(DATA_PATH, "pyRL_items.csv"))
action_rows = load_csv(os.path.join(DATA_PATH, "pyRL_actions.csv"))
if not items_rows:
    raise RuntimeError("pyRL_items.csv appears empty")
if not action_rows:
    raise RuntimeError("pyRL_actions.csv appears empty")

item_id_key = find_key(items_rows[0], "ItemID", "ID", "item_id")
action_id_key = find_key(action_rows[0], "ActionID", "ID", "action_id")
if item_id_key is None:
    raise KeyError("No ItemID‑like column in pyRL_items.csv")
if action_id_key is None:
    raise KeyError("No ActionID‑like column in pyRL_actions.csv")

items_data: Dict[str, Dict[str, str]] = {row[item_id_key]: row for row in items_rows}
actions_data: Dict[str, Dict[str, str]] = {row[action_id_key]: row for row in action_rows}

###############################################################
# Character loading / saving (robust to header variants)
###############################################################

def load_characters(filename: str) -> Dict[str, Dict[str, str]]:
    rows = load_csv(os.path.join(DATA_PATH, filename))
    if not rows:
        raise RuntimeError(f"{filename} is empty")
    key_name = find_key(rows[0], "ID", "SaveID", "ToonID", "CharacterID") or find_key(rows[0], "Name") or list(rows[0].keys())[0]
    chars: Dict[str, Dict[str, str]] = {}
    for i, row in enumerate(rows):
        key = row.get(key_name) or f"ROW{i}"
        while key in chars:
            key += "_dup"
        chars[key] = row
    return chars


def save_characters(filename: str, characters: Dict[str, Dict[str, str]]) -> None:
    if not characters:
        return
    fieldnames = list(next(iter(characters.values())).keys())
    with open(os.path.join(DATA_PATH, filename), "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=fieldnames)
        wr.writeheader()
        for row in characters.values():
            wr.writerow({h: row.get(h, "") for h in fieldnames})

###############################################################
# Domain constants & classes
###############################################################

ATTR_ORDER = [
    "STA", "STR", "AGI", "DEX", "HIT", "BAL", "WGT", "HEI",
    "INT", "WIL", "FOR", "FOC", "PSY",
    "ARC", "BLS", "MAN", "ALC",
    "CUR", "COR", "SUM", "HEX",
]

STAT_ATTR_MAP = {
    "AtkPw": ["STR", "STR", "AGI", "DEX", "BAL"],
    "AtkSp": ["AGI", "AGI", "DEX", "WIL", "FOC"],
    "MgcPw": ["INT", "INT", "MAN", "ARC", "WIL"],
    "Block": ["STR", "FOR", "INT", "BAL", "WIL"],
    "Dodge": ["FOC", "AGI", "DEX", "BAL", "PSY"],
    "Armor": ["STR", "FOR", "STA", "AGI", "BLS"],
    "MgcRs": ["PSY", "BLS", "WIL", "MAN", "FOR"],
    "Crits": ["HIT", "HIT", "HIT", "ARC", "FOC"],
}

DEFAULT_KEYS = {"A": "1", "S": "2", "Z": None, "X": None, "D": None, "C": None}


class Item:
    def __init__(self, row: Dict[str, str]):
        self.id = row[item_id_key]
        self.slot = int(row.get("Slot", "0"))
        self.name = row.get("Name", f"Item{self.id}")
        self.bonuses = []
        for key in ("Bonus1", "Bonus2"):
            txt = row.get(key, "")
            if ":" in txt:
                attr, val = txt.split(":", 1)
                self.bonuses.append((attr.strip(), int(val)))
        self.action_id = row.get("ActionID") or None
        self.type = row.get("Type", "melee")
        self.check_attr = row.get("GearCheck")
        self.check_amt = int(row.get("GearCheckAmount", "0") or 0)

    def apply_bonuses(self, attrs: Dict[str, int]):
        for attr, val in self.bonuses:
            attrs[attr] = attrs.get(attr, 0) + val


class Action:
    def __init__(self, row: Dict[str, str]):
        self.id = row[action_id_key]
        self.name = row.get("Name", f"Action{self.id}")
        self.base_dmg = float(row.get("BaseDmg", "5"))
        self.kind = row.get("Type", "melee").lower()  # melee or magic


class Character:
    def __init__(self, row: Dict[str, str], player: bool = False):
        self.raw_row = row
        self.id = row.get("ID") or row.get("Name")
        self.name = row.get("Name", self.id)
        self.is_player = player

        # base attributes
        self.attrs: Dict[str, int] = {a: int(row.get(a, "0") or 0) for a in ATTR_ORDER}
        # equipment
        self.items: Dict[int, Item] = {}
        for slot in range(1, 9):
            iid = row.get(f"Item{slot}")
            if iid and iid in items_data:
                itm = Item(items_data[iid])
                self.items[slot] = itm
                itm.apply_bonuses(self.attrs)
        self.compute_stats()
        self.hp = self.max_hp
        self.attack_bar = 0.0
        self.input_key = "A"
        self.log = deque(maxlen=10)

    def compute_stats(self):
        self.max_hp = 50 + (5 * self.attrs["STA"]) + (2 * self.attrs["STR"]) + (2 * self.attrs["WIL"]) + self.attrs["FOR"] + self.attrs["FOC"] + self.attrs["BLS"]
        self.stats = {s: sum(self.attrs[a] for a in alist) for s, alist in STAT_ATTR_MAP.items()}

    def keys_map(self):
        mapping = DEFAULT_KEYS.copy()
        slots_to_keys = {6: "Z", 5: "X", 7: "D", 8: "C"}
        for slot, key in slots_to_keys.items():
            itm = self.items.get(slot)
            if itm and itm.action_id:
                mapping[key] = itm.action_id
        return mapping

    # bar‑fill per second
    def fill_rate(self) -> float:
        atksp = max(0, min(self.stats["AtkSp"], 100))  # clamp 0‑100
        t_full = max(0.5, 1.2 + (5.0 - 1.2) * (1 - atksp / 100.0))
        return 100.0 / t_full

###############################################################
# Combat helpers
###############################################################

def do_damage(att: "Character", defn: "Character", act: "Action"):
    if act.kind == "melee":
        base = att.stats["AtkPw"]
        mitigate_stat = defn.stats["Block"]
    else:
        base = att.stats["MgcPw"]
        mitigate_stat = defn.stats["MgcRs"]

    # dodge (max 90 %)
    dodge_p = min(max(defn.stats["Dodge"] / 1000, 0.0), 0.9)
    if random.random() < dodge_p:
        return 0, "dodged"

    dmg = base + act.base_dmg
    # crit (max 95 %)
    crit_p = min(att.stats["Crits"] / 300, 0.95)
    if random.random() < crit_p:
        dmg *= 2
        kind = "crit"
    else:
        kind = "hit"

    # mitigation 0–stat %
    mit = random.uniform(0, max(mitigate_stat, 0)) / 100.0
    final = max(1, int(dmg * (1 - mit)))
    return final, kind

###############################################################
# Engine class
###############################################################

class CombatEngine:
    REFRESH = 0.1

    def __init__(self, player: Character, enemy: Character):
        self.player = player
        self.enemy = enemy
        self.p_keys = player.keys_map()
        seq_txt = enemy.raw_row.get("Sequence", "1,1,1,1,1,1,1,1,1")
        self.e_seq = [s.strip() for s in seq_txt.split(",") if s.strip()]
        self.e_idx = 0
        self.running = True

    # --------------------------------------------------------
    def render(self):
        clear_screen()
        for ent in (self.player, self.enemy):
            bar_blocks = 20
            filled = int(ent.attack_bar / 5)
            bar = "█" * filled + " " * (bar_blocks - filled)
            hp_txt = f"{ent.hp}/{ent.max_hp}"
            print(f"[{ent.name}] HP {hp_txt:<9} BAR [{bar}] {int(ent.attack_bar)}%  Queued:{ent.input_key}")
            print(
                f"AtkPw {ent.stats['AtkPw']:<3} AtkSp {ent.stats['AtkSp']:<3} MgcPw {ent.stats['MgcPw']:<3} "
                f"Block {ent.stats['Block']:<3} Dodge {ent.stats['Dodge']:<3} Armor {ent.stats['Armor']:<3} "
                f"MgcRs {ent.stats['MgcRs']:<3} Crits {ent.stats['Crits']:<3}"
            )
            if ent.is_player:
                legend = " ".join(f"{k}={self.action_name(v)}" for k, v in self.p_keys.items() if v)
                print("Keys:", legend)
            print()
        print("--- Log ---")
        for line in self.player.log:
            print(line)
        print("\n[A,S,Z,X,D,C] choose action – Q quits")

    def action_name(self, act_id: str) -> str:
        row = actions_data.get(act_id)
        return row.get("Name", act_id) if row else act_id

    # --------------------------------------------------------
    def update_entity(self, ent: Character, opp: Character, dt: float, is_player: bool):
        ent.attack_bar += ent.fill_rate() * dt
        while ent.attack_bar >= 100:
            ent.attack_bar -= 100
            act_id = (
                self.p_keys.get(ent.input_key, "1") if is_player else self.e_seq[self.e_idx % len(self.e_seq)]
            )
            if not is_player:
                self.e_idx += 1
            act_row = actions_data.get(act_id)
            if not act_row:
                ent.log.appendleft(f"{ent.name} tried unknown action {act_id}")
                continue
            action = Action(act_row)
            dmg, kind = do_damage(ent, opp, action)
            opp.hp = max(0, opp.hp - dmg)
            msg = f"{ent.name}->{opp.name} {action.name} {kind} {dmg} dmg (HP {opp.hp})"
            ent.log.appendleft(msg)
            opp.log.appendleft(msg)
            if opp.hp == 0:
                break

    # --------------------------------------------------------
    def loop(self):
        last = time.time()
        while self.running and self.player.hp > 0 and self.enemy.hp > 0:
            now = time.time()
            dt = now - last
            last = now
            # input
            k = get_key()
            if k == "Q":
                break
            # only test membership if k is a string
            if k and k in "ASZXDC":
                self.player.input_key = k
            # update
            self.update_entity(self.player, self.enemy, dt, True)
            self.update_entity(self.enemy, self.player, dt, False)
            # draw
            self.render()
            time.sleep(self.REFRESH)
        self.render()
        print("\n>>", "Victory!" if self.enemy.hp <= 0 else "Defeat or Quit.")

###############################################################
# Menu helpers
###############################################################

def choose(rows: Dict[str, Dict[str, str]], title: str) -> Dict[str, str]:
    ids = list(rows.keys())
    while True:
        clear_screen()
        print(title)
        for i, cid in enumerate(ids, 1):
            nm = rows[cid].get("Name", cid)
            print(f"{i}. {nm} (ID {cid})")
        pick = input("Choose number >> ")
        if pick.isdigit():
            idx = int(pick) - 1
            if 0 <= idx < len(ids):
                return rows[ids[idx]]
        input("Invalid. Press enter to retry..")

###############################################################
# Main entry
###############################################################

def main():
    choice = ""
    while choice not in ("1", "2"):
        clear_screen()
        choice = input("Select character list:\n1) Default characters\n2) Saved characters\n> ")
    char_file = "pyRL_toons.csv" if choice == "1" else "pyRL_saved.csv"
    chars = load_characters(char_file)
    player_row = choose(chars, "Pick your hero")
    player = Character(player_row, player=True)
    npc_row = choose(load_characters("pyRL_npcs.csv"), "Pick opponent")
    enemy = Character(npc_row)

    CombatEngine(player, enemy).loop()

    if player.hp > 0 and char_file == "pyRL_saved.csv":
        chars[player_row.get("ID", list(chars.keys())[0])] = player_row  # TODO: persist updated stats
        save_characters(char_file, chars)

    print("\nThanks for playing!")
    if os.name != "nt":
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, _orig_tty_attrs)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        if os.name != "nt":
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, _orig_tty_attrs)
        print("\nExiting..")
