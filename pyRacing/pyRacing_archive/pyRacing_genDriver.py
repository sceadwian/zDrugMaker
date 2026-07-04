import random
import string

def generate_name():
    return ''.join(random.choice(string.ascii_uppercase) for _ in range(random.randint(3, 8))).capitalize()

def generate_surname():
    return ''.join(random.choice(string.ascii_uppercase) for _ in range(random.randint(4, 10))).capitalize()

def generate_symbol():
    return ''.join(random.choice(string.ascii_uppercase) for _ in range(3))

def generate_driver():
    name = generate_name()
    surname = generate_surname()
    symbol = generate_symbol()
    max_speed = random.randint(340, 380)
    accel = random.randint(68, 80)
    drag_coeff = random.randint(58, 79)
    downforce_coeff = random.randint(65, 91)
    cornering = random.randint(61, 80)
    overtake = random.randint(30, 95)
    consistency = random.randint(5, 95)
    defending = random.randint(15, 95)
    stamina = random.randint(8, 90)
    
    return f"{name},{surname},{symbol},{max_speed},{accel},{drag_coeff},{downforce_coeff},{cornering},{overtake},{consistency},{defending},{stamina}"

# Generate 20 random drivers
drivers = [generate_driver() for _ in range(20)]

# Print the generated drivers
for driver in drivers:
    print(driver)