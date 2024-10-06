#version 3b fixed the simulation a bit. some minor tweaks to prevent cars from halting.
#version 3c added more to the reporting of the race.
#version 3d Added new attributes + load driver attributes + fixed reporting position to txt
#version 3e+3f overtaking + 3f colour
#version 3g events
#version 3h performance pop up box
import os
import time
import random
import csv
from datetime import datetime
import tkinter as tk
from tkinter import ttk


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
        # New attributes for random events
        self.current_event = None
        self.event_duration = 0
        self.event_effect = 0

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
            (" --- GOD MODE !!!!!!!! --- ", lambda: 110 < self.speed < 124 and random.random() < 0.01, 69, 26)
        ]

        possible_events = [event for event in events if event[1]()]
        if possible_events:
            event = random.choice(possible_events)
            self.current_event = event[0]
            self.event_effect = event[2]
            self.event_duration = event[3]

    def move(self, track_sequence, track_length, time_step, current_time, num_laps, cars):
        if not self.finished:
            current_tile_index = int(self.distance / 20) % len(track_sequence)
            current_tile = track_sequence[current_tile_index]
            is_turning = current_tile == 'U'
        
            # Check for random events
            self.check_for_random_event(is_turning)

            if is_turning:
                self.update_speed_turn()
            else:
                self.update_speed_straight(random.uniform(0.8, 1.2))

            # Apply event effect
            if self.current_event:
                self.speed += self.event_effect
        
            # Ensure speed doesn't go below 0
            self.speed = max(0, self.speed)

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
            line = " " * bounce_pos + Colors.GREEN + car.symbol + Colors.RESET + " " * (display_width - bounce_pos - 1)
        else:
            line = Colors.YELLOW + "=" * progress + Colors.RESET + " " * (display_width - progress)
        
        status = ""
        if car.overtake_boost > 0:
            status = Colors.CYAN + " [OVERTAKING]" + Colors.RESET
        elif car.overtake_penalty > 0:
            status = Colors.RED + " [BLOCKED]" + Colors.RESET
        elif car.overtake_cooldown > 0:
            status = Colors.MAGENTA + f" [COOLDOWN: {car.overtake_cooldown}]" + Colors.RESET
        elif car.current_event:
            status = Colors.BLUE + f" [{car.current_event.upper()}]" + Colors.RESET
        
        print(f"{Colors.WHITE}{i:2d}. {Colors.BLUE}{car.symbol} {Colors.WHITE}|{line}| Lap {car.laps_completed + 1} - Best Lap: {best_lap}{status}")
    
    print(f"\n{Colors.WHITE}Car Details:")
    for i, car in enumerate(sorted_cars, 1):
        print(f"{Colors.WHITE}{i:2d}. {Colors.BLUE}{car.symbol}: {Colors.WHITE}Distance: {Colors.YELLOW}{car.distance:.2f} m, {Colors.WHITE}Speed: {Colors.GREEN}{car.speed:.2f} km/h")
    
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
class Graph(tk.Canvas):
    def __init__(self, master, width, height, x_label, y_label, title):
        super().__init__(master, width=width, height=height)
        self.width = width
        self.height = height
        self.margin = 40
        self.plot_width = self.width - 2 * self.margin
        self.plot_height = self.height - 2 * self.margin

        self.create_text(self.width // 2, 20, text=title)
        self.create_text(self.width // 2, self.height - 10, text=x_label)
        self.create_text(10, self.height // 2, text=y_label, angle=90)

        self.plot_area = self.create_rectangle(
            self.margin, self.margin,
            self.width - self.margin, self.height - self.margin
        )

        self.lines = {}
        self.max_points = 100
        self.data = {}

    def update_data(self, car, x, y):
        if car not in self.data:
            self.data[car] = {'x': [], 'y': []}
        
        self.data[car]['x'].append(x)
        self.data[car]['y'].append(y)
        
        if len(self.data[car]['x']) > self.max_points:
            self.data[car]['x'].pop(0)
            self.data[car]['y'].pop(0)
        
        self.plot()

    def plot(self):
        if not self.data:
            return

        all_x = [x for car_data in self.data.values() for x in car_data['x']]
        all_y = [y for car_data in self.data.values() for y in car_data['y']]

        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)

        x_range = max(x_max - x_min, 1)
        y_range = max(y_max - y_min, 1)

        colors = ['red', 'blue', 'green', 'orange']

        for line in self.lines.values():
            self.delete(line)
        self.lines.clear()

        for i, (car, car_data) in enumerate(self.data.items()):
            coords = []
            for j in range(len(car_data['x'])):
                x = self.margin + (car_data['x'][j] - x_min) / x_range * self.plot_width
                y = self.height - self.margin - (car_data['y'][j] - y_min) / y_range * self.plot_height
                coords.extend([x, y])

            if len(coords) >= 4:
                self.lines[car] = self.create_line(coords, fill=colors[i], width=2, smooth=True)

class RaceGUI:
    def __init__(self, master, cars):
        self.master = master
        self.cars = cars
        self.master.title("Race Monitor")
        self.master.geometry("800x700")

        self.selected_cars = []
        self.paused = False

        # Create checkboxes for car selection
        self.car_vars = {}
        self.car_frame = ttk.Frame(self.master)
        self.car_frame.pack(pady=10)
        
        for car in self.cars:
            var = tk.BooleanVar()
            ttk.Checkbutton(self.car_frame, text=f"{car.last_name}", variable=var, command=self.update_selected_cars).pack(side=tk.LEFT, padx=5)
            self.car_vars[car] = var

        # Create pause button
        self.pause_button = ttk.Button(self.master, text="Pause", command=self.toggle_pause)
        self.pause_button.pack(pady=5)

        # Create graphs
        self.speed_graph = Graph(self.master, 700, 300, "Time (s)", "Speed (km/h)", "Speed over Time")
        self.speed_graph.pack(side=tk.TOP, pady=5)

        self.distance_graph = Graph(self.master, 700, 300, "Time (s)", "Distance (m)", "Distance over Time")
        self.distance_graph.pack(side=tk.TOP, pady=5)

    def update_selected_cars(self):
        self.selected_cars = [car for car, var in self.car_vars.items() if var.get()]
        self.selected_cars = self.selected_cars[:4]  # Limit to 4 cars
        
        for car in self.car_vars:
            if car not in self.selected_cars:
                self.car_vars[car].set(False)
        
        self.speed_graph.data.clear()
        self.distance_graph.data.clear()

    def toggle_pause(self):
        self.paused = not self.paused
        self.pause_button.config(text="Resume" if self.paused else "Pause")

    def update_plots(self):
        if not self.paused:
            current_time = time.time() - start_time
            for car in self.selected_cars:
                self.speed_graph.update_data(car, current_time, car.speed)
                self.distance_graph.update_data(car, current_time, car.distance)

def simulate_race(track_sequence, cars, num_laps, time_step=0.1, gui=None):
    global start_time
    track_length = len(track_sequence) * 20
    start_time = time.time()
    
    for car in cars:
        car.current_lap_start_time = start_time
    
    finish_position = 1
    while any(not car.finished for car in cars):
        if gui and gui.paused:
            gui.master.update()
            time.sleep(0.1)
            continue

        current_time = time.time() - start_time
        for car in cars:
            if not car.finished:
                car.move(track_sequence, track_length, time_step, current_time, num_laps, cars)
                if car.finished and car.finish_position == 0:
                    car.finish_position = finish_position
                    finish_position += 1
        
        render_race_progress(cars, track_length)
        
        if gui:
            gui.update_plots()
            gui.master.update()

        time.sleep(time_step)

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

    # Create Tkinter window and RaceGUI instance
    root = tk.Tk()
    gui = RaceGUI(root, cars)

    # Run the race simulation in a separate thread
    import threading
    race_thread = threading.Thread(target=simulate_race, args=(track_sequence, cars, 5, 0.1, gui))
    race_thread.start()

    # Start the Tkinter main loop
    root.mainloop()

    # Wait for the race thread to finish
    race_thread.join()

    log_filename = f"race_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    write_race_results(cars, os.path.join(current_dir, log_filename), track_length, track_filename)
    print(f"\nRace results have been written to {log_filename}")

if __name__ == "__main__":
    main()