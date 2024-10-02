import random
import math
import tkinter as tk
from tkinter import ttk

def straight_formula(current_speed, cc_accel, cc_dragc, cc_downc):
    random_factor = random.random() * 1.2
    new_speed = (current_speed + 0.2 * random_factor * (cc_downc + cc_dragc - cc_accel) +
                 (cc_accel / 2.5) - current_speed * (1 - (cc_dragc / 500)) *
                 (0.10 + 0.31 * ((math.sqrt(current_speed) - 100) / 1500)) -
                 current_speed * (cc_downc / 5000))
    return max(0, new_speed)  # Ensure speed doesn't go negative

def turn_formula(current_speed, cc_cornr, cc_downc):
    return current_speed * (0.4 + (cc_cornr / 200) + (cc_downc / 2000))

def simulate_car(cc_accel, cc_dragc, cc_downc, cc_cornr):
    speed = 0
    speeds = []
    distances = [0]
    for cycle in range(60):  # 60 seconds total
        if cycle < 10 or (11 <= cycle < 16) or (20 <= cycle < 30) or (35 <= cycle < 60):
            speed = straight_formula(speed, cc_accel, cc_dragc, cc_downc)
        else:
            speed = turn_formula(speed, cc_cornr, cc_downc)
        speeds.append(speed)
        distances.append(distances[-1] + speed)  # Integrate speed to get distance
    return speeds, distances[1:]  # Remove the initial 0 from distances

def plot_graphs(speeds_list, distances_list, colors):
    for canvas in [speed_canvas, distance_canvas]:
        canvas.delete("all")  # Clear previous graphs
    
    canvas_width = 800
    canvas_height = 300
    x_scale = (canvas_width - 70) / 59  # 60 points, 59 intervals

    # Speed graph
    max_speed = max(max(speeds) for speeds in speeds_list)
    y_scale_speed = (canvas_height - 70) / (max_speed * 1.1)  # Add 10% margin at the top

    # Distance graph
    max_distance = max(max(distances) for distances in distances_list)
    y_scale_distance = (canvas_height - 70) / (max_distance * 1.1)  # Add 10% margin at the top

    # Draw axes for both graphs
    for canvas in [speed_canvas, distance_canvas]:
        canvas.create_line(50, canvas_height - 50, canvas_width - 20, canvas_height - 50, fill="black")  # X-axis
        canvas.create_line(50, canvas_height - 50, 50, 20, fill="black")  # Y-axis

    # Plot lines for each car on both graphs
    for speeds, distances, color in zip(speeds_list, distances_list, colors):
        # Speed graph
        for i in range(len(speeds) - 1):
            x1 = 50 + i * x_scale
            y1 = canvas_height - 50 - speeds[i] * y_scale_speed
            x2 = 50 + (i + 1) * x_scale
            y2 = canvas_height - 50 - speeds[i + 1] * y_scale_speed
            speed_canvas.create_line(x1, y1, x2, y2, fill=color)

        # Distance graph
        for i in range(len(distances) - 1):
            x1 = 50 + i * x_scale
            y1 = canvas_height - 50 - distances[i] * y_scale_distance
            x2 = 50 + (i + 1) * x_scale
            y2 = canvas_height - 50 - distances[i + 1] * y_scale_distance
            distance_canvas.create_line(x1, y1, x2, y2, fill=color)

    # Add labels and ticks for both graphs
    speed_canvas.create_text(canvas_width // 2, canvas_height - 20, text="Time (s)")
    speed_canvas.create_text(20, canvas_height // 2, text="Speed", angle=90)
    distance_canvas.create_text(canvas_width // 2, canvas_height - 20, text="Time (s)")
    distance_canvas.create_text(20, canvas_height // 2, text="Distance", angle=90)

    # X-axis ticks and labels for both graphs
    for canvas in [speed_canvas, distance_canvas]:
        for i in range(0, 61, 10):
            x = 50 + i * x_scale
            canvas.create_line(x, canvas_height - 50, x, canvas_height - 45, fill="black")
            canvas.create_text(x, canvas_height - 35, text=str(i))

    # Y-axis ticks and labels
    for i in range(0, int(max_speed) + 1, 20):
        y = canvas_height - 50 - i * y_scale_speed
        speed_canvas.create_line(45, y, 50, y, fill="black")
        speed_canvas.create_text(35, y, text=str(i))

    for i in range(0, int(max_distance) + 1, 500):
        y = canvas_height - 50 - i * y_scale_distance
        distance_canvas.create_line(45, y, 50, y, fill="black")
        distance_canvas.create_text(35, y, text=str(i))

    # Add legend to both graphs
    for canvas in [speed_canvas, distance_canvas]:
        for i, color in enumerate(colors):
            canvas.create_rectangle(canvas_width - 120, 20 + i*30, canvas_width - 20, 50 + i*30, fill="white", outline="black")
            canvas.create_line(canvas_width - 110, 35 + i*30, canvas_width - 70, 35 + i*30, fill=color)
            canvas.create_text(canvas_width - 45, 35 + i*30, text=f"Car {i+1}")

    # Add race segment labels to both graphs
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
        cc_accel = int(accel_entries[i].get())
        cc_dragc = int(dragc_entries[i].get())
        cc_downc = int(downc_entries[i].get())
        cc_cornr = int(cornr_entries[i].get())
        speeds, distances = simulate_car(cc_accel, cc_dragc, cc_downc, cc_cornr)
        speeds_list.append(speeds)
        distances_list.append(distances)
    plot_graphs(speeds_list, distances_list, colors)

# Create main window
root = tk.Tk()
root.title("Multi-Car Acceleration and Distance Visualization")

# Create input frame
input_frame = ttk.Frame(root, padding="10")
input_frame.pack(fill=tk.X)

# Create input fields for 4 cars
accel_entries = []
dragc_entries = []
downc_entries = []
cornr_entries = []
colors = ["red", "blue", "green", "purple"]

for i in range(4):
    car_frame = ttk.Frame(input_frame)
    car_frame.grid(row=0, column=i, padx=10)

    ttk.Label(car_frame, text=f"Car {i+1}", font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=2)
    
    ttk.Label(car_frame, text="CC_accel:").grid(row=1, column=0, sticky=tk.W)
    accel_entry = ttk.Entry(car_frame, width=10)
    accel_entry.insert(0, "70")
    accel_entry.grid(row=1, column=1)
    accel_entries.append(accel_entry)

    ttk.Label(car_frame, text="CC_dragC:").grid(row=2, column=0, sticky=tk.W)
    dragc_entry = ttk.Entry(car_frame, width=10)
    dragc_entry.insert(0, "70")
    dragc_entry.grid(row=2, column=1)
    dragc_entries.append(dragc_entry)

    ttk.Label(car_frame, text="CC_downC:").grid(row=3, column=0, sticky=tk.W)
    downc_entry = ttk.Entry(car_frame, width=10)
    downc_entry.insert(0, "70")
    downc_entry.grid(row=3, column=1)
    downc_entries.append(downc_entry)

    ttk.Label(car_frame, text="CC_cornr:").grid(row=4, column=0, sticky=tk.W)
    cornr_entry = ttk.Entry(car_frame, width=10)
    cornr_entry.insert(0, "70")
    cornr_entry.grid(row=4, column=1)
    cornr_entries.append(cornr_entry)

# Create update button
update_button = ttk.Button(input_frame, text="Update Graph", command=update_graph)
update_button.grid(row=1, column=0, columnspan=4, pady=10)

# Create canvases for speed and distance graphs
speed_canvas = tk.Canvas(root, width=800, height=300)
speed_canvas.pack()
distance_canvas = tk.Canvas(root, width=800, height=300)
distance_canvas.pack()

# Initial graph update
update_graph()

root.mainloop()