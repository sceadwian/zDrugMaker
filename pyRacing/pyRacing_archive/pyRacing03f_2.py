import os
import time
import random
import csv
from datetime import datetime

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

    def update_speed_turn(self):
        self.speed = self.speed * (0.4 + (self.cc_cornr / 200) + (self.cc_downC / 2000))
        if self.speed < 50:
            self.speed = 50

    def update_speed_straight(self, random_factor):
        new_speed = (self.speed + 
                     0.2 * random_factor * (self.cc_downC + self.cc_dragC - self.cc_accel) + 
                     (self.cc_accel / 2) - 
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

    def move(self, track_sequence, track_length, time_step, current_time, num_laps, cars):
        if not self.finished:
            current_tile_index = int(self.distance / 20) % len(track_sequence)
            current_tile = track_sequence[current_tile_index]
            is_turning = current_tile == 'U'
        
            if is_turning:
                self.update_speed_turn()
            else:
                self.update_speed_straight(random.uniform(0.8, 1.2))
        
            # Calculate distance moved in this time step
            distance_moved = (self.speed * 1000 / 3600) * time_step
            self.distance += distance_moved
        
            # Check for overtaking
            self.check_overtaking(cars)

            # Update overtaking cooldown
            if self.overtake_cooldown > 0:
                self.overtake_cooldown -= 1

            # Check if a lap is completed
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
                    self.overtake_cooldown = 30
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
    
    for i, car in enumerate(sorted_cars, 1):
        progress = int((car.distance / track_length) * display_width)
        best_lap = f"{car.best_lap_time:.2f} s" if car.best_lap_time != float('inf') else "N/A"
        
        if car.finished:
            bounce_pos = int(time.time() * 5) % display_width
            line = " " * bounce_pos + car.symbol + " " * (display_width - bounce_pos - 1)
        else:
            line = "=" * progress + " " * (display_width - progress)
        
        status = ""
        if car.overtake_boost > 0:
            status = " [OVERTAKING]"
        elif car.overtake_penalty > 0:
            status = " [BLOCKED]"
        elif car.overtake_cooldown > 0:
            status = f" [COOLDOWN: {car.overtake_cooldown}]"
        
        print(f"{i:2d}. {car.symbol} |{line}| Lap {car.laps_completed + 1} - Best Lap: {best_lap}{status}")
    
    print("\nCar Details:")
    for i, car in enumerate(sorted_cars, 1):
        print(f"{i:2d}. {car.symbol}: Distance: {car.distance:.2f} m, Speed: {car.speed:.2f} km/h")
    
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

    simulate_race(track_sequence, cars, num_laps=5)

    log_filename = f"race_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    write_race_results(cars, os.path.join(current_dir, log_filename), track_length, track_filename)
    print(f"\nRace results have been written to {log_filename}")

if __name__ == "__main__":
    main()