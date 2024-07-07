import random
import csv

def load_fighters(file_path):
    fighters = []
    with open(file_path) as csvfile:
        readCSV = csv.reader(csvfile, delimiter=',')
        for row in readCSV:
            fighter = {
                'name': row[0],
                'surname': row[1],
                'stm': int(row[2]),
                'end': int(row[3]),
                'blk': int(row[4]),
                'str': int(row[5]),
                'mvt': int(row[6]),
                'dge': int(row[7]),
                'kck': int(row[8]),
                'pun': int(row[9]),
                'nat': row[10],
                'stt': int(row[11]),
                'pts': 0
            }
            fighters.append(fighter)
    return fighters

def shuffle_schedules(num_fighters):
    schedules = []
    for i in range(num_fighters):
        schedule = list(range(num_fighters))
        schedule.remove(i)
        random.shuffle(schedule)
        schedules.append(schedule)
    return schedules

def assign_fighter_stats(fighter):
    stats = {
        'hp': 100 + 5 * fighter['end'],
        'crit': 2 * (fighter['kck'] + fighter['pun']),
        'tired': 10 * fighter['stm'] + 100,
        'block': 3 * fighter['blk'],
        'power': fighter['str'] + random.randint(1, 4) + (10 * fighter['stm'] / 20),
        'turn_decay': fighter['mvt'] / 2,
        'dodge': 3 * fighter['mvt'],
        'score': sum([fighter['stm'], fighter['end'], fighter['kck'], fighter['pun'], fighter['blk'], fighter['str'], fighter['mvt']]),
        'status': fighter['stt']
    }
    return stats

def fight(fighter1, fighter2):
    f1_stats = assign_fighter_stats(fighter1)
    f2_stats = assign_fighter_stats(fighter2)

    fight_blockdodge1 = [0] * (100 - f1_stats['dodge'] - f1_stats['block']) + [1] * f1_stats['block'] + [2] * f1_stats['dodge']
    fight_blockdodge2 = [0] * (100 - f2_stats['dodge'] - f2_stats['block']) + [1] * f2_stats['block'] + [2] * f2_stats['dodge']

    con_status = f1_stats['status'] + f2_stats['status']

    turncount = 0
    while f1_stats['hp'] > 0 and f2_stats['hp'] > 0:
        turncount += 1
        print(f'======>>> turn# {turncount}')
        
        fight_rand = random.randint(1, 3)
        fight_rand3 = random.choice(fight_blockdodge1)
        fight_rand4 = random.choice(fight_blockdodge2)

        if fight_rand == 1:
            if con_status > 0: print(f'{fighter1["name"]} throws a punch at {fighter2["name"]}')
            if fight_rand4 == 0:
                if con_status > 0: print(f'The punch successfully lands on {fighter2["name"]} ... POW !!!')
                f2_stats['hp'] -= f1_stats['power']
            elif fight_rand4 == 1:
                if con_status > 0: print(f'{fighter2["name"]} manages to block the strike from {fighter1["name"]}... BLOCKED !')
            elif fight_rand4 == 2:
                if con_status > 0: print(f'{fighter2["name"]} swiftly moves away from {fighter1["name"]}\'s strike ... DODGED !')
        
        elif fight_rand == 2:
            if con_status > 0: print(f'{fighter1["name"]} kicks {fighter2["name"]}')
            if fight_rand4 == 0:
                if con_status > 0: print(f'{fighter2["name"]} takes a direct kick from {fighter1["name"]} ... POOM !!!')
                f2_stats['hp'] -= f1_stats['power']
            elif fight_rand4 == 1:
                if con_status > 0: print(f'Confidently, {fighter2["name"]} blocks the kick ... BLOCKED !')
            elif fight_rand4 == 2:
                if con_status > 0: print(f'{fighter2["name"]} quickly evades {fighter1["name"]}\'s kick ... DODGED !')
        
        elif fight_rand == 3:
            if con_status > 0: print(f'{fighter1["name"]} looks like he\'s getting into an offensive position \nInstead keeps moving to keep {fighter2["name"]} guessing what\'s coming next')
            if fight_rand4 == 0:
                if con_status > 0: print(f'{fighter2["name"]} analyses {fighter1["name"]}\'s movement and gets ready to strike')
            elif fight_rand4 == 1:
                if con_status > 0: print(f'{fighter2["name"]} monitors {fighter1["name"]} carefully')
            elif fight_rand4 == 2:
                if con_status > 0: print(f'{fighter2["name"]} is a calculating fighter and is likely waiting to find {fighter1["name"]} in a more vulnerable position')
        
        f1_stats['tired'] -= f1_stats['turn_decay']
        f1_stats['power'] -= f1_stats['turn_decay'] / 20
        f2_stats['tired'] -= f2_stats['turn_decay']
        f2_stats['power'] -= f2_stats['turn_decay'] / 20
        print(f'con1_hp = {f1_stats["hp"]} \ncon2_hp = {f2_stats["hp"]} \ncon1_tired = {f1_stats["tired"]} \ncon2_tired = {f2_stats["tired"]} \ncon1_power = {f1_stats["power"]} \ncon2_power = {f2_stats["power"]}')

        if f1_stats['hp'] <= 0:
            print(f'{fighter1["name"]} falls down to the ground and the fight is over !!!\n {fighter2["name"]} is the winner')
            return 2
        if f2_stats['hp'] <= 0:
            print(f'{fighter2["name"]} falls down to the ground and the fight is over !!!\n {fighter1["name"]} is the winner')
            return 1

        if turncount % 10 == 0:
            round_end_message = f'This is the end of round {turncount // 10}'
            print(round_end_message)
            if f1_stats['hp'] > f2_stats['hp']:
                print(f'\n{fighter1["name"]} looked like the better of the two so far, let us see what {fighter2["name"]} can bring in the next round. He still has a lot of fighting in him.\n')
            else:
                print(f'\n{fighter2["name"]} looked like the better of the two so far, let us see what {fighter1["name"]} can bring in the next round. He still has a lot of fighting in him.\n')
            input('Press ENTER to continue...\n\n')

def main():
    fighters = load_fighters('luta_toons.csv')
    schedules = shuffle_schedules(len(fighters))

    print("\n================================================================================")
    print("     LBS Ascii Lutador v0.0.6")
    print("================================================================================\n\n")

    print('\n\nWelcome to Ascii Lutador. This is a simulator created by lbs which attempts to model a small mixed style fighting tournament. Contenders are randomly generated and fights will be crudely simulated. \n\n')

    print('xxxxxxxxxxxxxxxxxxxxxxxxx\n')
    print('Their attributes will be\n')
    print('STM - Stamina dictates how long the fighter can handle fighting')
    print('END - Endurance is proportional to HP pool')
    print('BLK - Blocking affects how often the fighter blocks an attack')
    print('STR - Strength affects how much power is dealt with each attack')
    print('MVT - Movement increases how much the fighter moves during match, which helps defensively')
    print('DGE - Dodge rating relates to how well the fighter avoids a hit')
    print('KCK - Kicking relates to the chance of successfully dealing a kick')
    print('PUN - Punching relates to the chance of successfully dealing a punch')
    print('\n')
    input('Press ENTER to continue...\n\n')

    print('Name            /stam/end/block/str/mvt/dge/kck/pun')
    for i, fighter in enumerate(fighters):
        print(f'Fighter #{i + 1} ==>')
        print(f'{fighter["name"]} {fighter["surname"]} - {fighter["nat"]}\n      {fighter["stm"]}  /  {fighter["end"]}  /  {fighter["blk"]}  /  {fighter["str"]}  /  {fighter["mvt"]}  /  {fighter["dge"]}  /  {fighter["kck"]}  /  {fighter["pun"]}\n')

    while any(schedules):
        for i, schedule in enumerate(schedules):
            if not schedule:
                continue
            opponent = schedule.pop()
            winner = fight(fighters[i], fighters[opponent])
            if winner == 1:
                fighters[i]['pts'] += 1
            elif winner == 2:
                fighters[opponent]['pts'] += 1

    print('Final Points:')
    for fighter in fighters:
        print(f'{fighter["name"]} {fighter["surname"]} - {fighter["pts"]} pts')

if __name__ == '__main__':
    main()
