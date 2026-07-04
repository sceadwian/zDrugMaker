#version 3b fixed the simulation a bit. some minor tweaks to prevent cars from halting.
#version 3c added more to the reporting of the race.
#version 3d Added new attributes + load driver attributes + fixed reporting position to txt
#version 3e+3f overtaking + 3f colour
#version 3g events
#version 3h performance pop up box + added 4 car comparissons)
#version 3i Stamina (03i_1 version was not used ... 10 lap with more output... there is a season tested with this version.)
#v03i_0_1 - added pit stops + made cars a bit faster + pit stops
#v3i_2 - fixed pit stops and some issues with 0_1
#v3j - Added last 4 laps + driver report txt + More events + starting positions
#v04 - Combined all pyRacing scripts into one file with a menu:
#      race sim + track viewer + track analyzer/sequencer + driver generator + physics graphs.
#      Fixes: lap/race times now use simulated time (deterministic, machine-independent),
#      overtaking works across the start/finish line, event effects match their labels,
#      event probabilities no longer double-gated, robust track-id parsing.
#v04h - UI overhaul: combined race screen with track-shaped progress bars, live gaps
#       to leader, position-change arrows vs grid, stamina bars, pit counts, average
#       lap pace, fastest-lap highlight, live event feed (overtakes/pits/incidents),
#       nicer grid/menu, podium ceremony after the race.

import os
import re
import time
import random
import csv
import string
from datetime import datetime
from collections import deque

# ANSI color codes
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GREY = '\033[90m'

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TILE_LENGTH = 20  # meters per track tile

# Rolling feed of race happenings (overtakes, pits, incidents) shown live
RACE_LOG = deque(maxlen=6)

def log_race_event(lap, msg):
    RACE_LOG.append((lap, msg))

# ============================================================
# Shared car physics (used by both the race sim and the graph tool)
# ============================================================

def straight_speed(speed, cc_accel, cc_dragC, cc_downC, stamina_factor, random_factor):
    new_speed = (speed +
                 0.2 * random_factor * (cc_downC + cc_dragC - cc_accel * stamina_factor) +
                 (cc_accel * stamina_factor / 1.7) -
                 speed * (1 - (cc_dragC / 500)) * (0.10 + 0.31 * ((speed**0.5 - 100) / 1500)) -
                 speed * (cc_downC / 5000))
    return max(0, new_speed)

def turn_speed(speed, cc_cornr, cc_downC, stamina_factor):
    new_speed = speed * (0.5 + (cc_cornr / 200) * stamina_factor + (cc_downC / 2000))
    return max(new_speed, 50)

# ============================================================
# Race simulation
# ============================================================

# (name, condition, effect, duration, weight)
# condition: where the event can happen; weight: relative likelihood among
# eligible events once the per-tick event roll has already succeeded.
# effect is the approximate sustained speed impact in km/h while active.
RANDOM_EVENTS = [
    ("Lock up",                 'turn',     -30,   5, 5),
    ("Brake overheating",       'turn',     -10,  20, 1),
    ("Handling malfunction",    'any',       -5,  30, 3),
    ("Gearbox malfunction",     'any',      -25,  40, 1),
    ("Throttle malfunction",    'straight', -40,  20, 3),
    ("Electrical reset",        'fast',    -150,  17, 2),
    ("Fuel pressure drop",      'any',       -5,  50, 1),
    ("Fuel flow issue",         'slow',      -5, 100, 1),
    ("Inspired",                'any',       33,  15, 5),
    ("Flustered :(",            'any',      -10,  30, 5),
    ("Adrenaline boost",        'any',        5,  40, 5),
    (" --- GOD MODE !!!!!!!! --- ", 'godmode', 69, 69, 1),
]

def event_condition_met(condition, is_turning, speed):
    if condition == 'any':
        return True
    if condition == 'turn':
        return is_turning
    if condition == 'straight':
        return not is_turning
    if condition == 'fast':
        return speed > 300
    if condition == 'slow':
        return speed < 150
    if condition == 'godmode':
        return 110 < speed < 124
    return False

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
        # Random events and pits
        self.current_event = None
        self.event_duration = 0
        self.event_effect = 0
        self.stamina_pool = 100  # Start with 100% stamina
        self.distance_since_last_stamina_decrease = 0
        self.in_pit = False
        self.pit_cycles = 0
        self.pit_stop_count = 0
        self.last_4_lap_times = deque(maxlen=4)
        self.start_position = 0  # grid slot, for position-change arrows

    def update_stamina(self, distance_moved):
        self.distance_since_last_stamina_decrease += distance_moved
        if self.distance_since_last_stamina_decrease >= 3000:
            self.stamina_pool = max(0, self.stamina_pool - 5)
            self.distance_since_last_stamina_decrease = 0

    def update_speed_turn(self):
        self.speed = turn_speed(self.speed, self.cc_cornr, self.cc_downC, self.stamina_pool / 100)

    def update_speed_straight(self, random_factor):
        new_speed = straight_speed(self.speed, self.cc_accel, self.cc_dragC, self.cc_downC,
                                   self.stamina_pool / 100, random_factor)
        self.speed = min(new_speed, self.cc_maxSpd)

        # Apply overtaking effects
        if self.overtake_boost > 0:
            self.speed += 20
            self.overtake_boost -= 1
        elif self.overtake_penalty > 0:
            self.speed -= 20
            self.overtake_penalty -= 1

            # Additional stamina penalty based on cc_stam
            additional_penalty = 0.001 * (1 - self.cc_stam / 100)
            total_penalty = 0.001 + additional_penalty
            self.stamina_pool = max(0, self.stamina_pool - total_penalty * 100)

    def check_for_random_event(self, is_turning):
        if self.current_event:
            self.event_duration -= 1
            if self.event_duration <= 0:
                self.current_event = None
                self.event_effect = 0
            return

        # Base probability for an event to occur per tick
        base_prob = 0.005
        # Lower consistency increases probability
        event_prob = base_prob * (1 + (100 - self.cc_const) / 100)

        if random.random() < event_prob:
            self.trigger_random_event(is_turning)

    def trigger_random_event(self, is_turning):
        eligible = [e for e in RANDOM_EVENTS if event_condition_met(e[1], is_turning, self.speed)]
        if not eligible:
            return
        weights = [e[4] for e in eligible]
        name, _, effect, duration, _ = random.choices(eligible, weights=weights, k=1)[0]
        self.current_event = name
        self.event_effect = effect
        self.event_duration = duration
        log_race_event(self.laps_completed + 1, f"{self.symbol} — {name.strip()}")

    def check_for_pit_stop(self, track_length):
        if self.distance % track_length < 20 and self.stamina_pool < 50 and random.random() < 0.5:
            self.in_pit = True
            self.pit_cycles = random.randint(5, 10)
            self.pit_stop_count += 1
            log_race_event(self.laps_completed + 1, f"{self.symbol} pits (stop {self.pit_stop_count})")

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
            current_tile_index = int(self.distance / TILE_LENGTH) % len(track_sequence)
            current_tile = track_sequence[current_tile_index]
            is_turning = current_tile == 'U'

            self.check_for_random_event(is_turning)

            if is_turning:
                self.update_speed_turn()
            else:
                self.update_speed_straight(random.uniform(0.8, 1.2))

            if self.current_event:
                # The speed formula's damping pulls speed back toward equilibrium
                # each tick, so a raw per-tick addition would overshoot the labelled
                # effect ~6x. Scaling by 0.15 makes the sustained speed change land
                # near event_effect km/h.
                self.speed += self.event_effect * 0.15

            self.speed = max(0, self.speed)

            distance_moved = (self.speed * 1000 / 3600) * time_step
            self.distance += distance_moved

            self.update_stamina(distance_moved)

            self.check_overtaking(cars, track_length)

            if self.overtake_cooldown > 0:
                self.overtake_cooldown -= 1

            self.check_for_pit_stop(track_length)

            if self.distance >= track_length:
                self.laps_completed += 1
                self.distance %= track_length

                lap_time = current_time - self.current_lap_start_time
                if lap_time > 0:
                    self.lap_times.append(lap_time)
                    self.last_4_lap_times.append(lap_time)
                    if lap_time < self.best_lap_time:
                        self.best_lap_time = lap_time

                self.current_lap_start_time = current_time

            if self.laps_completed >= num_laps:
                self.finished = True
                self.distance = self.laps_completed * track_length
                self.total_race_time = current_time

    def check_overtaking(self, cars, track_length):
        if self.overtake_cooldown > 0:
            return  # Cannot attempt overtaking during cooldown

        for other_car in cars:
            if other_car != self and not other_car.finished:
                # Circular gap so cars straddling the start/finish line still count as close
                raw_diff = abs(self.distance - other_car.distance) % track_length
                distance_diff = min(raw_diff, track_length - raw_diff)
                if distance_diff < 10:  # Cars are close enough for an overtaking attempt
                    total_score = self.cc_ovrtk + other_car.cc_defnd
                    pass_chance = self.cc_ovrtk / total_score

                    if random.random() < pass_chance:
                        # Successful overtake
                        self.overtake_boost = 14
                        self.overtake_penalty = 0
                        log_race_event(self.laps_completed + 1, f"{self.symbol} powers past {other_car.symbol}!")
                    else:
                        # Failed overtake
                        self.overtake_boost = 0
                        self.overtake_penalty = 20
                        log_race_event(self.laps_completed + 1, f"{other_car.symbol} shuts the door on {self.symbol}")

                    self.overtake_cooldown = 50
                    break  # Only attempt one overtake per move

def load_track_visual(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file.readlines()]

def load_track_sequence(file_path):
    with open(file_path, 'r') as file:
        return file.read().strip().split(',')

def build_track_bar_background(track_sequence, bar_width):
    # Downsample the tile sequence into bar_width cells so the progress bar
    # mirrors the actual track shape: straights, turns, sector boundaries.
    cells = []
    for i in range(bar_width):
        tile = track_sequence[int(i / bar_width * len(track_sequence))]
        if tile == 'U':
            cells.append('~')   # turn
        elif tile == 'X':
            cells.append('|')   # sector boundary
        else:
            cells.append('-')   # straight
    return cells

def race_position_key(car, track_length):
    if car.finished:
        return (1, -car.finish_position)  # finishers rank by actual finish order
    return (0, car.laps_completed * track_length + car.distance)

def render_race_progress(cars, track_sequence, track_length, sim_time, num_laps, track_name=""):
    C = Colors
    BAR_W = 32
    W = 118

    os.system('cls' if os.name == 'nt' else 'clear')

    sorted_cars = sorted(cars, key=lambda car: race_position_key(car, track_length), reverse=True)
    leader = sorted_cars[0]
    leader_progress = leader.laps_completed * track_length + (0 if leader.finished else leader.distance)
    overall_best = min((car.best_lap_time for car in cars), default=float('inf'))
    track_bg = build_track_bar_background(track_sequence, BAR_W)

    # ---- Header ----
    lap_display = min(leader.laps_completed + 1, num_laps)
    header = (f"PYRACING GRAND PRIX  ·  {track_name}  ·  {track_length/1000:.2f} km"
              f"  ·  LAP {lap_display}/{num_laps}  ·  T+{sim_time:7.1f}s")
    print(f"{C.CYAN}{'═'*W}{C.RESET}")
    print(f"{C.BOLD}{C.YELLOW}{header:^{W}}{C.RESET}")
    print(f"{C.CYAN}{'═'*W}{C.RESET}")

    # ---- Running order ----
    print(f"{C.GREY}{'POS':>4}  {'':3} {'CAR':3} {'DRIVER':13} "
          f"{'S -' + '-'*(BAR_W-9) + '- F':^{BAR_W+2}} {'LAP':>4} {'GAP':>9} {'KM/H':>5}  {'%GRIP':10}  STATUS{C.RESET}")

    for i, car in enumerate(sorted_cars, 1):
        # Position-change arrow vs starting grid
        delta = car.start_position - i
        if delta > 0:
            arrow = f"{C.GREEN}{'▲' + str(delta):<3}{C.RESET}"
        elif delta < 0:
            arrow = f"{C.RED}{'▼' + str(-delta):<3}{C.RESET}"
        else:
            arrow = f"{C.GREY}{'·':<3}{C.RESET}"

        pos_col = C.BOLD + C.YELLOW if i == 1 else (C.WHITE if i <= 3 else C.GREY)
        name = f"{car.first_name[:1]}.{car.last_name[:11]}"

        # Track bar with car marker
        if car.finished:
            label = f" P{car.finish_position} FINISHED {car.total_race_time:.1f}s "
            bar = f"{C.GREEN}{label:·^{BAR_W}}{C.RESET}"
        else:
            marker_pos = min(int((car.distance % track_length) / track_length * BAR_W), BAR_W - 1)
            if car.in_pit:
                marker = C.MAGENTA + '█' + C.RESET
            elif car.current_event and car.event_effect < 0:
                marker = C.RED + '█' + C.RESET
            elif car.overtake_boost > 0 or (car.current_event and car.event_effect > 0):
                marker = C.GREEN + '█' + C.RESET
            else:
                marker = C.CYAN + '█' + C.RESET
            bar = (C.DIM + ''.join(track_bg[:marker_pos]) + C.RESET
                   + marker
                   + C.DIM + ''.join(track_bg[marker_pos+1:]) + C.RESET)

        # Gap to leader (time behind at the leader's average pace; laps if > a lap down)
        if car.finished:
            gap = f"{C.GREEN}{'🏁':>8}{C.RESET} "
        elif i == 1:
            gap = f"{C.BOLD}{C.YELLOW}{'LEADER':>9}{C.RESET}"
        else:
            gap_m = leader_progress - (car.laps_completed * track_length + car.distance)
            leader_pace = leader_progress / sim_time if sim_time > 0 else 0  # m/s
            if gap_m >= track_length:
                gap = f"{C.GREY}{'+' + str(int(gap_m // track_length)) + ' LAP':>9}{C.RESET}"
            elif leader_pace > 0:
                gap_s = gap_m / leader_pace
                gap = f"{C.WHITE}{'+' + format(gap_s, '.1f') + 's':>9}{C.RESET}"
            else:
                gap = f"{C.GREY}{'—':>9}{C.RESET}"

        spd_col = C.GREEN if car.speed > 280 else (C.YELLOW if car.speed > 150 else C.RED)

        # Stamina bar (10 cells)
        filled = round(car.stamina_pool / 10)
        stam_col = C.GREEN if car.stamina_pool > 66 else C.YELLOW if car.stamina_pool > 33 else C.RED
        stam_bar = f"{stam_col}{'█'*filled}{C.GREY}{'░'*(10-filled)}{C.RESET}"

        if car.finished:
            status = ""
        elif car.in_pit:
            status = f"{C.MAGENTA}IN PIT ({car.pit_cycles}){C.RESET}"
        elif car.overtake_boost > 0:
            status = f"{C.CYAN}ATTACKING{C.RESET}"
        elif car.overtake_penalty > 0:
            status = f"{C.RED}BLOCKED{C.RESET}"
        elif car.current_event:
            ev_col = C.GREEN if car.event_effect > 0 else C.RED
            status = f"{ev_col}{car.current_event.strip()[:16]}{C.RESET}"
        elif car.overtake_cooldown > 0:
            status = f"{C.GREY}cd {car.overtake_cooldown}{C.RESET}"
        else:
            status = ""

        lap_cell = car.laps_completed if car.finished else car.laps_completed + 1
        print(f"{pos_col}{i:>4}{C.RESET}  {arrow}{C.BOLD}{C.BLUE}{car.symbol:3}{C.RESET} {C.WHITE}{name:13}{C.RESET} "
              f"[{bar}] {C.WHITE}{lap_cell:>4}{C.RESET} {gap} {spd_col}{car.speed:5.0f}{C.RESET}  {stam_bar}  {status}")

    # ---- Timing table ----
    print(f"\n{C.CYAN}{'─'*W}{C.RESET}")
    print(f"{C.GREY}{'POS':>4} {'CAR':3} {'DRIVER':13} {'BEST LAP':>10} {'LAST LAP':>10} {'AVG LAP':>9} {'PITS':>5}   LAST 4 LAPS{C.RESET}")
    for i, car in enumerate(sorted_cars, 1):
        name = f"{car.first_name[:1]}.{car.last_name[:11]}"
        if car.best_lap_time != float('inf'):
            if car.best_lap_time == overall_best:
                best = f"{C.MAGENTA}{C.BOLD}{car.best_lap_time:>9.2f}★{C.RESET}"
            else:
                best = f"{C.WHITE}{car.best_lap_time:>9.2f} {C.RESET}"
        else:
            best = f"{C.GREY}{'—':>9} {C.RESET}"
        last = f"{car.last_4_lap_times[-1]:>10.2f}" if car.last_4_lap_times else f"{'—':>10}"
        avg = f"{sum(car.lap_times)/len(car.lap_times):>9.2f}" if car.lap_times else f"{'—':>9}"
        last4 = "  ".join(f"{lap:6.2f}" for lap in car.last_4_lap_times)
        print(f"{C.GREY}{i:>4}{C.RESET} {C.BLUE}{car.symbol:3}{C.RESET} {C.WHITE}{name:13}{C.RESET} {best}"
              f"{C.CYAN}{last}{C.RESET} {C.WHITE}{avg}{C.RESET} {C.GREY}{car.pit_stop_count:>5}{C.RESET}   {C.CYAN}{last4}{C.RESET}")

    # ---- Live feed ----
    print(f"\n{C.CYAN}{'─'*W}{C.RESET}")
    print(f"{C.BOLD}{C.WHITE} LIVE FEED{C.RESET}   {C.GREY}(~ turn zones on track bar · | sector line · ★ fastest lap){C.RESET}")
    for lap, msg in list(RACE_LOG)[::-1]:
        print(f"   {C.GREY}L{lap:<3}{C.RESET}{C.WHITE}{msg}{C.RESET}")

    time.sleep(0.1)

def write_driver_report(car, track_id, results_dir):
    os.makedirs(results_dir, exist_ok=True)
    filename = os.path.join(results_dir, f"{car.first_name}_{car.last_name}.csv")
    file_exists = os.path.isfile(filename)

    with open(filename, 'a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['TrackID', 'Position', 'FastestLap', 'TotalTime'])
        writer.writerow([
            track_id,
            car.finish_position,
            f"{car.best_lap_time:.2f}" if car.best_lap_time != float('inf') else "N/A",
            f"{car.total_race_time:.2f}" if car.finished else "DNF"
        ])

def assign_random_starting_positions(cars):
    random.shuffle(cars)
    for i, car in enumerate(cars):
        car.distance = i * 2  # 2 meters between each car
        car.start_position = len(cars) - i  # front of grid = furthest along track

def show_starting_grid(cars):
    C = Colors
    print(f"\n{C.CYAN}╔{'═'*44}╗{C.RESET}")
    print(f"{C.CYAN}║{C.BOLD}{C.YELLOW}{'STARTING GRID':^44}{C.RESET}{C.CYAN}║{C.RESET}")
    print(f"{C.CYAN}╠{'═'*44}╣{C.RESET}")
    # Grid order: last car in the list starts furthest forward
    for car in sorted(cars, key=lambda c: c.start_position):
        row_col = C.YELLOW if car.start_position <= 3 else C.WHITE
        inner = f" P{car.start_position:<2}  {car.symbol:3}  {car.first_name} {car.last_name}"
        print(f"{C.CYAN}║{row_col}{inner:<44}{C.CYAN}║{C.RESET}")
    print(f"{C.CYAN}╚{'═'*44}╝{C.RESET}")
    print("\nPress Enter to start the countdown...")
    input()

def simulate_green_light():
    print("\nPreparing to start the race...")
    time.sleep(1)
    print("  🔴")
    time.sleep(1)
    print("  🔴")
    time.sleep(1)
    print("  🔴")
    time.sleep(1)
    print("  🟢 GO!")
    time.sleep(0.5)

def simulate_race(track_sequence, cars, num_laps, time_step=0.1, quiet=False, track_name=""):
    track_length = len(track_sequence) * TILE_LENGTH

    RACE_LOG.clear()
    assign_random_starting_positions(cars)

    if not quiet:
        show_starting_grid(cars)
        simulate_green_light()

    # Simulated race clock: advances by time_step per tick regardless of how
    # long rendering takes, so lap/race times are deterministic and
    # machine-independent.
    sim_time = 0.0
    for car in cars:
        car.current_lap_start_time = 0.0

    finish_position = 1
    while any(not car.finished for car in cars):
        sim_time += time_step
        for car in cars:
            if not car.finished:
                car.move(track_sequence, track_length, time_step, sim_time, num_laps, cars)
                if car.finished and car.finish_position == 0:
                    car.finish_position = finish_position
                    finish_position += 1

        if not quiet:
            render_race_progress(cars, track_sequence, track_length, sim_time, num_laps, track_name)

    return sorted(cars, key=lambda car: (car.finish_position if car.finished else float('inf'), car.total_race_time))

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
            if not row:
                continue
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

def parse_track_id(track_filename):
    # 'track_3.csv' -> '3'; falls back to the filename stem if no number found
    stem = os.path.splitext(os.path.basename(track_filename))[0]
    match = re.search(r'(\d+)', stem)
    return match.group(1) if match else stem

def list_track_files():
    files = []
    for name in sorted(os.listdir(CURRENT_DIR)):
        if not name.lower().endswith('.csv'):
            continue
        if name.endswith('_seq.csv') or name == 'drivers.csv':
            continue
        files.append(name)
    return files

def choose_track_file(prompt="Select a track"):
    files = list_track_files()
    if not files:
        print("No track CSV files found in this folder.")
        return None

    print(f"\n{prompt}:")
    for i, name in enumerate(files, 1):
        print(f"  {i}. {name}")

    choice = input("Enter number (or press Enter to cancel): ").strip()
    if not choice:
        return None
    if not choice.isdigit() or not (1 <= int(choice) <= len(files)):
        print("Invalid selection.")
        return None
    return files[int(choice) - 1]

def run_race():
    track_filename = choose_track_file("Select a track to race on")
    if not track_filename:
        return
    track_path = os.path.join(CURRENT_DIR, track_filename)

    track_visual = load_track_visual(track_path)

    print("Track Layout:")
    for row in track_visual:
        print(row)
    print("\nPress Enter to set up the race...")
    input()

    seq_filename = track_filename.replace('.csv', '_seq.csv')
    seq_path = os.path.join(CURRENT_DIR, seq_filename)
    if not os.path.exists(seq_path):
        print(f"Error: Sequence file '{seq_filename}' not found. Run the track analyzer first (menu option 2).")
        return
    track_sequence = load_track_sequence(seq_path)

    track_length = len(track_sequence) * TILE_LENGTH

    cars = load_drivers(os.path.join(CURRENT_DIR, 'drivers.csv'))
    track_id = parse_track_id(track_filename)

    sorted_cars = simulate_race(track_sequence, cars, num_laps=8, track_name=track_filename)

    show_podium(sorted_cars)

    results_dir = os.path.join(CURRENT_DIR, 'driver_results')
    for car in sorted_cars:
        write_driver_report(car, track_id, results_dir)

    log_filename = f"race_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    write_race_results(sorted_cars, os.path.join(CURRENT_DIR, log_filename), track_length, track_filename)
    print(f"\nRace results have been written to {log_filename}")
    print(f"Individual driver reports have been updated in the 'driver_results' directory")

def show_podium(sorted_cars):
    C = Colors
    medals = ['🥇', '🥈', '🥉']
    fastest = min(sorted_cars, key=lambda c: c.best_lap_time)
    print(f"\n{C.YELLOW}{'═'*56}{C.RESET}")
    print(f"{C.BOLD}{C.YELLOW}{'🏆  PODIUM  🏆':^54}{C.RESET}")
    print(f"{C.YELLOW}{'═'*56}{C.RESET}")
    for i, car in enumerate(sorted_cars[:3]):
        grid_delta = car.start_position - car.finish_position
        moved = f"(P{car.start_position} on the grid, {'+' if grid_delta >= 0 else ''}{grid_delta})"
        print(f"  {medals[i]}  {C.BOLD}{C.WHITE}{car.first_name} {car.last_name}{C.RESET} "
              f"{C.BLUE}[{car.symbol}]{C.RESET}  {C.GREEN}{car.total_race_time:.2f}s{C.RESET}  {C.GREY}{moved}{C.RESET}")
    if fastest.best_lap_time != float('inf'):
        print(f"\n  {C.MAGENTA}★ Fastest lap: {fastest.best_lap_time:.2f}s — "
              f"{fastest.first_name} {fastest.last_name} [{fastest.symbol}]{C.RESET}")
    print(f"{C.YELLOW}{'═'*56}{C.RESET}")

# ============================================================
# Track viewer (from pyRacing_b01_showsTrack)
# ============================================================

def view_track():
    filename = choose_track_file("Select a track to view")
    if not filename:
        return
    file_path = os.path.join(CURRENT_DIR, filename)

    with open(file_path, 'r') as file:
        track_lines = [line.rstrip() for line in file.readlines()]

    for line in track_lines:
        colored_line = ''
        for char in line:
            if char == 'S':
                colored_line += Colors.GREEN + char + Colors.RESET
            elif char == '$':
                colored_line += Colors.YELLOW + char + Colors.RESET
            else:
                colored_line += char
        print(colored_line)

# ============================================================
# Track analyzer / sequence generator (from pyRacing_c03_trackReader)
# ============================================================

def load_track_grid(file_path):
    with open(file_path, 'r') as file:
        return [line.strip().split(',') for line in file]

def find_start_position(track):
    for y, row in enumerate(track):
        for x, cell in enumerate(row):
            if cell.strip() == 'S':
                return x, y
    return None

def get_next_position(x, y, direction):
    if direction == 'N':
        return x, y - 1
    elif direction == 'E':
        return x + 1, y
    elif direction == 'S':
        return x, y + 1
    elif direction == 'W':
        return x - 1, y

def is_valid_position(track, x, y):
    return 0 <= y < len(track) and 0 <= x < len(track[y])

def is_track(cell):
    return cell.strip() in ['#', '$', 'S']

def determine_start_direction(track, start_x, start_y):
    for direction in ['N', 'E', 'S', 'W']:
        next_x, next_y = get_next_position(start_x, start_y, direction)
        if is_valid_position(track, next_x, next_y) and is_track(track[next_y][next_x]):
            return direction
    return None

def analyze_track(track):
    start = find_start_position(track)
    if not start:
        return "Error: Start position 'S' not found."

    x, y = start
    direction = determine_start_direction(track, x, y)
    if not direction:
        return "Error: No valid starting direction found."

    path = []
    visited = set()
    segment_count = 0
    straight_count = 0
    turn_count = 0
    sector_borders = []
    sequence = ['S']

    while (x, y) not in visited:
        visited.add((x, y))
        segment_count += 1

        if track[y][x].strip() == '$':
            sector_borders.append(segment_count)
            sequence.append('X')

        surroundings = {
            'N': is_track(track[y-1][x]) if is_valid_position(track, x, y-1) else False,
            'E': is_track(track[y][x+1]) if is_valid_position(track, x+1, y) else False,
            'S': is_track(track[y+1][x]) if is_valid_position(track, x, y+1) else False,
            'W': is_track(track[y][x-1]) if is_valid_position(track, x-1, y) else False
        }

        # Determine the next direction (always turn right first)
        right_direction = {'N': 'E', 'E': 'S', 'S': 'W', 'W': 'N'}[direction]
        if surroundings[right_direction]:
            path.append("Turn Right")
            direction = right_direction
            turn_count += 1
            sequence.append('U')
        elif surroundings[direction]:
            path.append("Straight")
            straight_count += 1
            sequence.append('I')
        else:
            left_direction = {'N': 'W', 'W': 'S', 'S': 'E', 'E': 'N'}[direction]
            if surroundings[left_direction]:
                path.append("Turn Left")
                direction = left_direction
                turn_count += 1
                sequence.append('U')
            else:
                return f"Error: Dead end at ({x}, {y})"

        x, y = get_next_position(x, y, direction)
        if not is_valid_position(track, x, y) or not is_track(track[y][x]):
            return f"Error: Off track at ({x}, {y})"

    track_length_km = segment_count * TILE_LENGTH / 1000
    if len(sector_borders) >= 2:
        sector_sizes = [
            sector_borders[0] * TILE_LENGTH / 1000,
            (sector_borders[1] - sector_borders[0]) * TILE_LENGTH / 1000,
            (segment_count - sector_borders[1]) * TILE_LENGTH / 1000
        ]
    else:
        sector_sizes = None

    return {
        'path': path,
        'track_length_km': track_length_km,
        'sector_sizes': sector_sizes,
        'straight_count': straight_count,
        'turn_count': turn_count,
        'sequence': sequence
    }

def analyze_and_save_track():
    filename = choose_track_file("Select a track to analyze")
    if not filename:
        return
    file_path = os.path.join(CURRENT_DIR, filename)

    track = load_track_grid(file_path)
    for row in track:
        print(''.join(cell.strip() for cell in row))
    print("\nAnalyzing track...")

    result = analyze_track(track)
    if isinstance(result, str):  # Error message
        print(result)
        return

    print("\nTrack analysis:")
    print(f"Track length: {result['track_length_km']:.2f} km")
    if result['sector_sizes']:
        for i, size in enumerate(result['sector_sizes'], 1):
            print(f"Sector {i} size: {size:.2f} km")
    else:
        print("(Fewer than 2 sector boundaries '$' found - sector sizes not available)")
    print(f"Number of straights: {result['straight_count']}")
    print(f"Number of turns: {result['turn_count']}")

    sequence_file_path = file_path.rsplit('.', 1)[0] + '_seq.csv'
    with open(sequence_file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(result['sequence'])
    print(f"\nTrack sequence saved to: {sequence_file_path}")

# ============================================================
# Driver generator (from pyRacing_genDriver)
# ============================================================

def generate_driver_row():
    name = ''.join(random.choice(string.ascii_uppercase) for _ in range(random.randint(3, 8))).capitalize()
    surname = ''.join(random.choice(string.ascii_uppercase) for _ in range(random.randint(4, 10))).capitalize()
    symbol = ''.join(random.choice(string.ascii_uppercase) for _ in range(3))
    return [
        name, surname, symbol,
        random.randint(340, 380),  # max speed
        random.randint(68, 80),    # accel
        random.randint(58, 79),    # drag coeff
        random.randint(65, 91),    # downforce coeff
        random.randint(61, 80),    # cornering
        random.randint(30, 95),    # overtake
        random.randint(5, 95),     # consistency
        random.randint(15, 95),    # defending
        random.randint(8, 90),     # stamina
    ]

def generate_drivers():
    count_str = input("How many drivers to generate? (press Enter for 20): ").strip()
    count = int(count_str) if count_str else 20

    drivers = [generate_driver_row() for _ in range(count)]
    for driver in drivers:
        print(','.join(str(v) for v in driver))

    out_name = input("\nSave to file? Enter filename (press Enter to skip, 'drivers.csv' will be overwritten only if you type it): ").strip()
    if not out_name:
        return
    out_path = os.path.join(CURRENT_DIR, out_name)
    if os.path.exists(out_path):
        confirm = input(f"'{out_name}' already exists. Overwrite? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Not saved.")
            return
    with open(out_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(drivers)
    print(f"Saved {count} drivers to {out_name}")

# ============================================================
# Physics graph tool (from pyRacing_c01_ghaphs, now using the SAME
# formulas as the race sim so tuning results match race behaviour)
# ============================================================

def simulate_car_profile(cc_accel, cc_dragc, cc_downc, cc_cornr):
    speed = 0
    speeds = []
    distances = [0]
    for cycle in range(60):  # 60 seconds total
        if cycle < 10 or (11 <= cycle < 16) or (20 <= cycle < 30) or (35 <= cycle < 60):
            speed = straight_speed(speed, cc_accel, cc_dragc, cc_downc,
                                   stamina_factor=1.0, random_factor=random.uniform(0.8, 1.2))
        else:
            speed = turn_speed(speed, cc_cornr, cc_downc, stamina_factor=1.0)
        speeds.append(speed)
        distances.append(distances[-1] + speed)
    return speeds, distances[1:]

def run_graph_tool():
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        print("Error: tkinter is not available in this Python installation.")
        return

    colors = ["red", "blue", "green", "purple"]

    root = tk.Tk()
    root.title("Multi-Car Acceleration and Distance Visualization")

    input_frame = ttk.Frame(root, padding="10")
    input_frame.pack(fill=tk.X)

    accel_entries, dragc_entries, downc_entries, cornr_entries = [], [], [], []

    for i in range(4):
        car_frame = ttk.Frame(input_frame)
        car_frame.grid(row=0, column=i, padx=10)

        ttk.Label(car_frame, text=f"Car {i+1}", font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=2)

        for row_idx, (label, entries) in enumerate([
            ("CC_accel:", accel_entries),
            ("CC_dragC:", dragc_entries),
            ("CC_downC:", downc_entries),
            ("CC_cornr:", cornr_entries),
        ], start=1):
            ttk.Label(car_frame, text=label).grid(row=row_idx, column=0, sticky=tk.W)
            entry = ttk.Entry(car_frame, width=10)
            entry.insert(0, "70")
            entry.grid(row=row_idx, column=1)
            entries.append(entry)

    speed_canvas = tk.Canvas(root, width=800, height=300)
    distance_canvas = tk.Canvas(root, width=800, height=300)

    def plot_graphs(speeds_list, distances_list):
        for canvas in [speed_canvas, distance_canvas]:
            canvas.delete("all")

        canvas_width = 800
        canvas_height = 300
        x_scale = (canvas_width - 70) / 59

        max_speed = max(max(speeds) for speeds in speeds_list)
        y_scale_speed = (canvas_height - 70) / (max_speed * 1.1)

        max_distance = max(max(distances) for distances in distances_list)
        y_scale_distance = (canvas_height - 70) / (max_distance * 1.1)

        for canvas in [speed_canvas, distance_canvas]:
            canvas.create_line(50, canvas_height - 50, canvas_width - 20, canvas_height - 50, fill="black")
            canvas.create_line(50, canvas_height - 50, 50, 20, fill="black")

        for speeds, distances, color in zip(speeds_list, distances_list, colors):
            for i in range(len(speeds) - 1):
                x1 = 50 + i * x_scale
                y1 = canvas_height - 50 - speeds[i] * y_scale_speed
                x2 = 50 + (i + 1) * x_scale
                y2 = canvas_height - 50 - speeds[i + 1] * y_scale_speed
                speed_canvas.create_line(x1, y1, x2, y2, fill=color)

            for i in range(len(distances) - 1):
                x1 = 50 + i * x_scale
                y1 = canvas_height - 50 - distances[i] * y_scale_distance
                x2 = 50 + (i + 1) * x_scale
                y2 = canvas_height - 50 - distances[i + 1] * y_scale_distance
                distance_canvas.create_line(x1, y1, x2, y2, fill=color)

        speed_canvas.create_text(canvas_width // 2, canvas_height - 20, text="Time (s)")
        speed_canvas.create_text(20, canvas_height // 2, text="Speed", angle=90)
        distance_canvas.create_text(canvas_width // 2, canvas_height - 20, text="Time (s)")
        distance_canvas.create_text(20, canvas_height // 2, text="Distance", angle=90)

        for canvas in [speed_canvas, distance_canvas]:
            for i in range(0, 61, 10):
                x = 50 + i * x_scale
                canvas.create_line(x, canvas_height - 50, x, canvas_height - 45, fill="black")
                canvas.create_text(x, canvas_height - 35, text=str(i))

        for i in range(0, int(max_speed) + 1, 20):
            y = canvas_height - 50 - i * y_scale_speed
            speed_canvas.create_line(45, y, 50, y, fill="black")
            speed_canvas.create_text(35, y, text=str(i))

        for i in range(0, int(max_distance) + 1, 500):
            y = canvas_height - 50 - i * y_scale_distance
            distance_canvas.create_line(45, y, 50, y, fill="black")
            distance_canvas.create_text(35, y, text=str(i))

        for canvas in [speed_canvas, distance_canvas]:
            for i, color in enumerate(colors):
                canvas.create_rectangle(canvas_width - 120, 20 + i*30, canvas_width - 20, 50 + i*30, fill="white", outline="black")
                canvas.create_line(canvas_width - 110, 35 + i*30, canvas_width - 70, 35 + i*30, fill=color)
                canvas.create_text(canvas_width - 45, 35 + i*30, text=f"Car {i+1}")

        segments = [
            (0, 10, "Straight"),
            (10, 11, "Turn"),
            (11, 16, "Straight"),
            (16, 20, "Turn"),
            (20, 30, "Straight"),
            (30, 35, "Turn"),
            (35, 60, "Straight")
        ]
        for canvas in [speed_canvas, distance_canvas]:
            for start, end, label in segments:
                x = 50 + (start + (end - start) / 2) * x_scale
                canvas.create_text(x, canvas_height - 65, text=label, angle=45, anchor="se")

    def update_graph():
        speeds_list = []
        distances_list = []
        for i in range(4):
            speeds, distances = simulate_car_profile(
                int(accel_entries[i].get()),
                int(dragc_entries[i].get()),
                int(downc_entries[i].get()),
                int(cornr_entries[i].get()))
            speeds_list.append(speeds)
            distances_list.append(distances)
        plot_graphs(speeds_list, distances_list)

    update_button = ttk.Button(input_frame, text="Update Graph", command=update_graph)
    update_button.grid(row=1, column=0, columnspan=4, pady=10)

    speed_canvas.pack()
    distance_canvas.pack()

    update_graph()
    root.mainloop()

# ============================================================
# Menu
# ============================================================

def main():
    C = Colors
    while True:
        print(f"\n{C.CYAN}╔{'═'*48}╗{C.RESET}")
        print(f"{C.CYAN}║{C.BOLD}{C.YELLOW}{'p y R A C I N G   v 0 4 h':^48}{C.RESET}{C.CYAN}║{C.RESET}")
        print(f"{C.CYAN}╠{'═'*48}╣{C.RESET}")
        for key, label in [('1', 'Run a race'),
                           ('2', 'Analyze a track & generate sequence file'),
                           ('3', 'View a track layout'),
                           ('4', 'Generate random drivers'),
                           ('5', 'Car physics graph tool'),
                           ('q', 'Quit')]:
            inner = f"  {key}.  {label}"
            print(f"{C.CYAN}║{C.WHITE}{inner:<48}{C.CYAN}║{C.RESET}")
        print(f"{C.CYAN}╚{'═'*48}╝{C.RESET}")
        choice = input("\nSelect an option: ").strip().lower()

        if choice == '1':
            run_race()
        elif choice == '2':
            analyze_and_save_track()
        elif choice == '3':
            view_track()
        elif choice == '4':
            generate_drivers()
        elif choice == '5':
            run_graph_tool()
        elif choice == 'q':
            break
        else:
            print("Invalid option, try again.")

if __name__ == "__main__":
    main()
