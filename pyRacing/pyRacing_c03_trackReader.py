import os
import time

def load_track(file_path):
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
    directions = ['N', 'E', 'S', 'W']
    for direction in directions:
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

    while (x, y) not in visited:
        visited.add((x, y))
        
        # Check surrounding cells
        surroundings = {
            'N': is_track(track[y-1][x]) if is_valid_position(track, x, y-1) else False,
            'E': is_track(track[y][x+1]) if is_valid_position(track, x+1, y) else False,
            'S': is_track(track[y+1][x]) if is_valid_position(track, x, y+1) else False,
            'W': is_track(track[y][x-1]) if is_valid_position(track, x-1, y) else False
        }

        # Determine the next direction (always turn right first)
        right_direction = {'N': 'E', 'E': 'S', 'S': 'W', 'W': 'N'}[direction]
        if surroundings[right_direction]:  # Try turning right first
            path.append("Turn Right")
            direction = right_direction
        elif surroundings[direction]:  # Can continue straight
            path.append("Straight")
        else:
            # Try turning left last (clockwise)
            left_direction = {'N': 'W', 'W': 'S', 'S': 'E', 'E': 'N'}[direction]
            if surroundings[left_direction]:
                path.append("Turn Left")
                direction = left_direction
            else:
                return f"Error: Dead end at ({x}, {y})"

        # Update the position based on the new direction
        x, y = get_next_position(x, y, direction)
        if not is_valid_position(track, x, y) or not is_track(track[y][x]):
            return f"Error: Off track at ({x}, {y})"

    return path
    


def render_track(file_path):
    os.system('cls' if os.name == 'nt' else 'clear')
    track = load_track(file_path)
    for row in track:
        print(''.join(cell.strip() for cell in row))
    print("\nAnalyzing track...")
    time.sleep(2)
    
    path = analyze_track(track)
    if isinstance(path, str):  # Error message
        print(path)
    else:
        print("\nTrack analysis:")
        for i, move in enumerate(path, 1):
            print(f"{i}. {move}")

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = input("Enter the track filename (press Enter for 'track.csv'): ").strip() or 'track.csv'
    file_path = os.path.join(current_dir, filename)

    if os.path.exists(file_path):
        render_track(file_path)
    else:
        print(f"Error: The file '{filename}' does not exist in the current directory.")

if __name__ == "__main__":
    main()
    time.sleep(30)