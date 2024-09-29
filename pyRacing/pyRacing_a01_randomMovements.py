import os
import time
import random
from typing import List


class Car:
    def __init__(self, symbol, drag_coefficient, cooling_efficiency, acceleration, cornering_ability, downforce):
        self.symbol = symbol
        self.position = None
        self.speed = 0
        self.acceleration = acceleration
        self.drag_coefficient = drag_coefficient
        self.cooling_efficiency = cooling_efficiency
        self.cornering_ability = cornering_ability
        self.downforce = downforce
        self.lap = 0
        self.sector = 0
        self.distance = 0

    def update_position(self, track):
        drag_force = 0.5 * self.drag_coefficient * (self.speed ** 2)
        self.speed += self.acceleration - drag_force
        self.speed = max(0, min(self.speed, 5))  # Limit speed between 0 and 5

        print(f"{self.symbol} speed: {self.speed}, position: {self.position}")

        if track[self.position[0]][self.position[1]] in ['#', '$', 'S']:
            self.speed *= (0.5 + 0.5 * self.cornering_ability)

        move = int(self.speed)
        for _ in range(move):
            next_pos = self.get_next_position(track)
            if next_pos == self.position:
                break  # Properly break out of the loop if no valid moves
            self.position = next_pos  # Correct indentation to update position after each move
            self.distance += 20  # Each character represents 20 meters

        print(f"{self.symbol} moved to {self.position}, distance: {self.distance}")

        if track[self.position[0]][self.position[1]] == '$':
            self.sector += 1
        elif track[self.position[0]][self.position[1]] == 'S':
            if self.sector == 3:
                self.lap += 1
                self.sector = 0

    def get_next_position(self, track):
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]  # Up, Down, Left, Right
        random.shuffle(directions)  # Randomize direction

        for dx, dy in directions:
            new_x, new_y = self.position[0] + dx, self.position[1] + dy
            if 0 <= new_x < len(track) and 0 <= new_y < len(track[0]):
                if track[new_x][new_y] not in ['#', 'S']:  # Avoid blocked and start positions
                    return (new_x, new_y)  # Move to the new position
        return self.position  # Stay in the same position if no valid moves


def load_track(filename: str) -> List[str]:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, filename)
    try:
        with open(file_path, 'r') as file:
            track = [line.strip() for line in file if line.strip()]
            for row in track:
                print(row)  # Add this line to debug the track layout
            return track
    except FileNotFoundError:
        print(f"Error: The file '{filename}' was not found in the directory: {script_dir}")
        exit(1)


def find_start_position(track):
    for i, row in enumerate(track):
        for j, cell in enumerate(row):
            if cell == 'S':
                return i, j
    raise ValueError("Start position 'S' not found in the track")


def render_track(track, cars):
    os.system('cls' if os.name == 'nt' else 'clear')

    track_with_cars = [list(row) for row in track]
    for car in cars:
        if car.position:
            x, y = car.position
            track_with_cars[x][y] = car.symbol

    for row in track_with_cars:
        print(''.join(row))

    print("\nCar Positions:")
    for car in cars:
        print(f"{car.symbol}: Lap {car.lap}, Sector {car.sector}, Distance {car.distance}m")


def simulate_race(track, cars, num_laps):
    start_pos = find_start_position(track)
    for car in cars:
        car.position = start_pos

    while any(car.lap < num_laps for car in cars):
        for car in cars:
            if car.lap < num_laps:
                car.update_position(track)
        render_track(track, cars)
        time.sleep(0.1)

    print("\nRace Finished!")
    for car in sorted(cars, key=lambda x: (-x.lap, -x.distance)):
        print(f"{car.symbol}: Completed {car.lap} laps, Distance {car.distance}m")


def main():
    track = load_track('track.csv')

    cars = [
        Car('A', 0.3, 0.8, 0.5, 0.7, 0.6),
        Car('B', 0.25, 0.85, 0.55, 0.75, 0.65),
        Car('C', 0.28, 0.82, 0.52, 0.72, 0.62),
        Car('D', 0.27, 0.83, 0.53, 0.73, 0.63),
        Car('E', 0.29, 0.81, 0.51, 0.71, 0.61),
        Car('F', 0.26, 0.84, 0.54, 0.74, 0.64),
        Car('G', 0.31, 0.79, 0.49, 0.69, 0.59),
        Car('H', 0.32, 0.78, 0.48, 0.68, 0.58),
        Car('I', 0.33, 0.77, 0.47, 0.67, 0.57),
        Car('J', 0.34, 0.76, 0.46, 0.66, 0.56),
        Car('K', 0.35, 0.75, 0.45, 0.65, 0.55),
        Car('L', 0.36, 0.74, 0.44, 0.64, 0.54),
        Car('M', 0.37, 0.73, 0.43, 0.63, 0.53),
        Car('N', 0.38, 0.72, 0.42, 0.62, 0.52),
    ]

    num_laps = 3
    simulate_race(track, cars, num_laps)


if __name__ == "__main__":
    main()
