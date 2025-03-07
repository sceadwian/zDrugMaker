import time
import datetime
import os
import ctypes
from collections import defaultdict

class BehaviorTimer:
    """
    A timer to record durations for which specific keys are held.
    
    Animal 1 keys: W, A, S, D  
    Animal 2 keys: J, K, L, I  
    Quit: T (requires double press confirmation)  
    Pause: P
    """
    
    DEFAULT_RECORD_KEYS_ANIMAL_1 = ['W', 'A', 'S', 'D']
    DEFAULT_RECORD_KEYS_ANIMAL_2 = ['J', 'K', 'L', 'I']
    DEFAULT_QUIT_KEY = 'T'
    DEFAULT_PAUSE_KEY = 'P'
    # Lower the refresh rate to 0.1 seconds
    TIMELINE_INTERVAL = 0.1  
    SEGMENT_DURATION = 900  # 15 minutes in seconds
    LINE_WIDTH = 100        # Characters per line
    # Set the block duration for graphing to 30 seconds instead of 10
    BLOCK_DURATION = 30.0

    # ANSI color codes for key labels
    KEY_COLORS = {
        'W': '\033[93m',  # Yellow
        'A': '\033[92m',  # Green
        'S': '\033[94m',  # Blue
        'D': '\033[91m',  # Red
        'J': '\033[93m',  # Yellow
        'K': '\033[92m',  # Green
        'L': '\033[94m',  # Blue
        'I': '\033[91m',  # Red
    }
    RESET_COLOR = '\033[0m'  # Reset color code

    def __init__(self, animal_name, trial_name, key_labels_file='zTimer.txt', 
                 record_keys_animal_1=None, record_keys_animal_2=None, 
                 quit_key=DEFAULT_QUIT_KEY, pause_key=DEFAULT_PAUSE_KEY):
        self.animal_name = animal_name
        self.trial_name = trial_name
        self.key_labels = self.read_key_labels(key_labels_file)
        self.record_keys_animal_1 = [key.upper() for key in (record_keys_animal_1 or self.DEFAULT_RECORD_KEYS_ANIMAL_1)]
        self.record_keys_animal_2 = [key.upper() for key in (record_keys_animal_2 or self.DEFAULT_RECORD_KEYS_ANIMAL_2)]
        self.quit_key = quit_key.upper()
        self.pause_key = pause_key.upper()

        self.start_time = None
        self.is_running = False
        self.is_paused = False
        self.total_pause_time = 0
        self.pause_start_time = None
        self.events = []

        # For tracking which keys are currently pressed
        self.key_down = {key: False for key in self.record_keys_animal_1 + self.record_keys_animal_2}
        self.current_event_start = {key: None for key in self.record_keys_animal_1 + self.record_keys_animal_2}
        # To store timeline markers (each marker is a dot or colored key)
        self.timeline_buffer = []

        self.record_vk = {key: ord(key) for key in self.record_keys_animal_1 + self.record_keys_animal_2}
        self.quit_vk = ord(self.quit_key)
        self.pause_vk = ord(self.pause_key)

        # Windows API for checking key state
        self.GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState

        # For the graphs: track block durations for keys 'A' and 'J'
        # Each BLOCK_DURATION-second block records the total seconds the key was held.
        self.block_start = 0.0  # Relative elapsed time when current block started
        self.current_block_duration_A = 0.0
        self.current_block_duration_J = 0.0
        self.a_block_durations = []  # List of completed block durations for key A
        self.j_block_durations = []  # List for key J

        self.current_segment_behaviors = defaultdict(int)

    def read_key_labels(self, filename):
        """
        Read key labels from a file of the form: key=label
        """
        key_labels = {}
        try:
            with open(filename, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        key, label = line.split('=')
                        key = key.strip().upper()
                        label = label.strip()
                        key_labels[key] = label
                    except ValueError:
                        print(f"Warning: Skipping invalid line in {filename}: {line}")
        except FileNotFoundError:
            print(f"Warning: Key labels file {filename} not found. Using default keys.")
        
        if not key_labels:
            key_labels = {
                'W': 'forward',
                'A': 'left',
                'S': 'backward',
                'D': 'right',
                'J': 'forward',
                'K': 'left',
                'L': 'backward',
                'I': 'right'
            }
        return key_labels

    def key_pressed(self, vk_code):
        """
        Check whether a key is currently pressed.
        """
        state = self.GetAsyncKeyState(vk_code)
        return (state & 0x8000) != 0

    def handle_pause(self):
        """
        Toggle pause. When pausing, end any ongoing events.
        """
        if not self.is_paused:
            self.is_paused = True
            self.pause_start_time = time.time()
            self.end_current_events()
        else:
            self.is_paused = False
            pause_duration = time.time() - self.pause_start_time
            self.total_pause_time += pause_duration
            self.pause_start_time = None
        return self.is_paused

    def end_current_events(self):
        """
        End any keys that are currently being held.
        """
        elapsed = time.time() - self.start_time - self.total_pause_time
        for key in self.record_keys_animal_1 + self.record_keys_animal_2:
            if self.key_down[key] and self.current_event_start[key] is not None:
                end_time = elapsed
                duration = end_time - self.current_event_start[key]
                self.events.append({
                    'key': key,
                    'start': self.current_event_start[key],
                    'end': end_time,
                    'duration': duration
                })
                self.current_event_start[key] = None
                self.key_down[key] = False

    def update_graph(self):
        """
        Display twin graphs (side-by-side) for keys 'A' (Animal 1) and 'J' (Animal 2).
        Each graph is based on BLOCK_DURATION-second blocks (30 seconds now).
        The y-axis (height) represents the total seconds (0–30) the key was pressed
        in that particular block.
        """
        # Create temporary copies that include the current (ongoing) block if not paused.
        a_data = self.a_block_durations.copy()
        j_data = self.j_block_durations.copy()
        if not self.is_paused:
            a_data.append(self.current_block_duration_A)
            j_data.append(self.current_block_duration_J)

        if len(a_data) == 0 or len(j_data) == 0:
            print("Not enough data for twin graphs.")
            return

        # Show the last up-to 10 blocks.
        window_size = min(10, len(a_data))
        a_blocks = a_data[-window_size:]
        j_blocks = j_data[-window_size:]
        graph_height = 10  # number of rows

        # Build the graph rows (each column represents one block)
        a_graph_rows = []
        j_graph_rows = []
        for row in range(graph_height, 0, -1):
            a_row = ""
            j_row = ""
            for block in a_blocks:
                # Calculate filled height relative to BLOCK_DURATION (max possible is BLOCK_DURATION seconds)
                filled = int((block / self.BLOCK_DURATION) * graph_height)
                a_row += "#" if filled >= row else " "
            for block in j_blocks:
                filled = int((block / self.BLOCK_DURATION) * graph_height)
                j_row += "#" if filled >= row else " "
            a_graph_rows.append(a_row)
            j_graph_rows.append(j_row)

        # Print the twin graphs side by side.
        print("\nTwin Graphs (30-second blocks):")
        print("Graph for 'A' (Animal 1)         Graph for 'J' (Animal 2)")
        for i in range(graph_height):
            print(f"{a_graph_rows[i]}      {j_graph_rows[i]}")
        # x-axis labels (simple dashes)
        print("-" * window_size + "      " + "-" * window_size)
        # Optionally, print numerical values below each graph.
        a_values = " ".join(f"{val:4.1f}" for val in a_blocks)
        j_values = " ".join(f"{val:4.1f}" for val in j_blocks)
        print(f"A durations: {a_values}")
        print(f"J durations: {j_values}")

    def update_ui(self, elapsed):
        """
        Clear the screen and display an updated UI panel with:
          • Header info (animal, trial, elapsed time, instructions)
          • Current segment statistics (per-key counts and most frequent key)
          • Twin graphs for keys 'A' and 'J' based on 30-second blocks
          • A timeline marker (history of key presses)
        """
        os.system('cls' if os.name=='nt' else 'clear')
        # Header Panel
        print("=== Behavior Observation Timer ===")
        print(f"Animal: {self.animal_name} | Trial: {self.trial_name} | Elapsed: {elapsed:.2f} sec")
        print("Press 'T' twice to quit, 'P' to pause/resume")
        print(f"Animal 1 keys: {', '.join(self.record_keys_animal_1)}")
        print(f"Animal 2 keys: {', '.join(self.record_keys_animal_2)}")
        print("\n--- Current Segment Statistics ---")
        for key in self.record_keys_animal_1 + self.record_keys_animal_2:
            count = self.current_segment_behaviors.get(key, 0)
            print(f"  {key} ({self.key_labels.get(key, '')}): {count} presses")
        if self.current_segment_behaviors:
            most_freq_key, freq = max(self.current_segment_behaviors.items(), key=lambda x: x[1])
            most_freq_label = self.key_labels.get(most_freq_key, "")
            print(f"Most frequent in segment: {most_freq_key} ({most_freq_label}) with {freq} presses")
        
        # Display twin graphs
        self.update_graph()

        # Display timeline markers (the last 100 markers)
        print("\n--- Timeline Markers ---")
        print("".join(self.timeline_buffer[-100:]))

    def start(self):
        """
        Start monitoring key states and updating the UI.
        """
        self.start_time = time.time()
        self.is_running = True
        self.total_pause_time = 0
        self.is_paused = False
        self.current_segment_behaviors = defaultdict(int)
        self.timeline_buffer = []
        self.block_start = 0.0
        self.current_block_duration_A = 0.0
        self.current_block_duration_J = 0.0
        self.a_block_durations = []
        self.j_block_durations = []

        while self.is_running:
            current_time = time.time()
            elapsed = current_time - self.start_time - self.total_pause_time
            
            # Check for pause key press (with a short debounce)
            if self.key_pressed(self.pause_vk):
                time.sleep(0.2)
                self.handle_pause()

            # Check for quit key with double-press confirmation
            if self.key_pressed(self.quit_vk):
                print("\nAre you sure you want to quit? Press 'T' again to confirm.")
                while self.key_pressed(self.quit_vk):
                    time.sleep(0.05)
                confirmed = False
                timeout = time.time() + 3
                while time.time() < timeout:
                    if self.key_pressed(self.quit_vk):
                        confirmed = True
                        break
                    time.sleep(0.05)
                if confirmed:
                    self.end_current_events()
                    self.is_running = False
                    break

            if not self.is_paused:
                # Poll each key's state and update per-key event counts
                for key in self.record_keys_animal_1 + self.record_keys_animal_2:
                    vk = self.record_vk[key]
                    pressed = self.key_pressed(vk)
                    
                    if pressed:
                        self.current_segment_behaviors[key] += 1
                        if not self.key_down[key]:
                            self.key_down[key] = True
                            self.current_event_start[key] = elapsed
                    elif self.key_down[key]:
                        self.key_down[key] = False
                        if self.current_event_start[key] is not None:
                            end_time = elapsed
                            duration = end_time - self.current_event_start[key]
                            self.events.append({
                                'key': key,
                                'start': self.current_event_start[key],
                                'end': end_time,
                                'duration': duration
                            })
                            self.current_event_start[key] = None

                # Update timeline marker: show pressed keys (with colors) or a dot if none pressed
                pressed_keys = [key for key in self.record_keys_animal_1 + self.record_keys_animal_2 if self.key_down[key]]
                marker = ''.join(f"{self.KEY_COLORS.get(key, '')}{key}{self.RESET_COLOR}" for key in pressed_keys) if pressed_keys else "."
                self.timeline_buffer.append(marker)
                if len(self.timeline_buffer) > 1000:
                    self.timeline_buffer = self.timeline_buffer[-1000:]

                # --- Update block durations for the graphs ---
                # For key A and key J, accumulate duration if pressed.
                if self.key_pressed(self.record_vk['A']):
                    self.current_block_duration_A += self.TIMELINE_INTERVAL
                if self.key_pressed(self.record_vk['J']):
                    self.current_block_duration_J += self.TIMELINE_INTERVAL

                # Check if the current BLOCK_DURATION-second block is complete (handle possible multiple blocks)
                while elapsed - self.block_start >= self.BLOCK_DURATION:
                    self.a_block_durations.append(self.current_block_duration_A)
                    self.j_block_durations.append(self.current_block_duration_J)
                    self.current_block_duration_A = 0.0
                    self.current_block_duration_J = 0.0
                    self.block_start += self.BLOCK_DURATION

            self.update_ui(elapsed)
            time.sleep(self.TIMELINE_INTERVAL)

        print("\n\nTimer stopped.")

    def save_log(self, log_dir='logs'):
        """
        Save a log file that summarizes the session and details each event.
        """
        try:
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            sanitized_animal_name = "".join(c if c.isalnum() else "_" for c in self.animal_name)
            sanitized_trial_name = "".join(c if c.isalnum() else "_" for c in self.trial_name)
            filename = os.path.join(log_dir, f"behavior_log_{sanitized_animal_name}_{sanitized_trial_name}_{timestamp}.txt")
            session_duration = time.time() - self.start_time - self.total_pause_time

            total_recorded_time_by_key = {key: 0.0 for key in self.record_keys_animal_1 + self.record_keys_animal_2}
            count_by_key = {key: 0 for key in self.record_keys_animal_1 + self.record_keys_animal_2}
            for event in self.events:
                total_recorded_time_by_key[event['key']] += event['duration']
                count_by_key[event['key']] += 1

            with open(filename, 'w', encoding='utf-8') as f:
                f.write("Behavior Observation Log\n")
                f.write(f"Animal: {self.animal_name}\n")
                f.write(f"Trial: {self.trial_name}\n")
                f.write(f"Session Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Session Duration (excluding pauses): {session_duration:.2f} seconds\n")
                f.write(f"Total Pause Time: {self.total_pause_time:.2f} seconds\n\n")

                f.write("Key events summary:\n")
                for key in self.record_keys_animal_1 + self.record_keys_animal_2:
                    total_time = total_recorded_time_by_key[key]
                    count = count_by_key[key]
                    percentage = (total_time / session_duration * 100) if session_duration > 0 else 0
                    avg_time = total_time / count if count > 0 else 0
                    f.write(f"  Key '{key}' ({self.key_labels.get(key, '')}): {count} events, "
                            f"total held {total_time:.2f} seconds, "
                            f"average held {avg_time:.2f} seconds ({percentage:.2f}%)\n")

                f.write("\nVisual Timeline:\n")
                self._generate_visual_timeline(f, session_duration)

                f.write("\nDetailed Event Log:\n")
                f.write("Event#\tKey\tLabel\tStart(s)\tEnd(s)\tDuration(s)\n")
                for i, event in enumerate(self.events, 1):
                    f.write(f"{i}\t{event['key']}\t{self.key_labels.get(event['key'], '')}\t"
                            f"{event['start']:.2f}\t{event['end']:.2f}\t{event['duration']:.2f}\n")

            print(f"\n\nLog file saved as: {filename}")
        except Exception as e:
            print(f"\n\nError saving log file: {e}")

    def _generate_visual_timeline(self, file, total_duration):
        """
        Generate a visual timeline representation.
        """
        num_segments = int(total_duration / self.SEGMENT_DURATION) + 1
        file.write("\nDetailed Visual Timeline (each line represents 15 minutes):\n")
        file.write("Legend: '.' = no activity, letter = key pressed\n\n")
        
        for key in self.record_keys_animal_1 + self.record_keys_animal_2:
            file.write(f"\n{key} ({self.key_labels.get(key, '')}):\n")
            for segment in range(num_segments):
                segment_start = segment * self.SEGMENT_DURATION
                segment_end = min((segment + 1) * self.SEGMENT_DURATION, total_duration)
                timeline = ['.'] * self.LINE_WIDTH
                for event in self.events:
                    if event['key'] == key:
                        if (event['start'] <= segment_end and event['end'] >= segment_start):
                            start_pos = max(0, event['start'] - segment_start)
                            end_pos = min(self.SEGMENT_DURATION, event['end'] - segment_start)
                            start_idx = int((start_pos / self.SEGMENT_DURATION) * self.LINE_WIDTH)
                            end_idx = int((end_pos / self.SEGMENT_DURATION) * self.LINE_WIDTH)
                            if end_idx <= start_idx:
                                end_idx = start_idx + 1
                            for idx in range(start_idx, min(end_idx, self.LINE_WIDTH)):
                                timeline[idx] = key
                start_min = int(segment_start / 60)
                start_sec = int(segment_start % 60)
                end_min = int(segment_end / 60)
                end_sec = int(segment_end % 60)
                timeline_str = ''.join(timeline)
                time_range = f"[{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}]"
                file.write(f"{timeline_str} {time_range}\n")
            file.write("\n")

def main():
    welcome_message = (
        "Welcome to the Behavior Observation Timer!\n"
        "This tool records and analyzes behavior by monitoring key presses.\n"
        "Animal 1 is assigned keys: W, A, S, D.\n"
        "Animal 2 is assigned keys: J, K, L, I.\n"
        "Press 'T' twice to quit, 'P' to pause/resume.\n"
        "Key labels are read from 'zTimer.txt' (or default labels are used).\n"
    )
    print(welcome_message)

    animal_name = input("Enter animal name: ")
    trial_name = input("Enter trial name: ")

    timer = BehaviorTimer(animal_name, trial_name)
    try:
        timer.start()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected. Exiting.")
    finally:
        timer.save_log()
        time.sleep(10)
        print("Program ended.")

if __name__ == "__main__":
    main()
