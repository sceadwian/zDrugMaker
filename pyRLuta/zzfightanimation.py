import time
import os
import random

# Define the health of the boxers
health_1 = 10
health_2 = 10

# Boxers
boxer_1 = """
 O 
/|\\
/ \\
"""
boxer_2 = """
 O 
/|\\
/ \\
"""

# Display the initial state
print(boxer_1 + "\nBoxer 1 health: " + str(health_1))
print(boxer_2 + "\nBoxer 2 health: " + str(health_2))
time.sleep(1)

# The fight continues until one of the boxers is out of health
while health_1 > 0 and health_2 > 0:
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # Decide which boxer is punching
    if random.choice([True, False]):
        health_2 -= 1  # boxer 1 punches, boxer 2 loses health
        print(boxer_1.replace("/", "-") + "\nBoxer 1 health: " + str(health_1))
        print(boxer_2.replace("O", "x") + "\nBoxer 2 health: " + str(health_2))
    else:
        health_1 -= 1  # boxer 2 punches, boxer 1 loses health
        print(boxer_1.replace("O", "x") + "\nBoxer 1 health: " + str(health_1))
        print(boxer_2.replace("\\", "-") + "\nBoxer 2 health: " + str(health_2))
    
    time.sleep(1)

# Announce the winner
os.system('cls' if os.name == 'nt' else 'clear')
if health_1 > 0:
    print("Boxer 1 wins!")
else:
    print("Boxer 2 wins!")
