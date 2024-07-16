import random
import time
import csv

import os
os.chdir('C:/Users/madma/Documents/zDrugMaker/pyXenes')

# Initialize lists for fighter attributes
L_name, L_surname, L_stm, L_end, L_blk, L_str, L_mvt, L_dge, L_kck, L_pun, L_nat, L_stt = ([] for _ in range(12))
L_pts = [0] * 20

# Initialize global variables for the contenders
con1_n = con2_n = ''
con1_hp = con2_hp = con1_crit = con2_crit = con1_tired = con2_tired = 0
con1_block = con2_block = con1_power = con2_power = con1_turn_decay = con2_turn_decay = 0
con1_dodge = con2_dodge = con1_score = con2_score = 0

# Read the CSV file and populate the lists
with open('fighters.csv') as csvfile:
    readCSV = csv.reader(csvfile, delimiter=',')
    next(readCSV)  # Skip header row
    for row in readCSV:
        L_name.append(row[0])
        L_surname.append(row[1])
        L_stm.append(int(row[2]))
        L_end.append(int(row[3]))
        L_blk.append(int(row[4]))
        L_str.append(int(row[5]))
        L_mvt.append(int(row[6]))
        L_dge.append(int(row[7]))
        L_kck.append(int(row[8]))
        L_pun.append(int(row[9]))
        L_nat.append(row[10])
        L_stt.append(row[11])

# Create and shuffle fight schedules
schedules = [list(range(20)) for _ in range(20)]
for schedule in schedules:
    schedule.remove(schedules.index(schedule))
    random.shuffle(schedule)

def pick_fight(contender1, contender2):
    global con1_n, con1_hp, con1_crit, con1_tired, con1_block, con1_power, con1_turn_decay, con1_dodge, con1_score
    global con2_n, con2_hp, con2_crit, con2_tired, con2_block, con2_power, con2_turn_decay, con2_dodge, con2_score
    
    con1_n = f"{L_name[contender1]} {L_surname[contender1]}"
    con2_n = f"{L_name[contender2]} {L_surname[contender2]}"
    
    for i, (c1, c2) in enumerate(zip([con1_n, con1_hp, con1_crit, con1_tired, con1_block, con1_power, con1_turn_decay, con1_dodge, con1_score],
                                     [con2_n, con2_hp, con2_crit, con2_tired, con2_block, con2_power, con2_turn_decay, con2_dodge, con2_score])):
        if i == 0: continue
        c1 = c2 = 0
    
    for i, contender in enumerate([contender1, contender2]):
        hp = 100 + 5 * L_end[contender]
        crit = 2 * (L_kck[contender] + L_pun[contender])
        tired = 10 * L_stm[contender] + 100
        block = 3 * L_blk[contender]
        power = L_str[contender] + random.randint(1, 4) + (tired // 20)
        turn_decay = L_mvt[contender] / 2
        dodge = 3 * L_mvt[contender]
        score = sum([L_stm[contender], L_end[contender], L_kck[contender], L_pun[contender], L_blk[contender], L_str[contender], L_mvt[contender]])
        
        if i == 0:
            con1_hp, con1_crit, con1_tired, con1_block, con1_power, con1_turn_decay, con1_dodge, con1_score = hp, crit, tired, block, power, turn_decay, dodge, score
        else:
            con2_hp, con2_crit, con2_tired, con2_block, con2_power, con2_turn_decay, con2_dodge, con2_score = hp, crit, tired, block, power, turn_decay, dodge, score

def fight():
    global con1_hp, con1_tired, con1_turn_decay, con1_power
    global con2_hp, con2_tired, con2_turn_decay, con2_power
    
    print(f"\n{con1_n} vs {con2_n}")
    print(f"{con1_n}: HP {con1_hp}, Power {con1_power:.2f}")
    print(f"{con2_n}: HP {con2_hp}, Power {con2_power:.2f}")
    
    fight_zeros1 = 100 - con1_dodge - con1_block 
    fight_zeros2 = 100 - con2_dodge - con2_block
    fight_blockdodge1 = [0] * fight_zeros1 + [1] * con1_block + [2] * con1_dodge
    fight_blockdodge2 = [0] * fight_zeros2 + [1] * con2_block + [2] * con2_dodge

    round_count = 0
    while True:
        round_count += 1
        print(f"\nRound {round_count}")
        
        for attacker, defender, blockdodge in [(1, 2, fight_blockdodge2), (2, 1, fight_blockdodge1)]:
            action = random.choice(["punch", "kick", "move"])
            defense = random.choice(blockdodge)
            
            attacker_vars = [con1_power, con1_tired, con1_turn_decay] if attacker == 1 else [con2_power, con2_tired, con2_turn_decay]
            defender_vars = [con2_hp] if defender == 2 else [con1_hp]
            
            if action in ["punch", "kick"] and defense == 0:
                damage = attacker_vars[0]
                defender_vars[0] -= damage
                print(f"{'Con1' if attacker == 1 else 'Con2'} {action}es for {damage:.2f} damage!")
            elif action in ["punch", "kick"] and defense == 1:
                print(f"{'Con1' if attacker == 1 else 'Con2'} {action}es, but it was blocked!")
            elif action in ["punch", "kick"] and defense == 2:
                print(f"{'Con1' if attacker == 1 else 'Con2'} {action}es, but it was dodged!")
            else:
                print(f"{'Con1' if attacker == 1 else 'Con2'} moves.")
            
            attacker_vars[1] -= attacker_vars[2]
            attacker_vars[0] -= attacker_vars[2] / 20
            
            if attacker == 1:
                con1_power, con1_tired, con1_turn_decay = attacker_vars
                con2_hp = defender_vars[0]
            else:
                con2_power, con2_tired, con2_turn_decay = attacker_vars
                con1_hp = defender_vars[0]
        
        print(f"{con1_n}: HP {con1_hp:.2f}, Power {con1_power:.2f}")
        print(f"{con2_n}: HP {con2_hp:.2f}, Power {con2_power:.2f}")
        
        if con1_hp <= 0:
            print(f"\n{con2_n} wins!")
            return 2
        if con2_hp <= 0:
            print(f"\n{con1_n} wins!")
            return 1
        
        time.sleep(0.01)  # Pause for 1 second between rounds

# Main tournament loop
for i, schedule in enumerate(schedules):
    print(f"\nFighter {i} ({L_name[i]} {L_surname[i]}) fights:")
    for opponent in schedule:
        pick_fight(i, opponent)
        winner = fight()
        if winner == 1:
            L_pts[i] += 1
        elif winner == 2:
            L_pts[opponent] += 1

print("\nTournament Results:")
for i in range(len(L_pts)):
    print(f'{L_name[i]} {L_surname[i]} - {L_pts[i]} pts')