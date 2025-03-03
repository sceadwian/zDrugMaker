import time
import datetime
import os
import ctypes
from collections import defaultdict
import tkinter as tk
from tkinter import messagebox

class BehaviorTimerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Behavior Observation Timer")
        self.root.geometry("800x750")

        # Initialize variables
        self.animal_name = tk.StringVar()
        self.trial_name = tk.StringVar()
        self.record_keys = ['W', 'A', 'S', 'D', 'NUMPAD1', 'NUMPAD2', 'NUMPAD3', 'NUMPAD5']  # Numpad keys
        self.quit_key = 'I'
        self.pause_key = 'P'
        self.timeline_interval = 0.05
        self.key_labels = self.read_key_labels('zTimer.txt')  # Initial labels

        self.start_time = None
        self.is_running = False
        self.is_paused = False
        self.total_pause_time = 0
        self.pause_start_time = None
        self.events = []
        self.key_down = {key: False for key in self.record_keys}
        self.current_event_start = {key: None for key in self.record_keys}

        # Virtual Key Codes (VK codes) for numpad and regular keys
        self.record_vk = {
            'W': ord('W'), 'A': ord('A'), 'S': ord('S'), 'D': ord('D'),
            'NUMPAD1': 0x61, 'NUMPAD2': 0x62, 'NUMPAD3': 0x63, 'NUMPAD5': 0x65  # Numpad VK codes
        }
        self.quit_vk = ord(self.quit_key)
        self.pause_vk = ord(self.pause_key)
        self.GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState

        # Tracking for tallies
        self.total_time_by_key = {key: 0.0 for key in self.record_keys}
        self.count_by_key = {key: 0 for key in self.record_keys}

        # Build GUI
        self.setup_ui()

    def setup_ui(self):
        welcome = (
            "Welcome to the Behavior Observation Timer!\n"
            "Edit key labels below, then enter names and click 'Start'."
        )
        tk.Label(self.root, text=welcome, justify="left").pack(pady=10)

        tk.Label(self.root, text="Animal Name:").pack()
        tk.Entry(self.root, textvariable=self.animal_name).pack()
        tk.Label(self.root, text="Trial Name:").pack()
        tk.Entry(self.root, textvariable=self.trial_name).pack()

        # Editable Key Labels (Display as 1, 2, 3, 5 but map to numpad)
        self.label_frame = tk.LabelFrame(self.root, text="Edit Key Assignments", padx=10, pady=10)
        self.label_frame.pack(pady=10, fill="x")
        self.label_entries = {}
        display_keys = ['W', 'A', 'S', 'D', '1', '2', '3', '5']  # For UI display
        for display_key, actual_key in zip(display_keys, self.record_keys):
            frame = tk.Frame(self.label_frame)
            frame.pack(fill="x")
            tk.Label(frame, text=f"{display_key} =", width=5).pack(side=tk.LEFT)
            entry = tk.Entry(frame)
            entry.insert(0, self.key_labels.get(actual_key, ''))
            entry.pack(side=tk.LEFT, fill="x", expand=True)
            self.label_entries[actual_key] = entry

        # Buttons Frame
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="Start Timer", command=self.start).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Exit", command=self.exit).pack(side=tk.LEFT, padx=5)

        # Legend
        legend_frame = tk.LabelFrame(self.root, text="Control Keys", padx=10, pady=10)
        legend_frame.pack(pady=10, fill="x")
        legend_text = "P = Pause/Resume\nI = Quit"
        tk.Label(legend_frame, text=legend_text, justify="left").pack()

        # Tally Display
        self.tally_frame = tk.LabelFrame(self.root, text="Key Tallies", padx=10, pady=10)
        self.tally_frame.pack(pady=10, fill="x")
        self.tally_labels = {}
        for key in self.record_keys:
            label = tk.Label(self.tally_frame, text=self.get_tally_text(key), justify="left")
            label.pack()
            self.tally_labels[key] = label

        # Status and Graph Frame
        self.status_frame = tk.LabelFrame(self.root, text="Status and Live Graph", padx=10, pady=10)
        self.status_frame.pack(pady=10, fill="x")
        self.status_var = tk.StringVar(value="Status: Ready")
        self.status_label = tk.Label(self.status_frame, textvariable=self.status_var)
        self.status_label.pack()

        # Bar Graph Canvas
        self.canvas = tk.Canvas(self.status_frame, width=600, height=200, bg="white")
        self.canvas.pack(pady=5)
        self.bar_colors = {
            'W': 'yellow', 'A': 'green', 'S': 'blue', 'D': 'red',
            'NUMPAD1': 'purple', 'NUMPAD2': 'orange', 'NUMPAD3': 'pink', 'NUMPAD5': 'cyan'
        }
        self.draw_initial_graph()

    def draw_initial_graph(self):
        self.canvas.delete("all")
        self.canvas.create_text(300, 10, text="Total Time per Key (seconds)", font=("Arial", 10))
        bar_width = 60
        spacing = 10
        display_keys = ['W', 'A', 'S', 'D', '1', '2', '3', '5']
        for i, (disp_key, actual_key) in enumerate(zip(display_keys, self.record_keys)):
            x0 = i * (bar_width + spacing) + 20
            y0 = 180
            x1 = x0 + bar_width
            y1 = y0
            self.canvas.create_rectangle(x0, y0, x1, y1, fill=self.bar_colors[actual_key], tags=f"bar_{actual_key}")
            self.canvas.create_text(x0 + bar_width // 2, 190, text=disp_key, font=("Arial", 10))

    def update_graph(self):
        max_height = 150
        max_time = max(self.total_time_by_key.values(), default=1) or 1
        for i, key in enumerate(self.record_keys):
            time_value = self.total_time_by_key[key]
            height = (time_value / max_time) * max_height if max_time > 0 else 0
            x0 = i * 70 + 20
            y0 = 180
            x1 = x0 + 60
            y1 = y0 - height
            self.canvas.coords(f"bar_{key}", x0, y0, x1, y1)
            self.canvas.itemconfig(f"bar_{key}", fill=self.bar_colors[key])

    def get_tally_text(self, key):
        total_time = self.total_time_by_key[key]
        count = self.count_by_key[key]
        session_duration = (time.time() - self.start_time - self.total_pause_time) if self.start_time else 0
        percent = (total_time / session_duration * 100) if session_duration > 0 else 0
        display_key = key.replace('NUMPAD', '')  # Show as 1, 2, 3, 5 in UI
        return f"{display_key} ({self.key_labels.get(key, '')}): {count} presses, {total_time:.2f}s, {percent:.2f}%"

    def read_key_labels(self, filename):
        # Updated default labels
        key_labels = {
            'W': 'twitch', 'A': 'chew', 'S': 'freeze', 'D': 'active',
            'NUMPAD1': '1', 'NUMPAD2': '2', 'NUMPAD3': '3', 'NUMPAD5': '5'
        }
        try:
            with open(filename, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        key, label = line.split('=')
                        key = key.strip().upper()
                        if key in ['1', '2', '3', '5']:
                            key = f'NUMPAD{key}'  # Convert to numpad key internally
                        key_labels[key] = label.strip()
                    except ValueError:
                        pass
        except FileNotFoundError:
            pass
        return key_labels

    def key_pressed(self, vk_code):
        state = self.GetAsyncKeyState(vk_code)
        return (state & 0x8000) != 0

    def handle_pause(self):
        if not self.is_paused:
            self.is_paused = True
            self.pause_start_time = time.time()
            for key in self.record_keys:
                if self.key_down[key] and self.current_event_start[key] is not None:
                    elapsed = time.time() - self.start_time - self.total_pause_time
                    duration = elapsed - self.current_event_start[key]
                    self.events.append({
                        'key': key, 'start': self.current_event_start[key],
                        'end': elapsed, 'duration': duration
                    })
                    self.total_time_by_key[key] += duration
                    self.count_by_key[key] += 1
                    self.current_event_start[key] = None
                    self.key_down[key] = False
            self.status_var.set("Status: Paused")
        else:
            self.is_paused = False
            pause_duration = time.time() - self.pause_start_time
            self.total_pause_time += pause_duration
            self.pause_start_time = None
            self.status_var.set("Status: Running")
        self.update_tallies()
        self.update_graph()

    def start(self):
        if not self.animal_name.get() or not self.trial_name.get():
            messagebox.showerror("Error", "Please enter both animal name and trial name.")
            return

        # Update key labels from entries
        display_keys = ['W', 'A', 'S', 'D', '1', '2', '3', '5']
        for disp_key, actual_key in zip(display_keys, self.record_keys):
            new_label = self.label_entries[actual_key].get().strip()
            if new_label:
                self.key_labels[actual_key] = new_label
            elif actual_key not in self.key_labels:
                self.key_labels[actual_key] = disp_key  # Default to display key if empty
            self.tally_labels[actual_key].config(text=self.get_tally_text(actual_key))

        self.start_time = time.time()
        self.is_running = True
        self.is_paused = False
        self.total_pause_time = 0
        self.events = []
        self.total_time_by_key = {key: 0.0 for key in self.record_keys}
        self.count_by_key = {key: 0 for key in self.record_keys}
        self.status_var.set("Status: Running")
        self.draw_initial_graph()
        self.root.update()
        self.run_timer()

    def run_timer(self):
        last_pause_state = False
        while self.is_running:
            current_time = time.time()

            # Check pause key
            pause_pressed = self.key_pressed(self.pause_vk)
            if pause_pressed and not last_pause_state:
                self.handle_pause()
            last_pause_state = pause_pressed

            if not self.is_paused:
                elapsed = current_time - self.start_time - self.total_pause_time

                # Check quit key
                if self.key_pressed(self.quit_vk):
                    for key in self.record_keys:
                        if self.key_down[key] and self.current_event_start[key] is not None:
                            duration = elapsed - self.current_event_start[key]
                            self.events.append({
                                'key': key, 'start': self.current_event_start[key],
                                'end': elapsed, 'duration': duration
                            })
                            self.total_time_by_key[key] += duration
                            self.count_by_key[key] += 1
                    self.is_running = False
                    self.status_var.set("Status: Stopped")
                    self.save_log()
                    break

                # Check record keys
                for key in self.record_keys:
                    pressed = self.key_pressed(self.record_vk[key])
                    if pressed:
                        if not self.key_down[key]:
                            self.key_down[key] = True
                            self.current_event_start[key] = elapsed
                    elif self.key_down[key]:
                        self.key_down[key] = False
                        if self.current_event_start[key] is not None:
                            duration = elapsed - self.current_event_start[key]
                            self.events.append({
                                'key': key, 'start': self.current_event_start[key],
                                'end': elapsed, 'duration': duration
                            })
                            self.total_time_by_key[key] += duration
                            self.count_by_key[key] += 1
                            self.current_event_start[key] = None

                self.update_tallies()
                self.update_graph()

            self.root.update()
            time.sleep(self.timeline_interval)

    def update_tallies(self):
        for key in self.record_keys:
            self.tally_labels[key].config(text=self.get_tally_text(key))

    def save_log(self):
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(log_dir, f"behavior_log_{self.animal_name.get()}_{self.trial_name.get()}_{timestamp}.txt")
        session_duration = time.time() - self.start_time - self.total_pause_time

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Animal: {self.animal_name.get()}\n")
            f.write(f"Trial: {self.trial_name.get()}\n")
            f.write(f"Session Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Duration: {session_duration:.2f} seconds\n")
            f.write(f"Total Pause Time: {self.total_pause_time:.2f} seconds\n\n")
            
            f.write("Key Summary:\n")
            for key in self.record_keys:
                total = self.total_time_by_key[key]
                count = self.count_by_key[key]
                avg = total / count if count > 0 else 0
                percent = (total / session_duration * 100) if session_duration > 0 else 0
                display_key = key.replace('NUMPAD', '')
                f.write(f"  {display_key} ({self.key_labels.get(key, '')}): {count} events, "
                        f"{total:.2f}s, avg {avg:.2f}s ({percent:.2f}%)\n")

            f.write("\nDetailed Events:\n")
            for i, event in enumerate(self.events, 1):
                display_key = event['key'].replace('NUMPAD', '')
                f.write(f"{i}\t{display_key}\t{self.key_labels.get(event['key'], '')}\t"
                        f"{event['start']:.2f}\t{event['end']:.2f}\t{event['duration']:.2f}\n")

        messagebox.showinfo("Log Saved", f"Log file saved as: {filename}")

    def exit(self):
        if self.is_running:
            self.is_running = False
            self.save_log()
        self.root.quit()

if __name__ == "__main__":
    root = tk.Tk()
    app = BehaviorTimerGUI(root)
    root.mainloop()