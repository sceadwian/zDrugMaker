import time
import datetime
import os
import ctypes

class BehaviorTimer:
    """
    A timer to record durations for which specific keys are held.
    The user is prompted for animal name and trial info before the timer starts.
    Key labels are read from zTimer.txt file.
    Measured keys (by default: X, Z, M, K) are polled via the Windows API.
    Press the quit key (default: Q) to end the session.
    Press 'W' to pause/unpause the session.
    """
    
    def __init__(self, animal_name, trial_name, key_labels_file='zTimer.txt', 
                 record_keys=None, quit_key='Q', pause_key='W',
                 timeline_interval=0.05, dots_per_line=100):
        # Set animal and trial info
        self.animal_name = animal_name
        self.trial_name = trial_name
        
        # Read key labels from file
        self.key_labels = self.read_key_labels(key_labels_file)
        
        # Define which keys to measure
        if record_keys is None:
            record_keys = list(self.key_labels.keys())
        self.record_keys = [key.upper() for key in record_keys]
        self.quit_key = quit_key.upper()
        self.pause_key = pause_key.upper()
        
        # Timeline display parameters
        self.timeline_interval = timeline_interval
        self.dots_per_line = dots_per_line

        self.start_time = None
        self.is_running = False
        self.is_paused = False
        self.total_pause_time = 0
        self.pause_start_time = None
        self.events = []

        # Track key states
        self.key_down = {key: False for key in self.record_keys}
        self.current_event_start = {key: None for key in self.record_keys}
        self.dot_count = 0

        # Create mappings for virtual key codes
        self.record_vk = {key: ord(key) for key in self.record_keys}
        self.quit_vk = ord(self.quit_key)
        self.pause_vk = ord(self.pause_key)

        # Windows API access
        self.GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState

    # [Previous methods remain unchanged: read_key_labels, key_pressed]
    def read_key_labels(self, filename):
        """
        Read key labels from a text file. 
        Expected format: key=label (one per line)
        """
        key_labels = {}
        try:
            with open(filename, 'r') as f:
                for line in f:
                    # Strip whitespace and skip empty lines
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Split into key and label
                    try:
                        key, label = line.split('=')
                        key = key.strip().upper()
                        label = label.strip()
                        key_labels[key] = label
                    except ValueError:
                        print(f"Warning: Skipping invalid line in {filename}: {line}")
        except FileNotFoundError:
            print(f"Warning: Key labels file {filename} not found. Using default keys.")
        
        # Default to uppercase keys if no labels found
        if not key_labels:
            key_labels = {
                'X': 'twitches',
                'Z': 'chewing',
                'M': 'freezing',
                'K': 'ambulation'
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
        Handle pausing and unpausing the timer.
        Returns the current pause state.
        """
        if not self.is_paused:
            # Entering pause state
            print("\nSession paused")
            self.is_paused = True
            self.pause_start_time = time.time()
            # End any currently pressed keys
            for key in self.record_keys:
                if self.key_down[key] and self.current_event_start[key] is not None:
                    elapsed = time.time() - self.start_time - self.total_pause_time
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
        else:
            # Resuming from pause
            print("\nSession resumed")
            self.is_paused = False
            pause_duration = time.time() - self.pause_start_time
            self.total_pause_time += pause_duration
            self.pause_start_time = None
        return self.is_paused

    def start(self):
        """
        Start the timer, monitor key states, and display timeline markers.
        """
        self.start_time = time.time()
        self.is_running = True
        self.total_pause_time = 0
        self.is_paused = False

        # Print initial instructions with key labels
        print(f"\nTimer started for animal '{self.animal_name}' and trial '{self.trial_name}'.")
        key_label_str = ", ".join([f"{key} = {self.key_labels[key]}" for key in self.record_keys])
        print(f"Measuring keys: {key_label_str}")
        print(f"Press '{self.quit_key}' to quit, '{self.pause_key}' to pause/unpause")
        print("Timeline: ", end="", flush=True)

        last_pause_state = False
        while self.is_running:
            current_time = time.time()
            
            # Check for pause key press (detect transition from not pressed to pressed)
            pause_pressed = self.key_pressed(self.pause_vk)
            if pause_pressed and not last_pause_state:
                self.handle_pause()
                if self.is_paused:
                    print("P", end="", flush=True)
                else:
                    print("R", end="", flush=True)
                self.dot_count += 1
            last_pause_state = pause_pressed

            if not self.is_paused:
                elapsed = current_time - self.start_time - self.total_pause_time

                # Check if the quit key is pressed
                if self.key_pressed(self.quit_vk):
                    # Finalize any key that is still pressed
                    for key in self.record_keys:
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
                    self.is_running = False
                    break

                # Check the state for each key being monitored
                for key in self.record_keys:
                    vk = self.record_vk[key]
                    pressed = self.key_pressed(vk)
                    if pressed and not self.key_down[key]:
                        # Key transitioned from not pressed to pressed
                        self.key_down[key] = True
                        self.current_event_start[key] = elapsed
                    elif not pressed and self.key_down[key]:
                        # Key transitioned from pressed to released
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

                # Build timeline marker
                pressed_keys = [key for key in self.record_keys if self.key_down[key]]
                marker = ''.join(pressed_keys) if pressed_keys else "."
                print(marker, end="", flush=True)
                self.dot_count += 1

                # Print elapsed time every dots_per_line markers
                if self.dot_count % self.dots_per_line == 0:
                    minutes = int(elapsed // 60)
                    seconds = elapsed % 60
                    print(f" {minutes:02d}:{seconds:05.2f}")
                    print("Timeline: ", end="", flush=True)

            time.sleep(self.timeline_interval)

        print("\n\nTimer stopped.")

    # [Previous methods remain unchanged: save_log, _generate_visual_timeline]
    def save_log(self, log_dir='logs'):
        """
        Save a log file that summarizes the session and details each event,
        including a visual timeline representation.
        """
        try:
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(log_dir, f"behavior_log_{timestamp}.txt")
            session_duration = time.time() - self.start_time - self.total_pause_time

            # Calculate total recorded time and event counts for each key
            total_recorded_time_by_key = {key: 0.0 for key in self.record_keys}
            count_by_key = {key: 0 for key in self.record_keys}
            for event in self.events:
                total_recorded_time_by_key[event['key']] += event['duration']
                count_by_key[event['key']] += 1

            with open(filename, 'w', encoding='utf-8') as f:
                # Session summary
                f.write("Behavior Observation Log\n")
                f.write(f"Animal: {self.animal_name}\n")
                f.write(f"Trial: {self.trial_name}\n")
                f.write(f"Session Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Session Duration (excluding pauses): {session_duration:.2f} seconds\n")
                f.write(f"Total Pause Time: {self.total_pause_time:.2f} seconds\n\n")

                # Key events summary
                f.write("Key events summary:\n")
                for key in self.record_keys:
                    total_time = total_recorded_time_by_key[key]
                    count = count_by_key[key]
                    percentage = (total_time / session_duration * 100) if session_duration > 0 else 0
                    avg_time = total_time / count if count > 0 else 0
                    f.write(f"  Key '{key}' ({self.key_labels[key]}): {count} events, "
                            f"total held {total_time:.2f} seconds, "
                            f"average held {avg_time:.2f} seconds ({percentage:.2f}%)\n")

                # Generate visual timeline
                f.write("\nVisual Timeline:\n")
                self._generate_visual_timeline(f, session_duration)

                # Detailed event log
                f.write("\nDetailed Event Log:\n")
                f.write("Event#\tKey\tLabel\tStart(s)\tEnd(s)\tDuration(s)\n")
                for i, event in enumerate(self.events, 1):
                    f.write(f"{i}\t{event['key']}\t{self.key_labels[event['key']]}\t"
                            f"{event['start']:.2f}\t{event['end']:.2f}\t{event['duration']:.2f}\n")

            print(f"\n\nLog file saved as: {filename}")
        except Exception as e:
            print(f"\n\nError saving log file: {e}")

    def _generate_visual_timeline(self, file, total_duration):
        """
        Generate a visual timeline with improved resolution for long experiments.
        """
        SEGMENT_DURATION = 900  # 15 minutes in seconds
        LINE_WIDTH = 100       # Characters per line
        
        num_segments = int(total_duration / SEGMENT_DURATION) + 1
        
        file.write("\nDetailed Visual Timeline (each line represents 15 minutes):\n")
        file.write("Legend: '.' = no activity, letter = key pressed\n\n")
        
        for key in self.record_keys:
            file.write(f"\n{key} ({self.key_labels[key]}):\n")
            
            for segment in range(num_segments):
                segment_start = segment * SEGMENT_DURATION
                segment_end = min((segment + 1) * SEGMENT_DURATION, total_duration)
                
                timeline = ['.'] * LINE_WIDTH
                
                for event in self.events:
                    if event['key'] == key:
                        if (event['start'] <= segment_end and 
                            event['end'] >= segment_start):
                            start_pos = max(0, event['start'] - segment_start)
                            end_pos = min(SEGMENT_DURATION, event['end'] - segment_start)
                            
                            start_idx = int((start_pos / SEGMENT_DURATION) * LINE_WIDTH)
                            end_idx = int((end_pos / SEGMENT_DURATION) * LINE_WIDTH)
                            
                            if end_idx <= start_idx:
                                end_idx = start_idx + 1
                                
                            for idx in range(start_idx, min(end_idx, LINE_WIDTH)):
                                timeline[idx] = key
                
                start_min = int(segment_start / 60)
                start_sec = int(segment_start % 60)
                end_min = int(segment_end / 60)
                end_sec = int(segment_end % 60)
                
                timeline_str = ''.join(timeline)
                time_range = f"[{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}]"
                file.write(f"{timeline_str} {time_range}\n")
            
            file.write("\n")

if __name__ == "__main__":
    # Display a welcome message and an explanation of what the script does.
    welcome_message = (
        "Welcome to the Behavior Observation Timer!\n"
        "This tool allows you to record and analyze behavior by monitoring key presses.\n"
        "You will be prompted to enter the animal's name and the trial information.\n"
        "The script reads key labels from 'zTimer.txt' (or uses default labels if the file is not found).\n"
        "It then starts monitoring specific keys (by default, X, Z, M, and K),\n"
        "and logs the duration each key is pressed. A visual timeline is displayed in real time,\n"
        "and you can end the session by pressing the quit key (default: Q).\n"
        "After quitting, a detailed log file will be saved.\n"
    )
    print(welcome_message)

    # Prompt the user for animal and trial information.
    animal_name = input("Enter animal name: ")
    trial_name = input("Enter trial name: ")

    # Create and start the behavior timer.
    timer = BehaviorTimer(animal_name, trial_name)
    try:
        timer.start()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected. Exiting.")
    finally:
        timer.save_log()
        time.sleep(10)
        print("Program ended.")