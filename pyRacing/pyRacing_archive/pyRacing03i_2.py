#version 3b fixed the simulation a bit. some minor tweaks to prevent cars from halting.
#version 3c added more to the reporting of the race.
#version 3d Added new attributes + load driver attributes + fixed reporting position to txt
#version 3e+3f overtaking + 3f colour
#version 3g events
#version 3h performance pop up box + added 4 car comparissons)
#version 3h performance pop up box
#version 3h performance pop up box + added 4 car comparissons) - !!! dis implemented !!!!!  Maybe introduce later... I saved Claude prompt on EV
#version 3i Stamina (03i_1 version was not used ... 10 lap with more output... there is a season tested with this version.)
#v03i_0_1 - added pit stops + made cars a bit faster + pit stops
#v3i_2 - fixed pit stops and some issues with 0_1

import os
import time
import random
import csv
from datetime import datetime

# ANSI color codes
class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'

class Car:
    def __init__(self, first_name, last_name, symbol, cc_maxSpd, cc_accel, cc_dragC, cc_downC, cc_cornr, cc_ovrtk, cc_const, cc_defnd, cc_stam):
        self.first_name = first_name
        self.last_name = last_name
        self.symbol = symbol
        # Car characteristics
        self.cc_maxSpd = cc_maxSpd
        self.cc_accel = cc_accel
        self.cc_dragC = cc_dragC
        self.cc_downC = cc_downC
        self.cc_cornr = cc_cornr
        self.cc_ovrtk = cc_ovrtk
        self.cc_const = cc_const
        self.cc_defnd = cc_defnd
        self.cc_stam = cc_stam
        # Race progress attributes
        self.distance = 0
        self.speed = 0
        self.laps_completed = 0
        self.lap_times = []
        self.best_lap_time = float('inf')
        self.current_lap_start_time = 0
        self.finished = False
        self.total_race_time = float('inf')
        self.finish_position = 0
        # Overtaking attributes
        self.overtake_boost = 0
        self.overtake_penalty = 0
        self.overtake_cooldown = 0
        # New attributes for random events and pits
        self.current_event = None
        self.event_duration = 0
        self.event_effect = 0
        self.stamina_pool = 100  # Start with 100% stamina
        self.distance_since_last_stamina_decrease = 0
        self.in_pit = False
        self.pit_cycles = 0

    def update_stamina(self, distance_moved):
        self.distance_since_last_stamina_decrease += distance_moved
        if self.distance_since_last_stamina_decrease >= 3000:  # changed from 200 track segments * 20 meters per segment = 4000 for 10 stam
            self.stamina_pool = max(0, self.stamina_pool - 5)
            self.distance_since_last_stamina_decrease = 0

    def update_speed_turn(self):
        stamina_factor = self.stamina_pool / 100
        self.speed = self.speed * (0.5 + (self.cc_cornr / 200) * stamina_factor + (self.cc_downC / 2000))
        if self.speed < 50:
            self.speed = 50

    def update_speed_straight(self, random_factor):
        stamina_factor = self.stamina_pool / 100
        new_speed = (self.speed + 
                     0.2 * random_factor * (self.cc_downC + self.cc_dragC - self.cc_accel * stamina_factor) + 
                     (self.cc_accel * stamina_factor / 1.7) - 
                     self.speed * (1 - (self.cc_dragC / 500)) * (0.10 + 0.31 * ((self.speed**0.5 - 100) / 1500)) - 
                     self.speed * (self.cc_downC / 5000))
        self.speed = min(new_speed, self.cc_maxSpd)

        # Apply overtaking effects
        if self.overtake_boost > 0:
            self.speed += 20
            self.overtake_boost -= 1
        elif self.overtake_penalty > 0:
            self.speed -= 20
            self.overtake_penalty -= 1
            
            # Calculate additional stamina penalty based on cc_stam
            additional_penalty = 0.001 * (1 - self.cc_stam / 100)  # Up to 5% additional penalty
            total_penalty = 0.001 + additional_penalty  # 0.5% base penalty + additional penalty
            
            self.stamina_pool = max(0, self.stamina_pool - total_penalty * 100)  # Convert to percentage and deduct

    def check_for_random_event(self, is_turning):
        if self.current_event:
            self.event_duration -= 1
            if self.event_duration <= 0:
                self.current_event = None
                self.event_effect = 0
            return

        # Base probability for an event to occur (adjust as needed)
        base_prob = 0.005  # This gives roughly one event every 2-3 laps for 20 drivers
        
        # Modify probability based on consistency (lower consistency increases probability)
        event_prob = base_prob * (1 + (100 - self.cc_const) / 100)

        if random.random() < event_prob:
            self.trigger_random_event(is_turning)

    def trigger_random_event(self, is_turning):
        events = [
            ("Lock up", lambda: is_turning and random.random() < 0.01, -30, 5),
            ("Handling malfunction", lambda: random.random() < 0.02, -5, 40),
            ("Throttle malfunction", lambda: not is_turning and random.random() < 0.03, -40, 20),
            ("Electrical reset", lambda: self.speed > 300 and random.random() < 0.02, -150, 17),
            ("Fuel flow issue", lambda: self.speed < 150 and random.random() < 0.01, -5, 100),
            ("Inspired", lambda: random.random() < 0.05, 33, 15),
            (" --- GOD MODE !!!!!!!! --- ", lambda: 110 < self.speed < 124 and random.random() < 0.01, 69, 69)
        ]

        possible_events = [event for event in events if event[1]()]
        if possible_events:
            event = random.choice(possible_events)
            self.current_event = event[0]
            self.event_effect = event[2]
            self.event_duration = event[3]

    def check_for_pit_stop(self, track_length):
        if self.distance % track_length < 20 and self.stamina_pool < 50 and random.random() < 0.5:
            self.in_pit = True
            self.pit_cycles = random.randint(5, 10)

    def perform_pit_stop(self):
        if self.in_pit:
            self.pit_cycles -= 1
            if self.pit_cycles <= 0:
                self.stamina_pool = 100
                self.in_pit = False


    def move(self, track_sequence, track_length, time_step, current_time, num_laps, cars):
        if self.in_pit:
            self.perform_pit_stop()
        elif not self.finished:
            current_tile_index = int(self.distance / 20) % len(track_sequence)
            current_tile = track_sequence[current_tile_index]
            is_turning = current_tile == 'U'
        
            self.check_for_random_event(is_turning)

            if is_turning:
                self.update_speed_turn()
            else:
                self.update_speed_straight(random.uniform(0.8, 1.2))

            if self.current_event:
                self.speed += self.event_effect
        
            self.speed = max(0, self.speed)

            distance_moved = (self.speed * 1000 / 3600) * time_step
            self.distance += distance_moved
            
            self.update_stamina(distance_moved)
        
            self.check_overtaking(cars)

            if self.overtake_cooldown > 0:
                self.overtake_cooldown -= 1

            self.check_for_pit_stop(track_length)

            if self.distance >= track_length:
                self.laps_completed += 1
                self.distance %= track_length
        
                lap_time = current_time - self.current_lap_start_time
                if lap_time > 0:
                    self.lap_times.append(lap_time)
                    if lap_time < self.best_lap_time:
                        self.best_lap_time = lap_time
        
                self.current_lap_start_time = current_time
            
            if self.laps_completed >= num_laps:
                self.finished = True
                self.distance = self.laps_completed * track_length
                self.total_race_time = current_time

    def check_overtaking(self, cars):
        if self.overtake_cooldown > 0:
            return  # Cannot attempt overtaking during cooldown

        for other_car in cars:
            if other_car != self and not other_car.finished:
                distance_diff = abs(self.distance - other_car.distance)
                if distance_diff < 10:  # Cars are close enough for an overtaking attempt
                    # Calculate the probability of success based on the ratio of ovrtk and defnd
                    total_score = self.cc_ovrtk + other_car.cc_defnd
                    pass_chance = self.cc_ovrtk / total_score  # Overtaking car's chance of success

                    # Draw a random number between 0 and 1
                    if random.random() < pass_chance:
                        # Successful overtake
                        self.overtake_boost = 14  # Doubled from 7
                        self.overtake_penalty = 0  # Clear any penalty
                    else:
                        # Failed overtake
                        self.overtake_boost = 0  # No boost for failed overtakes
                        self.overtake_penalty = 20  # Doubled from 10

                    # Set cooldown
                    self.overtake_cooldown = 50
                    break  # Only attempt one overtake per move

def load_track_visual(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file.readlines()]

def load_track_sequence(file_path):
    with open(file_path, 'r') as file:
        return file.read().strip().split(',')

def render_race_progress(cars, track_length, display_width=80):
    os.system('cls' if os.name == 'nt' else 'clear')
    
    sorted_cars = sorted(cars, key=lambda car: (car.finished, car.laps_completed * track_length + car.distance), reverse=True)
    
    print(f"{Colors.CYAN}{'='*display_width}{Colors.RESET}")
    print(f"{Colors.YELLOW}{'RACE PROGRESS':^{display_width}}{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*display_width}{Colors.RESET}\n")
    
    for i, car in enumerate(sorted_cars, 1):
        progress = int((car.distance / track_length) * (display_width - 20))
        best_lap = f"{car.best_lap_time:.2f}s" if car.best_lap_time != float('inf') else "N/A"
        
        if car.finished:
            bounce_pos = int(time.time() * 5) % (display_width - 20)
            line = " " * bounce_pos + Colors.GREEN + car.symbol + Colors.RESET + " " * (display_width - 20 - bounce_pos - 1)
        else:
            line = Colors.YELLOW + "=" * progress + Colors.RESET + " " * (display_width - 20 - progress)
        
        status = ""
        if car.in_pit:
            status = Colors.MAGENTA + f"[PIT:{car.pit_cycles}]" + Colors.RESET
        elif car.overtake_boost > 0:
            status = Colors.CYAN + "[OVR]" + Colors.RESET
        elif car.overtake_penalty > 0:
            status = Colors.RED + "[BLK]" + Colors.RESET
        elif car.overtake_cooldown > 0:
            status = Colors.MAGENTA + f"[CD:{car.overtake_cooldown}]" + Colors.RESET
        elif car.current_event:
            status = Colors.BLUE + f"[{car.current_event[:3].upper()}]" + Colors.RESET
        
        stamina_color = Colors.GREEN if car.stamina_pool > 66 else Colors.YELLOW if car.stamina_pool > 33 else Colors.RED
        
        print(f"{Colors.WHITE}{i:2d}. {Colors.BLUE}{car.symbol} {Colors.WHITE}|{line}| L{car.laps_completed + 1:2d} {stamina_color}{car.stamina_pool:5.1f}%{Colors.RESET} {status:10s}")
    
    print(f"\n{Colors.CYAN}{'='*display_width}{Colors.RESET}")
    print(f"{Colors.YELLOW}{'DETAILED STATISTICS':^{display_width}}{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*display_width}{Colors.RESET}\n")
    
    print(f"{Colors.WHITE}{'Pos':>3} {'Car':^5} {'Driver':^20} {'Best Lap':^10} {'Speed':^10} {'Distance':^12}{Colors.RESET}")
    print(f"{Colors.WHITE}{'-'*3} {'-'*5} {'-'*20} {'-'*10} {'-'*10} {'-'*12}{Colors.RESET}")
    
    for i, car in enumerate(sorted_cars, 1):
        driver_name = f"{car.first_name[:1]}. {car.last_name[:8]}"
        best_lap = f"{car.best_lap_time:.2f}s" if car.best_lap_time != float('inf') else "N/A"
        print(f"{Colors.WHITE}{i:3d} {Colors.BLUE}{car.symbol:^5} {Colors.WHITE}{driver_name:20s} {best_lap:10s} {Colors.GREEN}{car.speed:10.2f} {Colors.YELLOW}{car.distance:12.2f}{Colors.RESET}")
    
    time.sleep(0.1)

def simulate_race(track_sequence, cars, num_laps, time_step=0.1):
    track_length = len(track_sequence) * 20
    start_time = time.time()
    
    for car in cars:
        car.current_lap_start_time = start_time
    
    finish_position = 1
    while any(not car.finished for car in cars):
        current_time = time.time() - start_time
        for car in cars:
            if not car.finished:
                car.move(track_sequence, track_length, time_step, current_time, num_laps, cars)
                if car.finished and car.finish_position == 0:
                    car.finish_position = finish_position
                    finish_position += 1
        
        render_race_progress(cars, track_length)

def write_race_results(cars, filename, track_length, track_name):
    sorted_cars = sorted(cars, key=lambda car: (car.finish_position if car.finished else float('inf'), car.total_race_time))
    
    with open(filename, 'w') as f:
        f.write("Race Results\n")
        f.write("============\n\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Track: {track_name}\n\n")
        f.write("Pos | Car | Driver                | Best Lap   | Total Time\n")
        f.write("----+-----+----------------------+------------+------------\n")
        
        for car in sorted_cars:
            best_lap = f"{car.best_lap_time:.2f} s" if car.best_lap_time != float('inf') else "N/A"
            total_time = f"{car.total_race_time:.2f} s" if car.finished else "DNF"
            driver_name = f"{car.first_name} {car.last_name}"
            f.write(f"{car.finish_position:3d} | {car.symbol:3s} | {driver_name:20s} | {best_lap:10s} | {total_time:10s}\n")

def load_drivers(file_path):
    cars = []
    with open(file_path, 'r') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            cars.append(Car(
                first_name=row[0],
                last_name=row[1],
                symbol=row[2],
                cc_maxSpd=int(row[3]),
                cc_accel=int(row[4]),
                cc_dragC=int(row[5]),
                cc_downC=int(row[6]),
                cc_cornr=int(row[7]),
                cc_ovrtk=int(row[8]),
                cc_const=int(row[9]),
                cc_defnd=int(row[10]),
                cc_stam=int(row[11])
            ))
    return cars

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))

    track_filename = input("Enter the visual track filename (e.g. 'track_1.csv'): ").strip()
    track_visual = load_track_visual(os.path.join(current_dir, track_filename))
    
    print("Track Layout:")
    for row in track_visual:
        print(row)
    print("\nPress Enter to start the race...")
    input()

    seq_filename = track_filename.replace('.csv', '_seq.csv')
    track_sequence = load_track_sequence(os.path.join(current_dir, seq_filename))

    track_length = len(track_sequence) * 20

    drivers_filename = 'drivers.csv'
    cars = load_drivers(os.path.join(current_dir, drivers_filename))

    simulate_race(track_sequence, cars, num_laps=8)  # Changed to 8 laps

    log_filename = f"race_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    write_race_results(cars, os.path.join(current_dir, log_filename), track_length, track_filename)
    print(f"\nRace results have been written to {log_filename}")

if __name__ == "__main__":
    main()