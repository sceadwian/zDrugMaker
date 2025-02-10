import time
import datetime
import msvcrt
import os
from threading import Thread

class BehaviorTimer:
    def __init__(self):
        self.start_time = None
        self.is_running = False
        self.events = []
        self.current_x_press = None
        self.is_x_pressed = False
        self.dot_count = 0
        
    def start(self):
        self.start_time = time.time()
        self.is_running = True
        print("\nTimer started. Hold 'x' to record behavior, 'q' to quit.")
        print("Timeline: ", end="", flush=True)
        
        # Create separate thread to monitor keyboard
        keyboard_thread = Thread(target=self._monitor_keyboard)
        keyboard_thread.daemon = True
        keyboard_thread.start()
        
        # Main loop to display time and visual feedback
        while self.is_running:
            if self.is_x_pressed:
                print("X", end="", flush=True)
            else:
                print(".", end="", flush=True)
            self.dot_count += 1
            
            if self.dot_count % 100 == 0:
                elapsed = time.time() - self.start_time
                minutes = int(elapsed // 60)
                seconds = elapsed % 60
                print(f" {minutes:02d}:{seconds:05.2f}")
                print("Timeline: ", end="", flush=True)
            
            time.sleep(0.05)
            
    def _monitor_keyboard(self):
        while self.is_running:
            if msvcrt.kbhit():
                key = msvcrt.getch().decode('utf-8').lower()
                
                if key == 'x' and not self.is_x_pressed:
                    # X key was just pressed
                    self.is_x_pressed = True
                    self.current_x_press = time.time() - self.start_time
                elif key == 'x' and self.is_x_pressed:
                    # X key was released
                    self.is_x_pressed = False
                    end_time = time.time() - self.start_time
                    duration = end_time - self.current_x_press
                    self.events.append({
                        'start': self.current_x_press,
                        'end': end_time,
                        'duration': duration
                    })
                    self.current_x_press = None
                elif key == 'q':
                    # If x was being pressed when q was pressed, record the final event
                    if self.is_x_pressed:
                        end_time = time.time() - self.start_time
                        duration = end_time - self.current_x_press
                        self.events.append({
                            'start': self.current_x_press,
                            'end': end_time,
                            'duration': duration
                        })
                    self.is_running = False
                    break

    def save_log(self):
        try:
            if not os.path.exists('logs'):
                os.makedirs('logs')
                
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"logs/behavior_log_{timestamp}.txt"
            
            with open(filename, 'w') as f:
                # Header
                f.write("Behavior Observation Log\n")
                f.write(f"Session Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Session Duration: {time.time() - self.start_time:.2f} seconds\n")
                f.write(f"Total Number of X-Press Events: {len(self.events)}\n")
                
                # Calculate total time X was pressed
                total_x_time = sum(event['duration'] for event in self.events)
                f.write(f"Total Time X Pressed: {total_x_time:.2f} seconds\n")
                
                # Calculate percentage of session time X was pressed
                session_duration = time.time() - self.start_time
                x_percentage = (total_x_time / session_duration) * 100
                f.write(f"Percentage of Session Time X Pressed: {x_percentage:.2f}%\n\n")
                
                # Detailed event log
                f.write("Detailed Event Log:\n")
                f.write("Event#\tStart(s)\tEnd(s)\tDuration(s)\n")
                
                for i, event in enumerate(self.events, 1):
                    f.write(f"{i}\t{event['start']:.2f}\t{event['end']:.2f}\t{event['duration']:.2f}\n")
            
            print(f"\n\nLog file saved as: {filename}")
        except Exception as e:
            print(f"\n\nError saving log file: {str(e)}")

if __name__ == "__main__":
    timer = BehaviorTimer()
    try:
        timer.start()
    except KeyboardInterrupt:
        pass
    finally:
        if timer.events:
            timer.save_log()
        print("\nProgram ended.")