import time
import datetime
import os
import ctypes

class BehaviorTimer:
    """
    A timer to record durations for which specific keys are held.
    The user is prompted for animal name and trial info before the timer starts.
    Measured keys (by default: X, Z, M, K) are polled via the Windows API.
    Press the quit key (default: Q) to end the session.
    """
    
    def __init__(self, animal_name, trial_name, record_keys=None, quit_key='Q',
                 timeline_interval=0.05, dots_per_line=100):
        # Set animal and trial info
        self.animal_name = animal_name
        self.trial_name = trial_name
        
        # Define which keys to measure.
        # If not provided, default to ['X', 'Z', 'M', 'K']
        if record_keys is None:
            record_keys = ['X', 'Z', 'M', 'K']
        self.record_keys = [key.upper() for key in record_keys]
        self.quit_key = quit_key.upper()
        
        # Timeline display parameters.
        self.timeline_interval = timeline_interval  # seconds between timeline updates
        self.dots_per_line = dots_per_line           # markers printed per line before showing elapsed time

        self.start_time = None
        self.is_running = False
        self.events = []  # List to store events; each event is a dict with key, start, end, duration

        # For each record key, track whether it is currently pressed,
        # and if so, the time when it was pressed.
        self.key_down = {key: False for key in self.record_keys}
        self.current_event_start = {key: None for key in self.record_keys}
        self.dot_count = 0

        # Create mappings for virtual key codes.
        self.record_vk = {key: ord(key) for key in self.record_keys}
        self.quit_vk = ord(self.quit_key)

        # Use ctypes to access the Windows API function GetAsyncKeyState.
        self.GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState

    def key_pressed(self, vk_code):
        """
        Check whether a key (specified by its virtual-key code) is currently pressed.
        GetAsyncKeyState returns a short whose most-significant bit is set if the key is down.
        """
        state = self.GetAsyncKeyState(vk_code)
        return (state & 0x8000) != 0

    def start(self):
        """
        Start the timer, monitor key states, and display timeline markers.
        """
        self.start_time = time.time()
        self.is_running = True

        # Print initial instructions.
        print(f"\nTimer started for animal '{self.animal_name}' and trial '{self.trial_name}'.")
        print(f"Measuring keys: {', '.join(self.record_keys)}. Press '{self.quit_key}' to quit.")
        print("Timeline: ", end="", flush=True)

        while self.is_running:
            elapsed = time.time() - self.start_time

            # Check if the quit key is pressed.
            if self.key_pressed(self.quit_vk):
                # Finalize any key that is still pressed.
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

            # Check the state for each key being monitored.
            for key in self.record_keys:
                vk = self.record_vk[key]
                pressed = self.key_pressed(vk)
                if pressed and not self.key_down[key]:
                    # Key transitioned from not pressed to pressed.
                    self.key_down[key] = True
                    self.current_event_start[key] = elapsed
                elif not pressed and self.key_down[key]:
                    # Key transitioned from pressed to released.
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

            # Build a marker for the timeline:
            # If any keys are currently pressed, list them (in order);
            # otherwise, print a dot.
            pressed_keys = [key for key in self.record_keys if self.key_down[key]]
            marker = ''.join(pressed_keys) if pressed_keys else "."
            print(marker, end="", flush=True)
            self.dot_count += 1

            # Every dots_per_line markers, print the elapsed time.
            if self.dot_count % self.dots_per_line == 0:
                minutes = int(elapsed // 60)
                seconds = elapsed % 60
                print(f" {minutes:02d}:{seconds:05.2f}")
                print("Timeline: ", end="", flush=True)

            time.sleep(self.timeline_interval)

        print("\n\nTimer stopped.")

    def save_log(self, log_dir='logs'):
        """
        Save a log file that summarizes the session and details each event.
        """
        try:
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(log_dir, f"behavior_log_{timestamp}.txt")
            session_duration = time.time() - self.start_time

            # Calculate total recorded time and event counts for each key.
            total_recorded_time_by_key = {key: 0.0 for key in self.record_keys}
            count_by_key = {key: 0 for key in self.record_keys}
            for event in self.events:
                total_recorded_time_by_key[event['key']] += event['duration']
                count_by_key[event['key']] += 1

            with open(filename, 'w') as f:
                # Session summary.
                f.write("Behavior Observation Log\n")
                f.write(f"Animal: {self.animal_name}\n")
                f.write(f"Trial: {self.trial_name}\n")
                f.write(f"Session Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Session Duration: {session_duration:.2f} seconds\n\n")
                f.write("Key events summary:\n")
                for key in self.record_keys:
                    total_time = total_recorded_time_by_key[key]
                    count = count_by_key[key]
                    percentage = (total_time / session_duration * 100) if session_duration > 0 else 0
                    # Calculate average held time with error handling if count is 0.
                    avg_time = total_time / count if count > 0 else 0
                    f.write(f"  Key '{key}': {count} events, total held {total_time:.2f} seconds, "
                            f"average held {avg_time:.2f} seconds ({percentage:.2f}%)\n")
                f.write("\nDetailed Event Log:\n")
                f.write("Event#\tKey\tStart(s)\tEnd(s)\tDuration(s)\n")
                for i, event in enumerate(self.events, 1):
                    f.write(f"{i}\t{event['key']}\t{event['start']:.2f}\t{event['end']:.2f}\t{event['duration']:.2f}\n")

            print(f"\n\nLog file saved as: {filename}")
        except Exception as e:
            print(f"\n\nError saving log file: {e}")

if __name__ == "__main__":
    # Prompt the user for animal and trial information before starting.
    animal_name = input("Enter animal name: ")
    trial_name = input("Enter trial name: ")

    # Create and start the behavior timer.
    timer = BehaviorTimer(animal_name, trial_name,
                          record_keys=['X', 'Z', 'M', 'K'], quit_key='Q')
    try:
        timer.start()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected. Exiting.")
    finally:
        timer.save_log()
        print("Program ended.")
