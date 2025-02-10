import time
import datetime
import os
import ctypes

class BehaviorTimer:
    """
    A timer to record durations for which a specified key is held.
    Press and hold the record key (default: 'X') to start an event;
    release it to end the event. Press the quit key (default: 'Q') to stop the session.
    """
    
    def __init__(self, record_key='X', quit_key='Q', timeline_interval=0.05, dots_per_line=100):
        self.record_key = record_key.upper()
        self.quit_key = quit_key.upper()
        self.timeline_interval = timeline_interval  # seconds between timeline updates
        self.dots_per_line = dots_per_line         # markers printed per line before showing elapsed time
        
        self.start_time = None
        self.is_running = False
        self.events = []            # To store event dictionaries with start, end, and duration
        self.current_event_start = None
        self.dot_count = 0

        # Virtual-key codes for letters (A-Z): simply use ord(letter)
        self.record_vk = ord(self.record_key)
        self.quit_vk = ord(self.quit_key)
        
        # GetAsyncKeyState is available via ctypes (built-in)
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
        Start the timer, monitor key states, and print timeline markers.
        """
        self.start_time = time.time()
        self.is_running = True

        print(f"\nTimer started. Hold '{self.record_key}' to record behavior, press '{self.quit_key}' to quit.")
        print("Timeline: ", end="", flush=True)

        # We'll use a simple flag to track the state of the record key.
        record_key_down = False

        while self.is_running:
            current_time = time.time()
            elapsed = current_time - self.start_time

            # Check if the quit key is pressed.
            if self.key_pressed(self.quit_vk):
                # If an event is active, close it out.
                if record_key_down and self.current_event_start is not None:
                    end_time = elapsed
                    duration = end_time - self.current_event_start
                    self.events.append({
                        'start': self.current_event_start,
                        'end': end_time,
                        'duration': duration
                    })
                    self.current_event_start = None
                self.is_running = False
                break

            # Check the state of the record key.
            if self.key_pressed(self.record_vk):
                if not record_key_down:
                    # Key transition: was not pressed before, now pressed.
                    record_key_down = True
                    self.current_event_start = elapsed
            else:
                if record_key_down:
                    # Key transition: was pressed before, now released.
                    record_key_down = False
                    if self.current_event_start is not None:
                        end_time = elapsed
                        duration = end_time - self.current_event_start
                        self.events.append({
                            'start': self.current_event_start,
                            'end': end_time,
                            'duration': duration
                        })
                        self.current_event_start = None

            # Display visual feedback on the timeline.
            # Print "X" when recording; otherwise, print a dot.
            if record_key_down:
                print("X", end="", flush=True)
            else:
                print(".", end="", flush=True)
            self.dot_count += 1

            # Every dots_per_line markers, show the elapsed time.
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
            total_recorded_time = sum(event['duration'] for event in self.events)
            percentage = (total_recorded_time / session_duration * 100) if session_duration > 0 else 0

            with open(filename, 'w') as f:
                # Session summary header.
                f.write("Behavior Observation Log\n")
                f.write(f"Session Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Session Duration: {session_duration:.2f} seconds\n")
                f.write(f"Total Number of '{self.record_key}' Events: {len(self.events)}\n")
                f.write(f"Total Time '{self.record_key}' Held: {total_recorded_time:.2f} seconds\n")
                f.write(f"Percentage of Session Time '{self.record_key}' Held: {percentage:.2f}%\n\n")

                # Detailed event log.
                f.write("Detailed Event Log:\n")
                f.write("Event#\tStart(s)\tEnd(s)\tDuration(s)\n")
                for i, event in enumerate(self.events, 1):
                    f.write(f"{i}\t{event['start']:.2f}\t{event['end']:.2f}\t{event['duration']:.2f}\n")

            print(f"\n\nLog file saved as: {filename}")
        except Exception as e:
            print(f"\n\nError saving log file: {e}")

if __name__ == "__main__":
    timer = BehaviorTimer()
    try:
        timer.start()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected. Exiting.")
    finally:
        timer.save_log()
        print("Program ended.")
